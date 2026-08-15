from src.knowledge.drive_source import DriveSourceClient
from src.knowledge.private_models import DriveAllowlist, DriveAllowlistEntry


class FakeRequest:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class FakeFilesApi:
    def __init__(self):
        self.list_queries = []
        self.media_ids = []
        self.export_ids = []

    def get(self, *, fileId, fields):
        return FakeRequest(
            {
                "id": fileId,
                "name": f"Synthetic {fileId}",
                "mimeType": "application/pdf",
                "modifiedTime": "2026-08-15T12:00:00Z",
                "md5Checksum": "abc123",
                "parents": [],
            }
        )

    def list(self, *, q, fields, pageToken=None):
        self.list_queries.append(q)
        return FakeRequest(
            {
                "files": [
                    {
                        "id": "child-1",
                        "name": "Synthetic child.pdf",
                        "mimeType": "application/pdf",
                        "modifiedTime": "2026-08-15T12:00:00Z",
                        "md5Checksum": "def456",
                        "parents": ["folder-1"],
                    }
                ]
            }
        )

    def get_media(self, *, fileId):
        self.media_ids.append(fileId)
        return FakeRequest(b"synthetic-pdf-bytes")

    def export_media(self, *, fileId, mimeType):
        self.export_ids.append((fileId, mimeType))
        return FakeRequest(b"synthetic google doc text")


class FakeDriveService:
    def __init__(self):
        self.api = FakeFilesApi()

    def files(self):
        return self.api


def test_drive_lists_only_explicit_files_and_allowlisted_folder_children():
    service = FakeDriveService()
    client = DriveSourceClient(service=service)
    allowlist = DriveAllowlist(
        files=[DriveAllowlistEntry(id="file-1", source_type="synthesis")],
        folders=[DriveAllowlistEntry(id="folder-1", source_type="book")],
    )
    records = client.list_allowed(allowlist)
    assert {record.file_id for record in records} == {"file-1", "child-1"}
    assert service.api.list_queries == ["'folder-1' in parents and trashed = false"]


def test_drive_reads_pdf_bytes_without_writing_to_repo():
    service = FakeDriveService()
    client = DriveSourceClient(service=service)
    record = client._record_from_metadata(
        {
            "id": "pdf-1",
            "name": "Synthetic.pdf",
            "mimeType": "application/pdf",
            "modifiedTime": "2026-08-15T12:00:00Z",
            "md5Checksum": "abc",
        },
        DriveAllowlistEntry(id="pdf-1"),
    )
    assert client.read_bytes(record) == b"synthetic-pdf-bytes"
    assert service.api.media_ids == ["pdf-1"]


def test_drive_exports_google_doc_as_plain_text():
    service = FakeDriveService()
    client = DriveSourceClient(service=service)
    record = client._record_from_metadata(
        {
            "id": "doc-1",
            "name": "Synthetic doc",
            "mimeType": "application/vnd.google-apps.document",
            "modifiedTime": "2026-08-15T12:00:00Z",
        },
        DriveAllowlistEntry(id="doc-1", source_type="synthesis"),
    )
    assert client.read_bytes(record) == b"synthetic google doc text"
    assert service.api.export_ids == [("doc-1", "text/plain")]
