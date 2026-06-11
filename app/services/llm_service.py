import os
import json
from typing import List, Optional
from pydantic import BaseModel, Field
from tenacity import retry, wait_exponential, stop_after_attempt
from app.config import settings
import openai
from anthropic import Anthropic

class ReviewComment(BaseModel):
    file_path: str = Field(description="The path of the file being reviewed")
    line_number: int = Field(description="The line number where the issue or suggestion applies")
    issue_type: str = Field(description="The type of issue (e.g., Security, Bug, Style, Performance)")
    comment: str = Field(description="The markdown formatted feedback comment")
    suggested_fix: Optional[str] = Field(None, description="Optional actual code replacement block")

class ReviewResponse(BaseModel):
    comments: List[ReviewComment]
    summary: str = Field(description="A high level markdown summary of the entire PR review")

def get_style_guide() -> str:
    path = ".github/ai_style_guide.md"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""

def get_system_prompt() -> str:
    return f"""You are an expert Senior DevOps and AI Engineer acting as a PR Reviewer.
Your goal is to review code diffs, identify bugs, security issues, performance bottlenecks, and style violations.
You must output strictly in JSON format matching the requested schema.
Here is the team's style guide:
{get_style_guide()}
"""

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
def analyze_diff(diff_content: str) -> ReviewResponse:
    if settings.LLM_PROVIDER == "openai":
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": get_system_prompt()},
                {"role": "user", "content": f"Review the following PR diff:\n\n{diff_content}"}
            ],
            response_format=ReviewResponse,
            temperature=0.1
        )
        return response.choices[0].message.parsed
    elif settings.LLM_PROVIDER == "anthropic":
        client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        prompt = f"{get_system_prompt()}\n\nReview the following PR diff:\n\n{diff_content}\n\nReturn strictly valid JSON matching this schema:\n{json.dumps(ReviewResponse.model_json_schema())}"
        response = client.messages.create(
            model="claude-3-5-sonnet-20240620",
            max_tokens=2048,
            temperature=0.1,
            system="You are a JSON-only code reviewer bot. Do not output anything except JSON.",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        content = response.content[0].text
        # Fallback extraction just in case
        import re
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            content = match.group(0)
        return ReviewResponse.model_validate_json(content)
    elif settings.LLM_PROVIDER == "groq":
        client = openai.OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1"
        )
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": f"{get_system_prompt()}\n\nYou must return strictly valid JSON matching this schema:\n{json.dumps(ReviewResponse.model_json_schema())}"},
                {"role": "user", "content": f"Review the following PR diff:\n\n{diff_content}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        content = response.choices[0].message.content
        return ReviewResponse.model_validate_json(content)
    else:
        raise ValueError("Unsupported LLM Provider")
class TestGenerationResponse(BaseModel):
    test_file_path: str = Field(description="The path where the test file should be written")
    test_file_content: str = Field(description="The complete python test file content using pytest")

@retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
def generate_tests(diff_content: str) -> Optional[TestGenerationResponse]:
    prompt = "Review the following diff. If new functions or classes were added without corresponding tests, generate a complete pytest test file. Return JSON matching the schema."
    if settings.LLM_PROVIDER == "openai":
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a Python Pytest expert."},
                {"role": "user", "content": f"{prompt}\n\nDiff:\n{diff_content}"}
            ],
            response_format=TestGenerationResponse,
            temperature=0.1
        )
        if response.choices[0].message.parsed:
            return response.choices[0].message.parsed
    elif settings.LLM_PROVIDER == "groq":
        client = openai.OpenAI(
            api_key=settings.GROQ_API_KEY,
            base_url="https://api.groq.com/openai/v1"
        )
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": f"You are a Python Pytest expert.\n\nYou must return strictly valid JSON matching this schema:\n{json.dumps(TestGenerationResponse.model_json_schema())}"},
                {"role": "user", "content": f"{prompt}\n\nDiff:\n{diff_content}"}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        content = response.choices[0].message.content
        if content:
            return TestGenerationResponse.model_validate_json(content)
    return None
