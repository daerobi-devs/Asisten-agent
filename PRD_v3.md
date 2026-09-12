# PRD: [Nama Agent] — AI Agent Agentic Full-Feature (v3)

> Ganti `[Nama Agent]` dengan nama proyek pilihan Anda.

> - **v3 (dokumen ini): dikoreksi lagi** — "9Router" adalah software proxy/LLM gateway open-source spesifik yang **sudah Anda hosting sendiri** di `https://9router.daeroom.my.id/v1`. Ditambah fitur baru: coding capability, skill auto-install dari GitHub, memori terstruktur dengan file, browser access, dan akses laptop via Tailscale.

**Versi:** 0.3 (Draft)
**Tanggal:** 13 September 2026
**Status:** Draft — basis pengembangan Fase 1

---

## 1. Ringkasan Eksekutif

[Nama Agent] adalah AI agent agentic, self-hosted, dan persisten dengan kemampuan setara agent kelas Hermes Agent (Nous Research): tool-calling nyata, memori lintas sesi yang terstruktur, sistem skill yang bisa dipasang sendiri (termasuk dari GitHub), kemampuan coding, akses browser, gateway ke banyak platform chat, dukungan MCP, dan sekarang juga **terhubung ke instance 9Router milik Anda sendiri** sebagai salah satu backend LLM utama — plus opsi menambah provider AI lain secara langsung.

Karena Anda sudah punya Proxmox, Coolify, dan laptop yang saling terhubung lewat **Tailscale**, [Nama Agent] juga dirancang bisa dijangkau — dan menjangkau balik — semua node itu lewat jaringan Tailscale yang sama, termasuk mengakses laptop Anda langsung.

---

## 2. Klarifikasi Penting: Apa Itu 9Router (Bagian ini Menggantikan Asumsi di v1/v2)

**9Router** adalah software proxy/gateway LLM open-source (Node.js, biasanya port `20128`, API kompatibel OpenAI) yang berfungsi sebagai lapisan di depan 40+ provider AI (OpenAI, Anthropic, OpenRouter, Groq, DeepSeek, Together AI, dll), dengan fitur:

- Smart 3-tier fallback (Subscription → Cheap → Free)
- Multi-account round-robin per provider + quota tracking
- Token Saver (kompresi tool-result untuk hemat token)
- Combo & Vision Adapter, Media Providers, Proxy Pools
- Sistem Skills bawaan
- API endpoint OpenAI-compatible untuk dipakai tool/agent lain

Anda **sudah menjalankan instance 9Router sendiri** di endpoint `https://9router.daeroom.my.id/v1`, dengan API key yang sudah dibuat (mis. key "9router", "daeroom agent"). Ini artinya [Nama Agent] **tidak perlu membangun ulang** logika multi-provider dari nol — cukup jadikan 9Router sebagai salah satu backend LLM, sambil tetap membuka opsi menambahkan provider AI lain secara langsung (API key + base URL sendiri) di luar 9Router, sesuai kebutuhan.

---

## 3. Latar Belakang & Masalah

- Anda sudah punya infrastruktur multi-provider LLM lewat 9Router, tapi belum punya agent AI sendiri yang memanfaatkannya sebagai otak, sekaligus jadi asisten produktivitas & coding penuh.
- Anda ingin satu agent yang: bisa pasang kemampuan baru sendiri (skill dari GitHub), bisa coding, punya memori kuat yang bisa dilihat hasil kerjanya (file), bisa browsing, bisa menjangkau laptop pribadi, dan bisa dihubungi dari berbagai channel chat — semua berjalan di infrastruktur pribadi Anda (Proxmox + Coolify + Tailscale).

---

## 4. Tujuan (Goals)

