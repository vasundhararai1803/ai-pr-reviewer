import os
import hmac
import hashlib
import httpx
import json
import time
import jwt
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Header
from dotenv import load_dotenv
from app.diff_parser import parse_diff_positions

load_dotenv()

app = FastAPI(
    title="AI Pull Request Reviewer Engine",
    description="Production-hardened GitHub App Webhook Processor."
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")
APP_ID = os.getenv("GITHUB_APP_ID")

# Dynamically locate the .pem key file in the root directory
PRIVATE_KEY_PATH = None
for file in os.listdir("."):
    if file.endswith(".pem"):
        PRIVATE_KEY_PATH = file
        break

async_client = httpx.AsyncClient(timeout=30.0)

def generate_jwt() -> str:
    """Mints a short-lived JSON Web Token signed with our App's private key."""
    if not APP_ID or not PRIVATE_KEY_PATH:
        raise Exception("System misconfigured: Missing GITHUB_APP_ID or Private Key file.")
        
    with open(PRIVATE_KEY_PATH, "r") as f:
        private_key = f.read()
        
    payload = {
        "iat": int(time.time()) - 60,
        "exp": int(time.time()) + (10 * 60),
        "iss": int(APP_ID)
    }
    return jwt.encode(payload, private_key, algorithm="RS256")

async def get_installation_access_token(installation_id: int) -> str:
    """Exchanges the App JWT for a secure, temporary repository access token."""
    app_jwt = generate_jwt()
    url = f"https://api.github.com/app/installations/{installation_id}/access_tokens"
    headers = {
        "Authorization": f"Bearer {app_jwt}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "AI-PR-Reviewer-Engine"
    }
    res = await async_client.post(url, headers=headers)
    res.raise_for_status()
    return res.json()["token"]

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
    # Safe multi-layered extraction for repository coordinates
    repo = payload.get("repository", {})
    repo_name = repo.get("full_name")
    
    # Safe extraction for PR Number (handles issue comments or standard pull requests)
    pr_number = payload.get("number") or payload.get("pull_request", {}).get("number")
    
    pull_request = payload.get("pull_request", {})
    # Extract commit SHA safely across different webhook variants
    commit_sha = pull_request.get("head", {}).get("sha") or payload.get("after")
    
    # Extract GitHub App context
    installation_id = payload.get("installation", {}).get("id")
    
    # Infinite loop security guard
    sender = payload.get("sender", {})
    if sender.get("type") == "Bot" or "[bot]" in sender.get("login", "").lower():
        print(f"⚠️ Event bypassed: Triggered by bot account '{sender.get('login')}'. Loop blocked.")
        return

    # Add descriptive debugging to console logs to trace exactly what is missing
    if not pr_number or not repo_name or not commit_sha or not installation_id:
        print(f"❌ Structural Validation Failed:")
        print(f"  - repo_name: {repo_name}")
        print(f"  - pr_number: {pr_number}")
        print(f"  - commit_sha: {commit_sha}")
        print(f"  - installation_id: {installation_id}")
        return

    print(f"🚀 Authenticating via GitHub App Installation ID: {installation_id}")
    print(f"🎯 Parsing target branch diff for {repo_name} #{pr_number} at commit {commit_sha[:7]}")
    
    try:
        installation_token = await get_installation_access_token(installation_id)
    except Exception as e:
        print(f"❌ Failed token exchange via App infrastructure: {str(e)}")
        return

    # Fetch raw diff data safely using the application token
    diff_url = f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}"
    github_headers = {
        "Authorization": f"token {installation_token}",
        "Accept": "application/vnd.github.v3.diff",
        "User-Agent": "AI-PR-Reviewer-Engine"
    }
    
    try:
        diff_response = await async_client.get(diff_url, headers=github_headers)
        if diff_response.status_code != 200:
            print(f"❌ Failed to extract diff payload. Status: {diff_response.status_code}")
            return
        pr_diff = diff_response.text
    except Exception as e:
        print(f"❌ Network failure pulling code diff: {str(e)}")
        return

    valid_positions = parse_diff_positions(pr_diff)

    try:
        groq_url = "https://api.groq.com/openai/v1/chat/completions"
        groq_headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
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

    review_comments_url = f"https://api.github.com/repos/{repo_name}/pulls/{pr_number}/comments"
    post_headers = {
        "Authorization": f"token {installation_token}",
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "AI-PR-Reviewer-Engine"
    }

    for review in structured_data.get("reviews", []):
        file_path = review.get("file_path")
        line_number = review.get("line_number")
        comment_body = review.get("comment")

        if not file_path or line_number is None:
            continue
            
        try:
            line_number = int(line_number)
        except ValueError:
            continue

        file_map = valid_positions.get(file_path, {})
        position = file_map.get(line_number)

        if not position:
            continue

        comment_payload = {
            "body": f"🤖 **AI App Review:** {comment_body}",
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
            print(f"❌ Failed to post inline comment: {str(e)}")

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