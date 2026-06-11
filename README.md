---
title: Lumen AI Native Mini CRM
emoji: 🚀
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

<div align="center">

# 🚀 Lumen — AI-Native Mini CRM

**An AI-powered campaign co-pilot with live delivery feeds and customer segmentation.**

[![🤗 Live Demo on Hugging Face Spaces](https://img.shields.io/badge/🤗%20Live%20Demo-Hugging%20Face%20Spaces-yellow?style=for-the-badge)](https://huggingface.co/spaces/pronov06/lumen-crm)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-181717?style=for-the-badge&logo=github)](https://github.com/pronov06/Lumen---AI-Native-Mini-CRM)

> 🌐 **Try it live → [huggingface.co/spaces/pronov06/lumen-crm](https://huggingface.co/spaces/pronov06/lumen-crm)**

</div>

---

## ✨ Features

| Feature | Description |
|---|---|
| 🤖 **AI Co-pilot** | Describe a campaign goal; Gemini 2.5 Flash generates the segment, channel, and message plan |
| 📊 **Audience Analytics** | 240 seeded customers with lifecycle stages: VIP, active, at-risk, lapsed |
| 📢 **Campaign Engine** | Create, approve, and launch campaigns with one click |
| ⚡ **Live Delivery Feed** | Real-time WebSocket stream of message deliveries and receipts |
| 💬 **Chat Interface** | Conversational assistant mode for hands-free campaign planning |
| 🔒 **Dead Letter Queue** | Tracks failed deliveries for retry inspection |

---

## 🖥️ Screenshots

> The AI co-pilot generates a full campaign proposal — segment, channel, and personalized message — from a plain English goal.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│           React 18 + TypeScript         │  ← Frontend (Vite)
│         served by Nginx on :7860        │
└────────────────┬────────────────────────┘
                 │ reverse proxy
┌────────────────▼────────────────────────┐
│     FastAPI CRM Backend  (:8000)        │  ← REST + WebSocket
│   SQLite · In-memory bus · Gemini AI   │
└────────────────┬────────────────────────┘
                 │ HTTP callbacks
┌────────────────▼────────────────────────┐
│   Channel Simulator Service (:8001)     │  ← Simulates WhatsApp/SMS/Email/RCS
└─────────────────────────────────────────┘
All three processes managed by Supervisor inside a single Docker container.
```

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18 + TypeScript + Vite |
| Backend | Python 3.12 + FastAPI + SQLAlchemy (async) |
| AI | Google Gemini 2.5 Flash |
| Database | SQLite (auto-seeded on boot) / PostgreSQL (production) |
| Cache / Bus | In-memory (free tier) / Redis (production) |
| Serving | Nginx + Supervisor (single container) |
| Containerisation | Docker + Docker Compose |

---

## 🚀 Run Locally

```bash
# Clone the repo
git clone https://github.com/pronov06/Lumen---AI-Native-Mini-CRM.git
cd Lumen---AI-Native-Mini-CRM

# Add your Gemini API key
echo "CRM_GEMINI_API_KEY=your_key_here" >> services/crm/.env

# Start all services
docker compose up --build
# → App available at http://localhost:8080
```

## 🌐 Free Deployment (Single Container)

Deploy the entire stack for free on [Hugging Face Spaces](https://huggingface.co/spaces), [Koyeb](https://koyeb.com), or [Render](https://render.com) using the included `Dockerfile`:

```bash
docker build -f Dockerfile -t lumen-crm .
docker run -p 7860:7860 -e CRM_GEMINI_API_KEY="your_key" lumen-crm
```

See [README_FREE_DEPLOY.md](./README_FREE_DEPLOY.md) for full step-by-step instructions.

---

## 📄 License

MIT
