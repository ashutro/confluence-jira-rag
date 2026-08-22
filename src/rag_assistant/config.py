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

        return cls(
            confluence_base_url=base_url,
            confluence_email=email,
            confluence_api_token=api_token,
            confluence_space_key=space_key,
            jira_base_url=jira_url,
            jira_email=jira_email,
            jira_api_token=jira_token,
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
