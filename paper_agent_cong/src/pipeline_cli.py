import argparse
import datetime as dt
import os
import sys
from typing import List, Optional

from .models import Paper
from . import zotero_sync
from . import pipeline_engine as pe


def run_zotero_test(doi: str, push: bool = False) -> int:
    pe.ensure_dirs()
    client = zotero_sync.build_client()
    if client is None:
        print("Zotero test failed: client not configured.")
        print("Set: ZOTERO_LIBRARY_ID, ZOTERO_LIBRARY_TYPE, ZOTERO_API_KEY")
        return 2

    doi_norm = (doi or "").strip().lower()
    if not doi_norm:
        print("Zotero test failed: DOI is empty.")
        return 2

    print(f"Testing Zotero DOI lookup for: {doi_norm}")
    exists = zotero_sync.doi_in_zotero(client, doi_norm)
    print(f"DOI exists in Zotero: {exists}")
    if not push:
        print("Lookup test complete. Use --push to test create flow.")
        return 0

    if exists:
        print("Push test skipped: DOI already exists in Zotero.")
        return 0

    paper = Paper(
        paper_id=f"doi:{doi_norm}",
        title=f"Zotero Sync Test for {doi_norm}",
        authors=["Paper Agent Test"],
        abstract="This is a test item created by paper agent Zotero integration.",
        date=dt.date.today().isoformat(),
        link=f"https://doi.org/{doi_norm}",
        pdf_link=None,
        source="crossref",
        doi=doi_norm,
        journal="Integration Test",
    )
    ok, zot_url, err = zotero_sync.push_to_zotero(
        client,
        paper,
        score=99,
        tags=["paper-agent", "zotero-test"],
        reasons=["integration test"],
    )
    print(f"Push success: {ok}")
    if zot_url:
        print(f"Created item URL: {zot_url}")
    if err:
        print(f"Push error: {err}")
        return 1
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Daily Paper Assistant")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run fetch -> rank -> digest pipeline")
    run.add_argument("--force", action="store_true", help="Rerun even if today's digest PDF already exists")

    fetch_pdfs = sub.add_parser(
        "fetch-pdfs",
        help="Fetch papers from enabled sources and download PDFs only (no LLM calls)",
    )
    fetch_pdfs.add_argument(
        "--force",
        action="store_true",
        help="Rerun even if today's PDF download output already exists",
    )

    test_zotero = sub.add_parser(
        "test-zotero",
        help="Test Zotero integration (DOI lookup; optional push test)",
    )
    test_zotero.add_argument(
        "--doi",
        default=os.getenv("ZOTERO_TEST_DOI", "10.48550/arXiv.1706.03762"),
        help="DOI to test against Zotero",
    )
    test_zotero.add_argument(
        "--push",
        action="store_true",
        help="Also test push_to_zotero (creates item if DOI not already present)",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        try:
            return pe.run_pipeline(force=bool(getattr(args, "force", False)))
        except pe.ConfigError as e:
            print(f"Config error: {e}", file=sys.stderr)
            return 2
        except Exception as e:
            print(f"Pipeline failed: {e}", file=sys.stderr)
            return 1

    if args.command == "fetch-pdfs":
        try:
            return pe.run_fetch_stage_download_pdfs(force=bool(getattr(args, "force", False)))
        except pe.ConfigError as e:
            print(f"Config error: {e}", file=sys.stderr)
            return 2
        except Exception as e:
            print(f"Fetch stage failed: {e}", file=sys.stderr)
            return 1

    if args.command == "test-zotero":
        try:
            return run_zotero_test(doi=str(getattr(args, "doi", "")), push=bool(getattr(args, "push", False)))
        except Exception as e:
            print(f"Zotero test failed: {e}", file=sys.stderr)
            return 1

    parser.print_help()
    return 0
