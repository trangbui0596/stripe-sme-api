"""
Routes an incoming question to one of three response types:
  - answer:        clear answer exists in the SSA
  - clarification: answer depends on missing user context
  - escalation:    genuine ambiguity or topic not covered by SSA
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

SYSTEM_PROMPT = """You are a routing classifier for a Stripe Services Agreement (SSA) Q&A system.

Given a user question and relevant excerpts from the Stripe SSA, classify the query into exactly one type:

"answer"
  The excerpts contain a clear, direct answer. No additional context from the user is needed.

"clarification"
  The answer materially depends on context the user hasn't provided — such as account type,
  payment method, Connect vs direct charges, jurisdiction, or business model. Without this
  context, any answer would be incomplete or potentially wrong.

"escalation"
  The question involves genuine ambiguity, conflicting rules, topics not covered in the SSA,
  or requires legal judgment or Stripe support beyond what the agreement states.

Respond with JSON only — no markdown, no explanation outside the JSON:
{"type": "answer" | "clarification" | "escalation", "reasoning": "<one sentence>"}"""


def _format_chunks(chunks: list[dict]) -> str:
    return "\n\n---\n\n".join(f"[{c['source']}]\n{c['text']}" for c in chunks)


def classify(question: str, context_chunks: list[dict]) -> dict:
    context = _format_chunks(context_chunks)
    response = _get_client().messages.create(
        model="claude-sonnet-4-5",
        max_tokens=200,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": f"Question: {question}\n\nStripe SSA Excerpts:\n{context}",
            }
        ],
    )
    return _parse_json(response.content[0].text)
