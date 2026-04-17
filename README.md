# Welfare Bot – AI-powered Wellbeing Assistant

## Overview

Welfare Bot is a backend-driven AI system designed to support elderly wellbeing through conversational interaction, risk detection, and safety-aware response generation.

The system analyzes user messages, detects potential wellbeing risks (such as loneliness, fatigue, or health-related signals), and produces structured risk assessments alongside safe, context-aware responses.

The project focuses on combining:

* AI (LLM-based responses)
* rule-based risk analysis
* data validation
* multilingual interaction
* production-style backend architecture

---

## Key Features

### Risk-aware conversation pipeline

Each message goes through a structured backend flow:

1. Input validation (anti-spam, length, duplicates)
2. Risk assessment (rule-based engine)
3. Risk persistence (database)
4. Context-aware response generation via LLM
5. Safety validation of output

---

### Risk Engine (core logic)

The system detects signals such as:

* poor sleep
* lack of food or water
* fatigue
* dizziness
* loneliness
* fall or physical pain

Outputs:

* risk level (low, medium, high, critical)
* risk score
* category
* follow-up question
* suggested action

Important:

* Risk is determined in backend, not by AI
* AI only generates the response text

---

### Memory Summary (context optimization)

The system maintains a compressed long-term summary of the user:

* reduces token usage
* improves contextual continuity
* prevents prompt overflow

---

### Token Optimization

A token management layer:

* trims conversation history
* preserves important context
* keeps requests within model limits

---

### Multilingual Support

Supported languages:

* English
* Finnish
* Swedish

Features:

* automatic language detection
* consistent single-language responses
* no language mixing

---

### Validation Layer

All incoming messages are validated before processing:

* maximum length control
* anti-spam detection
* repeated message detection

This ensures higher data quality and more stable system behavior.

---

### Safety-first Design

* No medical diagnosis
* Controlled escalation for critical cases
* Risk-aware response logic
* Output validation to prevent unsafe or mixed-language replies

---

## Tech Stack

Backend:

* FastAPI
* PostgreSQL
* SQLAlchemy
* Alembic

AI:

* OpenAI API (LLM)

Frontend:

* React + TypeScript (Vite)

---

## Architecture

```text
Frontend (React)
        ↓
FastAPI API Layer
        ↓
Service Layer
  - risk_service
  - validation_service
  - memory_service
  - token_service
        ↓
PostgreSQL
```

---

## How this project demonstrates data and AI competencies

### Data processing

* structured storage of conversations and risk events
* relational data modeling
* linking users, messages, and risk analysis

### Data validation

* input cleaning and normalization
* spam detection
* duplicate detection

### AI usage

* LLM integration for response generation
* prompt engineering
* controlled AI behavior (backend-driven logic)

### Optimization

* token trimming
* memory summarization
* context control

### Evaluation

* risk scoring system
* test dataset and evaluation scripts
* ability to measure consistency of outputs

### Ethics and safety

* AI does not make autonomous risk decisions
* system avoids harmful outputs
* critical cases are escalated safely
* user wellbeing is prioritized

---

## API Endpoints

Users:

* GET /users
* POST /users

Conversations:

* GET /conversations/{user_id}/messages
* POST /conversations/message
* POST /conversations/message/stream

Risk:

* GET /conversations/{user_id}/risk-analysis

---

## Setup

```bash
cd welfare-bot-backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

---

## Recent Updates

* Added token management layer (token_service)
* Implemented memory summary system for context compression
* Introduced validation layer (anti-spam, duplicate detection, max length)
* Improved risk-aware prompt structure
* Added multilingual response handling
* Implemented safer response generation (stream vs non-stream based on risk)

---
