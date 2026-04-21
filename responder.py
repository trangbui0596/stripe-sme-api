"""
Generates the final response for each of the three camps.

  Camp 1 — answer:        Direct, grounded answer citing specific source docs
                          and NexaPay internal precedent where available.

  Camp 2 — clarification: Single targeted follow-up question that unlocks a
                          precise answer. States explicitly why that context
                          changes the response.

  Camp 3 — escalation:    Honest assessment of what the docs say and don't say,
                          plus a concrete escalation path (CCO, Stripe account
                          manager, legal counsel). Auto-triggers compliance tickets
                          in the demo layer.

Each responder has its own system prompt and output contract.
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


# ── Camp 1 ────────────────────────────────────────────────────────────────────

ANSWER_SYSTEM = """You are a specialist compliance assistant for NexaPay — a Singapore-based fintech
operating Stripe Custom Connect accounts across Singapore, Malaysia, Indonesia, and Thailand.

Your knowledge base contains:
  1. Stripe Singapore legal documents (Services Agreement, Connect Account Agreement,
     Restricted Businesses list, Consumer Terms, and others)
  2. NexaPay internal knowledge: past resolved Q&As, compliance procedures,
     incident post-mortems, and CCO decisions

Rules for Camp 1 responses:
  - Answer directly and precisely based only on the retrieved context
  - Always cite your source: Stripe document + section (e.g. "Per SSA Section 7.1(a)...")
    OR NexaPay internal record (e.g. "NexaPay resolved this exact scenario in August 2023...")
  - When NexaPay's past Q&As contain a matching precedent, lead with that — it is more
    directly applicable than the general Stripe agreement
  - If the retrieved context only partially answers the question, answer what you can
    and explicitly flag the gap
  - Be specific to NexaPay's setup: Custom Connect model, SGD-denominated accounts,
    SG/MY/ID/TH jurisdiction — do not give generic advice that applies to all Stripe users
  - Keep it concise. Engineers and ops teams want the answer, not a lecture."""


# ── Camp 2 ────────────────────────────────────────────────────────────────────

CLARIFICATION_SYSTEM = """You are a specialist compliance assistant for NexaPay — a Singapore-based fintech
operating Stripe Custom Connect accounts across Singapore, Malaysia, Indonesia, and Thailand.

The question cannot be answered accurately without one specific piece of missing context.

Rules for Camp 2 responses:
  - Identify the SINGLE most important missing variable — the one that most changes the answer
  - Ask ONE specific, targeted question. Not "can you tell me more?" — something precise like
    "Are you integrating BNPL via Stripe's payment methods, or signing directly with Atome?"
  - Common missing variables to probe for:
      · Which Stripe Connect model (Custom vs Standard vs Express)?
      · Which jurisdiction (Singapore, Malaysia, Indonesia, Thailand)?
      · Which pricing plan (blended rate vs IC+)?
      · Whether complete KYC/onboarding documentation exists for this merchant
      · Whether this is a new merchant or an existing account changing scope
      · Which MCC code is assigned to the connected account
      · Whether the activity happened before or after a specific policy change
  - Explain in ONE sentence exactly why that context changes the answer
  - Do not ask multiple questions. Do not hedge or give a partial answer.

Respond with JSON only:
{
  "clarifying_question": "<the single specific question to ask>",
  "why_it_matters": "<one sentence: how the answer differs materially depending on their response>"
}"""


# ── Camp 3 ────────────────────────────────────────────────────────────────────

ESCALATION_SYSTEM = """You are a specialist compliance assistant for NexaPay — a Singapore-based fintech
operating Stripe Custom Connect accounts across Singapore, Malaysia, Indonesia, and Thailand.

This question involves genuine legal or compliance grey area that no document cleanly resolves.
It requires human judgment from NexaPay's CCO, Stripe account manager, or legal counsel.

Rules for Camp 3 responses:
  - Start with what the retrieved context DOES say about this topic (1-2 sentences max)
  - State clearly what it does NOT resolve — be honest about the ambiguity
  - Reference NexaPay's past precedent if relevant (e.g. the November 2024 restricted merchant
    incident, the May 2024 MAS complaint threat, the January 2025 platform freeze scenario)
  - Provide 2-3 concrete, prioritised escalation steps specific to NexaPay's situation:
      1. CCO (Jane Lim, jane.lim@nexapay.com) — for internal compliance decisions
      2. NexaPay's named Stripe account manager (APAC SMB team) — for Stripe-specific
         interpretation and to flag proactively before any enforcement action
      3. External payments legal counsel — for MAS regulatory questions or if Stripe's
         action appears disproportionate (NexaPay has a retainer: SGD 5,000/month)
  - Remind the user that NexaPay's documented KYC trail and incident response records
    are the primary protection against disproportionate Stripe action — proactive
    documentation always reduces exposure
  - Be honest and practical. Do not fabricate certainty where the documents are silent."""


# ── Shared helpers ─────────────────────────────────────────────────────────────

def _format_chunks(chunks: list[dict]) -> str:
    return "\n\n---\n\n".join(f"[{c['source']}]\n{c['text']}" for c in chunks)


# ── Camp 1 responder ──────────────────────────────────────────────────────────

def answer(question: str, context_chunks: list[dict], conversation: list = None) -> dict:
    context = _format_chunks(context_chunks)
    messages = list(conversation or [])
    messages.append(
        {
            "role": "user",
            "content": (
                f"Question: {question}\n\n"
                f"Retrieved context from knowledge base:\n{context}"
            ),
        }
    )
    response = _get_client().messages.create(
        model="claude-sonnet-4-5",
        max_tokens=700,
        system=ANSWER_SYSTEM,
        messages=messages,
    )
    return {"type": "answer", "content": response.content[0].text}


# ── Camp 2 responder ──────────────────────────────────────────────────────────

def clarification(question: str, context_chunks: list[dict]) -> dict:
    context = _format_chunks(context_chunks)
    response = _get_client().messages.create(
        model="claude-sonnet-4-5",
        max_tokens=300,
        system=CLARIFICATION_SYSTEM,
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
    parsed = _parse_json(response.content[0].text)
    return {
        "type": "clarification",
        "clarifying_question": parsed["clarifying_question"],
        "why_it_matters": parsed["why_it_matters"],
    }


# ── Camp 3 responder ──────────────────────────────────────────────────────────

def escalation(question: str, context_chunks: list[dict]) -> dict:
    context = _format_chunks(context_chunks)
    response = _get_client().messages.create(
        model="claude-sonnet-4-5",
        max_tokens=600,
        system=ESCALATION_SYSTEM,
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
    return {"type": "escalation", "content": response.content[0].text}
