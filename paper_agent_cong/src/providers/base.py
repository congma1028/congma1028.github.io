from abc import ABC, abstractmethod
from typing import List

from ..models import Paper


class BaseProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def fetch(self) -> List[Paper]:
        raise NotImplementedError
