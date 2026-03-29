# HisaabWala

# VoiceBooks — Product Requirements Document (v1)

## 1. Overview

**Product:** VoiceBooks — Voice-first AI accountant for illiterate shopkeepers
**Version:** v1 (MVP)
**Team:** 2-3 engineers
**Timeline:** 5 days
**Interface:** Pure WhatsApp (no app, no dashboard, no frontend)

## 2. Problem Statement

80% of India's 63M SMBs do zero bookkeeping. Most owners are semi-literate, can't use apps, and run businesses entirely in their heads — losing lakhs in uncollected dues and invisible cash leaks. Every existing solution assumes literacy and app fluency.

## 3. Target User

- Hindi-speaking small shopkeeper (kirana, hardware, general store)
- Tier 2-3 Indian cities
- Semi-literate, uses WhatsApp daily
- Does mental accounting, no written records
- Primary pain: tracking udhaar (credit) and collecting dues

## 4. Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | FastAPI + Uvicorn |
| Database | Supabase PostgreSQL |
| File Storage | Supabase Storage |
| ASR | Groq Whisper API |
| LLM | Claude API (Haiku for extraction, cost-efficient) |
| WhatsApp | Twilio WhatsApp Business API |
| Task Queue | Celery + Redis |
| Deployment | Docker Compose on EC2 (or Railway/Render) |

## 5. Features (v1 Scope)

### 5.1 Zero-Friction Registration
- First message from unknown number triggers onboarding
- System detects phone number from Twilio webhook payload (no manual input)
- Only collects: shop name (via voice or text)
- Flow: Unknown number → welcome message → shopkeeper says shop name → merchant created → confirmation sent
- `is_onboarding` flag on merchant row routes messages through onboarding vs normal flow

### 5.2 Voice-to-Ledger (Core)
- Shopkeeper sends WhatsApp voice note
- Pipeline: Twilio webhook → download .ogg audio → ffmpeg convert if needed → Groq Whisper transcription → Claude extraction → validate → store → confirm
- Handles multi-transaction voice notes ("Ramesh ne 500 diye, Suresh 200 udhaar, Mohan ka 1000 aa gaya")
- Multi-transaction confirmations sent as one numbered message, not individual floods
- Hindi number normalization ("paanch sau" → 500) handled by LLM prompt

### 5.3 Auto-Confirm with 2-Minute Timer
- Transactions stored immediately with status "pending"
- Celery countdown task (2 min) auto-confirms if no correction received
- Batching: wait 30 seconds of inactivity before sending consolidated confirmation message
- 2-minute timer starts from the batched confirmation, not from individual transaction creation

### 5.4 Correction Flow
- Shopkeeper replies within 2 minutes to correct
- Corrections matched to most recent pending transaction
- If ambiguous (two pending with same amount): ask for clarification in Hindi
- "Number 2 galat hai, 300 tha" for multi-transaction corrections

### 5.5 Duplicate Detection
- Same person + same amount + same direction within 10-minute window
- Flags before confirming: "Yeh pehle bhi log ho chuka hai, dobara save karein?"

### 5.6 Udhaar Balance Query
- Shopkeeper asks "Ramesh ka kitna baaki hai" or "Ramesh ka hisaab batao"
- System queries confirmed transactions for that entity under that merchant
- Returns net outstanding balance

### 5.7 Daily Auto-Summary
- Celery beat task at 9 PM IST
- Queries each active merchant's today's transactions (IST timezone-aware)
- Sends formatted WhatsApp message: today's sales, credit given, credit recovered, net position
- Uses Meta-approved WhatsApp template message (required for outside 24-hour session window)

### 5.8 Credit-Ready PDF Report
- Triggered by: "mera hisaab bhejo", "monthly report", or similar
- Aggregates: total inflow, total outflow, net position, per-entity receivables/payables
- Bilingual: Hindi + English (readable by both shopkeeper and loan officer)
- Generated via HTML template + WeasyPrint (in Docker for dependency management)
- Uploaded to Supabase Storage, download link sent via WhatsApp

### 5.9 Voice-as-Receipt
- Original audio file stored in Supabase Storage
- URL linked to transaction row (audio_url field)
- Creates audit trail for disputes

## 6. Intent Routing

Every incoming message classified before processing. Single LLM call (Option B) handles both intent classification and data extraction in one structured JSON response.

**Intents:**
| Intent | Trigger Examples | Action |
|--------|-----------------|--------|
| new_transaction | "Ramesh ne 500 diye" | Extract → store → confirm |
| correction | "woh 500 nahi, 300 tha" | Match to pending → update |
| balance_query | "Ramesh ka hisaab batao" | Query → respond with balance |
| report_request | "mera hisaab bhejo" | Generate PDF → send link |
| onboarding_response | (during registration) | Store shop name → complete setup |
| greeting | "namaste", "hello" | Friendly response with usage hint |
| unknown | unrecognizable input | "Maaf kijiye, samajh nahi aaya. Kripya dobara boliye." |

**LLM Response Format:**
```json
{
  "intent": "new_transaction",
  "confidence": 0.95,
  "transactions": [
    {
      "person_name": "Ramesh",
      "amount": 500,
      "direction": "incoming",
      "transaction_type": "payment",
      "item": null
    }
  ]
}
```

## 7. Data Model

### 7.1 merchants
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| phone_number | VARCHAR | Unique, from Twilio payload |
| shop_name | VARCHAR | Collected during onboarding |
| language | VARCHAR | Default "hi", for v2 multi-lang |
| is_onboarding | BOOLEAN | Routes message flow |
| created_at | TIMESTAMPTZ | UTC |

