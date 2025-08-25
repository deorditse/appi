# test_llm.py
import asyncio
from pathlib import Path
import sounddevice as sd
from dotenv import load_dotenv
from infrastructure.services.llm.src.openai_impl import OpenAiLLMService

load_dotenv()


async def main():
    svc = OpenAiLLMService(model="gpt-4o-realtime-preview")
    rate = 24000
    sd.default.channels = 1
    print(sd.query_devices())

    stream = sd.RawOutputStream(samplerate=rate, channels=1, dtype="int16", blocksize=1024, latency="low")
    stream.start()
    try:
        got = 0
        async for chunk in svc.audio_stream(Path("send_audio.pcm")):
            if chunk:
                stream.write(chunk)
                got += len(chunk)
        if got == 0:
            print("[WARN] Не пришло ни одного аудио-чанка. Посмотрите лог EVENT.")
    finally:
        stream.stop();
        stream.close()


if __name__ == "__main__":
    asyncio.run(main())
