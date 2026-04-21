# Stripe SME API

A specialist AI API that answers Stripe compliance questions grounded in your company's institutional knowledge — internal past Q&As, compliance procedures, and live Stripe Singapore legal docs. Classifies questions into three response types: direct answer, clarification, and escalation with auto-created compliance tickets.

**Live demo (NexaPay synthetic data):** https://stripe-sme-api.netlify.app/  
**Interactive API docs:** https://stripe-sme-api.onrender.com/docs

---

## How it works

Every query goes through three steps:

```
Question
   │
   ▼
[1] Retrieve — TF-IDF search across Stripe SG legal docs + your internal knowledge base
               Top 5 most relevant chunks surfaced (k=5 chosen to compensate for
               TF-IDF's keyword-only matching; upgrade to embeddings → k=3)
   │
   ▼
[2] Classify — Claude reads the question + retrieved chunks and routes to one of three camps:
               Camp 1 (answer)        — context is sufficient, answer exists in the docs
               Camp 2 (clarification) — answer depends on a company-specific variable not yet provided
               Camp 3 (escalation)    — genuine grey area requiring human judgment
   │
   ▼
[3] Respond  — Camp 1: grounded answer citing source doc + internal precedent
               Camp 2: single targeted clarifying question + why it matters
               Camp 3: honest assessment + concrete escalation path + auto-creates compliance tickets
```

---

## Quick start

```bash
# 1. Clone and install
git clone https://github.com/trangbui0596/stripe-sme-api.git
cd stripe-sme-api
pip install -r requirements.txt

# 2. Set your Anthropic API key
cp .env.example .env
# Edit .env and paste your key: ANTHROPIC_API_KEY=sk-ant-...

# 3. Add your company data (see below)
# Edit the three files in data/

# 4. Build the knowledge index
python ingest.py --web

# 5. Run the API
uvicorn main:app --reload
```

The API is now live at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

---

## Substituting the synthetic data with your own

The `data/` folder contains three plain-text files that represent your company's institutional knowledge. The current files use **NexaPay** — a synthetic fintech company created to demonstrate the specialist model. Replace them with your own company's data and rebuild the index.

### Step 1 — Edit the three files in `data/`

| File | What it contains |
|---|---|
| `data/company_profile.txt` | Who your company is, your tech stack, markets, key relationships |
| `data/compliance_procedures.txt` | Your internal procedures, onboarding flows, incident response steps |
| `data/past_qa.txt` | Past questions your team has asked and resolved — the most valuable source |

See [`data/README.md`](data/README.md) for the exact format each file expects, with templates.

### Step 2 — Rebuild the index

```bash
python ingest.py --web
```

This re-fetches all 11 Stripe Singapore legal documents and re-indexes everything including your updated data files. Takes 1–2 minutes. Outputs `store.pkl`.

### Step 3 — Restart the server

```bash
uvicorn main:app --reload
```

The API now answers questions grounded in your company's knowledge. No code changes required.

---

## What the Stripe legal docs cover

The following documents are automatically fetched from `stripe.com/en-sg/legal` on every `ingest.py --web` run:

| Document | What it governs |
|---|---|
| Services Agreement | Core platform terms, fees, liability, termination |
| Connected Account Agreement | Merchant-facing obligations under Connect |
| Restricted Businesses | Categories prohibited or requiring approval |
| Consumer Terms | End-user payment terms |
| Partner Ecosystem | Integration partner obligations |
| App Developer Agreement | App marketplace terms |
| Privacy Policy | Data handling and retention |
| IP Policy | Intellectual property |
| Climate Contribution Terms | Stripe Climate |
| Atlas Terms | Company formation |
| Licenses | Software licensing |

---

## API reference

### `POST /ask`

```json
{
  "question": "We refunded a transaction — do we still owe Stripe their fee?",
  "context": {},
  "conversation": [],
  "force_answer": false
}
```

| Field | Type | Description |
|---|---|---|
| `question` | string | The compliance question to ask |
| `conversation` | array | Prior turns as `[{"role": "user"/"assistant", "content": "..."}]`. Pass `[]` for a new thread |
| `force_answer` | bool | `true` after the user answers a clarifying question — skips re-classification |

**Response shapes:**

```json
// Camp 1 — Direct answer
{ "type": "answer", "content": "Per SSA Section 7.1(a), Stripe retains..." }

// Camp 2 — Needs clarification
{ "type": "clarification", "clarifying_question": "Are you on blended or IC+ pricing?", "why_it_matters": "The fee structure differs entirely..." }

// Camp 3 — Escalation required
{ "type": "escalation", "content": "This requires review by your CCO. Here's what the SSA says..." }
```

### `POST /feedback`

Logs a thumbs-up/down vote to `data/feedback.jsonl` — the training data pipeline.

```json
{
  "question": "...",
  "response": "...",
  "rating": "up" | "down" | "flag",
  "explanation": "Answer too generic | free text"
}
```

### `GET /health`

```json
{ "status": "ok" }
```

---

## Project structure

```
stripe-sme-api/
├── main.py           # FastAPI entrypoint — routes and request models
├── classifier.py     # Camp 1/2/3 routing logic — Claude classifier
├── responder.py      # Response generators for each camp
├── retrieval.py      # TF-IDF search over the indexed knowledge base
├── ingest.py         # Fetches Stripe docs + indexes data/ files → store.pkl
├── store.pkl         # Built index (committed for fast startup — rebuild with ingest.py)
├── demo.html         # Interactive side-by-side demo (Generic LLM vs SME API)
├── requirements.txt
├── render.yaml       # Render deployment config
├── .env.example      # API key template
└── data/
    ├── README.md               # Format guide for substituting your own data
    ├── company_profile.txt     # [REPLACE] Your company's profile and setup
    ├── compliance_procedures.txt # [REPLACE] Your internal procedures
    ├── past_qa.txt             # [REPLACE] Your past resolved Q&As
    └── feedback.jsonl          # Auto-created — RLHF training data from user votes
```

---

## Deployment

**Backend (Render):**
1. Connect your GitHub repo to Render
2. New → Web Service → select this repo
3. Add environment variable: `ANTHROPIC_API_KEY`
4. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

**Frontend (Netlify):**
1. Update `API_URL` in `demo.html` to your Render URL + `/ask`
2. Drag and drop `demo.html` to [netlify.com](https://netlify.com)

---

## Upgrading retrieval (optional)

The default retrieval uses TF-IDF (`scikit-learn`) — zero native dependencies, works on any machine. For higher precision, upgrade to vector embeddings:

1. Replace `TfidfVectorizer` in `ingest.py` with `text-embedding-3-small` (OpenAI) or `all-MiniLM-L6-v2` (sentence-transformers)
2. Drop k from 5 to 3 in `retrieval.py` — semantic search is precise enough that fewer chunks are needed
3. Expected Precision@5 improvement: ~40–50% → ~80–90%
