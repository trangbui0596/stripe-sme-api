# Knowledge Base — Data Format Guide

The three files in this folder are the only things you need to replace to make the API work for your company. The current files contain **NexaPay**, a synthetic fintech company created to demonstrate the specialist model. Replace them with your own data, then run `python ingest.py --web` to rebuild the index.

No code changes required. The API, classifier, and responder are fully data-agnostic.

---

## File 1: `company_profile.txt`

**Purpose:** Tells the model who your company is, how you use Stripe, and what your technical setup looks like. This context shapes every response — the model uses it to avoid giving generic advice that doesn't apply to your setup.

**What to include:**
- Company name, what you do, which markets you operate in
- Which Stripe product you use (Payments, Connect, Billing, Terminal — and which Connect model if applicable: Custom, Express, or Standard)
- Your currency and jurisdiction
- Key third-party integrations (payment methods, BNPL providers, identity verification)
- Approximate transaction volumes and merchant counts if relevant
- Any ongoing initiatives or evaluations that affect compliance decisions

**Format:** Plain text. No special structure required. Write it like an internal onboarding doc — clear, factual, specific.

**Template:**

```
[YOUR COMPANY NAME] — COMPANY PROFILE

Overview:
[Company name] is a [describe business] operating in [markets/countries].
Founded [year]. [Brief description of what the product does.]

Stripe Setup:
- Product: Stripe [Payments / Connect / Billing / Terminal]
- Connect model: [Custom / Express / Standard / N/A]
- Settlement currencies: [e.g. SGD, USD, GBP]
- Merchant count: approximately [X] connected accounts
- Transaction volume: approximately [X] per month

Markets:
[List countries/regions you operate in and any jurisdiction-specific notes]

Key Integrations:
[List payment methods, BNPL providers, identity verification, fraud tools, etc.]

Current Priorities:
[Any ongoing evaluations, upcoming launches, or compliance initiatives]
```

**Ideal length:** 300–600 words.

---

## File 2: `compliance_procedures.txt`

**Purpose:** Documents your internal compliance and operational processes. The model uses this to give procedure-specific advice — not just what Stripe's agreement says, but what *your team* is supposed to do in response.

**What to include:**
- Merchant onboarding steps (KYC/KYB requirements, verification tools, approval gates)
- Ongoing monitoring cadence (how often you review accounts, what triggers a review)
- Incident response procedure (who gets notified, in what order, within what timeframe)
- Known compliance gaps or outstanding remediation items
- Key personnel and their roles (CCO, CRO, legal counsel, Stripe account manager)

**Format:** Plain text. Use clear section headers and numbered steps where applicable.

**Template:**

```
[YOUR COMPANY NAME] COMPLIANCE PROCEDURES
Last updated: [Month Year]

MERCHANT ONBOARDING FLOW
Step 1 — [First verification step]
  - [Requirement]
  - [Requirement]

Step 2 — [Second verification step]
  - [Requirement]

[Continue for all steps]

ONGOING MONITORING
- [Frequency and type of review]
- [What triggers an alert or escalation]

INCIDENT RESPONSE — [VIOLATION TYPE]
If [trigger condition]:
  Step 1: [First action — who, what, within how long]
  Step 2: [Second action]
  [Continue]

KEY PERSONNEL
- Chief Compliance Officer: [Name], [email]
- [Other relevant roles]

KNOWN GAPS (as of [date])
- [Gap 1 and planned remediation]
- [Gap 2 and planned remediation]
```

**Ideal length:** 400–800 words.

---

## File 3: `past_qa.txt`

**Purpose:** The most valuable file. Past resolved questions teach the model what your team has already figured out — so it can cite your own precedents instead of giving generic answers. A question your CCO answered last year is more directly applicable than the general Stripe agreement.

**What to include:**
- Real questions your team has asked internally (Slack, email, support tickets)
- The resolution that was reached — including any confirmation from Stripe, legal counsel, or regulators
- The outcome and any policy or process changes that resulted
- Edge cases, grey areas, and decisions that required escalation

**Format:** Use the structure below for each entry. Consistent structure helps the retriever surface the right precedent.

**Template:**

```
[YOUR COMPANY NAME] — PAST STRIPE QUESTIONS AND RESOLUTIONS
Source: [Where these came from — e.g. internal Slack archive, compliance log]

---

TOPIC: [Short descriptive title — e.g. "Dispute Deduction — Platform vs Connected Account Balance"]
Date: [Month Year] | Asked by: [Role] | Channel: [Where it was asked]

Question: [The exact question that was asked]
Resolution: [The answer that was reached, including any sources cited, Stripe confirmation, or legal review]
Outcome: [What changed as a result — policy update, process change, engineering fix, etc.]

---

TOPIC: [Next topic]
Date: [Month Year] | Asked by: [Role] | Channel: [Where it was asked]

Question: [Question]
Resolution: [Resolution]
Outcome: [Outcome]

---

[Repeat for each past Q&A]
```

**Tips for maximum retrieval quality:**
- Use descriptive TOPIC headers — the retriever matches on these. "Dispute Deduction — Platform vs Connected Account Balance" is far more retrievable than "Q14"
- Include the channel context (e.g. `#stripe-questions`, `#compliance-incidents`) — it helps the model understand the seriousness and context of each question
- Include resolution details even if the answer was "we don't know yet" — that's useful signal too
- Aim for 10–30 past Q&As to start. Quality matters more than volume.

**Ideal length:** As long as your archive goes. 1,000–5,000 words is a good starting range.

---

## Rebuilding the index after changes

Any time you edit these files, run:

```bash
python ingest.py --web
```

Then restart the server:

```bash
uvicorn main:app --reload
```

The API immediately reflects your updated knowledge base. No redeployment of the API logic required.

---

## What NOT to put in these files

- Raw database exports or structured JSON — the retriever works on natural language prose, not tabular data
- Files longer than ~10,000 words each — chunk quality degrades at very long lengths; split into multiple topic-specific files instead (see `ingest.py` → `LOCAL_DATA_LABELS` to add more files)
- Sensitive credentials, PII, or anything you wouldn't put in a shared internal doc — this data is indexed and retrievable by anyone with API access

## Adding more data files

To add a fourth file (e.g. `data/regulatory_guidance.txt`):

1. Create the file in `data/`
2. Add it to `LOCAL_DATA_LABELS` in `ingest.py`:
   ```python
   LOCAL_DATA_LABELS = {
       "company_profile.txt":        "Company Profile",
       "compliance_procedures.txt":  "Compliance Procedures",
       "past_qa.txt":                "Past Q&A",
       "regulatory_guidance.txt":    "Regulatory Guidance",   # ← add this
   }
   ```
3. Run `python ingest.py --web` to rebuild
