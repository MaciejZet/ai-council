from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.knowledge.private_models import DriveAllowlist, DriveAllowlistEntry

DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
GOOGLE_FOLDER_MIME = "application/vnd.google-apps.folder"
GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
FILE_FIELDS = "id,name,mimeType,modifiedTime,md5Checksum,parents"


@dataclass(frozen=True)
class DriveSourceRecord:
    file_id: str
    name: str
    mime_type: str
    modified_time: str | None
    md5_checksum: str | None
    allowlist_entry: DriveAllowlistEntry


class DriveSourceClient:
    def __init__(self, service: Any | None = None):
        self._service = service

    def _get_service(self):
        if self._service is None:
            import google.auth
            from googleapiclient.discovery import build

            credentials, _ = google.auth.default(scopes=[DRIVE_READONLY_SCOPE])
            self._service = build(
                "drive",
                "v3",
                credentials=credentials,
                cache_discovery=False,
            )
        return self._service

    def _record_from_metadata(
        self,
        metadata: dict[str, Any],
        allowlist_entry: DriveAllowlistEntry,
    ) -> DriveSourceRecord:
        return DriveSourceRecord(
            file_id=str(metadata["id"]),
            name=str(metadata.get("name", metadata["id"])),
            mime_type=str(metadata.get("mimeType", "application/octet-stream")),
            modified_time=metadata.get("modifiedTime"),
            md5_checksum=metadata.get("md5Checksum"),
            allowlist_entry=allowlist_entry,
        )

    def _get_file(self, entry: DriveAllowlistEntry) -> DriveSourceRecord:
        payload = (
            self._get_service()
            .files()
            .get(fileId=entry.id, fields=FILE_FIELDS)
            .execute()
        )
        if payload.get("mimeType") == GOOGLE_FOLDER_MIME:
            raise ValueError(f"Allowlisted file id {entry.id!r} points to a folder")
        return self._record_from_metadata(payload, entry)

    def _list_folder(
        self,
        entry: DriveAllowlistEntry,
        folder_id: str,
    ) -> list[DriveSourceRecord]:
        records: list[DriveSourceRecord] = []
        page_token: str | None = None
        while True:
            query = f"'{folder_id}' in parents and trashed = false"
            response = (
                self._get_service()
                .files()
                .list(
                    q=query,
                    fields=f"nextPageToken,files({FILE_FIELDS})",
                    pageToken=page_token,
                )
                .execute()
            )
            for metadata in response.get("files", []):
                if metadata.get("mimeType") == GOOGLE_FOLDER_MIME:
                    if entry.recursive:
                        records.extend(self._list_folder(entry, str(metadata["id"])))
                    continue
                records.append(self._record_from_metadata(metadata, entry))
            page_token = response.get("nextPageToken")
            if not page_token:
                break
        return records

    def list_allowed(self, allowlist: DriveAllowlist) -> list[DriveSourceRecord]:
        records = [self._get_file(entry) for entry in allowlist.files]
        for entry in allowlist.folders:
            records.extend(self._list_folder(entry, entry.id))

        deduplicated: dict[str, DriveSourceRecord] = {}
        for record in records:
            deduplicated.setdefault(record.file_id, record)
        return list(deduplicated.values())

    def read_bytes(self, record: DriveSourceRecord) -> bytes:
        files = self._get_service().files()
        if record.mime_type == GOOGLE_DOC_MIME:
            payload = files.export_media(fileId=record.file_id, mimeType="text/plain").execute()
        elif record.mime_type.startswith("application/vnd.google-apps."):
            raise ValueError(f"Unsupported Google Workspace MIME type: {record.mime_type}")
        else:
            payload = files.get_media(fileId=record.file_id).execute()

        if isinstance(payload, str):
            return payload.encode("utf-8")
        return bytes(payload)
