# Automated AI PR Reviewer Engine 

**An asynchronous, containerized AI code review engine built with FastAPI, Docker, and Groq.**

## Live Demo & System Proof

![Live Demo & System Proof](assets/demo_screenshot.png)

## Architectural Decisions & Production Tradeoffs

Building a production-grade webhook consumer requires designing for failure, rate limits, and network asynchronous boundaries. Below is the engineering rationale behind the core architectural choices of this engine.

### 1. Asynchronous Task Delegation vs. Synchronous Processing
* **The Problem:** GitHub mandates a strict **10-second timeout** window for all webhook response handshakes. Generating deep LLM analysis, formatting code blocks, and making upstream network requests frequently exceeds 15–20 seconds, risking broken handshakes and aggressive platform retries.
* **The Solution:** Implemented an **Asynchronous Worker Pattern** using FastAPI's native `BackgroundTasks`. 
* **Tradeoff:** The HTTP endpoint performs structural signature validation and payload parsing instantly, returning a `202 Accepted` status back to GitHub in **< 50ms**. The actual business logic (fetching code diffs, communicating with the Groq API, and posting review comments) is delegated completely out-of-band to a background thread pool, safely shielding the core loop from connection termination.

### 2. Idempotency & De-duplication Control
* **The Problem:** Distributed webhooks guarantee *at-least-once* delivery, meaning network blips can cause GitHub to fire duplicate events for the exact same Pull Request event. Processing every delivery blindly causes the AI agent to spam duplicate comment blocks onto the developer's timeline.
* **The Solution:** Engineered a **State Tracking Idempotency Layer**. The system extracts the unique `X-GitHub-Delivery` UUID header alongside the Pull Request's `head_commit_sha`. Before routing payloads to the LLM engine, the system evaluates the state cache to see if that specific commit fingerprint is already processing or complete. Duplicate deliveries are discarded instantly with an early return, ensuring zero timeline noise.

### 3. Token Budget Management & Diff Compaction
* **The Problem:** Large feature branches or legacy code migrations can generate code diffs that span thousands of lines, instantly exploding past LLM Context Windows (Token Limits) and driving unnecessary API expenditures.
* **The Solution:** Implemented a multi-layered **Diff Compaction Engine**:
    * **Heuristic Pruning:** The system explicitly filters out boilerplate binary files, lockfiles (`package-lock.json`, `poetry.lock`), and minified assets before tokenizer evaluation.
    * **Unified Batched Mutations:** Instead of executing individual API requests and dropping distinct single-line comments (creating severe API call overhead), the engine builds a unified structured array layout. It instructs the LLM to emit a single consolidated schema, which is pushed natively via a single `POST /reviews` call. This reduces API consumption by up to 80% on large branches.

---

## System Architecture

Unlike standard synchronous AI wrappers that block request flows and trigger GitHub webhook timeouts, this engine is built around an out-of-band asynchronous dispatch model. 

### Core Architectural Mechanics:
1. **Asynchronous Edge Router:** The FastAPI endpoint processes incoming GitHub `X-Hub-Signature-256` HMAC authentications, parses webhooks, drops an instantaneous `202 Accepted` network frame to clear GitHub's strict 10-second window, and instantly hands off processing to local `BackgroundTasks`.
2. **Unified Single-Payload Exchange:** Instead of executing separate, expensive API loops for top-level summaries and line reviews (which hit free-tier token gates and add heavy latency), the orchestrator passes an isolated context envelope to Groq. It extracts a highly structured, single JSON object containing both the markdown report and pinpoint inline critiques simultaneously.
3. **Native Batched Mutation:** Relies entirely on GitHub's modern Review API (`POST /pulls/{pr}/reviews`). It completely strips away fragile regex parsing and volatile diff-position arithmetic by injecting raw line targets and explicit `"side": "RIGHT"` alignments directly into unified collection objects.

---

## Feature Breakdown & Hardening

* **Prompt Fencing Guardrails:** Protects against active prompt-injection attacks. Code patches are tightly sandboxed inside explicit `[START OF UNTRUSTED CODE DATA]` structural boundaries, accompanied by system instructions forcing the core model to treat incoming characters purely as literal string payloads for static evaluation.
* **Deterministic Configuration Lifecycle:** Mitigates risk by stripping out local file globbing for credential detection. Cryptographic asymmetric `.pem` RSA keys are systematically parsed directly from injected, environment-isolated configurations managed safely inside Docker boundaries.
* **Hermetic Container Build:** Fully packaged via a multi-stage `Dockerfile` running Python slim runtimes to freeze dependency layers (`requirements.txt`), ensuring absolute portability between local validation environments and live cloud runtimes (Render/Railway).

---

## Empirical Evaluation & Quality Engineering

To prevent system drift and curb the number-one defect of AI tooling—hallucinations and false positives—this project includes a dedicated, empirical verification harness. The review system does not just prompt a model; it metrics-tests it.

Run the internal accuracy benchmark locally using:
```bash
python3 scripts/evaluate_reviewer.py
```
