import base64
import json
import ssl
from abc import ABC
from pathlib import Path
from typing import Optional, AsyncIterator

import certifi
import websockets
from openai import OpenAI, APIConnectionError, APIStatusError, RateLimitError

from infrastructure.utils.utils import api_key_openai

from infrastructure.services.llm.llm import LLMService


class OpenAiLLMService(LLMService, ABC):
    def __init__(
            self,
            system_message: Optional[str] = None,
            model: str = "gpt-5",
    ) -> None:
        super().__init__(system_message=system_message, model=model)
        self._client = OpenAI(api_key=api_key_openai())
        self._model = model

    async def audio_stream(
            self,
            path: Path,
            *,
            voice: str = "alloy",
            prompt: str = "Ответь на вопрос из этого аудиофайла подробно и по сути.",
    ) -> AsyncIterator[bytes]:
        """Отправляет локальный аудиофайл целиком в Realtime API и стримит PCM16 чанки (bytes)."""
        if not path.exists():
            raise FileNotFoundError(path)

        url = f"wss://api.openai.com/v1/realtime?model={self._model}"
        headers_list = [
            ("Authorization", f"Bearer {self._client.api_key}"),
            ("OpenAI-Beta", "realtime=v1"),
        ]

        ssl_ctx = ssl.create_default_context()
        ssl_ctx.load_verify_locations(cafile=certifi.where())

        ws_ctx = websockets.connect(url, additional_headers=headers_list, max_size=None, ssl=ssl_ctx)

        async with ws_ctx as ws:
            # 0) настройка сессии: голос + «безопасный» VAD
            await ws.send(json.dumps({
                "type": "session.update",
                "session": {
                    "instructions": self._system_message or prompt,
                    "voice": voice,
                    "output_audio_format": "pcm16",
                    # "input_audio_format": "pcm16",
                }
            }))

            # 1) отправка ВЕСЬ файл одним append
            audio_b64 = base64.b64encode(path.read_bytes()).decode("ascii")
            await ws.send(json.dumps({"type": "input_audio_buffer.append", "audio": audio_b64}))
            await ws.send(json.dumps({"type": "input_audio_buffer.commit"}))

            # 2) запрос ответа (разрешены только ["text"] или ["audio","text"])
            await ws.send(json.dumps({
                "type": "response.create",
                "response": {"modalities": ["audio", "text"]}
            }))

            # 3) читаем события с логом
            async for raw in ws:
                evt = json.loads(raw)
                et = evt.get("type")
                # --- ВКЛЮЧИТЕ ЛОГ НА ПЕРВЫЕ ТЕСТЫ ---
                print("EVENT:", et, {k: v for k, v in evt.items() if k not in ("audio", "delta")})
                if et == "response.audio.delta":
                    yield base64.b64decode(evt["audio"])  # PCM16 mono 24 kHz
                elif et in ("response.audio.done", "response.done"):
                    break
                elif et == "response.delta":
                    # при желании соберите текст
                    pass
                elif et == "error":
                    raise RuntimeError(f"Realtime error: {evt}")

    def text(self, prompt: str) -> str:
        """Текст → текст (через Responses API)."""
        try:
            resp = self._client.responses.create(
                model="gpt-4o-mini",  # используйте обычную текстовую модель
                input=prompt,
                instructions=self._system_message or "Отвечай кратко и по делу.",
                temperature=0.2,
            )
            return resp.output_text.strip()
        except (APIConnectionError, APIStatusError, RateLimitError) as e:
            raise RuntimeError(f"OpenAI API error (send_text): {e}") from e
