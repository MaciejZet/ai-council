from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from src.knowledge.private_models import DriveAllowlist


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class PrivateKnowledgeConfig:
    allowlist_file: Path | None
    state_file: Path
    pinecone_namespace: str
    debug_titles: bool
    enabled: bool

    @classmethod
    def from_env(cls) -> "PrivateKnowledgeConfig":
        allowlist_raw = os.getenv("PRIVATE_KNOWLEDGE_ALLOWLIST_FILE", "").strip()
        allowlist_file = Path(allowlist_raw).expanduser() if allowlist_raw else None
        state_file = Path(
            os.getenv("PRIVATE_KNOWLEDGE_STATE_FILE", ".private_knowledge/state.json")
        ).expanduser()
        namespace = os.getenv("PINECONE_PRIVATE_NAMESPACE", "private-library").strip()
        if not namespace:
            namespace = "private-library"
        return cls(
            allowlist_file=allowlist_file,
            state_file=state_file,
            pinecone_namespace=namespace,
            debug_titles=_env_bool("PRIVATE_KNOWLEDGE_DEBUG_TITLES", False),
            enabled=allowlist_file is not None,
        )

    def load_allowlist(self) -> DriveAllowlist:
        if self.allowlist_file is None:
            return DriveAllowlist()
        payload = json.loads(self.allowlist_file.read_text(encoding="utf-8"))
        return DriveAllowlist.model_validate(payload)
