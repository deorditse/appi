from abc import abstractmethod, ABC
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class LLMService(ABC):
    def __init__(
            self,
            system_message: Optional[str] = None,
            model: Optional[str] = None,
    ):
        self._system_message = system_message

    @abstractmethod
    def audio_stream(
            self,
            path: Path,
            *,
            voice: str,
            prompt: str
    ):
        """Отправляет WAV в модель и сохраняет голосовой ответ в reply_path."""
        raise NotImplementedError

    @abstractmethod
    def text(self, prompt: str):
        """Отправляет текст в модель"""
        raise NotImplementedError
