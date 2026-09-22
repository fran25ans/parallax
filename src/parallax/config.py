from __future__ import annotations

import os
from pathlib import Path


def load_local_environment(project_root: Path | None = None) -> None:
    root = project_root or Path(__file__).resolve().parents[2]
    env_file = root / ".env.local"
    if not env_file.is_file():
        return

    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        name = name.strip()
        if name in {
            "NEBIUS_API_KEY",
            "NEBIUS_TOKEN_FACTORY_KEY",
            "NEBIUS_PROJECT_ID",
        }:
            os.environ.setdefault(name, value.strip())


def nebius_api_key() -> str:
    load_local_environment()
    key = os.environ.get("NEBIUS_API_KEY") or os.environ.get(
        "NEBIUS_TOKEN_FACTORY_KEY"
    )
    if not key:
        raise RuntimeError(
            "Nebius key is not configured. Set NEBIUS_API_KEY in .env.local."
        )
    return key


def live_nebius_spend_allowed() -> bool:
    return os.environ.get("PARALLAX_ALLOW_NEBIUS_SPEND", "").lower() == "true"


def nebius_project_id() -> str:
    load_local_environment()
    project_id = os.environ.get("NEBIUS_PROJECT_ID")
    if not project_id:
        raise RuntimeError(
            "Nebius project ID is not configured. Set NEBIUS_PROJECT_ID in .env.local."
        )
    if not project_id.startswith(("project-", "aiproject-")):
        raise RuntimeError(
            "NEBIUS_PROJECT_ID must start with 'project-' or 'aiproject-'."
        )
    return project_id