| # | Tujuan |
|---|--------|
| G1 | Agent terhubung ke instance 9Router milik Anda sebagai backend LLM utama (via API key + base URL 9Router) |
| G2 | Agent bisa ditambahkan provider/API key AI lain secara langsung, di luar 9Router, kapan saja |
| G3 | Dashboard agent menampilkan status penuh arsitektur: provider aktif (baik lewat 9Router maupun langsung), skill terpasang, channel aktif, MCP server terkoneksi |
| G4 | Agent bisa memasang skill baru sendiri, termasuk mengambil & memasang skill dari repo GitHub |
| G5 | Agent punya kemampuan coding: menulis, mengedit, menjalankan, dan menguji kode di sandbox aman |
| G6 | Memori agent terstruktur & persisten, dengan workspace file yang bisa Anda lihat langsung hasil kerjanya |
| G7 | Agent punya tool browser (browsing web, ambil screenshot, isi form) |
| G8 | Agent bisa menjangkau laptop pribadi Anda lewat jaringan Tailscale yang sudah ada |
| G9 | Cron/scheduler untuk tugas terjadwal |
| G10 | Kanban board untuk manajemen tugas |
| G11 | Multi-channel: Telegram, Discord, WhatsApp (via Baileys) |
| G12 | MCP client — bisa konek ke banyak MCP server eksternal |
| G13 | Web UI (TypeScript) + Terminal/CLI |
| G14 | Deploy seragam di Coolify & Proxmox (via Docker), semuanya nyambung lewat Tailscale |
| G15 | Codebase ±80% Python, UI web pakai TypeScript |

### Non-Goals (v1 pengembangan)
- Menjalankan skill dari GitHub tanpa review sama sekali (**risiko keamanan** — lihat Bagian 12). Auto-install tetap ada, tapi dengan tahap tinjauan sebelum skill baru diberi izin eksekusi penuh.
- Multi-tenant / banyak pengguna.
- Melatih model sendiri — semua LLM diakses lewat 9Router atau API provider lain.

---

## 5. Target Pengguna

Anda sendiri sebagai power user & developer, yang ingin satu agent AI pribadi penuh: otak fleksibel (lewat 9Router + provider lain), tangan yang bisa coding & browsing, memori yang bisa diaudit, dan jangkauan ke seluruh infrastruktur pribadi (Proxmox, Coolify, laptop) lewat Tailscale.

---

## 6. Fitur Detail

### 6.1 LLM Backend Manager (9Router + Provider Lain)

- **Backend utama:** koneksi ke 9Router (`base_url = https://9router.daeroom.my.id/v1`, API key dari dashboard 9Router). Karena 9Router sendiri sudah OpenAI-compatible, integrasinya sederhana — [Nama Agent] cukup memakai client OpenAI-compatible standar.
- **Backend tambahan (opsional, jumlah bebas — bukan cuma 9):** Anda bisa menambahkan provider AI lain langsung (mis. OpenAI, Anthropic, dll) dengan API key + base URL masing-masing, terpisah dari 9Router — berguna kalau ada provider yang belum/tidak ingin dimasukkan ke 9Router.
- Agent otomatis mendeteksi model yang tersedia di tiap backend (lewat endpoint `/models`).
- **Strategi pemilihan model:** default ikut apa yang sudah diatur combo/fallback di 9Router (karena 9Router sudah punya sistem 3-tier fallback sendiri); untuk backend tambahan di luar 9Router, agent pakai aturan sederhana (priority order / manual pilih) di v1.
- **Dashboard status terpadu:** satu layar yang menampilkan status 9Router (quota, provider aktif di dalamnya — ditarik dari API 9Router kalau tersedia) berdampingan dengan status backend tambahan.
- Semua log pemakaian (token, biaya, backend mana yang dipakai) dicatat untuk transparansi.

### 6.2 Skill System + Auto-Install dari GitHub

