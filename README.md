---
title: Lumen AI Native Mini CRM
emoji: 🚀
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# Lumen Mini CRM — AI-Native Campaign Co-pilot

A full-stack AI-native CRM with a **Gemini-powered campaign co-pilot**, live delivery feed, and customer segmentation engine.

## Features
- 🤖 **AI Co-pilot** — Describe a campaign goal; Gemini generates a complete segment + message plan
- 📊 **Audience Analytics** — Browse 240 seeded customers with lifecycle stages (VIP, lapsed, active, at-risk)
- 📢 **Campaign Engine** — Create, launch, and track campaigns with real-time WebSocket delivery updates
- 💬 **Chat Interface** — Conversational assistant mode for hands-free campaign planning
- ⚡ **Live Feed** — Real-time event stream of message deliveries and receipts

## Stack
| Layer | Technology |
|---|---|
| Frontend | React 18 + TypeScript + Vite |
| Backend | Python 3.12 + FastAPI + SQLAlchemy |
| AI | Google Gemini 2.5 Flash |
| Database | SQLite (ephemeral, auto-seeded on boot) |
| Serving | Nginx (reverse proxy) + Supervisor |

## Environment Variables
Set `CRM_GEMINI_API_KEY` in the Space secrets to enable the AI co-pilot.
