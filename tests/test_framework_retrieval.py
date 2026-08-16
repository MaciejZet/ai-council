import src.knowledge.retriever as retriever
from src.knowledge.private_models import KnowledgeRetrievalResult


def test_framework_tags_are_added_only_when_supplied():
    with_framework = retriever._build_filter(
        category=None,
        source_type=None,
        domains=["marketing"],
        experts=["marketing"],
        framework_tags=["positioning"],
    )
    assert {"framework_tags": {"$in": ["positioning"]}} in with_framework["$and"]

    without_framework = retriever._build_filter(
        category=None,
        source_type=None,
        domains=["marketing"],
        experts=["marketing"],
        framework_tags=None,
    )
    assert "framework_tags" not in repr(without_framework)


def test_query_knowledge_forwards_framework_tags(monkeypatch):
    seen = {}

    def fake_result(query, **kwargs):
        seen.update(kwargs)
        return KnowledgeRetrievalResult(status="ok", chunks=[{"text": "x"}])

    monkeypatch.setattr(retriever, "query_knowledge_result", fake_result)

    chunks = retriever.query_knowledge("q", framework_tags=["value_equation"])

    assert chunks == [{"text": "x"}]
    assert seen["framework_tags"] == ["value_equation"]