- Skill disimpan sebagai modul terpisah dengan struktur standar (manifest + kode + dependency list), sama seperti pola Hermes Agent / 9Router.
- **Alur pasang skill dari GitHub:**
  1. Anda kasih instruksi atau URL repo GitHub ke agent.
  2. Agent men-download/clone repo ke folder sandbox sementara.
  3. Agent membaca manifest/README untuk memahami apa yang dilakukan skill tsb, lalu **menampilkan ringkasan ke Anda** (apa yang akan diinstal, dependency apa, akses apa yang dibutuhkan) sebelum aktivasi penuh.
  4. Setelah Anda konfirmasi, skill dipindah ke folder skill resmi & didaftarkan ke tool registry.
- **Guardrail wajib:** skill baru dari sumber luar (GitHub) tidak otomatis dapat izin penuh (mis. akses filesystem luas atau jaringan) — izin diberikan bertahap/eksplisit, supaya kode pihak ketiga yang belum tepercaya tidak langsung punya akses penuh ke sistem Anda (lihat risiko di Bagian 12).

### 6.3 Kemampuan Coding

- Agent bisa menulis, membaca, mengedit, dan menjalankan kode di **sandbox terisolasi** (container terpisah, bukan langsung di host).
- Mendukung alur umum coding agent: baca file proyek → buat/ubah kode → jalankan test/build → laporkan hasil (mirip pola Claude Code/Cursor, tapi berjalan sebagai bagian dari [Nama Agent] sendiri).
- Hasil kerja (file yang dibuat/diubah) otomatis masuk ke workspace yang bisa dilihat lewat Web UI (file browser) — lihat Bagian 6.4.
- Sandbox punya batasan resource (CPU/RAM/waktu eksekusi) supaya tidak membebani server.

### 6.4 Memori Terstruktur + Workspace File

- **Memori jangka pendek:** konteks percakapan aktif.
- **Memori jangka panjang terstruktur:** bukan cuma blob teks — disimpan sebagai entitas terstruktur (mis. per-proyek, per-topik, per-tugas) di database, supaya bisa ditelusuri, bukan cuma "tebak-tebakan" similarity search.
- **Workspace file:** folder kerja persisten tempat agent menyimpan semua hasil nyata — file kode, dokumen, laporan, hasil scraping, dll. Web UI punya file browser supaya Anda bisa langsung buka/lihat/download hasil kerja agent tanpa harus minta ditampilkan di chat.
- Riwayat versi file penting (mis. lewat git internal di workspace) supaya perubahan bisa dilacak.

### 6.5 Browser Access
- Tool browser otomatis (headless, via Playwright) untuk: membuka URL, membaca isi halaman, mengisi form, klik elemen, ambil screenshot.
- Berguna untuk riset, mengambil data dari halaman yang butuh interaksi (bukan cuma fetch API), atau tugas yang memang perlu "melihat" halaman seperti manusia.
- Screenshot/hasil browsing juga masuk ke workspace file (Bagian 6.4).

### 6.6 Akses Laptop via Tailscale
- Karena Proxmox, Coolify, dan laptop Anda sudah satu jaringan Tailscale, [Nama Agent] menambahkan **komponen kecil (companion agent)** yang dijalankan di laptop, listen di alamat Tailscale laptop, dengan API terbatas (mis. baca/tulis file di folder tertentu, jalankan perintah yang di-whitelist, ambil screenshot).
- Agent utama (di Coolify/Proxmox) memanggil companion ini lewat alamat Tailscale laptop — tidak perlu expose apa pun ke internet publik, karena Tailscale sudah membuat jalur privat.
- **Guardrail:** companion di laptop defaultnya hanya mengizinkan operasi yang di-whitelist eksplisit (baca folder tertentu, jalankan skrip tertentu) — bukan akses shell penuh tanpa batas, supaya laptop pribadi Anda tetap aman kalau ada bug di agent.

### 6.7 Cron Job / Scheduler
- Tugas terjadwal/berulang, bisa memicu tool apa pun (termasuk coding task, browser task, atau kirim notifikasi ke channel).
- Riwayat eksekusi (sukses/gagal, output) terlihat di Web UI & CLI.

