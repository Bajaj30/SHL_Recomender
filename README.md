# SHL Assessment Recommender API

A production-ready RAG (Retrieval-Augmented Generation) API built for the SHL Assessment recommendation challenge. It uses FastAPI, FAISS, and Google's Vertex AI (Gemini 2.5 Flash) to recommend assessments based on natural language queries, strictly bounded by the SHL catalog.

**Live Deployment URL:** `https://shl-recommender-486950393746.us-central1.run.app`

## 📁 File Structure

The codebase is highly modular, separating routing, retrieval, generation, and evaluation:

*   **`main.py`**: The FastAPI server. Handles the `/chat` and `/health` routes. This is also where the crucial **"Staple Injection"** pattern occurs (ensuring required baseline tests like `OPQ32r` are always appended to the retrieval context).
*   **`retriever.py`**: The vector search engine. Uses `sentence-transformers` (`all-MiniLM-L6-v2`) to embed user queries and searches an in-memory `FAISS` index of the SHL catalog.
*   **`llm.py`**: The Vertex AI wrapper. Handles Google Cloud authentication (via ADC) and communicates with the Gemini API, enforcing strict JSON output.
*   **`prompt.py`**: The "brain" of the application. Contains the massive System Prompt structured as a Finite State Machine (Clarify, Recommend, Refine, Compare, Refuse). It contains hard rules, few-shot examples, and exact JSON schema definitions.
*   **`test_runner.py`**: A custom, automated evaluation suite containing ~20 edge-case tests (Schema Compliance, Recall@10, Behavior Probes, Zero Hallucination checks) mapped directly to the grading rubric.
*   **`prepare_catalog.py`**: A data-pipeline script that flattens the deeply nested, raw `Catalog.json` into `catalog_prepared.json` (creating dense, semantic `search_text` paragraphs for optimal FAISS retrieval).
*   **`Approach.md`**: The required 2-page document detailing design choices, prompt engineering, and evaluation metrics.
*   **`Dockerfile`**: A multi-stage, slim Docker build used for zero-secret deployment to Google Cloud Run.

---

## 🔄 Data Flow

When a user sends a request to the `/chat` endpoint, the data follows this exact pipeline:

1.  **Request Reception (`main.py`)**: The FastAPI server receives the conversational history payload.
2.  **Semantic Search (`retriever.py`)**: 
    *   The user's most recent message is passed to the embedding model.
    *   FAISS searches the in-memory vector database and retrieves the Top-15 most semantically relevant assessments from the SHL catalog.
3.  **Staple Injection (`main.py`)**: 
    *   Because FAISS only retrieves *semantically* similar items, it often misses universally required baseline tests (e.g., personality/cognitive tests for developers). 
    *   The server forcefully injects a hardcoded list of "Staple Items" (e.g., `OPQ32r`, `Verify Interactive G+`) into the FAISS results, completely eliminating URL hallucination by the LLM.
4.  **Prompt Assembly (`prompt.py`)**: The retrieved items + staples are formatted into a rigid Markdown catalog and injected into the System Prompt, along with the user's chat history.
5.  **LLM State Machine (`llm.py`)**: 
    *   The payload is sent to Vertex AI (Gemini). 
    *   The LLM evaluates the user's intent against the "Five Actions" defined in the prompt.
    *   It generates a deterministic, strictly formatted JSON response based on the few-shot examples.
6.  **Response Delivery (`main.py`)**: The JSON response is parsed into a Pydantic model to guarantee schema validation before being returned to the user.
