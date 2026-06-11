from fastapi import FastAPI
from app.api.webhook import router as webhook_router

app = FastAPI(title="AI-PR-Reviewer")

app.include_router(webhook_router)

@app.get("/health")
def health_check():
    return {"status": "healthy"}
