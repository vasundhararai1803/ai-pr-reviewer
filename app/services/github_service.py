from github import Github
from app.config import settings
from typing import List, Dict, Any
import httpx

def get_github_client() -> Github:
    return Github(settings.GITHUB_TOKEN)

def get_pr_diff(repo_name: str, pr_number: int) -> str:
    gh = get_github_client()
    repo = gh.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    # Using httpx to fetch the raw diff URL
    diff_url = pr.diff_url
    response = httpx.get(diff_url)
    return response.text

def post_pr_comments(repo_name: str, pr_number: int, commit_id: str, comments: List[Dict[str, Any]], summary: str):
    gh = get_github_client()
    repo = gh.get_repo(repo_name)
    pr = repo.get_pull(pr_number)
    
    # Post global summary
    pr.create_issue_comment(summary)
    
    # Post inline comments
    for c in comments:
        try:
            body = c["comment"]
            if c.get("suggested_fix"):
                body += f"\n\n```python\n{c['suggested_fix']}\n```"
            pr.create_review_comment(
                body=body,
                commit_id=commit_id,
                path=c["file_path"],
                line=c["line_number"]
            )
        except Exception as e:
            print(f"Failed to post comment on {c['file_path']}:{c['line_number']}: {e}")

def create_file_in_pr(repo_name: str, branch_name: str, file_path: str, content: str, commit_message: str):
    gh = get_github_client()
    repo = gh.get_repo(repo_name)
    try:
        repo.create_file(file_path, commit_message, content, branch=branch_name)
        print(f"Successfully created {file_path}")
    except Exception as e:
        print(f"Failed to create file {file_path}: {e}")
