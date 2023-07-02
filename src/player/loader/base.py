from abc import ABC, abstractmethod
from src.player.media_metadata import MediaMetadata
from typing import List


class BaseLoader:
    @abstractmethod
    def load(self, url: str) -> List[MediaMetadata]:
        raise NotImplementedError("Called BaseLoader::load")