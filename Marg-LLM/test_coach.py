
import asyncio
from app.coach import ask_classroom_coach


async def main():

    question = (
        "How can a teacher identify students who are "
        "struggling to understand a lesson?"
    )

    print("\n========== MARG CLASSROOM COACH ==========\n")
    print("Teacher:", question)

    result = await ask_classroom_coach(question)

    print("\nCOACH RESPONSE:\n")
    print(result["answer"])

    print("\nEDUCATIONAL SOURCES:\n")

    for source in result["sources"]:
        print(
            f"- {source['document']} "
            f"(Page {source['page']})"
        )


if __name__ == "__main__":
    asyncio.run(main())
