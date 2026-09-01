from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api.routes import router

app = FastAPI(title="MedIntel AI - Pharmaceutical Intelligence")

# Allow the frontend (which we'll build next) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://rx-cite-ai-7s6q.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix="/api")


@app.get("/health")
def health_check():
    return {"status": "ok", "model": settings.llm_model}
