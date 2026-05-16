# Waypoint — AI Voice Course Counsellor

Waypoint is a real-time voice AI counsellor ("Clara") for a fictional Australian university. It's an exploration of what's possible with Google ADK, Gemini Live native audio, and pgvector RAG — open-sourced so other developers building on the same stack can skip the potholes I hit.

**Live demo:** https://waypoint.vozara.ai/
*This is a demo deployment hosted by [VoZara](https://vozara.ai) and may be taken down or migrated in future. For a guaranteed-working setup, run locally — see [Local Development Setup](#local-development-setup).*

---

## What this is, and isn't

**This is** a hackathon-grade exploration shipped complete — system prompt, retrieval logic, eval suite, deployment config. The patterns are production-shaped (turn isolation, fresh-session-per-connection, ADK workarounds for the 1007/1008/1011 wire crashes) but the product itself is a demo. Kingsford University is fictional; the seed data is illustrative.

**This isn't** a maintained product. Issues for clear bugs are welcome, but I'm not actively triaging feature requests or pull requests. If you want to use these patterns in something serious, fork it.


---

## What Clara can do

| Say this | What happens |
|----------|-------------|
| "What engineering courses do you have?" | Course cards slide in as she speaks |
| "Tell me more about the Bachelor of Cybersecurity" | Full detail card — fees, ATAR, career outcomes |
| "Are there scholarships for international students?" | Scholarship cards with value, eligibility, deadline |
| "What ATAR do I need?" | Info card with markdown table from the knowledge base |
| "Can I book a campus tour for XXXX" | Booking confirmation with `GT-XXXXX` reference |
| Share a photo (transcript, award, campus map) | Clara sees it and responds in context |
| Share your screen | Clara sees what you're looking at and responds |
| Speak in any language | Clara matches your language automatically |

---

## Architecture

```
Browser (HTML/JS)
  │  PCM audio 16kHz + image/jpeg frames (VAD-gated for screen sharing)
  ▼
FastAPI WebSocket  (/ws/{client_id})   ← Cloud Run
  │
  ▼
ADK Runner  (InMemorySessionService — fresh session per connection)
  │  LiveRequestQueue — bidirectional audio + vision
  ▼
Gemini Live API  (gemini-3.1-flash-live-preview · Google Developer API)
  │  function_call → tool result
  ▼
7 ADK Tools  →  Cloud SQL PostgreSQL + pgvector  (semantic search)
  │
  └─ display callback → WebSocket side-channel → Browser cards (no round-trip wait)
```


---

## Tech Stack

| Layer | Choice |
|-------|--------|
| Agent framework | `google-adk` |
| Model | `gemini-3.1-flash-live-preview` via Google Developer API |
| Backend | FastAPI + Uvicorn |
| Database | Cloud SQL PostgreSQL 16 + pgvector |
| Embeddings | `gemini-embedding-001` (1536-dim, Matryoshka) |
| Frontend | Plain HTML/JS — no build step |
| Deployment | Cloud Run (`min-instances=1`, `memory=1Gi`) |
| CI/CD | Cloud Build (`cloudbuild.yaml`) |
| Secrets | Secret Manager (`waypoint-db-url`) |

---

## Project Structure

```
backend/
  main.py       # FastAPI app + WebSocket bridge + ADK monkey-patches
  agent.py      # ADK Agent "Clara" — model, instruction, 7 tools
  tools.py      # Tool functions (psycopg2, pgvector semantic search)
  seed.py       # Schema + seed data + embedding generation script
frontend/
  index.html    # Voice UI — mic/text toggle, transcript, card sidebar
data/
  seed.sql      # 16 courses, 10 events, 8 scholarships
  knowledge/    # Markdown docs → RAG (admissions, fees, visa, campus life…)
eval_suite.py   # 3-layer automated eval: tool correctness + routing + multi-turn
eval_report.json  # Latest results: 63/64 passed (98%)
Makefile        # make deploy / seed-prod / eval / logs
cloudbuild.yaml # CI/CD pipeline
Dockerfile
EVAL.md         # Eval suite documentation
```

---

## Agent Tools

| Tool | What it does |
|------|-------------|
| `search_courses(query, faculty?)` | pgvector semantic search over 16 courses |
| `get_course_detail(name)` | Full detail card for a single named course |
| `recommend_courses(interests, strengths, study_mode?)` | Personalised recommendations |
| `search_events(event_type?, date_range?)` | Upcoming events filtered by type |
| `search_knowledge(query)` | RAG over 50 knowledge chunks (admissions, ATAR, HECS, visa…) |
| `search_scholarships(query, scholarship_type?)` | 8 scholarships with filters |
| `book_campus_tour(name, date, party_size, email?)` | DB insert → returns `GT-XXXXX` ref |

---

## Local Development Setup

### Prerequisites

- Python 3.11+
- A [Neon](https://neon.tech) account (free tier — local dev only)
- A Google AI Studio API key **or** a GCP project with Vertex AI enabled

### 1. Clone and install

```bash
git clone <repo-url>
cd gemini-live-uni-guide
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Auth — choose one:
GOOGLE_API_KEY=your-google-ai-studio-key          # AI Studio (recommended — no GCP needed)
GOOGLE_GENAI_USE_VERTEXAI=FALSE                   # Required when using AI Studio key

# OR — Vertex AI (requires GCP project with Vertex AI enabled)
# GOOGLE_CLOUD_PROJECT=your-gcp-project-id
# GOOGLE_GENAI_USE_VERTEXAI=TRUE

# Database (Neon for local dev)
DATABASE_URL=postgresql://user:pass@...neon.tech/neondb?sslmode=require

MODEL_NAME=gemini-3.1-flash-live-preview
```

### 3. Seed the database

Applies schema, inserts seed data, and generates embeddings:

```bash
python backend/seed.py
```

Expected output:
```
Applying schema …
Inserting seed data …
Generating course embeddings …
  [courses] Embedded 16 courses.
Generating knowledge doc embeddings …
  [knowledge] admissions.md: 6 chunks embedded.
  ...
Database ready: 16 courses, 10 events, 50 knowledge doc chunks, 8 scholarships
```

### 4. Run the backend

```bash
make run
# or: cd backend && uvicorn main:app --reload --port 8080
```

### 5. Open the frontend

Open `frontend/index.html` in your browser (no build step needed).
Click the mic button and start talking.

---

## Reproducible Testing

### Automated eval suite (no voice required)

The eval suite tests all 3 layers without a live voice session:

```bash
# Full suite — Layer 1 (tool correctness) + Layer 2 (routing) + Layer 2b (multi-turn)
python eval_suite.py

# Layer 1 only — calls each tool directly against the DB, checks response shape
python eval_suite.py --layer1-only

# Layer 2 only — sends 24 queries to Gemini text API, checks tool routing
python eval_suite.py --layer2-only

# Layer 2b only — 4 multi-turn conversations, 17 turns total
python eval_suite.py --layer2b-only

# Skip multi-turn (faster)
python eval_suite.py --no-multiturn
```

Results are written to `eval_report.json`. Latest run: **63/64 passed (98%)**.

| Layer | Tests | Passed | What it covers |
|-------|-------|--------|----------------|
| Layer 1 | 23 | 23 | All 7 tools return correct, well-shaped responses from DB |
| Layer 2 | 24 | 23 | Clara routes 24 natural-language queries to the right tool |
| Layer 2b | 17 | 17 | 4 multi-turn conversations with context-aware routing |

See [EVAL.md](EVAL.md) for full methodology, test case descriptions, and known limitations.



#### Scenario 1 — Quick smoke test (2 min)

Simple single-turn queries to verify each tool is working:

| Say this | Expected result |
|----------|----------------|
| "Hi Clara, what can you help me with?" | Greeting, no tool call |
| "What engineering courses do you offer?" | 3–4 course cards slide in |
| "Tell me more about the Master of Data Science" | Full detail card — fees, duration, career outcomes |
| "Are there any scholarships for international students?" | Scholarship card (Kingsford International Student Scholarship) |
| "What ATAR do I need for medicine?" | Info card from knowledge base |
| "What events are on this month?" | Upcoming events list |
| "I'd like to book a tour for March 22nd, my name is Alex" | Booking confirmation with `GT-XXXXX` reference |

---

#### Scenario 2 — Demo video scenario: International student (5 min)

This is the scenario shown in the [demo video](https://waypoint.vozara.ai/).

1. **"Hi Clara, I have a friend from China who wants to explore courses at Kingsford"**
   → Clara surfaces international entry requirements and asks about field of interest

2. **Share [`testing/Chinese transcript_v2.png`](testing/Chinese%20transcript_v2.png)** (Chinese high school transcript — Wang Xiaoming, strong in Maths 99, Chemistry 98, Physics 98)
   → Clara reads the transcript, identifies STEM strengths, recommends Master of Data Science and Bachelor of Computer Science

3. **"Can you give me more information on the Master of Data Science?"**
   → Full detail card: 2-year program, fees, entry requirements, career outcomes

4. **"I'd like to explore scholarships for international students"**
   → Kingsford International Student Scholarship card with value, eligibility, and application link

5. **"What are the next steps to apply?"**
   → Info cards with admissions checklist and visa requirements

6. **Share a Google Maps screenshot of the Kingsford campus**
   → Clara identifies the International Centre and describes nearby resources

7. **"Are there any events coming up?"**
   → Open Day and webinar cards

8. **"I'd love to book a campus tour on the 22nd of March"**
   → Tour booked, confirmation reference returned (e.g. `GT0000005`)

---

#### Scenario 3 — Personalised recommendation via transcript (5 min)

Uses the English-language test transcript from the `testing/` folder.

1. **"I'm not sure what to study — can you help me figure out the right path?"**

2. **Share [`testing/High school transcript.png`](testing/High%20school%20transcript.png)** (Alex J. Vance — strong in AP Physics, AP Chem, Pre-Calculus, Computer Applications; GPA 3.82)
   → Clara reads the transcript and recommends Engineering or Data Science pathways

3. **"Which of those would have better career outcomes?"**
   → Clara calls `search_knowledge` and surfaces graduate salary / career data

4. **"Are there merit scholarships I could apply for with a 3.8 GPA?"**
   → Merit scholarship cards

5. **"I'd love to visit — can I book a tour for April 15th, party of 2?"**
   → Booking confirmed with reference number

---

#### Scenario 4 — Academic award + arts portfolio (3 min)

Tests vision with non-transcript documents.

1. **Share [`testing/Academic award.png`](testing/Academic%20award.png)** (Dux of Innovation Academy, 4.0 GPA, Jonathan S. Reid)
   → Clara acknowledges the award and asks what field Jonathan wants to pursue

2. **"He's interested in creative fields"**

3. **Share [`testing/Creative arts protfolio.png`](testing/Creative%20arts%20protfolio.png)** (Clara Vance — oil painting, digital illustration, sequential art)
   → Clara recommends Bachelor of Creative Arts or Design programs

4. **"What scholarships exist for arts students?"**
   → Faculty scholarship cards for Creative Arts

---

#### Scenario 5 — Multi-turn context retention (3 min)

Tests that Clara remembers earlier context without re-stating it.

1. **"What cybersecurity degrees do you have?"** → search results
2. **"Tell me more about the cybersecurity one."** ← no course name repeated → Clara uses context
3. **"What scholarships are there for engineering students?"** → scholarship cards
4. **"Are there any info sessions for that faculty?"** → events cards

---

## Cloud Deployment

The service is deployed on Google Cloud Run backed by Cloud SQL.

### Infrastructure

| Resource | Details |
|----------|---------|
| Cloud Run | 1 service · `us-central1` · `min-instances=1` · `memory=1Gi` |
| Cloud SQL | PostgreSQL 16 + pgvector · `us-central1` |
| Artifact Registry | Docker image stored in `us-central1` |
| Secret Manager | DATABASE_URL injected at runtime |

Specific resource names (service, instance, secret) are driven by Cloud Build substitutions — see [cloudbuild.yaml](cloudbuild.yaml) and [Makefile](Makefile) for the defaults.

### Deploy

```bash
# Requires gcloud CLI authenticated to the target GCP project.
# Override defaults via env vars — see top of Makefile.
PROJECT=your-gcp-project make deploy
```

### Reseed production database

```bash
# Terminal 1: start Auth Proxy
make proxy

# Terminal 2: reseed
make seed-prod
```

### View logs

```bash
make logs
```

---

## Evaluation Results

```
Layer 1 — Tool Correctness:    23/23  (100%)
Layer 2 — Tool Routing:        23/24   (96%)  [R05: online study mode preference miss]
Layer 2b — Multi-turn:         17/17  (100%)
─────────────────────────────────────────────
Total:                         63/64   (98%)
```

Run `python eval_suite.py` to reproduce. Requires `.env` with `DATABASE_URL` and `GOOGLE_API_KEY`.

---

## License & Attribution

Apache License 2.0 — see [LICENSE](LICENSE).

If you build something using the patterns here (the ADK monkey-patches, the display-data side-channel, the turn-isolation rule, the eval structure), a link back is appreciated but not required.

---

## About

Built by Eliot Chen — [LinkedIn](https://www.linkedin.com/in/eliotchen).

Eliot builds AI systems in regulated industry contexts — as a Solution Architect and through [VoZara](https://vozara.ai), a voice agent platform. Waypoint is an exploration of Google ADK patterns he wanted to understand before bringing agent-to-agent communication back to the production platform.