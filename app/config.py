import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _sqlite_uri(raw: str | None) -> str:
    """Build a Windows-safe absolute sqlite URI under the project."""
    default_path = BASE_DIR / "data" / "dreamframe.db"
    if not raw:
        return f"sqlite:///{default_path.as_posix()}"

    # Relative forms like sqlite:///data/foo.db break on Windows (drive root).
    if raw.startswith("sqlite:///"):
        path_part = raw.removeprefix("sqlite:///")
        if path_part != ":memory:" and not Path(path_part).is_absolute():
            return f"sqlite:///{(BASE_DIR / path_part).resolve().as_posix()}"

    return raw


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

    # Database configuration
    _database_url = os.getenv("DATABASE_URL")
    if _database_url and not _database_url.startswith("sqlite"):
        # Use provided PostgreSQL/external database URL
        SQLALCHEMY_DATABASE_URI = _database_url
    else:
        # Fall back to SQLite (local development or Render)
        SQLALCHEMY_DATABASE_URI = _sqlite_uri(_database_url)

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    if SQLALCHEMY_DATABASE_URI.startswith("sqlite"):
        SQLALCHEMY_ENGINE_OPTIONS = {
            "connect_args": {
                "check_same_thread": False
            }
        }
    else:
        SQLALCHEMY_ENGINE_OPTIONS = {}

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    # Default: Groq free OpenAI-compatible API
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.groq.com/openai/v1")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "openai/gpt-oss-20b")
    OPENAI_IMAGE_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "dall-e-2")
    # pollinations = free scenic images, no signup (default)
    # huggingface = free with HF account token
    IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "pollinations")
    HF_TOKEN = os.getenv("HF_TOKEN", "")
    HF_IMAGE_MODEL = os.getenv("HF_IMAGE_MODEL", "black-forest-labs/FLUX.1-schnell")
    POLLINATIONS_API_KEY = os.getenv("POLLINATIONS_API_KEY", "")
    USE_MOCK_AI = os.getenv("USE_MOCK_AI", "true").lower() in {"1", "true", "yes", "on"}
    GENERATE_IMAGES = os.getenv("GENERATE_IMAGES", "false").lower() in {"1", "true", "yes", "on"}
