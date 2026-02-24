from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Paper:
    paper_id: str
    title: str
    authors: List[str]
    abstract: str
    date: str
    link: str
    pdf_link: Optional[str]
    source: str = ""
    doi: Optional[str] = None
    journal: Optional[str] = None
