# Daily Paper Assistant

## Goal
Run a daily pipeline that:
1. fetches recent papers from enabled sources (currently arXiv + Crossref),
2. performs first-pass filtering/ranking with a configurable LLM using title + abstract,
3. performs second-pass enrichment by reading full paper text (appendix removed),
4. generates a LaTeX digest and compiled PDF.

## Project Structure

```text
paper_agent_cong/
  SPEC.md
  requirements.txt
  config/
    interests.yaml
    sources.yaml
    runtime.yaml
  src/
    __init__.py
    models.py
    papers.py          # thin CLI entrypoint
    pipeline_engine.py # pipeline orchestration
    pipeline_cli.py
    config_sources.py
    source_fetch.py
    first_pass.py
    second_pass.py
    llm_client.py
    pdf_processing.py
    digest.py
    core/
      database.py
    providers/
      base.py
      arxiv.py
      crossref.py
  digests/
  build/
  logs/
```

## Configuration

Runtime config is read from files (not hardcoded):

- Research interests: `config/interests.yaml`
- Sources: `config/sources.yaml`
- Runtime knobs: `config/runtime.yaml`

`interests.yaml` supports:
- `interests`: string or list (required for prompt context; `research_profile` is also accepted as fallback)
- `exclude_topics`: optional list/string of case-insensitive phrases; papers matching title+abstract are removed before first pass

Supported `sources.yaml` shape (current implementation):

```yaml
arxiv:
  enabled: true
  categories:
    - cs.LG
  per_category_max_results: 10
  lookback_hours: 24
  align_to_submission_deadline: true
  retries: 5
  request_delay_seconds: 15.0
  user_agent: "paper-agent-daily-digest/1.0 (+mailto:you@example.com)"

crossref:
  enabled: true
  arxiv_pdf_fallback: 1
  journals:
    - Annals of Statistics
    - Journal of the American Statistical Association
  max_results_per_journal: 10
  from_days: 14
  request_delay_seconds: 1.0
  user_agent: "paper-agent-daily-digest/1.0 (+mailto:you@example.com)"
```

## CLI

Main command:

```bash
python -m src.papers run
```

Fetch-only stage test (no LLM calls):

```bash
python -m src.papers fetch-pdfs
```

Both commands support `--force`.

`run` pipeline steps:

1. Preflight-check LLM provider/model/API key before fetch.
2. Fetch from enabled sources in config.
3. Deduplicate across sources (DOI -> arXiv id -> normalized title key).
4. First-pass LLM filter/rank using full title + full abstract.
5. Second-pass LLM enrichment on shortlisted papers using full paper text with appendix removed.
6. Keep papers sorted by first-pass score; second pass processes top-`SECOND_PASS_LIMIT` (default 20, `0` means all).
7. Write digest TeX and compile digest PDF.

arXiv fetch behavior:
- Uses one combined category query.
- Sorts by `submittedDate` descending.
- Keeps only papers in a 24-hour window (`lookback_hours`), optionally aligned to arXiv submission cutoff (`align_to_submission_deadline: true`, 14:00 US/Eastern window boundary).

## LLM Provider Selection

Provider is selected at runtime with environment variables:

- `LLM_PROVIDER`: `gemini` | `openai` | `openai_compatible` | `ollama`
- `LLM_MODEL`: model id for selected provider

Provider-specific credentials/endpoints:

- Gemini: `GEMINI_API_KEY`
- OpenAI: `OPENAI_API_KEY` (optional `OPENAI_BASE_URL`)
- OpenAI-compatible: `LLM_BASE_URL`, optional `LLM_API_KEY`
- Ollama: optional `OLLAMA_BASE_URL` (default `http://localhost:11434`)

## LLM Evaluation Output

First-pass evaluation includes:

- `include` (bool)
- `score` (0-100 int)
- `confidence` (`low` | `medium` | `high`)
- `reasons` (1-3 short bullets)
- `tags` (3-6 keywords)
- `summary` (2-3 sentences)

First-pass cache:
- SQLite table `llm_eval_cache` in `data/paper_agent.db`

Paper status persistence:

- SQLite table `papers` in `data/paper_agent.db`
- Status lifecycle: `fetched` -> `shortlisted`/`rejected` -> `digested`
- Status is tracked for persistence/reporting.

Second-pass cache:

- `logs/llm_report_cache.json`

Daily first-pass usage log:

- `logs/llm_usage_YYYY-MM-DD.json`

Daily second-pass usage log:

- `logs/llm_report_usage_YYYY-MM-DD.json`

Daily error log:

- `logs/llm_errors_YYYY-MM-DD.log`

## Runtime Knobs (`config/runtime.yaml`)

Controls to reduce cost/quota usage and tune filtering:

- `llm_max_concurrency`
- `first_pass_limit` (primary knob; how many fetched papers are sent to first-pass LLM after lexical prefilter ranking.
  `0` or negative means no first-pass cap, i.e., evaluate all fetched papers)
- `second_pass_limit` (how many first-pass shortlisted papers go to full-text second pass.
  `0` or negative means no second-pass cap, i.e., process all shortlisted papers)
- `report_max_concurrency` (second-pass full-text LLM concurrency)
- `first_pass_temperature` (default `0.1`; lower = stricter/more deterministic first-pass judgments)
- `second_pass_temperature` (default `0.1`; lower = more stable second-pass summaries/tags)
- `llm_retry_max_attempts` (default `5`, clamp `1..10`; max retry attempts for provider HTTP calls)
- `zotero_sync_score_threshold` (default `85`; papers with score strictly above this are synced)
- `clear_db_cache_on_run` (default `false`; when true, clears SQLite cache DB at run start)
- `exclude_topics` (runtime-level fallback list; merged with `interests.yaml` exclusions)

Crossref PDF fallback controls (`sources.yaml`):

- `crossref.arxiv_pdf_fallback` in `sources.yaml` (recommended `1`)
- Optional env override: `CROSSREF_ARXIV_PDF_FALLBACK=0|1`

ArXiv recency controls (`sources.yaml`):

- `arxiv.lookback_hours` (default `24`): fetch window size.
- `arxiv.align_to_submission_deadline` (default `true`): align the 24h window to arXiv-style submission cutoff
  (14:00 America/New_York) instead of rolling `now - lookback_hours`.

## Output Files

- TeX digest: `digests/YYYY-MM-DD.tex`
- PDF digest: `digests/YYYY-MM-DD.pdf`

Digest sections:

- Title page: `Daily Paper Digest --- DATE`
- `Top Papers` section with per-paper fields:
  - Title
  - Authors
  - Link
  - Score
  - Tags
  - 2-3 sentence summary
  - Why relevant (LLM reasons)

## PDF Compilation Rules

- Prefer `tectonic` if installed.
- Otherwise use `pdflatex` in `build/YYYY-MM-DD/`, copy only PDF into `digests/`, then delete build dir.
- Result: `digests/` contains no `.aux`, `.log`, `.toc`, `.out`, etc.

## Setup

Example setup with venv named `paper_agent`:

```bash
cd /Users/congma/Documents/GitHub/paper_agent_cong
python3 -m venv paper_agent
source paper_agent/bin/activate
pip install -r requirements.txt
export LLM_PROVIDER='gemini'
export GEMINI_API_KEY='your_api_key_here'
export LLM_MODEL='gemini-2.5-flash'
# Edit config/runtime.yaml for pass limits, concurrency, temperatures, retries, and Zotero threshold.
python -m src.papers run
```

Stage-1 test with no LLM calls:

```bash
python -m src.papers fetch-pdfs --force
```
