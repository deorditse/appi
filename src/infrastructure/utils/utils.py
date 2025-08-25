from common.utils import get_env


def api_key_openai() -> str:
    return get_env('OPENAI_API_KEY')


def api_key_deepseek() -> str:
    return get_env('DEEPSEEK_API_KEY')
