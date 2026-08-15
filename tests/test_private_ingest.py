from src.knowledge import ingest
from src.knowledge.private_models import PrivateSourceMetadata


class FakeIndex:
    def __init__(self, fail_upsert=False):
        self.fail_upsert = fail_upsert
        self.upserts = []
        self.deletes = []

    def upsert(self, **kwargs):
        if self.fail_upsert:
            raise RuntimeError("synthetic upsert failure")
        self.upserts.append(kwargs)

    def delete(self, **kwargs):
        self.deletes.append(kwargs)


def metadata():
    return PrivateSourceMetadata(
        doc_id="stable-id",
        title="Synthetic Source",
        source_type="book",
        language="en",
        domains=["strategy"],
        experts=["strategy"],
        framework_tags=["synthetic-framework"],
        drive_file_id="synthetic-drive-id",
        content_hash="content-hash",
        modified_time="2026-08-15T12:00:00Z",
    )


def test_identity_helpers_are_deterministic_and_content_sensitive():
    assert ingest.content_sha256("abc") == ingest.content_sha256(b"abc")
    assert ingest.stable_doc_id("gdrive", "file-1") == ingest.stable_doc_id("gdrive", "file-1")
    assert ingest.generate_chunk_id("doc", "hash-a", 1) != ingest.generate_chunk_id(
        "doc", "hash-b", 1
    )


def test_upsert_text_document_uses_private_namespace_and_metadata(monkeypatch):
    index = FakeIndex()
    monkeypatch.setattr(ingest, "get_pinecone_index", lambda: index)
    monkeypatch.setattr(ingest, "get_embeddings", lambda texts: [[0.1, 0.2] for _ in texts])
    monkeypatch.setattr(
        ingest,
        "chunk_text",
        lambda text: [{"text": "synthetic chunk", "chunk_index": 0, "start_char": 0, "end_char": 15}],
    )

    result = ingest.upsert_text_document("synthetic", metadata(), namespace="private-test")

    assert result["chunks_count"] == 1
    assert index.upserts[0]["namespace"] == "private-test"
    vector = index.upserts[0]["vectors"][0]
    assert vector["metadata"]["doc_id"] == "stable-id"
    assert vector["metadata"]["domains"] == ["strategy"]
    assert "source_path" not in vector["metadata"]
    assert index.deletes[0]["namespace"] == "private-test"


def test_upsert_failure_does_not_delete_previous_vectors(monkeypatch):
    index = FakeIndex(fail_upsert=True)
    monkeypatch.setattr(ingest, "get_pinecone_index", lambda: index)
    monkeypatch.setattr(ingest, "get_embeddings", lambda texts: [[0.1] for _ in texts])
    monkeypatch.setattr(
        ingest,
        "chunk_text",
        lambda text: [{"text": "synthetic", "chunk_index": 0, "start_char": 0, "end_char": 9}],
    )

    try:
        ingest.upsert_text_document("synthetic", metadata(), namespace="private-test")
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected synthetic upsert failure")

    assert index.deletes == []
