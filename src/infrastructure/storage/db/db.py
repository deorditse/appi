from abc import ABC, abstractmethod


class IDatabase(ABC):
    @abstractmethod
    def recognize(self) -> tuple[str, str]:
        """Распознаёт речь и возвращает (распознанный_текст, путь_к_аудио)"""
        pass
