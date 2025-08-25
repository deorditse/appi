from typing import Optional

from openai import OpenAI, APIConnectionError, APIStatusError, RateLimitError

from infrastructure.utils.utils import api_key_openai

from infrastructure.services.llm.llm import LLMService


class OpenAiLLMService(LLMService):
    def __init__(self, system_message: Optional[str] = None, model: Optional[str] = None) -> None:
        super().__init__(system_message=system_message, model=model)
        self._client = OpenAI(api_key=api_key_openai())
        self._model = model or 'gpt-5'

    def audio(self):
        pass

    def text(self, prompt: str) -> str:
        """Текст → текст (через Responses API)."""
        try:
            resp = self._client.responses.create(
                model=self._model,
                input=prompt,
                instructions=self._system_message
            )
            # Для Responses API общий текст можно получить так:
            return resp.output_text  # эквивалентно сборке из контента
        except (APIConnectionError, APIStatusError, RateLimitError) as e:
            raise RuntimeError(f"OpenAI API error (send_text): {e}") from e
