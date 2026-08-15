import json

import pytest

from src.knowledge.drive_source import DriveSourceRecord
from src.knowledge.private_config import PrivateKnowledgeConfig
from src.knowledge.private_models import DriveAllowlist, DriveAllowlistEntry
from src.knowledge.private_sync import PrivateKnowledgeSync


class FakeDrive:
    def __init__(self, records, payload=b"Synthetic private source sentence."):
        self.records = records
        self.payload = payload
        self.read_count = 0

    def list_allowed(self, allowlist):
        return self.records

    def read_bytes(self, record):
        self.read_count += 1
        return self.payload


def make_record(modified="2026-08-15T12:00:00Z"):
    return DriveSourceRecord(
        file_id="synthetic-file-id",
        name="Synthetic Source",
        mime_type="application/vnd.google-apps.document",
        modified_time=modified,
        md5_checksum=None,
        allowlist_entry=DriveAllowlistEntry(
            id="synthetic-file-id",
            source_type="synthesis",
            domains=["strategy"],
            experts=["strategy"],
        ),
    )


def make_config(tmp_path, monkeypatch):
    allowlist_path = tmp_path / "allowlist.json"
    allowlist_path.write_text(json.dumps({"files": [{"id": "synthetic-file-id"}], "folders": []}))
    state_path = tmp_path / "state.json"
    monkeypatch.setenv("PRIVATE_KNOWLEDGE_ALLOWLIST_FILE", str(allowlist_path))
    monkeypatch.setenv("PRIVATE_KNOWLEDGE_STATE_FILE", str(state_path))
    monkeypatch.setenv("PINECONE_PRIVATE_NAMESPACE", "private-test")
    return PrivateKnowledgeConfig.from_env()


def test_sync_skips_unchanged_remote_version(tmp_path, monkeypatch):
    config = make_config(tmp_path, monkeypatch)
    record = make_record()
    state = {
        "version": 1,
        "documents": {
            record.file_id: {
                "doc_id": "old-doc",
                "remote_version": record.modified_time,
                "content_hash": "old-hash",
                "last_ingested_at": "2026-08-15T12:05:00Z",
                "chunks": 3,
            }
        },
    }
    config.state_file.write_text(json.dumps(state), encoding="utf-8")
    drive = FakeDrive([record])
    calls = []
    sync = PrivateKnowledgeSync(config, drive, upsert_func=lambda *args, **kwargs: calls.append(args))
    report = sync.sync()
    assert report.skipped == 1
    assert report.updated == 0
    assert drive.read_count == 0
    assert calls == []


def test_sync_updates_changed_doc_and_state_only_after_success(tmp_path, monkeypatch):
    config = make_config(tmp_path, monkeypatch)
    record = make_record(modified="2026-08-15T13:00:00Z")
    drive = FakeDrive([record])
    captured = {}

    def fake_upsert(text, metadata, *, namespace):
        captured["text"] = text
        captured["metadata"] = metadata
        captured["namespace"] = namespace
        return {"chunks_count": 2}

    sync = PrivateKnowledgeSync(config, drive, upsert_func=fake_upsert)
    report = sync.sync()
    saved = json.loads(config.state_file.read_text(encoding="utf-8"))
    assert report.updated == 1
    assert captured["namespace"] == "private-test"
    assert captured["metadata"].drive_file_id == "synthetic-file-id"
    assert saved["documents"]["synthetic-file-id"]["chunks"] == 2
    assert "title" not in saved["documents"]["synthetic-file-id"]


def test_sync_does_not_advance_state_after_failed_upsert(tmp_path, monkeypatch):
    config = make_config(tmp_path, monkeypatch)
    drive = FakeDrive([make_record()])

    def fail_upsert(*args, **kwargs):
        raise RuntimeError("synthetic upsert failure")

    sync = PrivateKnowledgeSync(config, drive, upsert_func=fail_upsert)
    report = sync.sync()
    assert report.failed == 1
    if config.state_file.exists():
        saved = json.loads(config.state_file.read_text(encoding="utf-8"))
        assert saved.get("documents", {}) == {}


def test_sync_logs_neither_private_text_nor_title_by_default(tmp_path, monkeypatch, caplog):
    config = make_config(tmp_path, monkeypatch)
    drive = FakeDrive([make_record()])
    sync = PrivateKnowledgeSync(
        config,
        drive,
        upsert_func=lambda *args, **kwargs: {"chunks_count": 1},
    )
    sync.sync()
    log_text = caplog.text
    assert "Synthetic private source sentence" not in log_text
    assert "Synthetic Source" not in log_text
