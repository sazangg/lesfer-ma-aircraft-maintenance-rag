"""Settings, read from the environment (and .env). See .env.example."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    mode: str = os.getenv("ANFA_MODE", "replay")  # replay | live | record
    api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    base_url: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    chat_model: str = os.getenv("ANFA_CHAT_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")
    embed_model: str = os.getenv("ANFA_EMBED_MODEL", "nvidia/nemotron-3.5-embed-1b:free")
    vision_model: str = os.getenv("ANFA_VISION_MODEL", "nvidia/nemotron-3.5-super-vl:free")
    # 2048 by default; 1024 fits pgvector's standard index (at most 2000 dimensions).
    embed_dimensions: int = int(os.getenv("ANFA_EMBED_DIMENSIONS", "1024"))
    database_url: str = os.getenv("DATABASE_URL", "postgresql://anfa:anfa@localhost:54329/anfa")


SETTINGS = Settings()
