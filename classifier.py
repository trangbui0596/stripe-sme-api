"""
Routes an incoming question to one of three camps:

  Camp 1 — answer:        Context is sufficient. A clear, grounded answer
                          exists in the retrieved Stripe SG legal docs or
                          NexaPay's internal knowledge base.

  Camp 2 — clarification: The answer materially depends on a company-specific
                          variable the user hasn't provided (e.g. which Connect
                          model, which jurisdiction, which pricing plan, whether
                          KYC docs exist). Without it, any answer would be
                          incomplete or potentially wrong.

  Camp 3 — escalation:    The question involves genuine legal/compliance grey
                          area, conflicting rules, financial risk, or a topic
                          that requires human judgment beyond what any document
                          can resolve. Auto-triggers compliance tickets.

Decision logic (applied in order):
  1. Can this be answered definitively from the retrieved context alone?
     → Camp 1
  2. Would knowing one specific piece of company context unlock a precise answer?
     → Camp 2
  3. Is this a grey area where reasonable interpretations conflict, where
     NexaPay's specific liability is unclear, or where the stakes require
     a human (CCO, legal counsel, Stripe account manager) to weigh in?
     → Camp 3
"""

import json
import re
import os
import anthropic


def _get_client():
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], max_retries=3)


def _parse_json(text: str) -> dict:
    """Extract JSON from response even if Claude wraps it in markdown code blocks."""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))
    return json.loads(text)


SYSTEM_PROMPT = """You are a routing classifier for a specialist compliance Q&A system built for NexaPay — a Singapore-based fintech operating Stripe Custom Connect accounts across Singapore, Malaysia, Indonesia, and Thailand.

Your knowledge base contains two source types:
  1. Stripe Singapore legal documents (Services Agreement, Connect Account Agreement, Restricted Businesses list, etc.)
  2. NexaPay internal knowledge (past resolved Q&As, compliance procedures, incident post-mortems, CCO decisions)

Given a user question and retrieved excerpts from this knowledge base, classify the query into exactly one camp:

CAMP 1 — "answer"
  The retrieved context contains enough information to give a clear, specific, actionable answer.
  The answer does not require guessing about the user's setup.
  Use this when: the Stripe docs directly address the question, OR NexaPay's past Q&As contain a matching precedent.
  Bias toward this camp when the retrieved context is rich and directly relevant.

CAMP 2 — "clarification"
  The answer exists — but it materially depends on a company-specific variable not yet provided.
  Common missing variables: which Stripe Connect model (Custom vs Standard vs Express), which jurisdiction
  (SG vs MY vs ID vs TH), which pricing plan (blended vs IC+), whether KYC documentation exists,
  whether the merchant is a new or existing account, what MCC code is assigned.
  Use this when: knowing one specific detail would unlock a precise, correct answer.
  Do NOT use this as a fallback for vague questions — only when a specific variable genuinely changes the answer.

CAMP 3 — "escalation"
  The question involves genuine legal or compliance grey area that no document cleanly resolves.
  Indicators: conflicting rules across jurisdictions, questions about NexaPay's liability exposure,
  questions about Stripe's discretionary enforcement powers, novel situations not covered by precedent,
  or cases where the financial or legal risk is high enough that a human must decide.
  Use this when: the right answer requires the CCO, Stripe account manager, or legal counsel to weigh in.
  This camp auto-triggers compliance tickets — only use it when escalation is genuinely warranted.

Respond with JSON only — no markdown, no explanation outside the JSON:
{"type": "answer" | "clarification" | "escalation", "reasoning": "<one sentence explaining why this camp was chosen>", "confidence": "high" | "medium" | "low"}

Confidence guide:
  high   — the camp is obvious from the context
  medium — the question sits near a boundary between two camps
  low    — the retrieved context is sparse or the question is ambiguous"""


def _format_chunks(chunks: list[dict]) -> str:
    return "\n\n---\n\n".join(f"[{c['source']}]\n{c['text']}" for c in chunks)


def classify(question: str, context_chunks: list[dict]) -> dict:
    context = _format_chunks(context_chunks)
    response = _get_client().messages.create(
        model="claude-sonnet-4-5",
        max_tokens=250,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Question: {question}\n\n"
                    f"Retrieved context from knowledge base:\n{context}"
                ),
            }
        ],
    )
    return _parse_json(response.content[0].text)
