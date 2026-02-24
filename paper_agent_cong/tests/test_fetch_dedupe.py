from src.models import Paper
from src import pipeline_engine as pe


class _FakeArxivProvider:
    def __init__(self, *args, **kwargs):
        pass

    def fetch(self):
        return [
            Paper(
                paper_id="a1",
                title="Same Paper",
                authors=[],
                abstract="",
                date="2026-02-23",
                link="https://arxiv.org/abs/a1",
                pdf_link="https://arxiv.org/pdf/a1.pdf",
                source="arxiv",
                doi="10.1000/dup",
                journal="arXiv",
            )
        ]


class _FakeCrossrefProvider:
    def __init__(self, *args, **kwargs):
        pass

    def fetch(self):
        return [
            Paper(
                paper_id="doi:10.1000/dup",
                title="Same Paper",
                authors=[],
                abstract="",
                date="2026-02-23",
                link="https://doi.org/10.1000/dup",
                pdf_link=None,
                source="crossref",
                doi="10.1000/dup",
                journal="Biometrika",
            )
        ]


def test_fetch_all_sources_dedupes_by_doi(monkeypatch):
    monkeypatch.setattr(pe, "ArxivProvider", _FakeArxivProvider)
    monkeypatch.setattr(pe, "CrossrefProvider", _FakeCrossrefProvider)
    papers = pe.fetch_all_sources(
        arxiv_cfg={
            "enabled": True,
            "categories": ["cs.LG"],
            "per_category_max_results": 1,
            "retries": 1,
            "request_delay_seconds": 0.0,
            "user_agent": "ua",
        },
        crossref_cfg={
            "enabled": True,
            "journals": ["Biometrika"],
            "max_results_per_journal": 1,
            "from_days": 7,
            "request_delay_seconds": 0.0,
            "user_agent": "ua",
            "arxiv_pdf_fallback": 0,
        },
    )
    assert len(papers) == 1
    assert papers[0].doi == "10.1000/dup"
