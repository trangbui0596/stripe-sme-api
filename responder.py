"""
Generates the final response for each of the three query types.
Each type has its own system prompt and output contract.
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

ANSWER_SYSTEM = """You are a Stripe Services Agreement (SSA) subject matter expert answering questions for a fintech engineering team.

Rules:
- Answer directly and precisely based only on the provided SSA excerpts
- Cite the specific section your answer comes from (e.g. "Per SSA Section 7.2...")
- If the excerpts only partially cover the question, answer what you can and flag the gap
- No speculation beyond what the SSA states
- Keep it concise — engineers want the answer, not a lecture"""

CLARIFICATION_SYSTEM = """You are a Stripe Services Agreement (SSA) subject matter expert. The question cannot be answered accurately without more context.

Rules:
- Identify the single most important missing piece of context
- Ask ONE specific, targeted follow-up question — not a vague "tell me more"
- Explain in one sentence exactly why that context changes the answer
- Do not ask multiple questions

Respond with JSON only:
{
  "clarifying_question": "<the specific question to ask>",
  "why_it_matters": "<one sentence: how the answer differs depending on their response>"
}"""

ESCALATION_SYSTEM = """You are a Stripe Services Agreement (SSA) subject matter expert. This question goes beyond what the SSA clearly resolves.

Rules:
- Briefly state what the SSA does and doesn't say about this topic (1-2 sentences)
- Provide 2-3 concrete, actionable strategies (e.g. contact Stripe support, review account-specific addendum, consult legal counsel)
- Be honest — do not fabricate certainty where the SSA is silent
- Keep the tone helpful and practical"""


def _format_chunks(chunks: list[dict]) -> str:
    return "\n\n---\n\n".join(f"[{c['source']}]\n{c['text']}" for c in chunks)


def answer(question: str, context_chunks: list[dict], conversation: list = None) -> dict:
    context = _format_chunks(context_chunks)
    messages = list(conversation or [])
    messages.append(
        {
            "role": "user",
            "content": f"Question: {question}\n\nStripe SSA Excerpts:\n{context}",
        }
    )
    response = _get_client().messages.create(
        model="claude-sonnet-4-5",
        max_tokens=600,
        system=ANSWER_SYSTEM,
        messages=messages,
    )
    return {"type": "answer", "content": response.content[0].text}


def clarification(question: str, context_chunks: list[dict]) -> dict:
    context = _format_chunks(context_chunks)
    response = _get_client().messages.create(
        model="claude-sonnet-4-5",
        max_tokens=300,
        system=CLARIFICATION_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": f"Question: {question}\n\nStripe SSA Excerpts:\n{context}",
            }
        ],
    )
    parsed = _parse_json(response.content[0].text)
    return {
        "type": "clarification",
        "clarifying_question": parsed["clarifying_question"],
        "why_it_matters": parsed["why_it_matters"],
    }


def escalation(question: str, context_chunks: list[dict]) -> dict:
    context = _format_chunks(context_chunks)
    response = _get_client().messages.create(
        model="claude-sonnet-4-5",
        max_tokens=500,
        system=ESCALATION_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": f"Question: {question}\n\nStripe SSA Excerpts:\n{context}",
            }
        ],
    )
    return {"type": "escalation", "content": response.content[0].text}
