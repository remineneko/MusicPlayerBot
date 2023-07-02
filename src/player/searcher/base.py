from abc import ABC, abstractmethod


class BaseSearcher(ABC):
    @abstractmethod
    def is_valid_url(self, url: str) -> bool:
        raise NotImplementedError("Called BaseSearcher::search.")