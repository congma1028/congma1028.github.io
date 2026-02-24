from src.digest import render_tex
from src.models import Paper


def _mk_item(zotero_synced: bool, zotero_url: str = ""):
    return {
        "paper": Paper(
            paper_id="p1",
            title="Test Paper",
            authors=["A B"],
            abstract="abs",
            date="2026-02-23",
            link="https://example.org/paper",
            pdf_link="https://example.org/paper.pdf",
            source="arxiv",
            doi="10.1000/test",
            journal="arXiv",
        ),
        "eval": {
            "score": 91,
            "tags": ["ml", "theory"],
            "summary": "summary",
            "reasons": ["reason 1"],
        },
        "zotero_synced": zotero_synced,
        "zotero_url": zotero_url,
    }


def test_render_tex_adds_zotero_link_marker_when_synced():
    tex = render_tex("2026-02-23", [_mk_item(True, "https://www.zotero.org/users/1/items/ABC")])
    assert r"\href{https://www.zotero.org/users/1/items/ABC}{[Zotero]}" in tex


def test_render_tex_omits_zotero_marker_when_not_synced():
    tex = render_tex("2026-02-23", [_mk_item(False)])
    assert "[Zotero]" not in tex
