"""
Chunk 4 — FastAPI Application
Endpoints:
    GET  /health  → {"status": "ok"}
    POST /chat    → full RAG pipeline: retrieve → build prompt → call LLM → respond

Startup:
    Loads the prepared catalog and builds the FAISS index once.
    All subsequent /chat requests reuse the in-memory index.
"""

import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import settings
from retriever import build_index, retrieve
from llm import call_llm
from prompt import build_system_prompt


# ---------------------------------------------------------------------------
# Pydantic models — exact schema from the assignment spec (non-negotiable)
# ---------------------------------------------------------------------------

class Message(BaseModel):
    """A single turn in the conversation history."""
    role: str       # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """
    The POST /chat request body.
    Contains the full conversation history — the API is stateless,
    so every request must include all previous messages.
    """
    messages: list[Message]


class Recommendation(BaseModel):
    """A single assessment recommendation drawn from the SHL catalog."""
    name: str           # assessment name, e.g. "Java 8 (New)"
    url: str            # catalog URL — must match catalog exactly
    test_type: str      # comma-separated codes, e.g. "K" or "P,C"


class ChatResponse(BaseModel):
    """
    The POST /chat response body.
    - reply:               agent's natural-language message
    - recommendations:     [] when clarifying/refusing; 1-10 items otherwise
    - end_of_conversation: true only when user confirms final shortlist
    """
    reply: str
    recommendations: list[Recommendation]
    end_of_conversation: bool


# ---------------------------------------------------------------------------
# Shared state — loaded once at startup, reused across all requests
# ---------------------------------------------------------------------------

_catalog: list[dict] = []
_index = None            # FAISS index
_embed_model = None      # SentenceTransformer model

# Items the LLM frequently references as "defaults" (Action B rules).
# Force-injected into every retrieval so the LLM always has correct URLs.
_STAPLE_NAMES = {
    "Occupational Personality Questionnaire OPQ32r",
    "SHL Verify Interactive G+",
    "OPQ Leadership Report",
    "Dependability and Safety Instrument (DSI)",
    "Contact Center Call Simulation (New)",
    "Entry Level Customer Serv-Retail & Contact Center",
}


# ---------------------------------------------------------------------------
# Lifespan — startup / shutdown logic
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs once when the server starts:
      1. Load the prepared catalog JSON
      2. Build the FAISS index (embeds all catalog items)
    Both are stored in module-level variables for reuse.
    """
    global _catalog, _index, _embed_model

    # 1. Load catalog
    catalog_path = settings.resolve_path(settings.prepared_catalog_path)
    print(f"[startup] Loading catalog from: {catalog_path}")
    with open(catalog_path, "r", encoding="utf-8") as f:
        _catalog = json.load(f)
    print(f"[startup] Loaded {len(_catalog)} catalog items")

    # 2. Build FAISS index
    _index, _embed_model = build_index(_catalog)
    print("[startup] FAISS index ready")

    yield   # ← server is running and accepting requests

    # Shutdown (nothing to clean up for now)
    print("[shutdown] Server stopping")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SHL Assessment Recommender",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow all origins for the evaluator and Postman
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)



def _extract_latest_query(messages: list[Message]) -> str:
    """
    Extracts the most recent user message to use as the retrieval query.
    Falls back to concatenating all user messages if there's only one.
    """
    for msg in reversed(messages):
        if msg.role == "user":
            return msg.content
    return ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    """Health check — evaluator calls this first (2-minute grace period)."""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Main conversation endpoint.
    Pipeline: extract query → FAISS retrieve → build prompt → call LLM → respond
    """

    # --- Guard: empty messages array ---
    if not request.messages:
        return ChatResponse(
            reply="Hi! I help you find SHL assessments. What role are you hiring for?",
            recommendations=[],
            end_of_conversation=False,
        )

    # --- Guard: no user messages in history ---
    query = _extract_latest_query(request.messages)
    if not query.strip():
        return ChatResponse(
            reply="I didn't catch that. Could you describe the role you're hiring for?",
            recommendations=[],
            end_of_conversation=False,
        )

    try:
        # 1. Retrieve top-K relevant catalog items via FAISS
        retrieved = retrieve(query, _index, _embed_model, _catalog)

        # 2. Force-inject staple items the LLM frequently needs
        #    These are "default" items referenced in the prompt rules.
        #    Without them in the context, the LLM hallucinates URLs.
        retrieved_urls = {item["link"] for item in retrieved}
        for item in _catalog:
            if item["link"] not in retrieved_urls and item["name"] in _STAPLE_NAMES:
                retrieved.append(item)

        # 3. Build the system prompt with retrieved catalog items
        system_prompt = build_system_prompt(retrieved)

        # 3. Convert Pydantic Message objects to plain dicts for the LLM
        #    Keep only the last 14 messages (7 turns) to stay within context window
        messages_dicts = [{"role": m.role, "content": m.content} for m in request.messages]
        if len(messages_dicts) > 14:
            messages_dicts = messages_dicts[-14:]

        # 4. Call the LLM
        result = call_llm(messages_dicts, system_prompt)

        # 5. Return the response (already validated by llm.py)
        return ChatResponse(
            reply=result["reply"],
            recommendations=[
                Recommendation(**rec) for rec in result["recommendations"]
            ],
            end_of_conversation=result["end_of_conversation"],
        )

    except Exception as exc:
        # Catch-all: never return a 500 — always return valid schema
        print(f"[chat] Unexpected error: {type(exc).__name__}: {exc}")
        return ChatResponse(
            reply="I'm having trouble processing that. Could you try rephrasing?",
            recommendations=[],
            end_of_conversation=False,
        )


# ---------------------------------------------------------------------------
# Dev server — run directly: python main.py
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
