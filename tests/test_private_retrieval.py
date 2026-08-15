from types import SimpleNamespace

from src.knowledge import retriever


class FakeIndex:
    def __init__(self, matches=None, error=None):
        self.matches = matches or []
        self.error = error
        self.calls = []

    def query(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(matches=self.matches)


def test_private_retrieval_uses_namespace_and_expert_domain_filters(monkeypatch):
    match = SimpleNamespace(
        score=0.82,
        metadata={
            "text": "Synthetic retrieved text.",
            "title": "Synthetic Source",
            "source_type": "synthesis",
            "language": "en",
            "domains": ["pricing"],
            "experts": ["monetization"],
            "framework_tags": ["synthetic-framework"],
            "chunk_index": 4,
            "total_chunks": 9,
            "doc_id": "synthetic-doc-id",
        },
    )
    index = FakeIndex([match])
    monkeypatch.setattr(retriever, "get_query_embedding", lambda query: [0.1, 0.2])
    monkeypatch.setattr(retriever, "get_pinecone_index", lambda: index)

    result = retriever.query_knowledge_result(
        "synthetic pricing question",
        domains=["pricing"],
        experts=["monetization"],
        namespace="private-test",
    )

    assert result.status == "ok"
    assert result.chunks[0]["doc_id"] == "synthetic-doc-id"
    assert index.calls[0]["namespace"] == "private-test"
    assert index.calls[0]["filter"] == {
        "$and": [
            {"domains": {"$in": ["pricing"]}},
            {"experts": {"$in": ["monetization"]}},
        ]
    }


def test_private_retrieval_reports_no_matches(monkeypatch):
    index = FakeIndex([])
    monkeypatch.setattr(retriever, "get_query_embedding", lambda query: [0.1])
    monkeypatch.setattr(retriever, "get_pinecone_index", lambda: index)
    result = retriever.query_knowledge_result("synthetic", namespace="private-test")
    assert result.status == "no_matches"
    assert result.chunks == []


def test_private_retrieval_reports_unavailable_on_pinecone_error(monkeypatch):
    index = FakeIndex(error=RuntimeError("synthetic pinecone failure"))
    monkeypatch.setattr(retriever, "get_query_embedding", lambda query: [0.1])
    monkeypatch.setattr(retriever, "get_pinecone_index", lambda: index)
    result = retriever.query_knowledge_result("synthetic", namespace="private-test")
    assert result.status == "unavailable"
    assert result.error_code == "pinecone_query_failed"
    assert result.chunks == []


def test_agent_context_preserves_provenance_without_filesystem_paths():
    context = retriever.format_context_for_agent(
        [
            {
                "text": "Synthetic retrieved text.",
                "title": "Synthetic Source",
                "source_type": "synthesis",
                "doc_id": "synthetic-doc-id",
                "chunk_index": 4,
                "score": 0.82,
            }
        ],
        include_provenance=True,
    )
    assert "Synthetic Source" in context
    assert "synthetic-doc-id" in context
    assert "Synthetic retrieved text." in context
    assert "source_path" not in context


def test_display_sources_do_not_include_private_excerpt_by_default():
    sources = retriever.format_sources_for_display(
        [
            {
                "text": "Synthetic private text that must not be exposed by default.",
                "title": "Synthetic Source",
                "category": "strategia",
                "language": "en",
                "source_type": "synthesis",
                "domains": ["strategy"],
                "score": 0.82,
                "chunk_index": 1,
            }
        ]
    )
    assert "text" not in sources[0]
    assert "chunks_used" in sources[0]
    assert "text" not in sources[0]["chunks_used"][0]
