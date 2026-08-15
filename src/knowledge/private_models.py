from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

SourceType = Literal[
    "book",
    "summary",
    "personal_note",
    "synthesis",
    "internal_doc",
    "article",
    "ogólne",
    "web",
    "notion",
    "file",
]
KnowledgeStatus = Literal["ok", "no_matches", "disabled", "unavailable"]


class DriveAllowlistEntry(BaseModel):
    id: str
    source_type: SourceType = "book"
    domains: list[str] = Field(default_factory=list)
    experts: list[str] = Field(default_factory=list)
    framework_tags: list[str] = Field(default_factory=list)
    recursive: bool = True


class DriveAllowlist(BaseModel):
    files: list[DriveAllowlistEntry] = Field(default_factory=list)
    folders: list[DriveAllowlistEntry] = Field(default_factory=list)


class PrivateSourceMetadata(BaseModel):
    doc_id: str
    title: str
    source_type: SourceType
    language: str
    domains: list[str] = Field(default_factory=list)
    experts: list[str] = Field(default_factory=list)
    framework_tags: list[str] = Field(default_factory=list)
    drive_file_id: str
    content_hash: str
    modified_time: str | None = None


class KnowledgeRetrievalResult(BaseModel):
    status: KnowledgeStatus
    chunks: list[dict[str, Any]] = Field(default_factory=list)
    error_code: str | None = None


class SyncDocumentState(BaseModel):
    doc_id: str
    remote_version: str
    content_hash: str
    last_ingested_at: str
    chunks: int


class SyncState(BaseModel):
    version: int = 1
    documents: dict[str, SyncDocumentState] = Field(default_factory=dict)


class SyncReport(BaseModel):
    scanned: int = 0
    skipped: int = 0
    updated: int = 0
    deleted: int = 0
    failed: int = 0
    failed_doc_ids: list[str] = Field(default_factory=list)
