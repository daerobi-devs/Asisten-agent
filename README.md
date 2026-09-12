<div align="center">

# ⚡ LXION — Autonomous Multi-Channel AI Agent Studio

**High-Performance Autonomous Engineering Assistant & Personal Intelligence**  
*Orchestrating Multi-Channel Messaging, 0-Token Schedulers, Unified Google Workspace, and Tailscale Companion.*

[![Python 3.12](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com)
[![Coolify](https://img.shields.io/badge/Coolify-Supported-6B21A8?style=for-the-badge&logo=coolify&logoColor=white)](https://coolify.io)
[![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://telegram.org)
[![WhatsApp](https://img.shields.io/badge/WhatsApp-Baileys-25D366?style=for-the-badge&logo=whatsapp&logoColor=white)](https://github.com/WhiskeySockets/Baileys)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge)](LICENSE)

[Features](#-key-features) • [Architecture](#-architecture) • [Getting Started](#-getting-started) • [Coolify Deployment](#-deploying-on-coolify) • [Configuration](#-environment-variables)

</div>

---

## 📖 Overview

**LXION** is an autonomous personal AI assistant and engineering operating studio built with FastAPI, asyncio, and modern LLM tool-calling capabilities. It serves as your 24/7 personal copilot across multiple chat channels (Telegram, WhatsApp, and Discord), capable of managing Google Workspace, executing code in a sandboxed workspace, tracking tasks via an interactive Kanban board, and controlling remote companion devices via Tailscale.

---

## ✨ Key Features

### 1. 💬 Unified Multi-Channel Gateway
- **Simultaneous Cross-Platform Messaging**: Connects with **Telegram Bot** (hot polling & interactive markdown), **WhatsApp Web** (via Baileys Multi-Device WebSocket sidecar), and **Discord Bot**.
- **Central MessageBus**: Decoupled inbound routing and outbound message delivery with auto-session tracking and rich media document forwarding.

### 2. ⚡ Dual-Mode Cron Scheduler (0-Token & AI Prompts)
- **Deterministic 0-Token Alerts**: Direct notifications and reminders dispatched to Telegram or WhatsApp without consuming any LLM tokens (`send_channel_message`).
- **Autonomous AI Prompts**: Scheduled agent reasoning (e.g. morning daily briefs, news summaries, social media content drafts).
- **Flexible Cadences**: Supports **Daily** (`07:00`), **Weekly** (`senin,rabu@07:00` / `mon,wed@07:00`), **Intervals** (`5m`, `2h`), **Specific Dates**, and full Crontab syntax.

### 3. 🌐 Ultra-Efficient Unified Google Workspace Tool (`google_workspace`)
- Consolidates 6 Google cloud services into **1 single multi-action tool**, saving **~75% prompt schema tokens** compared to legacy architectures:
  - **Gmail**: Read inbox, inspect threads, and compose/send emails.
  - **Google Drive**: List, search, upload local files, and create folders.
  - **Google Calendar**: Check upcoming events and schedule new appointments.
  - **Google Docs**: Create documents, extract text, and append notes.
  - **Google Sheets**: Read rows, create spreadsheets, and append structured data.
  - **Google Tasks**: Track and complete to-do tasks.

### 4. 🎨 Linear & Raycast-Grade Web Studio UI
- Built with high-tier taste design principles: crisp slate typography, glassmorphism cards, seamless Dark/Light mode switcher with `localStorage` persistence, real-time token telemetries, and zero-clutter navigation.
- **Interactive Kanban Board**: Visual drag-and-drop agile boards with task breakdowns and linked file attachments.
- **Workspace Explorer & Zip Delivery**: Browse files hierarchically and deliver folders as compressed `.zip` archives directly to chat channels.

### 5. 💻 Tailscale Laptop Companion
- Seamlessly controls and monitors Windows companion laptops over a secure Tailscale private network:
  - Hardware health metrics (CPU, RAM, battery, uptime).
  - Real-time desktop screenshot capture.
  - Whitelisted directory reading and secure CLI execution.

### 6. 🧩 Skills & MCP Ecosystem
- **Skill Store**: Auto-install and hot-load community skills directly from GitHub repositories with automated security risk scanning.
- **Model Context Protocol (MCP)**: Native client supporting stdio MCP servers (Filesystem, GitHub, SQLite, etc.).

---

## 🏗 Architecture

```
                               ┌────────────────────────┐
                               │   User Chat Channels   │
                               │ Telegram, WhatsApp, DC │
                               └───────────┬────────────┘
                                           │
                                           ▼
┌────────────────────────┐     ┌────────────────────────┐     ┌────────────────────────┐
│     Tailscale Mesh     │◄────┤   Unified MessageBus   ├────►│  Taste UI Studio (Web) │
│ Windows Laptop Client  │     │   (FastAPI + AsyncIO)  │     │ Dark / Light Dashboard │
└────────────────────────┘     └───────────┬────────────┘     └────────────────────────┘
                                           │
             ┌─────────────────────────────┼─────────────────────────────┐
             ▼                             ▼                             ▼
┌────────────────────────┐   ┌────────────────────────┐   ┌────────────────────────┐
│   Dual-Mode Scheduler  │   │  Multi-Agent Factory   │   │ Unified Tool Registry  │
│  APScheduler 0-Tokens  │   │ LXION Core + Specialists│   │ 18 Consolidated Suites │
└────────────────────────┘   └─────────────┬──────────┘   └──────────────┬─────────┘
                                           │                             │
                                           ▼                             ▼
                             ┌────────────────────────┐   ┌────────────────────────┐
                             │ 9Router / LLM Providers │   │ Google Workspace Suite │
                             │  (OpenAI/Anthropic/GC) │   │ Gmail, Drive, Calendar │
                             └────────────────────────┘   └────────────────────────┘
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.12 or newer
- Git & Docker (optional for containerized deployment)
- Node.js (for WhatsApp Baileys sidecar)

### Local Installation

1. **Clone the Repository**:
   ```bash
   git clone git@github.com:daerobi-devs/Asisten-agent.git
   cd Asisten-agent
   ```

2. **Set Up Virtual Environment**:
   ```bash
   python -m venv venv
   # On Linux/macOS:
   source venv/bin/activate
   # On Windows:
   .env\Scriptsctivate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   pip install -e .
   ```

4. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your 9Router API key and Bot tokens
   ```

5. **Launch WhatsApp Sidecar (Optional)**:
   ```bash
   cd sidecar/whatsapp
   npm install
   node server.js
   ```

6. **Start LXION Core**:
   ```bash
   python -m uvicorn lxion.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   Open `http://localhost:8000` to access the Web Studio.

---

## 🐳 Deploying on Coolify

LXION is pre-configured for seamless container deployment on **Coolify** or any Docker VPS:

### Step 1: Push Code to GitHub
Ensure sensitive files (`.env`, `credentials/`, `whatsapp_sessions/`) are ignored by `.gitignore` (pre-configured).

### Step 2: Create New Resource in Coolify
1. In Coolify, click **+ New Resource** -> **Application** -> **Public/Private GitHub Repository**.
2. Select repository `daerobi-devs/Asisten-agent` and branch `main`.
3. Choose **Docker Compose** as the build pack.

### Step 3: Configure Persistent Storage Volumes (Crucial)
In your Coolify application settings, navigate to **Storages**:
| Source (Host / Volume) | Destination (Container) | Purpose |
| :--- | :--- | :--- |
| `lxion_workspace` | `/app/workspace` | Preserves agent files & scripts |
| `lxion_credentials` | `/app/credentials` | Preserves Google OAuth tokens |
| `lxion_whatsapp` | `/app/whatsapp_sessions` | Preserves WhatsApp session keys |
| `lxion_logs` | `/app/logs` | Preserves execution logs |

### Step 4: Environment Variables
Add your environment variables in Coolify's **Environment** tab:
```bash
NINE_ROUTER_BASE_URL=https://9router.daeroom.my.id/v1
NINE_ROUTER_API_KEY=your_key_here
DEFAULT_MODEL=auto
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
DISCORD_BOT_TOKEN=your_discord_bot_token
```

Click **Deploy** — Coolify will automatically build and launch LXION with PostgreSQL and Redis.

---

## ⚙️ Environment Variables

| Variable | Description | Default |
| :--- | :--- | :--- |
| `NINE_ROUTER_BASE_URL` | 9Router OpenAI-compatible API base | `https://9router.daeroom.my.id/v1` |
| `NINE_ROUTER_API_KEY` | 9Router bearer authentication token | `""` |
| `DEFAULT_MODEL` | Default LLM model identifier | `auto` |
| `TELEGRAM_BOT_TOKEN` | Telegram Bot token from @BotFather | `""` |
| `DISCORD_BOT_TOKEN` | Discord Developer portal bot token | `""` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis cache and message queue URL | `redis://localhost:6379/0` |
| `WORKSPACE_DIR` | Relative directory for user files | `./workspace` |
| `COMPANION_HOST` | Tailscale IP of Windows companion laptop | `100.x.x.x` |
| `COMPANION_PORT` | Windows companion daemon port | `9099` |

---

## 🧪 Automated Testing

LXION includes a comprehensive pytest suite covering 100% of core features:
```bash
pytest
```
```
============================= 53 passed in 24.37s =============================
```

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

<div align="center">
Built with ❤️ for Autonomous Engineering Intelligence
</div>
