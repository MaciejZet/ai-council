from scripts.check_private_corpus import check_paths


def test_guard_rejects_private_working_paths():
    violations = check_paths(
        [
            "private_knowledge/export.txt",
            "drive_exports/book.pdf",
            ".private_knowledge/state.json",
        ]
    )
    assert len(violations) == 3


def test_guard_rejects_ebook_formats_anywhere():
    assert check_paths(["assets/book.epub"])
    assert check_paths(["docs/library.azw3"])


def test_guard_allows_public_docs_and_test_pdf():
    assert check_paths(
        [
            "docs/architecture.md",
            "tests/fixtures/public-domain-sample.pdf",
        ]
    ) == []
