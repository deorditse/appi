import os

from dotenv import load_dotenv

load_dotenv()


def get_env(name: str, default=None) -> str:
    value = os.getenv(name)
    if value is None and default is None:
        raise RuntimeError(f"Undefined environment variable {name}")
    return value or default