### 7.2 entities
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| merchant_id | UUID | FK → merchants |
| name | VARCHAR | LLM-normalized (strip ji/bhai) |
| phone | VARCHAR | Nullable, for v2 reminders |
| contact_type | VARCHAR | Nullable, smartphone/keypad for v2 |
| created_at | TIMESTAMPTZ | UTC |

### 7.3 transactions
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| merchant_id | UUID | FK → merchants |
| entity_id | UUID | FK → entities |
| amount | DECIMAL | |
| direction | VARCHAR | "incoming" / "outgoing" |
| transaction_type | VARCHAR | payment / credit_given / credit_recovery / expense |
| item | VARCHAR | Nullable |
| audio_url | VARCHAR | Supabase Storage URL |
| raw_transcript | TEXT | Whisper output |
| status | VARCHAR | pending / confirmed / rejected |
| message_id | VARCHAR | Twilio message SID (idempotency) |
| batch_id | UUID | Groups multi-transaction voice notes |
| created_at | TIMESTAMPTZ | UTC |
| confirmed_at | TIMESTAMPTZ | Nullable, set on confirm |

### 7.4 message_log
| Column | Type | Notes |
|--------|------|-------|
| id | UUID | PK |
| merchant_id | UUID | FK → merchants |
| direction | VARCHAR | "inbound" / "outbound" |
| message_type | VARCHAR | voice / text |
| twilio_sid | VARCHAR | Twilio message SID |
| raw_content | TEXT | Transcript or text body |
| created_at | TIMESTAMPTZ | UTC |

## 8. Entity Resolution (v1)

- LLM normalizes names during extraction (strips honorifics: bhai, ji, didi, etc.)
- Exact match within merchant's entities after normalization
- No match → create new entity
- No clear name extractable ("woh electrician wala") → ask: "Kiska naam batayein?"
- Shopkeeper can correct entity linking after the fact

## 9. Error Handling

| Scenario | Response |
|----------|----------|
| Whisper transcription fails / noise | "Maaf kijiye, samajh nahi aaya. Kripya dobara boliye." |
| LLM extraction low confidence (<0.7) | Ask for clarification in Hindi |
| No name extractable | "Kiska naam batayein?" |
| Multi-transaction ambiguous correction | List pending with numbers, ask which one |
| Twilio webhook retry (duplicate SID) | Check message_id, skip if already processed |
| API failure (Groq/Claude down) | "Abhi thodi dikkat hai, thodi der mein dobara bhejiye." |

## 10. Security & Data Isolation

- **merchant_id filtering on EVERY query** — no exceptions
- Each merchant only sees their own entities and transactions
- Phone numbers stored but not exposed in responses
- Audio files in Supabase Storage with merchant-scoped paths
- Rate limiting: max 50 messages per merchant per day (Redis counter)

## 11. Third-Party Compliance (Pre-Build Requirements)

| Task | Timeline | Blocker Level |
|------|----------|---------------|
| Twilio WhatsApp Business API approval | 1-7 days | **CRITICAL — start immediately** |
| Meta WhatsApp template messages (daily summary, re-engagement) | 24-48 hours after submission | HIGH |
| Groq API access verification + rate limit check | Same day | MEDIUM |
| Claude API budget estimation | Same day | LOW |

## 12. Audio Format Handling

- Twilio delivers WhatsApp voice notes as .ogg opus files
- Verify Groq Whisper accepts .ogg directly
- If not: ffmpeg conversion step (.ogg → .wav/.mp3) on server
- **Test on Day 1 — do not assume compatibility**

## 13. Deployment Architecture

- Docker Compose with 4 services: FastAPI + Uvicorn, Redis, Celery worker, Celery beat
- Single EC2 instance (or Railway/Render)
- Supabase pgbouncer enabled for connection pooling (free tier has connection limits)
- All timestamps stored as UTC, queries converted to IST where needed
- Environment variables: Twilio credentials, Groq API key, Claude API key, Supabase URL + key, Redis URL

## 14. Build Schedule

| Day | Focus | Deliverable |
|-----|-------|-------------|
| Day 1 | Twilio webhook + audio pipeline | Voice note received, downloaded, transcribed. WhatsApp templates submitted. Audio format verified. |
| Day 2 | LLM extraction + intent routing | Claude prompt handling all intents. Multi-transaction extraction. Hindi number normalization tested with 20+ real voice samples. |
| Day 3 | Full transaction flow | Entity resolution, DB storage, confirmation messages, auto-confirm timer, correction flow, duplicate detection. |
| Day 4 | Queries + reports + summary | Udhaar balance queries, PDF report generation, daily summary Celery task, intent routing integrated end-to-end. |
| Day 5 | Integration testing + deployment | End-to-end testing with real phones, edge cases, error handling, Docker Compose deployment, production Twilio number live. |

## 15. Explicitly Out of v1 Scope

- GST auto-mapping
- Multi-language support (beyond Hindi)
- Phone call interface
- Anomaly / fraud detection
- Web dashboard
- Direct reminders to debtors (Ramesh)
- SMS fallback for keypad phones
- Expense categorization / tagging
- Any frontend or UI

## 16. Success Metrics (v1)

- Voice note → confirmed transaction in < 15 seconds end-to-end
- Extraction accuracy > 90% on Hindi/Hinglish voice notes
- Zero cross-merchant data leakage
- Shopkeeper can generate a credit report within 1 message
- Daily summary delivered reliably at 9 PM IST

## 17. v2 Roadmap (Post-MVP)

- Direct udhaar reminders to debtors (WhatsApp + SMS)
- Contact number collection and storage
- Multi-language support (Bhojpuri, Marathi, Tamil, etc.)
- GST code mapping and filing assistance
- Phone call interface (Twilio Voice)
- Web dashboard for loan officers / NBFC partners
- Anomaly detection for suspicious entries
- Lending partnerships (data layer for credit scoring)
