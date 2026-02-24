from src.models import Paper
from src.zotero_sync import _paper_to_zotero_item


def test_preprint_payload_does_not_use_publication_title():
    paper = Paper(
        paper_id="2602.12345",
        title="ArXiv Title",
        authors=["Jane Doe"],
        abstract="A",
        date="2026-02-23",
        link="https://arxiv.org/abs/2602.12345",
        pdf_link="https://arxiv.org/pdf/2602.12345.pdf",
        source="arxiv",
        doi="10.48550/arXiv.2602.12345",
        journal="arXiv",
    )
    item = _paper_to_zotero_item(paper, score=90, tags=["ml"], reasons=["good"])
    assert item["itemType"] == "preprint"
    assert "publicationTitle" not in item
    assert item.get("archive") == "arXiv"
    assert item.get("archiveLocation") == "2602.12345"


def test_journal_payload_uses_publication_title():
    paper = Paper(
        paper_id="doi:10.1000/x",
        title="Journal Title",
        authors=["John Doe"],
        abstract="B",
        date="2026-02-23",
        link="https://doi.org/10.1000/x",
        pdf_link=None,
        source="crossref",
        doi="10.1000/x",
        journal="Biometrika",
    )
    item = _paper_to_zotero_item(paper, score=91, tags=["stats"], reasons=["nice"])
    assert item["itemType"] == "journalArticle"
    assert item.get("publicationTitle") == "Biometrika"
