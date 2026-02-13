import yaml
import re
from collections import defaultdict


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
    links = list(pub.get("links", []))
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


# Load publications from YAML
with open("publications.yaml", "r") as f:
    publications = yaml.safe_load(f)

# Group by year and topic
by_year = defaultdict(list)
by_topic = defaultdict(list)

for pub in publications:
    by_year[pub["year"]].append(pub)
    topics = pub.get("topics", [])
    if isinstance(topics, str):
        topics = [topics]
    for topic in topics:
        by_topic[topic].append(pub)

# Generate paper.jemdoc (by year)
paper_by_year = "# jemdoc: menu{menu}{paper.jemdoc}\n= Publications\n\n"

selected_pubs = [pub for pub in publications if pub.get("selected")]

if selected_pubs:
    paper_by_year += "== Selected papers\n\n"
    for pub in selected_pubs:
        paper_by_year += render_pub(pub)

for year in sorted(by_year.keys(), reverse=True):
    paper_by_year += f"== {year}\n\n"
    for pub in by_year[year]:
        paper_by_year += render_pub(pub)

# Generate paper_topic.jemdoc (by topic)
paper_by_topic = "# jemdoc: menu{menu}{paper_topic.jemdoc}\n= Publications by topics\n\n"

custom_topic_order = [
"Reinforcement learning",
    "Transfer learning",
    "Multi-modal learning",
    "Low-rank matrix recovery",
    "Scaled gradient descent",
    "Ranking",
    "Others"
]

remaining_topics = [t for t in by_topic.keys() if t not in custom_topic_order]
ordered_topics = custom_topic_order + sorted(remaining_topics)

for topic in ordered_topics:
    if topic in by_topic:

        paper_by_topic += f"== {topic}\n\n"
    for pub in by_topic[topic]:
        paper_by_topic += render_pub(pub)

# Write output files
with open("paper.jemdoc", "w") as f:
    f.write(paper_by_year)

with open("paper_topic.jemdoc", "w") as f:
    f.write(paper_by_topic)
