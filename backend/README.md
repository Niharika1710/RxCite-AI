# MedIntel AI

A pharmaceutical evidence assistant that answers drug questions grounded in FDA label evidence, with a confidence score on every answer and safety refusals when the evidence is thin. It is framed strictly as an **evidence assistant** — never a diagnosis or prescription tool.

Ask a question by text or by uploading a photo of a drug package. The system routes the query, gathers clinical context when the risk warrants it, retrieves supporting evidence from FDA drug labels, validates and cites that evidence, scores its own confidence, and either answers with citations or refuses and points the user to a professional.

---

## Why this project exists

Most "chat with a PDF" RAG demos will confidently answer anything. A medical assistant that does the same is dangerous. MedIntel AI is built around the opposite principle: **it should know when it doesn't know, and say so.** The confidence score, the citation validation, and the safety gate are the point — the answer is only trustworthy because the system is willing to refuse.

---

## What it does

- **Grounded answers** — every answer is generated only from retrieved FDA label passages, with clickable citations linking back to the official DailyMed label.
- **Confidence scoring** — a deterministic, rule-based score (High / Medium / Low) derived from retrieval quality, citation agreement, and coverage.
- **Safety refusals** — out-of-scope questions, thin evidence, or high-risk scenarios trigger a refusal that redirects the user to a healthcare professional.
- **Adaptive-depth triage** — for higher-risk questions, the system asks clinical follow-ups (age, pregnancy status, conditions, medications) scaled to the query's risk before answering. Simple factual lookups skip this entirely.
- **Image-to-evidence** — upload a photo of a drug package; the system reads the printed generic drug name (OCR-style) and runs it through the same pipeline.
- **Light / dark theme** — a warm-minimal light theme and a cool/clinical dark theme.

---

## Architecture

The backend is a multi-agent pipeline orchestrated with **LangGraph**. Each agent has a narrow responsibility and communicates through typed Pydantic contracts, so data flowing through the graph is validated and self-documenting.

```
          ┌─────────┐
Query ───▶│ Router  │  in scope? which drug?
          └────┬────┘
               │ in scope
          ┌────▼────┐
          │ Triage  │  gather clinical context (adaptive depth)
          └────┬────┘  ← pauses via LangGraph interrupt() for follow-ups
               │
          ┌────▼──────┐
          │ Retrieval │  section-diverse search over the vector store
          └────┬──────┘
          ┌────▼──────┐
          │ Citation  │  which chunks actually support the query
          └────┬──────┘
          ┌────▼───────┐
          │ Confidence │  deterministic High/Medium/Low score
          └────┬───────┘
          ┌────▼─────┐
          │  Safety  │  refuse, or proceed
          └────┬─────┘
          ┌────▼──────┐
          │ Response  │  grounded answer + citations, or refusal
          └───────────┘
```

**Vision path:** an image upload is handled by a vision agent that extracts the generic drug name from the package, then feeds that name into the same pipeline above. If no question is supplied, the system asks what the user wants to know; if no drug can be read, it refuses cleanly.

### Key design decisions

- **Narrow agents, typed contracts.** Each agent reads and writes explicit Pydantic models rather than loose dicts, which makes the pipeline auditable and each stage independently testable.
- **Deterministic confidence.** The confidence score is rule-based, not an LLM judgment call, so it is reproducible and explainable — it combines average retrieval distance, citation agreement, and coverage.
- **Section-diverse retrieval.** Large FDA labels have hundreds of chunks; a naive top-k search lets bulky sections (clinical trials, adverse reactions) crowd out short but critical ones (indications, contraindications). Retrieval pulls a wide candidate pool and guarantees each label section is represented before filling remaining slots by relevance.
- **Answerability awareness.** The response agent self-reports whether the retrieved evidence actually answers the question; when strong deterministic signals disagree with a flappy model verdict, the reproducible signals win.
- **Human-in-the-loop triage.** The triage agent uses LangGraph's `interrupt()` with SQLite checkpointing to pause mid-conversation for clinical follow-ups and resume after the user replies, surviving a server restart.

---

## Tech stack

**Backend**
- FastAPI (HTTP API)
- LangGraph (multi-agent orchestration + human-in-the-loop interrupts)
- ChromaDB (vector store, cosine distance)
- sentence-transformers `all-MiniLM-L6-v2` (local embeddings)
- Google Gemini API (routing, citation, and response generation)

**Frontend**
- Next.js (single-page chat interface)
- Multi-turn conversation with confidence-ring visualization and clickable DailyMed citations
- Light / dark theming

**Data**
- Drug labels ingested from the [openFDA](https://open.fda.gov/) drug label API, normalized into section-labeled chunks.

---

## Getting started

### Prerequisites
- Python 3.10+
- Node.js (for the frontend)
- A Google Gemini API key

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

Create a `.env` file in `backend/` (never commit this):

```
GOOGLE_API_KEY=your_key_here
CHROMA_PERSIST_DIR=./chroma_db
```

Ingest drug data and build the vector store (one-time):

```bash
python -m app.ingestion.run_embedding
```

Run the API:

```bash
uvicorn app.main:app --reload
```

The API is served at `http://127.0.0.1:8000` (interactive docs at `/docs`).

### Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## API

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/query` | POST | Start a text query (`{query}`) or resume a paused triage thread (`{thread_id, reply}`). |
| `/api/query-image` | POST | Multipart upload: a package photo plus an optional typed question. |
| `/health` | GET | Health check. |

A turn either returns a final answer, or pauses and returns a follow-up question plus the `thread_id` needed to resume.

---

## Project status

**Working:** text and image query pipelines, adaptive triage, deterministic confidence scoring, citation-linked answers, safety refusals, light/dark theming.

**Planned / not yet implemented:**
- Additional knowledge domains (Ayurveda, home remedies) — shown as "coming soon" in the domain picker; these require carefully scoped, appropriately-caveated evidence sources and are a design task, not a drop-in.
- Category-based ingestion by therapeutic class (prototype exists; needs single-ingredient deduplication before use).

---

## Disclaimer

MedIntel AI is an informational tool for exploring FDA label evidence. It is **not** a substitute for professional medical advice, diagnosis, or treatment. Always consult a qualified healthcare provider for medical decisions.