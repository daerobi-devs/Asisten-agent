const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, fetchLatestBaileysVersion } = require('@whiskeysockets/baileys');
const pino = require('pino');
const express = require('express');
const QRCode = require('qrcode');
const path = require('path');
const fs = require('fs');

const app = express();
app.use(express.json());

const PORT = parseInt(process.env.PORT || '3001');
const CORE_URL = process.env.CORE_URL || 'http://localhost:8000';
const SESSION_PATH = path.resolve(__dirname, '../../workspace/whatsapp_sessions/baileys_auth');

let sock = null;
let qrString = null;
let qrImageBase64 = null;
let connectionState = 'disconnected'; // 'disconnected' | 'pairing' | 'connected'
let connectedPhone = null;
let pairingCode = null;
let isStarting = false;

async function startSock() {
  if (isStarting) return;
  isStarting = true;

  try {
    if (!fs.existsSync(SESSION_PATH)) {
      fs.mkdirSync(SESSION_PATH, { recursive: true });
    }

    const { state, saveCreds } = await useMultiFileAuthState(SESSION_PATH);
    const { version, isLatest } = await fetchLatestBaileysVersion().catch(() => ({ version: [2, 3000, 1015901307], isLatest: true }));
    console.log(`[Baileys] Connecting with WhatsApp Web version: ${version.join('.')} (latest: ${isLatest})`);

    sock = makeWASocket({
      version,
      auth: state,
      printQRInTerminal: true,
      logger: pino({ level: 'silent' }),
      browser: ['LXION AI Assistant', 'Chrome', '124.0.6367.207'],
      syncFullHistory: false
    });

    sock.ev.on('creds.update', saveCreds);

    sock.ev.on('connection.update', async (update) => {
      const { connection, lastDisconnect, qr } = update;

      if (qr) {
        qrString = qr;
        try {
          qrImageBase64 = await QRCode.toDataURL(qr, { margin: 2, scale: 7, color: { dark: '#08090a', light: '#ffffff' } });
        } catch (e) {
          console.error('[Baileys] Error rendering QR:', e);
        }
        connectionState = 'pairing';
        console.log('\n[Baileys] >>> REAL WhatsApp Multi-Device QR Code Ready to Scan <<<');
      }

      if (connection === 'open') {
        connectionState = 'connected';
        qrString = null;
        qrImageBase64 = null;
        pairingCode = null;
        const rawId = sock.user ? (sock.user.id || sock.user.jid || '') : '';
        connectedPhone = rawId.split(':')[0].split('@')[0];
        console.log(`\n[Baileys] \x1b[32m✓ WhatsApp Session LINKED & CONNECTED with phone: +${connectedPhone}\x1b[0m\n`);
      }

      if (connection === 'close') {
        const statusCode = (lastDisconnect?.error)?.output?.statusCode;
        const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
        console.log(`[Baileys] Connection closed (status: ${statusCode}). Reconnecting: ${shouldReconnect}`);
        connectionState = 'disconnected';
        qrString = null;
        qrImageBase64 = null;
        if (shouldReconnect) {
          setTimeout(() => {
            isStarting = false;
            startSock();
          }, 3000);
        } else {
          try {
            fs.rmSync(SESSION_PATH, { recursive: true, force: true });
          } catch (e) {}
          connectedPhone = null;
          isStarting = false;
        }
      }
    });

    // Inbound message listener
    sock.ev.on('messages.upsert', async ({ messages, type }) => {
      if (type !== 'notify') return;
      for (const msg of messages) {
        if (!msg.message) continue;
        if (msg.key.remoteJid === 'status@broadcast') continue;

        const isFromMe = Boolean(msg.key.fromMe);
        const remoteJid = msg.key.remoteJid;
        const text = msg.message.conversation ||
                     msg.message.extendedTextMessage?.text ||
                     msg.message.imageMessage?.caption ||
                     '';
        if (!text || !text.trim()) continue;

        const pushName = msg.pushName || 'WhatsApp User';
        const sender = remoteJid.replace('@s.whatsapp.net', '').replace('@g.us', '');

        console.log(`[Baileys INBOUND] From: +${sender} (${isFromMe ? 'Me/Self' : pushName}): "${text}"`);

        // Forward to LXION Core Webhook
        try {
          const res = await fetch(`${CORE_URL}/api/channels/whatsapp/webhook`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              sender: sender,
              text: text,
              is_from_me: isFromMe,
              push_name: pushName,
              remoteJid: remoteJid
            })
          });

          if (res.ok) {
            const data = await res.json();
            if (data.reply && data.reply.trim()) {
              console.log(`[Baileys OUTBOUND] Replying to ${remoteJid}: "${data.reply.substring(0, 60)}..."`);
              await sock.sendMessage(remoteJid, { text: data.reply });
            }
          }
        } catch (err) {
          console.error('[Baileys] Webhook forward error:', err.message);
        }
      }
    });

  } catch (err) {
    console.error('[Baileys] startSock error:', err);
  } finally {
    isStarting = false;
  }
}

