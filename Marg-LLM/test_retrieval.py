
from app.rag.retriever import retrieve_context


def main():
    question = "How can a teacher identify students who are struggling to understand a lesson?"

    print("\nMARG CLASSROOM COACH - RETRIEVAL TEST")
    print("=" * 50)

    results = retrieve_context(question, top_k=5)

    for index, result in enumerate(results, start=1):
        print(f"\nRESULT {index}")
        print(f"Source: {result['source']}")
        print(f"Page: {result['page']}")
        print(f"Distance: {result['distance']:.4f}")
        print(f"Content:\n{result['text'][:700]}")
        print("-" * 50)


if __name__ == "__main__":
    main()
