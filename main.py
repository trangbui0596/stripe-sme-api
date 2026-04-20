"""
Stripe SME API — FastAPI entrypoint.

Routes:
  POST /ask    Ask a question about the Stripe Services Agreement
  GET  /health Health check

Run:
    uvicorn main:app --reload
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
load_dotenv()

import retrieval
import classifier
import responder


@asynccontextmanager
async def lifespan(app: FastAPI):
    retrieval.load_store()
    yield


app = FastAPI(title="Stripe SME API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AskRequest(BaseModel):
    question: str
    context: dict = {}
    conversation: list = []
    # When True, skip classification and go straight to answer generation.
    # Use this after the user has already answered a clarifying question —
    # the classifier would otherwise re-route to clarification again.
    force_answer: bool = False


class AskResponse(BaseModel):
    type: str
    content: str | None = None
    clarifying_question: str | None = None
    why_it_matters: str | None = None


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="question must not be empty")

    chunks = retrieval.search(req.question)

    # Skip classification when caller signals context has already been provided
    if req.force_answer:
        return responder.answer(req.question, chunks, req.conversation or None)

    route = classifier.classify(req.question, chunks)

    if route["type"] == "answer":
        return responder.answer(req.question, chunks, req.conversation or None)
    elif route["type"] == "clarification":
        return responder.clarification(req.question, chunks)
    else:
        return responder.escalation(req.question, chunks)


@app.get("/health")
def health():
    return {"status": "ok"}