### 6.8 Kanban Board
- Papan tugas Backlog → In Progress → Done, dikelola agent (auto breakdown tugas kompleks) maupun manual oleh Anda.
- Terhubung ke workspace file & scheduler (kartu tugas bisa punya tenggat & tautan ke file hasil).

### 6.9 Multi-Channel Gateway
- **Telegram** (`python-telegram-bot`), **Discord** (`discord.py`), **WhatsApp via Baileys** (konfirmasi Anda) — catatan: Baileys tidak resmi, ada risiko nomor diblokir Meta, sebaiknya pakai nomor terpisah bukan nomor utama.
- Semua channel masuk ke satu message bus internal.

### 6.10 MCP Client
- Agent jadi MCP client, bisa konek ke banyak MCP server sekaligus (GitHub, Google Drive, filesystem, dll), tool dari tiap server otomatis masuk ke tool registry tanpa ubah kode core.

### 6.11 Antarmuka
- **Terminal/CLI** (prioritas pertama, `rich`/`textual`).
- **Web UI** (Next.js + TypeScript): dashboard LLM backend (9Router + lainnya), Kanban, file browser workspace, chat, status channel & MCP, panel skill terpasang, log audit — semua real-time via WebSocket.

### 6.12 Keamanan & Audit
- Semua kredensial (9Router key, provider lain, bot token, MCP auth, akses companion laptop) di secret vault terenkripsi.
- Audit log untuk: skill baru diaktifkan, perintah dijalankan di sandbox coding, aksi yang menyentuh companion laptop, penggantian backend LLM aktif.
- Rate-limit internal untuk mencegah pemakaian token/biaya membengkak akibat loop tak disengaja.

---

## 7. Arsitektur Tingkat Tinggi

```
                    ┌─────────────────────────────────────────┐
                    │        Antarmuka & Channel               │
                    │  Terminal/CLI   Web UI (Next.js+TS)      │
                    │  Telegram   Discord   WhatsApp(Baileys)  │
                    └───────────────────┬───────────────────────┘
                                        │ message bus internal
        ┌───────────────────────────────▼────────────────────────────────┐
        │                    Agent Core (Python, FastAPI)                 │
        │  Orchestrator/loop   Scheduler(cron)   Kanban store              │
        │  Memori terstruktur + Workspace file   Audit log                 │
        │  Tool & Skill registry (incl. skill auto-installer dari GitHub)  │
        └───┬──────────┬──────────┬───────────┬───────────┬────────────────┘
            │          │          │           │           │
      ┌─────▼───┐ ┌────▼─────┐ ┌─▼────────┐ ┌▼─────────┐ ┌▼─────────────┐
      │ LLM      │ │ Coding    │ │ Browser  │ │ MCP      │ │ Tailscale     │
      │ Backend  │ │ Sandbox   │ │ Tool     │ │ Client   │ │ Laptop        │
      │ Manager  │ │ (Docker)  │ │(Playwright)│(multi-srv)│ │ Connector     │
      └────┬─────┘ └───────────┘ └──────────┘ └────┬─────┘ └──────┬────────┘
           │                                        │              │
    ┌──────┴───────┐                        ┌───────┴───┐   ┌──────▼──────┐
    │ 9Router       │                        │MCP Server1│   │ Companion    │
    │ (self-hosted, │  ┌───────────────┐     │... N      │   │ Agent di      │
    │ sudah jalan)  │  │ Provider lain  │     └───────────┘   │ Laptop        │
    └───────────────┘  │ (langsung, API │                     │ (via Tailscale)│
                        │ key sendiri)   │                     └───────────────┘
                        └───────────────┘
```

Semua komponen server (Agent Core, sandbox, dll) berjalan di container Docker yang sama, dan **seluruh mesh (Proxmox, Coolify, laptop) sudah terhubung lewat Tailscale** — jadi tidak perlu expose port publik tambahan untuk komunikasi antar-node.

