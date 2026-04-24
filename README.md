# Welfare Bot

An AI-powered welfare assistant for elderly people — built to check in daily, detect risk signals, and notify care contacts when support is needed.

## Live Demo

[welfarebot-production.up.railway.app](https://welfarebot-production.up.railway.app)
---

## The Problem

Elderly people living alone are at risk of silent deterioration — missed meals, poor sleep, falls, loneliness, and medical emergencies that go unnoticed for hours or days. Existing solutions are either too clinical, too expensive, or require family members to constantly check in manually.

Welfare Bot solves this by having a warm, conversational AI check in with elderly users every day — in their own language, at their own pace — and quietly alerting care contacts when something is wrong.

---

## Business View

**Who it is for:**
- Elderly people living independently
- Their adult children or family members
- Care workers managing multiple clients

**What it replaces:**
- Daily phone calls from family members
- Expensive in-home monitoring hardware
- Generic reminder apps that feel cold and transactional

**Revenue model (future):**
- Monthly subscription per user (~€15–25/month)
- B2B licensing to care agencies and municipalities
- White-label for healthcare providers

**Why it works:**
- Low friction — just a conversation, no new device needed
- Multilingual — auto-detects Finnish, English, Swedish
- Voice-first — elderly users can speak instead of type
- Family-facing — care contacts get notified automatically on high risk

---

## What It Does

- Bot initiates a daily check-in conversation (morning, afternoon, evening)
- Detects risk signals in natural language: sleep, food, hydration, pain, mood, loneliness, falls, chest pain
- Assigns risk levels: low / medium / high / critical
- Changes its behavior based on risk — more direct and safety-focused at high/critical
- Limits conversations to 20 messages per day with a warm closing message
- Auto-detects language — responds in whatever language the user writes or speaks
- Voice interface — press once to start recording, press again to send
- Bot reads its own responses aloud via TTS
- Care contact form — store family member name, phone, email, notification preference
- Wellbeing analytics panel — daily scores for mood, sleep, food, hydration, medication, social activity
- Trend charts and human-readable insights over 7/14/30 days
- All output uses soft, non-threatening language — never clinical terms

---

## Tech Stack

**Backend**
- Python 3.11 + FastAPI
- PostgreSQL + SQLAlchemy ORM
- Alembic migrations
- OpenAI GPT-4o-mini (conversation)
- OpenAI Whisper (speech-to-text)
- OpenAI TTS nova (text-to-speech)
- JWT authentication (PyJWT + bcrypt)
- Deployed on Railway (Docker)

**Frontend**
- React 18 + TypeScript + Vite
- Plain CSS (no UI library)
- Voice recording via MediaRecorder API
- Responsive — desktop sidebar + mobile drawer layout

**Database tables**
- `users` — elderly users and admin/care worker accounts
- `conversation_messages` — full chat history with risk fields
- `risk_analyses` — per-message risk assessment
- `care_contacts` — linked family/care worker contacts
- `daily_checkins` — structured check-in answers
- `notifications` — pending alert queue
- `wellbeing_daily_metrics` — pre-aggregated daily wellbeing scores

---

## Architecture

```
┌─────────────────────────────────────────┐
│              Railway                    │
│                                         │
│  ┌──────────────┐   ┌────────────────┐  │
│  │   FastAPI    │   │   PostgreSQL   │  │
│  │   Backend    │──▶│   Database     │  │
│  └──────┬───────┘   └────────────────┘  │
│         │                               │
│  ┌──────▼───────┐                       │
│  │  React/TS    │                       │
│  │  Frontend    │                       │
│  │  (static)    │                       │
│  └──────────────┘                       │
└─────────────────────────────────────────┘
         │
         ▼
   OpenAI API
   (GPT-4o-mini + Whisper + TTS)
```

---

## Risk Engine

Rule-based multilingual risk assessment. Runs on every message.

| Level | Score | Signals | Bot behavior |
|---|---|---|---|
| Low | 0–3 | General wellbeing | Normal conversation |
| Medium | 4–5 | Poor sleep, mild fatigue | Follow-up questions |
| High | 6–7 | No food/water, fall, severe pain | Direct safety focus |
| Critical | 8–10 | Chest pain, breathing difficulty | Immediate action prompt |

---

## Wellbeing Scoring

Daily aggregation pipeline computes one row per user per day from check-ins, messages, and risk analyses.

| Component | Source | Weight |
|---|---|---|
| Mood | Check-in rating or risk signals | 25% |
| Sleep | Sleep quality rating (1–5) | 25% |
| Food | Meals eaten / tracked | 20% |
| Hydration | Drank enough water (bool) | 15% |
| Medication | Took medication (bool) | 10% |
| Social | Message count today | 5% |

Overall score blends check-in composite (70%) with risk signal (30%).
Output is always soft language — never raw scores shown to the user.

---

## Project Structure

```
welfare-bot/
├── Dockerfile
├── railway.toml
├── welfare-bot-backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/v1/endpoints/
│   │   │   ├── auth.py
│   │   │   ├── conversations.py
│   │   │   ├── voice.py
│   │   │   ├── care_contacts.py
│   │   │   └── wellbeing.py
│   │   ├── db/models/
│   │   ├── services/
│   │   │   ├── risk_service.py
│   │   │   ├── aggregation_pipeline.py
│   │   │   └── conversation_starter.py
│   │   └── integrations/
│   │       └── openai_client.py
│   ├── alembic/
│   └── requirements.txt
└── frontend/
    └── src/
        ├── App.tsx
        ├── index.css
        ├── api.ts
        ├── types.ts
        └── components/
            ├── ChatWindow.tsx
            ├── LoginPage.tsx
            ├── CareContactForm.tsx
            ├── WellbeingPanel.tsx
            ├── WellbeingScoreCard.tsx
            ├── WellbeingTrendChart.tsx
            └── WellbeingInsights.tsx
```

---

## Environment Variables (Railway)

```
DATABASE_URL        PostgreSQL connection string
OPENAI_API_KEY      OpenAI API key
SECRET_KEY          JWT signing secret (min 32 chars)
```

---

## Live Demo

[welfarebot-production.up.railway.app](https://welfarebot-production.up.railway.app)

**Test credentials:**
- Register a new account with role `user`
- Or use role `admin` to see all users

**Demo phrases to test risk detection:**
- Low (FI): `Nukuin hyvin, kiitos. Olo on hyvä tänään.`
- Medium (FI): `En oikein jaksanut nukkua ja olen ollut vähän yksinäinen.`
- High (FI): `En ole syönyt enkä juonut mitään tänään ja olen todella väsynyt.`
- Critical (FI): `Minulla on kova rintakipu.`
- English: `I haven't eaten or drunk anything today and I feel very weak.`
- Swedish: `Jag mår inte bra idag.`

---

## Roadmap

- [ ] Email notifications for HIGH risk (SendGrid/Gmail SMTP)
- [ ] SMS notifications for CRITICAL risk (Twilio)
- [ ] Phone call alerts for CRITICAL risk (Twilio Voice)
- [ ] Weekly digest email to care contacts
- [ ] Admin dashboard for care workers
- [ ] Structured morning check-in with scored questions
- [ ] Memory between sessions (conversation summary)
- [ ] Medication reminders

---

