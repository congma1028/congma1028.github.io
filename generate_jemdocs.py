import yaml
from collections import defaultdict

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
for year in sorted(by_year.keys(), reverse=True):
    paper_by_year += f"== {year}\n\n"
    for pub in by_year[year]:
        arxiv = pub.get("arxiv", "")
        paper_by_year += f"- [{arxiv} {pub['title']}] \\n\n{pub['authors']} \\n\n"
        if pub["venue"]:
            paper_by_year += f"/{pub['venue']}/\n"
    
        paper_by_year += "\n"

# Generate paper_topic.jemdoc (by topic)
paper_by_topic = "# jemdoc: menu{menu}{paper_topic.jemdoc}\n= Publications by topics\n\n"

custom_topic_order = [
    "Multi-modal learning",
    "Transfer learning",
    "Reinforcement learning",
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
        arxiv = pub.get("arxiv", "")
        paper_by_topic += f"- [{arxiv} {pub['title']}] \\n\n{pub['authors']} \\n\n"
        if pub["venue"]:
            paper_by_topic += f"/{pub['venue']}/\n"
        paper_by_topic += "\n"

# Write output files
with open("paper.jemdoc", "w") as f:
    f.write(paper_by_year)

with open("paper_topic.jemdoc", "w") as f:
    f.write(paper_by_topic)