---

## 8. Tumpukan Teknologi

| Layer | Teknologi | Catatan |
|---|---|---|
| Bahasa utama | Python 3.12 (~80%) | Core, tool layer, integrasi |
| Web/API framework | FastAPI | REST + WebSocket |
| LLM backend | Client OpenAI-compatible ke 9Router + adapter provider lain | 9Router jadi backend utama |
| Agent orchestration | Custom loop / LangGraph | Tool-calling, planning |
| Coding sandbox | Docker-in-Docker atau gVisor/firejail | Isolasi eksekusi kode |
| Browser tool | Playwright (Python) | Headless browsing |
| Scheduler | APScheduler (awal), Celery+Redis (kalau scale) | Cron jobs |
| Memori terstruktur | PostgreSQL (entitas terstruktur) + pgvector (semantic search) | Bukan cuma vector blob |
| Workspace file | Volume Docker persisten + Git internal (versioning) | Dilihat lewat file browser di Web UI |
| Skill installer | `git` + sandbox review sebelum aktivasi | Dari GitHub |
| Channel: Telegram/Discord/WhatsApp | `python-telegram-bot`, `discord.py`, Baileys (Node.js sidecar) | Baileys perlu proses Node terpisah, dijembatani ke core Python via API internal |
| MCP client | MCP Python SDK | Multi-server |
| Konektivitas jaringan | Tailscale (sudah ada) | Agent Core memanggil companion laptop via IP Tailscale |
| Companion laptop | Aplikasi kecil (Python/Node) yang jalan di laptop, expose API terbatas via Tailscale | Whitelist operasi |
| Web UI | Next.js + TypeScript + Tailwind | ~20% codebase |
| Realtime | WebSocket | |
| Secret vault | `age`/`sops` atau vault terenkripsi custom | |
| Kontainerisasi | Docker + Docker Compose | Basis semua target deploy |

---

## 9. Strategi Deployment

- **Coolify:** deploy Agent Core + Web UI sebagai aplikasi Docker Compose seperti biasa; karena sudah di jaringan Tailscale yang sama dengan Proxmox & laptop, tidak perlu expose port tambahan untuk akses internal.
- **Proxmox:** VM/LXC terpisah menjalankan Docker Compose yang sama; juga sudah tersambung Tailscale.
- **Laptop:** hanya menjalankan companion agent kecil (bukan seluruh sistem), diakses lewat alamat Tailscale-nya oleh Agent Core yang jalan di Coolify/Proxmox.
- Anda bisa memilih menjalankan Agent Core utama di Coolify **atau** Proxmox (atau redundan di keduanya di fase lanjutan) — arsitektur Docker yang sama berlaku di semua tempat.

---

## 10. Rencana Fase Pengembangan

| Fase | Cakupan | Keluaran |
|---|---|---|
| **Fase 1 — Core + Integrasi 9Router** | Agent loop dasar, CLI, koneksi ke 9Router sebagai backend LLM, memori dasar | Agent bisa chat lewat CLI memakai 9Router |
| **Fase 2 — Coding Sandbox & Workspace** | Sandbox coding, workspace file + file browser dasar | Agent bisa mengerjakan tugas coding sederhana & hasilnya terlihat sebagai file |
| **Fase 3 — Skill System + GitHub Installer** | Skill registry, alur install skill dari GitHub dengan review manual | Agent bisa dipasangi skill baru dari repo GitHub |
| **Fase 4 — Browser Tool & MCP Client** | Playwright browser tool, integrasi minimal 1-2 MCP server | Agent bisa browsing & pakai tool MCP eksternal |
| **Fase 5 — Scheduler & Kanban** | Cron job, Kanban task store | Tugas terjadwal & task tracking |
| **Fase 6 — Multi-Channel** | Telegram dulu, lalu Discord, lalu WhatsApp (Baileys) | Agent bisa dihubungi dari channel chat |
| **Fase 7 — Tailscale Laptop Connector** | Companion agent di laptop, whitelist operasi | Agent Core bisa memicu aksi terbatas di laptop |
| **Fase 8 — Web UI Lengkap** | Dashboard backend LLM, Kanban visual, file browser, chat, status semua komponen | UI penuh dipakai sehari-hari |
| **Fase 9 — Hardening & Provider Tambahan** | Tambah backend LLM langsung di luar 9Router sesuai kebutuhan, security review menyeluruh | Sistem stabil untuk pemakaian harian |

