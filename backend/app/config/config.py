import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "YouTube Migrator"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "127.0.0.1"
    
    # Database
    DATABASE_URL: str = "sqlite:///database/youtube_migrator.db"
    
    # Storage
    DOWNLOADS_DIR: str = "downloads"
    TOKENS_DIR: str = "tokens"
    LOGS_DIR: str = "logs"
    
    # OAuth
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/auth/callback"
    GOOGLE_CLIENT_SECRETS_FILE: str = "client_secret.json"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def base_dir(self) -> Path:
        # Resolves to project root (parent of backend/app/config)
        return Path(__file__).resolve().parent.parent.parent.parent

    @property
    def db_path(self) -> Path:
        if self.DATABASE_URL.startswith("sqlite:///"):
            rel_path = self.DATABASE_URL.replace("sqlite:///", "")
            return self.base_dir / rel_path
        return self.base_dir / "database" / "youtube_migrator.db"

    @property
    def downloads_path(self) -> Path:
        return self.base_dir / self.DOWNLOADS_DIR

    @property
    def tokens_path(self) -> Path:
        return self.base_dir / self.TOKENS_DIR

    @property
    def logs_path(self) -> Path:
        return self.base_dir / self.LOGS_DIR

    def ensure_directories(self):
        """Ensure all required local directories exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.downloads_path.mkdir(parents=True, exist_ok=True)
        self.tokens_path.mkdir(parents=True, exist_ok=True)
        self.logs_path.mkdir(parents=True, exist_ok=True)

settings = Settings()
