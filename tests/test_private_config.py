import json

from src.knowledge.private_config import PrivateKnowledgeConfig


def test_private_config_is_disabled_without_allowlist(monkeypatch):
    monkeypatch.delenv("PRIVATE_KNOWLEDGE_ALLOWLIST_FILE", raising=False)
    cfg = PrivateKnowledgeConfig.from_env()
    assert cfg.enabled is False


def test_private_config_uses_safe_defaults(monkeypatch):
    monkeypatch.delenv("PRIVATE_KNOWLEDGE_STATE_FILE", raising=False)
    monkeypatch.delenv("PINECONE_PRIVATE_NAMESPACE", raising=False)
    monkeypatch.delenv("PRIVATE_KNOWLEDGE_DEBUG_TITLES", raising=False)
    cfg = PrivateKnowledgeConfig.from_env()
    assert str(cfg.state_file) == ".private_knowledge/state.json"
    assert cfg.pinecone_namespace == "private-library"
    assert cfg.debug_titles is False


def test_private_config_loads_synthetic_allowlist(tmp_path, monkeypatch):
    allowlist = tmp_path / "allowlist.json"
    allowlist.write_text(
        json.dumps(
            {
                "folders": [
                    {
                        "id": "folder-synthetic-1",
                        "source_type": "book",
                        "domains": ["strategy"],
                        "experts": ["strategy"],
                    }
                ],
                "files": [],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("PRIVATE_KNOWLEDGE_ALLOWLIST_FILE", str(allowlist))
    cfg = PrivateKnowledgeConfig.from_env()
    parsed = cfg.load_allowlist()
    assert cfg.enabled is True
    assert parsed.folders[0].id == "folder-synthetic-1"
    assert parsed.folders[0].domains == ["strategy"]
