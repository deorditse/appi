from abc import ABC, abstractmethod
from typing import Optional

class ILocalCommandRepository(ABC):
    @abstractmethod
    def get_action_by_phrase(self, phrase: str) -> Optional[str]:
        """Вернуть действие по распознанной фразе (если найдено)"""
        pass

    @abstractmethod
    def add_command(self, phrase: str, action: str) -> None:
        """Добавить новую команду"""
        pass