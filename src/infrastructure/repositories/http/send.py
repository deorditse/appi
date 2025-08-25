from pathlib import Path
import sounddevice as sd
import os

from infrastructure.services.llm.src.openai_impl import OpenAiLLMService


class SendHttp:
    async def send_audio_file(self, path: Path, samplerate: int):
        svc = OpenAiLLMService(model="gpt-4o-realtime-preview")
        rate = samplerate
        sd.default.channels = 1
        print(sd.query_devices())

        stream = sd.RawOutputStream(
            samplerate=rate,
            channels=1,
            dtype="int16",
            blocksize=1024,
            latency="low"
        )
        stream.start()
        try:
            got = 0
            async for chunk in svc.audio_stream(path):
                if chunk:
                    stream.write(chunk)
                    got += len(chunk)
            if got == 0:
                print("[WARN] Не пришло ни одного аудио-чанка. Посмотрите лог EVENT.")
        finally:
            stream.stop()
            stream.close()
            try:
                if path.exists():
                    os.remove(path)
                    print(f"[CLEANUP] Файл {path} удалён.")
            except Exception as e:
                print(f"[CLEANUP ERROR] Не удалось удалить {path}: {e}")
