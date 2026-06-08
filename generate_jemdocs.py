import yaml
import re
import html
import sys
from collections import defaultdict


def slugify(value):
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "section"


def split_legacy_venue_links(venue):
    if not venue:
        return "", []

    text = venue
    links = []
    patterns = [
        r"\[(\S+)\s+\\\[(.*?)\\\]\]",
        r"\[(\S+)\s+\[(.*?)\]\]",
    ]

    for pattern in patterns:
        while True:
            m = re.search(pattern, text)
            if not m:
                break
            links.append({"url": m.group(1), "label": m.group(2)})
            text = (text[:m.start()] + text[m.end():]).strip()

    text = re.sub(r"\s{2,}", " ", text).strip(" ,;")
    return text, links


def render_links(pub):
    links = list(pub.get("links") or [])
    _, legacy_links = split_legacy_venue_links((pub.get("venue") or "").strip())
    links.extend(legacy_links)
    parts = []
    for link in links:
        url = link.get("url", "")
        label = link.get("label", "Link")
        if url:
            parts.append(f"[{url} \\[{label}\\]]")
    return " ".join(parts)


def render_pub(pub):
    arxiv = pub.get("arxiv", "")
    line = f"- [{arxiv} {pub['title']}] \\n\n{pub['authors']}"
    venue, _ = split_legacy_venue_links((pub.get("venue") or "").strip())
    links = render_links(pub)
    if venue:
        line += f"; /{venue}/"
    if links:
        if venue:
            line += f" {links}"
        else:
            line += f"; {links}"
    line += "\n\n"
    return line


def transform_pub_entry(match):
    """Transform a compiled jemdoc <ul><li><p>...</p></li></ul> entry into a pub-entry card."""
    content = match.group(1).strip()
    br_parts = content.split(" <br />\n", 1)
    title_html = br_parts[0].strip()
    meta_text = br_parts[1].strip() if len(br_parts) > 1 else ""

    # Extract [Label] resource links
    link_re = re.compile(r'<a\s[^>]*href="([^"]*)"[^>]*>\[([^\]]+)\]</a>')
    link_matches = link_re.findall(meta_text)
    links_html = "".join(
        f'<a class="pub-link-btn" href="{url}" target="_blank" rel="noopener noreferrer">{label}</a>'
        for url, label in link_matches
    )
    authors_venue = link_re.sub("", meta_text).strip().rstrip(";").strip()

    venue_match = re.search(r";\s*<i>(.*?)</i>", authors_venue)
    if venue_match:
        venue_html = f"<i>{venue_match.group(1)}</i>"
        authors = authors_venue[: venue_match.start()].strip()
    else:
        venue_html = ""
        authors = authors_venue

    meta_parts = [f'<span class="pub-authors">{authors}</span>']
    if venue_html:
        meta_parts.append(f'<span class="pub-venue">{venue_html}</span>')
    if links_html:
        meta_parts.append(f'<span class="pub-links">{links_html}</span>')

    return (
        f'<div class="pub-entry">'
        f'<div class="pub-title">{title_html}</div>'
        f'<div class="pub-meta">{"".join(meta_parts)}</div>'
        f"</div>"
    )


def postprocess_pub_entries(path):
    with open(path, "r") as f:
        content = f.read()
    pattern = re.compile(r"<ul>\n<li><p>(.*?)\n</p>\n</li>\n</ul>", re.DOTALL)
    updated = pattern.sub(transform_pub_entry, content)
    with open(path, "w") as f:
        f.write(updated)


def render_selection_marker(marker):
    return f"{marker}\n\n"


def render_anchor(anchor):
    return f'{{{{<a id="{anchor}"></a>}}}}\n'


def build_selection_bar_html(label, items):
    links = " ".join(
        f'<a href="#{html.escape(anchor, quote=True)}">{html.escape(text)}</a>'
        for text, anchor in items
    )
    return (
        f'<div class="pub-selection-bar"><span class="pub-selection-label">{html.escape(label)}</span>'
        f"{links}</div>"
    )


def postprocess_generated_html(path, marker, label, items):
    with open(path, "r") as f:
        content = f.read()

    replacement = build_selection_bar_html(label, items)
    pattern = re.compile(rf"<p>\s*{re.escape(marker)}\s*</p>", re.DOTALL)
    updated = pattern.sub(replacement, content, count=1)

    with open(path, "w") as f:
        f.write(updated)


def load_publications():
    with open("publications.yaml", "r") as f:
        publications = yaml.safe_load(f)

    by_year = defaultdict(list)
    by_topic = defaultdict(list)

    for pub in publications:
        by_year[pub["year"]].append(pub)
        topics = pub.get("topics") or []
        if isinstance(topics, str):
            topics = [topics]
        for topic in topics:
            by_topic[topic].append(pub)

    return publications, by_year, by_topic


def build_publication_outputs():
    publications, by_year, by_topic = load_publications()

    paper_by_year = "# jemdoc: menu{menu}{paper.jemdoc}\n= Publications\n\n"
    year_order = sorted(by_year.keys(), reverse=True)

    for year in year_order:
        paper_by_year += render_anchor(f"year-{year}")
        paper_by_year += f"== {year}\n\n"
        for pub in by_year[year]:
            paper_by_year += render_pub(pub)

    paper_by_topic = "# jemdoc: menu{menu}{paper_topic.jemdoc}\n= Publications by topics\n\n"

    custom_topic_order = [
        "Reinforcement learning and bandits",
        "Transfer learning",
        "Multi-modal learning",
        "Low-rank matrix estimation",
        "Scaled gradient descent",
        "Ranking",
        "Others",
    ]

    remaining_topics = [t for t in by_topic.keys() if t not in custom_topic_order]
    ordered_topics = custom_topic_order + sorted(remaining_topics)
    available_topics = [topic for topic in ordered_topics if topic in by_topic]
    topic_selection_items = [(topic, f"topic-{slugify(topic)}") for topic in available_topics]

    paper_by_topic += render_selection_marker("PUBLICATIONTOPICSELECTIONBAR")

    for topic in available_topics:
        paper_by_topic += render_anchor(f"topic-{slugify(topic)}")
        paper_by_topic += f"== {topic}\n\n"
        for pub in by_topic[topic]:
            paper_by_topic += render_pub(pub)

    return paper_by_year, paper_by_topic, topic_selection_items


def write_jemdoc_outputs():
    paper_by_year, paper_by_topic, _ = build_publication_outputs()

    with open("paper.jemdoc", "w") as f:
        f.write(paper_by_year)

    with open("paper_topic.jemdoc", "w") as f:
        f.write(paper_by_topic)


def postprocess_html_outputs():
    _, _, topic_selection_items = build_publication_outputs()
    postprocess_generated_html(
        "paper_topic.html",
        "PUBLICATIONTOPICSELECTIONBAR",
        "Jump to:",
        topic_selection_items,
    )
    postprocess_pub_entries("paper.html")
    postprocess_pub_entries("paper_topic.html")


if __name__ == "__main__":
    if "--postprocess-html" in sys.argv:
        postprocess_html_outputs()
    else:
        write_jemdoc_outputs()
