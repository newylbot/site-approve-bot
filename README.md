# 🤖 Lumino Bot — Dockerized Telegram Admin Panel

A lightweight Telegram bot that connects to your Supabase database and lets admins manage user approvals via Telegram.

---

## 🗂 Files Overview

- `main.py` — Bot source code  
- `config.env` — Environment secrets (Supabase, Telegram)  
- `requirements.txt` — Python dependencies  
- `Dockerfile` — Build instructions for Docker container  
- `docker-compose.yml` — Run config (optional but recommended)

---

## 🚀 Quick Start

### 🔧 1. Build Docker Image

```bash
docker build -t lumino-bot .
```

### ▶️ 2. Run the Container

```bash
docker run --name lumino_bot --env-file=config.env lumino-bot
```

### 🧩 Or with Docker Compose (Recommended)

```bash
docker-compose up --build -d
```

---

## 🧼 Cleanup Commands

### Stop & Remove Single Container

```bash
docker stop lumino_bot && docker rm lumino_bot
```

### Full Cleanup (Compose)

```bash
docker-compose down --rmi all --volumes --remove-orphans
```

---

## 🔐 Environment Variables (`config.env`)

Do **not commit** this file to version control.

```
SUPABASE_URL=https://...
SUPABASE_ANON_KEY=eyJ...
BOT_TOKEN=7820...
ADMIN_CHAT_ID=787...
LOG_CHANNEL_ID=-100...
```

---

## 🧠 Features

- ✅ Inline approval toggle buttons  
- 📋 Paginated user list via `/showall`  
- 🔎 User search via `/show <uuid/email/name>`  
- 📦 Docker-ready (no external dependencies)  
- 🔐 All secrets are safely stored in `.env` format  

---

## 💬 Need Help?

Ping the bot admin on Telegram or open an issue.