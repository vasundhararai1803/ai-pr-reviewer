import os
import hmac
import hashlib
import httpx
import json
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Header
from dotenv import load_dotenv
from app.diff_parser import parse_diff_positions

load_dotenv()

app = FastAPI(
    title="AI Pull Request Reviewer Engine",
    description="Production-hardened, non-blocking asynchronous webhook processor."
)

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")

async_client = httpx.AsyncClient(timeout=30.0)

async def verify_signature(request: Request, x_hub_signature_256: str):
    if not WEBHOOK_SECRET:
        return
    if not x_hub_signature_256:
        raise HTTPException(status_code=401, detail="Missing security signature.")
    body = await request.body()
    signature = "sha256=" + hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Cryptographic signature mismatch.")

async def review_pull_request(payload: dict):
    pull_request = payload.get("pull_request", {})
    repo = payload.get("repository", {})
    repo_name = repo.get("full_name")
    pr_number = payload.get("number")
    commit_sha = pull_request.get("head", {}).get("sha")
    
    sender = payload.get("sender", {})
    if sender.get("type") == "Bot" or "[bot]" in sender.get("login", "").lower():
        print(f"⚠️ Event bypassed: Triggered by bot account '{sender.get('login')}'. Loop blocked.")
        return

    if not pr_number or not repo_name or not commit_sha:
        print("❌ Invalid payload architecture: Missing repository details or commit SHA.")
        return

    print(f"🚀 Commencing Inline Code Review for {repo_name} #{pr_number}")

    # Fetch raw diff data
    diff_url = f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}"
    github_headers = {
        "Authorization": f"token {GITHUB_TOKEN}" if GITHUB_TOKEN else "",
        "Accept": "application/vnd.github.v3.diff",
        "User-Agent": "AI-PR-Reviewer-Engine"
    }
    
    try:
        diff_response = await async_client.get(diff_url, headers=github_headers)
        if diff_response.status_code != 200:
            print(f"❌ Failed to extract diff payload. HTTP Status: {diff_response.status_code}")
            return
        pr_diff = diff_response.text
    except Exception as e:
        print(f"❌ Network failure pulling code diff: {str(e)}")
        return

    # Parse valid diff positions using our custom algorithm to stop line hallucinations
    valid_positions = parse_diff_positions(pr_diff)

    if not GROQ_API_KEY:
        print("❌ System Exception: Missing operational GROQ_API_KEY.")
        return
        
    try:
        groq_url = "https://api.groq.com/openai/v1/chat/completions"
        groq_headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Enforce structured JSON return instructions
        system_prompt = (
            "You are an elite senior software architect. Inspect the following Git diff patch. "
            "Identify critical bugs, syntax crashes, or major security leaks. "
            "You MUST respond ONLY with a raw valid JSON object matching this schema:\n"
            "{\n"
            '  "reviews": [\n'
            '    {"file_path": "sample.py", "line_number": 12, "comment": "Bug explanation here"}\n'
            "  ]\n"
            "}\n"
            "Do not include any conversational markdown wrapper like ```json or trailing explanations."
        )

        groq_payload = {
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Review this PR Diff and extract issues into the JSON structure:\n\n{pr_diff}"}
            ],
            "response_format": {"type": "json_object"}
        }
        
        llm_response = await async_client.post(groq_url, json=groq_payload, headers=groq_headers)
        llm_response.raise_for_status()
        raw_output = llm_response.json()['choices'][0]['message']['content']
        structured_data = json.loads(raw_output)
    except Exception as e:
        print(f"❌ LLM Parsing layer failure: {str(e)}")
        return

    # Post Inline Comments to GitHub Review Comments API
    review_comments_url = f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}/comments"
    post_headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "AI-PR-Reviewer-Engine"
    }

    for review in structured_data.get("reviews", []):
        file_path = review.get("file_path")
        line_number = review.get("line_number")
        
        # Defensive programming: ensure type safety before feeding math filters
        if not file_path or line_number is None:
            print("⚠️ Missing parameters inside LLM structured JSON response block.")
            continue
            
        try:
            line_number = int(line_number)
        except ValueError:
            print(f"⚠️ Non-integer line number received from LLM output: {line_number}")
            continue
            
        comment_body = review.get("comment")

        # Cross-reference the parsed diff to get the exact position index
        file_map = valid_positions.get(file_path, {})
        position = file_map.get(line_number)

        if not position:
            print(f"⚠️ Skipping review line mapping for {file_path}:{line_number} (Position out of diff scope)")
            continue

        comment_payload = {
            "body": f"🤖 **AI Inline Catch:** {comment_body}",
            "commit_id": str(commit_sha),
            "path": str(file_path),
            "position": int(position)
        }

        try:
            res = await async_client.post(review_comments_url, json=comment_payload, headers=post_headers)
            if res.status_code == 201:
                print(f"📍 Placed inline comment on {file_path} at line {line_number}")
            else:
                print(f"⚠️ Inline post rejected [{res.status_code}]: {res.text}")
        except Exception as e:
            print(f"❌ Failed to communicate with GitHub Review Comments endpoint: {str(e)}")

@app.post("/webhook")
async def github_webhook(
    request: Request, 
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(None)
):
    await verify_signature(request, x_hub_signature_256)
    payload = await request.json()
    action = payload.get("action")
    
    print(f"⚡ Webhook event caught: '{action}'")
    
    if action in ["opened", "synchronize", "reopened"]:
        background_tasks.add_task(review_pull_request, payload)
        return {"status": "accepted", "detail": "Task queued successfully."}
        
    return {"status": "ignored", "detail": f"Action bypassed."}