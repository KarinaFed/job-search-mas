"""Configuration settings for the Job Search MAS."""
import os
from pydantic_settings import BaseSettings
from typing import Optional
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv(usecwd=True))


class Settings(BaseSettings):
    """Application settings."""
    
    # LiteLLM Configuration
    litellm_base_url: str = os.getenv("LITELLM_BASE_URL", "http://a6k2.dgx:34000/v1")
    litellm_api_key: str = os.getenv("LITELLM_API_KEY", "your_api_key")
    model_name: str = os.getenv("MODEL_NAME", "qwen3-32b")
    
    # Database
    postgres_host: str = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_db: str = os.getenv("POSTGRES_DB", "job_search_mas")
    postgres_user: str = os.getenv("POSTGRES_USER", "postgres")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "postgres_password")
    
    # Redis
    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_db: int = int(os.getenv("REDIS_DB", "0"))
    
    # HH.ru API
    hh_api_key: Optional[str] = os.getenv("HH_API_KEY")  # Legacy: direct access token
    hh_client_id: Optional[str] = os.getenv("HH_CLIENT_ID")  # OAuth2 Client ID
    hh_client_secret: Optional[str] = os.getenv("HH_CLIENT_SECRET")  # OAuth2 Client Secret
    hh_api_url: str = os.getenv("HH_API_URL", "https://api.hh.ru")
    
    # Application
    app_env: str = os.getenv("APP_ENV", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    api_title: str = "Job Search Multi-Agent System"
    api_version: str = "0.1.0"
    
    # Agent settings
    max_iterations: int = 10
    temperature: float = 0.7
    
    # Telegram Bot (optional)
    telegram_bot_token: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields instead of raising error
        protected_namespaces = ('settings_',)


settings = Settings()