---

## 11. Metrik Keberhasilan

- Agent berhasil melakukan chat & tool-call lewat backend 9Router tanpa masalah (akhir Fase 1).
- Agent berhasil menyelesaikan 1 tugas coding end-to-end (tulis kode → jalankan → laporkan hasil) dan filenya muncul di workspace (akhir Fase 2).
- Agent berhasil memasang 1 skill dari repo GitHub setelah proses review (akhir Fase 3).
- Agent berhasil browsing 1 halaman web dan memakai tool dari 1 MCP server eksternal (akhir Fase 4).
- Minimal 1 channel chat aktif dua arah (akhir Fase 6).
- Agent berhasil memicu 1 aksi di laptop lewat companion + Tailscale (akhir Fase 7).

---

## 12. Risiko & Mitigasi

| Risiko | Mitigasi |
|---|---|
| **Skill dari GitHub bisa berisi kode berbahaya/supply-chain attack** | Review manual wajib sebelum aktivasi penuh; jalankan dulu di sandbox terisolasi; izin akses (filesystem/network) diberikan bertahap, bukan otomatis penuh |
| **Companion di laptop disalahgunakan kalau ada bug di agent** | Whitelist operasi ketat, bukan shell akses penuh; semua panggilan ke companion tercatat di audit log |
| **Coding sandbox dieksploitasi untuk keluar dari container** | Pakai isolasi kuat (gVisor/firejail), batasi resource & network sandbox, jangan jalankan sebagai root |
| **WhatsApp via Baileys berisiko nomor diblokir Meta** | Gunakan nomor terpisah, bukan nomor utama |
| **Scope sangat besar (9 fase, banyak integrasi)** | Ikuti urutan fase di Bagian 10, jangan paralel semua sekaligus |
| **Ketergantungan pada satu instance 9Router** | Backend tambahan (provider langsung) tetap didukung sebagai cadangan kalau 9Router down |

---

## 13. Asumsi & Pertanyaan Terbuka

1. **Apakah 9Router versi Anda (v0.5.65) punya API/endpoint admin** (selain `/v1` untuk inference) yang bisa dipanggil untuk baca status quota/provider secara terprogram? Ini menentukan seberapa dalam dashboard [Nama Agent] bisa menampilkan status 9Router.
2. **Provider AI langsung mana saja** (di luar yang sudah ada di 9Router) yang ingin ditambahkan sebagai backend terpisah?
3. **Companion laptop:** OS laptop apa (Windows/Mac/Linux)? Ini menentukan cara terbaik membuat companion agent-nya.
4. **Operasi apa saja yang ingin diizinkan agent lakukan di laptop** (baca file tertentu? jalankan skrip tertentu? ambil screenshot?) — untuk menyusun whitelist di Bagian 6.6.
5. **Budget harian/bulanan** pemakaian token, untuk fitur alert/limit.

---

## 14. Lampiran
- Referensi arsitektur agent: Hermes Agent (Nous Research).
- Referensi backend LLM: 9Router (proxy self-hosted milik Anda) — endpoint OpenAI-compatible, fitur quota tracking & fallback bawaan.
- Dokumen ini akan terus diperbarui seiring jawaban di Bagian 13 dan detail baru dari Anda.
