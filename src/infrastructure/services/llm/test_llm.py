from infrastructure.services.llm.llm import LLMService
from infrastructure.services.llm.src.openai_impl import OpenAiLLMService
from dotenv import load_dotenv

load_dotenv()

llm: LLMService = OpenAiLLMService()


def test_llm():
    question = "Объясни разницу между RAG и fine-tuning в 2 предложениях."

    answer = llm.text(question)
    print("=== Текстовый ответ ===")
    print(answer)


if __name__ == "__main__":
    test_llm()
