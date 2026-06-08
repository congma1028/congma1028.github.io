# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Site Overview

Personal academic website for Cong Ma (UChicago Statistics). Built with **jemdoc** — a Python-based markup language that compiles `.jemdoc` source files to `.html`.

## Build Commands

**Rebuild all pages:**
```bash
bash update_main.sh
```

**Rebuild a single page:**
```bash
python2 jemdoc.py -c my.conf <page>.jemdoc
```

**Rebuild publications only (full pipeline):**
```bash
python3 generate_jemdocs.py          # generates paper.jemdoc + paper_topic.jemdoc from publications.yaml
python2 jemdoc.py -c my.conf paper.jemdoc
python2 jemdoc.py -c my.conf paper_topic.jemdoc
python3 generate_jemdocs.py --postprocess-html   # injects navigation bars into paper.html + paper_topic.html
```

After rebuilding, run this perl fix to restore broken anchor attributes (jemdoc HTML-escapes quotes):
```bash
perl -pi -e 's/target=&ldquo;_blank&rdquo;/target="_blank"/g; s/rel=&ldquo;noopener noreferrer&rdquo;/rel="noopener noreferrer"/g' index.html paper.html paper_topic.html group.html teaching.html tutorial.html talk.html
```

## Architecture

### Source vs. Generated Files

- **Edit these:** `*.jemdoc`, `publications.yaml`, `jemdoc.css`, `my.conf`, `MENU`
- **Never edit directly:** `paper.jemdoc`, `paper_topic.jemdoc` — auto-generated from `publications.yaml`
- **HTML files** are compiled output; commit them since the site is served directly from the repo

### Publications Pipeline

`publications.yaml` is the single source of truth for all papers. `generate_jemdocs.py` reads it and:
1. Groups papers by year and by topic
2. Writes `paper.jemdoc` (year view) and `paper_topic.jemdoc` (topic view)
3. In `--postprocess-html` mode, injects `<div class="pub-selection-bar">` jump-links into the already-compiled HTML

**YAML schema per entry:**
```yaml
- title: ...
  authors: ...
  year: 2025
  venue: NeurIPS, 2025        # optional
  arxiv: https://arxiv.org/abs/...
  links:                       # optional extra links
    - label: Slides
      url: Publication/foo/slides.pdf
  topics: Reinforcement learning  # string or list
  selected: true               # appears in "Selected papers" section
```

Topic display order is controlled by `custom_topic_order` in `generate_jemdocs.py`.

### jemdoc Configuration

`my.conf` injects a MathJax `<script>` tag via the `[windowtitle]` config block. The `MENU` file defines the site-wide navigation sidebar. `jemdoc.py` (Python 2) is the compiler; `jemdoc` (no extension) is a shell wrapper — use `python2 jemdoc.py` directly.

### CSS

`jemdoc.css` uses CSS custom properties (`--accent`, `--bg-page`, etc.) for theming. The `.pub-selection-bar` class styles the jump navigation injected by `generate_jemdocs.py`.