// ---------------- REST APIs for LXION Core / Frontend ----------------

app.get('/status', (req, res) => {
  res.json({
    status: connectionState,
    connected: connectionState === 'connected',
    phone: connectedPhone ? `+${connectedPhone}` : null,
    qr_image: qrImageBase64,
    pairing_code: pairingCode
  });
});

app.post('/generate-qr', async (req, res) => {
  if (connectionState === 'connected') {
    return res.json({
      status: 'connected',
      connected: true,
      phone: `+${connectedPhone}`,
      qr_image: null
    });
  }

  if (!sock || connectionState === 'disconnected') {
    startSock();
  }

  // Wait up to 5 seconds for QR to be emitted
  let waited = 0;
  while (!qrImageBase64 && waited < 5000) {
    await new Promise(r => setTimeout(r, 250));
    waited += 250;
  }

  res.json({
    status: connectionState,
    connected: connectionState === 'connected',
    phone: connectedPhone ? `+${connectedPhone}` : null,
    qr_image: qrImageBase64
  });
});

app.post('/pair-code', async (req, res) => {
  const phone = req.body.phone;
  if (!phone) {
    return res.status(400).json({ error: 'Phone number is required' });
  }

  const cleanPhone = phone.replace(/[^0-9]/g, '');
  if (!sock) {
    await startSock();
  }

  try {
    const code = await sock.requestPairingCode(cleanPhone);
    pairingCode = code;
    console.log(`[Baileys] Pairing Code for ${cleanPhone}: ${code}`);
    res.json({
      status: 'pairing_code',
      code: code,
      phone: cleanPhone
    });
  } catch (err) {
    console.error('[Baileys] Error requesting pairing code:', err);
    res.status(500).json({ error: err.message });
  }
});

app.post('/send', async (req, res) => {
  const { to, message } = req.body;
  if (!sock || connectionState !== 'connected') {
    return res.status(503).json({ error: 'WhatsApp is not connected' });
  }

  try {
    const jid = to.includes('@') ? to : `${to.replace(/[^0-9]/g, '')}@s.whatsapp.net`;
    await sock.sendMessage(jid, { text: message });
    res.json({ status: 'ok' });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

app.post('/disconnect', async (req, res) => {
  try {
    if (sock) {
      await sock.logout().catch(() => {});
    }
  } catch (e) {}

  try {
    fs.rmSync(SESSION_PATH, { recursive: true, force: true });
  } catch (e) {}

  connectionState = 'disconnected';
  connectedPhone = null;
  qrImageBase64 = null;
  qrString = null;
  pairingCode = null;

  // Restart socket to allow new QR generation
  setTimeout(() => {
    isStarting = false;
    startSock();
  }, 1000);

  res.json({ status: 'disconnected', connected: false });
});

app.listen(PORT, '0.0.0.0', () => {
  console.log(`[Baileys Sidecar] Running on http://localhost:${PORT}`);
  // Automatically initiate Baileys on startup
  startSock();
});
