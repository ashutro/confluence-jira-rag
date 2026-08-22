"""Configuration settings for Confluence + Jira RAG Assistant."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


def get_project_root() -> Path:
    """Find project root directory by searching for pyproject.toml from cwd or file location."""
    cwd = Path.cwd()
    if (cwd / "pyproject.toml").exists():
        return cwd
    for parent in cwd.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return cwd


@dataclass
class Settings:
    """Application settings loaded from environment or .env file."""

    confluence_base_url: str
    confluence_email: str
    confluence_api_token: str
    confluence_space_key: Optional[str] = None
    jira_base_url: Optional[str] = None
    jira_email: Optional[str] = None
    jira_api_token: Optional[str] = None
    jira_project_key: Optional[str] = None
    qdrant_url: Optional[str] = None
    qdrant_api_key: Optional[str] = None
    qdrant_path: str = "data/qdrant_db"
    qdrant_collection_name: str = "knowledge_base"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    openrouter_api_key: Optional[str] = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = "stealth/ox-alpha"
    openrouter_reasoning: bool = True

    @classmethod
    def from_env(cls, env_file: Optional[Path | str] = None) -> Settings:
        """Load settings from .env file or system environment variables."""
        if env_file:
            load_dotenv(dotenv_path=env_file)
        else:
            default_env = get_project_root() / ".env"
            if default_env.exists():
                load_dotenv(dotenv_path=default_env)
            else:
                load_dotenv()

        base_url = os.getenv("CONFLUENCE_BASE_URL", "").strip().rstrip("/")
        email = os.getenv("CONFLUENCE_EMAIL", "").strip()
        api_token = os.getenv("CONFLUENCE_API_TOKEN", "").strip()
        space_key = os.getenv("CONFLUENCE_SPACE_KEY", "").strip() or None

        jira_url = os.getenv("JIRA_BASE_URL", "").strip().rstrip("/") or None
        jira_email = os.getenv("JIRA_EMAIL", "").strip() or None
        jira_token = os.getenv("JIRA_API_TOKEN", "").strip() or None
        jira_proj = os.getenv("JIRA_PROJECT_KEY", "").strip() or None

        q_url = os.getenv("QDRANT_URL", "").strip().rstrip("/") or None
        q_key = os.getenv("QDRANT_API_KEY", "").strip() or None
        q_path = os.getenv("QDRANT_PATH", "data/qdrant_db").strip()
        q_col = os.getenv("QDRANT_COLLECTION_NAME", "knowledge_base").strip()
        emb_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5").strip()

        openrouter_key = os.getenv("OPENROUTER_API_KEY", "").strip() or None
        openrouter_base = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip().rstrip("/")
        openrouter_m = os.getenv("OPENROUTER_MODEL", "stealth/ox-alpha").strip()
        openrouter_reas = os.getenv("OPENROUTER_REASONING", "true").lower() in ("true", "1", "yes")

        return cls(
            confluence_base_url=base_url,
            confluence_email=email,
            confluence_api_token=api_token,
            confluence_space_key=space_key,
            jira_base_url=jira_url,
            jira_email=jira_email,
            jira_api_token=jira_token,
            jira_project_key=jira_proj,
            qdrant_url=q_url,
            qdrant_api_key=q_key,
            qdrant_path=q_path,
            qdrant_collection_name=q_col,
            embedding_model=emb_model,
            openrouter_api_key=openrouter_key,
            openrouter_base_url=openrouter_base,
            openrouter_model=openrouter_m,
            openrouter_reasoning=openrouter_reas,
        )

    def validate_confluence(self) -> None:
        """Validate that essential Confluence credentials are present."""
        missing = []
        if not self.confluence_base_url:
            missing.append("CONFLUENCE_BASE_URL")
        if not self.confluence_email:
            missing.append("CONFLUENCE_EMAIL")
        if not self.confluence_api_token:
            missing.append("CONFLUENCE_API_TOKEN")

        if missing:
            raise ValueError(
                f"Missing required Confluence settings: {', '.join(missing)}. "
                "Please configure them in your .env file or environment variables."
            )

    def validate_jira(self) -> None:
        """Validate that essential Jira credentials are present."""
        missing = []
        if not self.jira_base_url:
            missing.append("JIRA_BASE_URL")
        if not self.jira_email:
            missing.append("JIRA_EMAIL")
        if not self.jira_api_token:
            missing.append("JIRA_API_TOKEN")

        if missing:
            raise ValueError(
                f"Missing required Jira settings: {', '.join(missing)}. "
                "Please configure them in your .env file or environment variables."
            )
