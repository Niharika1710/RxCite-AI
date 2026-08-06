from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    openai_api_key: str = ""
    google_api_key: str = ""
    chroma_persist_dir: str = "./chroma_db"
    ncbi_email: str = ""
    ncbi_tool_name: str = "medintel-ai"

    llm_model: str = "gemini-3.5-flash-lite"
    embedding_model: str = "all-MiniLM-L6-v2"  # local, free, runs on CPU

    class Config:
        env_file = ".env"

settings = Settings()