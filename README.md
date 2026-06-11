# AI-PR-Reviewer

A production-ready Developer Tool that integrates with GitHub Webhooks to automatically review code diffs, write summaries, generate docstrings, and write unit tests using an LLM.

## Architecture

1. **Webhook Listener**: A FastAPI service that listens for `pull_request` events from GitHub. It validates payloads using the `X-Hub-Signature-256` header.
2. **GitHub Service**: Integrates with the GitHub API to fetch PR code diffs and post review comments and summaries back to the repository.
3. **LLM Orchestrator**: Uses OpenAI or Anthropic APIs to parse code diffs, identify issues, and suggest fixes in a structured format.

## Setup

1. Clone the repository and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Copy the `.env.example` to `.env` and fill in your secrets.
3. Run the server locally:
   ```bash
   uvicorn app.main:app --reload
   ```
4. Expose your local server to the internet using a tool like `ngrok` and configure your GitHub Webhook.

## Features
- **Auto-Review**: Line-by-line comments on PRs.
- **Summarization**: High-level PR summaries.
- **Auto-Test Generation**: Automatically detects missing tests and commits generated test files.
- **Style Customization**: Adheres to `.github/ai_style_guide.md` if present.
