"""Manual smoke test: call the local Qwen model with a small hand-written context.

Run from the project root:  python test_qwen.py   (requires Ollama running)
"""

import asyncio

from app.llm.ollama_client import generate_answer
from app.prompts.templates import chat_prompt


async def main():
    question = "What is formative assessment?"

    passages = [
        {
            "document": "manual-test",
            "title": "Manual test context",
            "page": 1,
            "text": (
                "Formative assessment is an ongoing process of collecting evidence of student "
                "learning during instruction. Teachers use this evidence to adjust teaching strategies."
            ),
        }
    ]

    answer = await generate_answer(chat_prompt(question, passages, None))

    print("\nMARG CLASSROOM COACH RESPONSE\n")
    print(answer)


if __name__ == "__main__":
    asyncio.run(main())
