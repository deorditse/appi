# --- commands.py (или в том же файле над main) ---
import re
from typing import Iterable

# Списки команд
START_COMMANDS = ["Шаня", "Привет Шаня", "Шанни", "Шань"]
PAUSE_COMMANDS = ["пауза", "замри", "подожди", "стоп", "останови"]
RESUME_COMMANDS = ["продолжи", "продолжить", "возобнови", "продолжай"]


def _normalize(s: str) -> str:
    return (s or "").strip().lower()


def _any_word_in_text(text: str, words: Iterable[str]) -> bool:
    """Матчим целые слова, а не подстроки (пример: 'стоп' ≠ 'ростопырка')."""
    text = _normalize(text)
    for w in words:
        w = _normalize(w)
        if not w:
            continue
        if re.search(rf"\b{re.escape(w)}\b", text):
            return True
    return False


def is_start(text: str) -> bool:
    return _any_word_in_text(text, START_COMMANDS)

def is_pause(text: str) -> bool:
    return _any_word_in_text(text, PAUSE_COMMANDS)

def is_resume(text: str) -> bool:
    return _any_word_in_text(text, RESUME_COMMANDS)
