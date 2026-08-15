from __future__ import annotations

import json
import tempfile
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from src.knowledge.drive_source import GOOGLE_DOC_MIME, DriveSourceClient, DriveSourceRecord
from src.knowledge.ingest import extract_text_from_pdf
from src.knowledge.private_config import PrivateKnowledgeConfig
from src.knowledge.private_ingest import content_sha256, stable_doc_id, upsert_text_document
from src.knowledge.private_models import (
    PrivateSourceMetadata,
    SyncDocumentState,
    SyncReport,
    SyncState,
)
from src.utils.logger import setup_logger

_sync_log = setup_logger("ai_council.private_knowledge.sync")

UpsertFunc = Callable[..., dict]


def _detect_language(text: str, name: str) -> str:
    sample = f"{name}\n{text[:4000]}"
    return "pl" if any(char in sample for char in "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ") else "en"


class PrivateKnowledgeSync:
    def __init__(
        self,
        config: PrivateKnowledgeConfig,
        drive: DriveSourceClient,
        *,
        upsert_func: UpsertFunc = upsert_text_document,
    ):
        self.config = config
        self.drive = drive
        self.upsert_func = upsert_func

    def _load_state(self) -> SyncState:
        if not self.config.state_file.exists():
            return SyncState()
        payload = json.loads(self.config.state_file.read_text(encoding="utf-8"))
        return SyncState.model_validate(payload)

    def _save_state(self, state: SyncState) -> None:
        path = self.config.state_file
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(
            json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)

    def _extract_text(self, record: DriveSourceRecord, payload: bytes) -> str:
        if record.mime_type == GOOGLE_DOC_MIME or record.mime_type.startswith("text/"):
            return payload.decode("utf-8", errors="replace")
        if record.mime_type == "application/pdf" or record.name.lower().endswith(".pdf"):
            with tempfile.TemporaryDirectory(prefix="ai-council-private-") as temporary_dir:
                pdf_path = Path(temporary_dir) / "source.pdf"
                pdf_path.write_bytes(payload)
                return extract_text_from_pdf(str(pdf_path))
        return payload.decode("utf-8", errors="replace")

    def sync(self, dry_run: bool = False) -> SyncReport:
        allowlist = self.config.load_allowlist()
        records = self.drive.list_allowed(allowlist)
        state = self._load_state()
        report = SyncReport(scanned=len(records))
        state_changed = False

        for record in records:
            remote_version = record.md5_checksum or record.modified_time or "unknown"
            previous = state.documents.get(record.file_id)
            if previous is not None and previous.remote_version == remote_version:
                report.skipped += 1
                continue

            doc_id = stable_doc_id("gdrive", record.file_id)
            if dry_run:
                report.updated += 1
                continue

            try:
                payload = self.drive.read_bytes(record)
                content_hash = content_sha256(payload)
                text = self._extract_text(record, payload)
                if not text.strip():
                    raise ValueError("source contains no extractable text")

                entry = record.allowlist_entry
                metadata = PrivateSourceMetadata(
                    doc_id=doc_id,
                    title=record.name,
                    source_type=entry.source_type,
                    language=_detect_language(text, record.name),
                    domains=entry.domains,
                    experts=entry.experts,
                    framework_tags=entry.framework_tags,
                    drive_file_id=record.file_id,
                    content_hash=content_hash,
                    modified_time=record.modified_time,
                )
                result = self.upsert_func(
                    text,
                    metadata,
                    namespace=self.config.pinecone_namespace,
                )
                if result.get("status", "success") != "success":
                    raise RuntimeError("private ingestion returned non-success status")

                state.documents[record.file_id] = SyncDocumentState(
                    doc_id=doc_id,
                    remote_version=remote_version,
                    content_hash=content_hash,
                    last_ingested_at=datetime.now(UTC).isoformat(),
                    chunks=int(result.get("chunks_count", 0)),
                )
                state_changed = True
                report.updated += 1
                if self.config.debug_titles:
                    _sync_log.info("Private knowledge updated doc_id=%s title=%s", doc_id, record.name)
                else:
                    _sync_log.info("Private knowledge updated doc_id=%s", doc_id)
            except Exception as exc:
                report.failed += 1
                report.failed_doc_ids.append(doc_id)
                _sync_log.warning(
                    "Private knowledge sync failed doc_id=%s error_type=%s",
                    doc_id,
                    type(exc).__name__,
                )

        if state_changed:
            self._save_state(state)
        return report
