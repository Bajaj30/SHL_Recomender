# Approach Document: SHL Assessment Recommender

**Source Code (Optional Review):** [https://github.com/Bajaj30/SHL_Recomender](https://github.com/Bajaj30/SHL_Recomender)

## 1. The Core Brain: Advanced Prompt Engineering (Primary Focus)
The fundamental challenge of this assignment was not connecting to an LLM, but forcing a highly conversational, non-deterministic model to act as a strict, deterministic routing engine. 

* **The "Five Actions" State Machine:** Rather than assigning the LLM a generic "helpful assistant" persona, I architected the system prompt as a finite state machine. The prompt forces the LLM to classify every user input into one of five strict buckets (Clarify, Recommend, Refine, Compare, Refuse) before generating a response.
* **Taming Hallucinations via Hard Rules:** I implemented a "sacred" ruleset in the prompt (e.g., *RULE 1 — URLS ARE SACRED*, *RULE 3 — CATALOG ONLY*). The LLM was explicitly instructed that if an assessment is not provided in its immediate context window, it literally does not exist.
* **Solving the `end_of_conversation` Ambiguity:** The LLM initially struggled to differentiate between a user asking a comparison question ("What's the difference between X and Y?") versus confirming a shortlist ("That looks perfect"). I solved this by defining exact positive trigger phrases ("locking it in", "confirmed") and explicitly listing negative triggers (e.g., "mid-negotiation") directly in the prompt logic.
* **Tone & Brevity via Few-Shot Examples:** Initially, the LLM's responses were too verbose. Instead of adding vague instructions like "be brief," I injected highly specific **Few-Shot Examples** and lowered the Vertex AI temperature to `0.1`. This deterministically forced the model to mimic the exact professional brevity of the examples with zero added latency.
* **The Out-of-Vocabulary Edge-Case:** I proactively handled requests for non-existent skills (e.g., a "Rust" test, which is not in the SHL catalog). By adding a specific few-shot example showing the LLM exactly how to acknowledge the gap and pivot to a live-coding alternative, I neutralized the risk of the model inventing a fake test.

## 2. Data Pipeline & The "Staple Injection" Breakthrough
* **Semantic Flattening:** Dumping raw JSON into FAISS yields poor retrieval. I built a pre-processing script (`prepare_catalog.py`) to flatten deeply nested metadata (competencies, job levels, languages) into a dense, human-readable `search_text` paragraph for each item. This transformed unstructured JSON into a format highly optimized for `sentence-transformers` embeddings.
* **Solving URL Hallucination via "Staple Injection":** 
  * *The Problem:* My prompt rules instructed the LLM to include tests like `OPQ32r` and `Verify Interactive G+` by default for senior roles. However, for a query like "Java Developer", FAISS would not retrieve `OPQ32r` because it lacks semantic similarity to Java. The LLM knew it had to recommend it, but without the item's exact URL in its context window, it hallucinated a fake one.
  * *The Solution:* I realized prompt engineering cannot fix a missing data problem. I implemented a "Staple Injection" step in the application layer (`main.py`). After FAISS retrieves the top-K results, the code forcefully appends universally required tests (OPQ32r, Verify G+, DSI, Contact Center) to the context *before* sending it to the LLM. This guaranteed the LLM always had the exact, copyable URLs available, instantly eliminating the hallucination bug.

## 3. System Architecture & Zero-Secret Deployment
* **The Stack:** FastAPI (for high-performance async routing), FAISS (for in-memory, low-latency vector search), `sentence-transformers` (local, fast embeddings), and Vertex AI via Google Cloud (Gemini 2.5 Flash).
* **The Deployment Pivot:**
  * *The Problem:* I initially planned to deploy on Render, which required generating a Service Account JSON key. However, my organization's GCP policy blocked key creation (`iam.disableServiceAccountKeyCreation`).
  * *The Solution:* I strategically pivoted to Google Cloud Run. This architectural upgrade allowed the application to use the native Application Default Credentials (ADC) attached to the Compute Engine service account. 
  * *The Result:* A highly secure, serverless deployment that authenticates with Vertex AI implicitly—requiring zero hardcoded secrets or environment variables.

## 4. Evaluation Methods & Metrics
To ensure the system was robust, I built `test_runner.py`, a custom automated test suite of ~20 integration tests mapped directly to the project requirements:
* **Retrieval Quality & Recommendation Relevance:** Measured using targeted "Recall@10" queries. I simulated specific personas (e.g., "mid-level Java developer") and programmatically asserted that the combined FAISS + LLM pipeline successfully surfaced the expected tests (e.g., Core Java) in the final JSON array.
* **Groundedness (Zero Hallucination):** Measured by cross-referencing output against the source of truth. The test runner asserted that *every* URL returned by the LLM existed verbatim in the original catalog JSON. If the LLM invented a test or altered a URL, the test instantly failed.
* **Overall Response Accuracy & Effectiveness:** Measured via "Behavior Probes." I tested edge-cases to ensure the finite state machine held up: vague inputs (asserting the LLM asked clarifying questions instead of blindly recommending), off-topic/legal questions (asserting clean refusals), prompt injections, and complex multi-turn refinements (asserting the LLM could add/drop specific items without losing context).

## 5. AI Tooling Usage
I heavily utilized an Agentic AI coding assistant (Google DeepMind's Antigravity) throughout this project. It was primarily used as a collaborative pair-programmer to:
* Parse and restructure the raw, nested JSON catalog.
* Write the automated test suite based on the provided PDF requirements.
* Diagnose server crashes and JSON schema errors by rapidly analyzing terminal logs and stack traces.
* Execute deployment commands and troubleshoot IAM permissions directly in the Google Cloud shell.
