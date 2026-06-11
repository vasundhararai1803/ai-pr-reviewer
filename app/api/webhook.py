import hmac
import hashlib
from fastapi import APIRouter, Request, Header, HTTPException, BackgroundTasks
from app.config import settings
from app.services.github_service import get_pr_diff, post_pr_comments, create_file_in_pr
from app.services.llm_service import analyze_diff, generate_tests

router = APIRouter()

def verify_signature(payload_body: bytes, signature_header: str):
    if not signature_header:
        raise HTTPException(status_code=403, detail="x-hub-signature-256 header is missing!")
    
    hash_object = hmac.new(settings.GITHUB_WEBHOOK_SECRET.encode('utf-8'), msg=payload_body, digestmod=hashlib.sha256)
    expected_signature = "sha256=" + hash_object.hexdigest()
    if not hmac.compare_digest(expected_signature, signature_header):
        raise HTTPException(status_code=403, detail="Request signatures didn't match!")

async def process_pull_request(payload: dict):
    action = payload.get("action")
    if action not in ["opened", "synchronize"]:
        return

    pr_data = payload.get("pull_request", {})
    repo_data = payload.get("repository", {})
    
    repo_name = repo_data.get("full_name")
    pr_number = pr_data.get("number")
    commit_id = pr_data.get("head", {}).get("sha")
    branch_name = pr_data.get("head", {}).get("ref")

    if not repo_name or not pr_number or not commit_id:
        return

    try:
        # Fetch diff
        diff_content = get_pr_diff(repo_name, pr_number)
        if not diff_content:
            return

        # Analyze diff
        review_response = analyze_diff(diff_content)
        
        # Post comments
        comments_dict = [c.model_dump() for c in review_response.comments]
        post_pr_comments(repo_name, pr_number, commit_id, comments_dict, review_response.summary)

        # Generate tests if needed
        test_response = generate_tests(diff_content)
        if test_response:
            create_file_in_pr(
                repo_name=repo_name,
                branch_name=branch_name,
                file_path=test_response.test_file_path,
                content=test_response.test_file_content,
                commit_message=f"chore(ai): auto-generated tests for {test_response.test_file_path}"
            )
            
    except Exception as e:
        print(f"Error processing PR: {e}")

@router.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks, x_hub_signature_256: str = Header(None)):
    payload_body = await request.body()
    # Note: If no secret is configured locally, we might skip signature validation in testing, but we enforce it for production.
    if settings.GITHUB_WEBHOOK_SECRET:
        verify_signature(payload_body, x_hub_signature_256)
    
    payload = await request.json()
    event_type = request.headers.get("X-GitHub-Event")
    
    if event_type == "pull_request":
        background_tasks.add_task(process_pull_request, payload)
        
    return {"status": "ok"}
