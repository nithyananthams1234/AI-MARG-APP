
from pathlib import Path
import hashlib

import chromadb
from sentence_transformers import SentenceTransformer
from pypdf import PdfReader


BASE_DIR = Path(__file__).resolve().parents[2]

PDF_DIRECTORY = BASE_DIR / "data" / "pdfs"
CHROMA_DIRECTORY = BASE_DIR / "data" / "chroma_db"

COLLECTION_NAME = "marg_classroom_knowledge"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200
BATCH_SIZE = 128


def split_text(text):
    text = " ".join(text.split())

    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = start + CHUNK_SIZE
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = end - CHUNK_OVERLAP

    return chunks


def make_chunk_id(source, page, chunk_index):
    unique_text = f"{source}|{page}|{chunk_index}"
    return hashlib.sha256(unique_text.encode("utf-8")).hexdigest()


def main():
    print("Loading embedding model...")

    model = SentenceTransformer(EMBEDDING_MODEL)

    print("Connecting to ChromaDB...")

    client = chromadb.PersistentClient(
        path=str(CHROMA_DIRECTORY)
    )

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"}
    )

    pdf_files = sorted(PDF_DIRECTORY.rglob("*.pdf"))

    print(f"Found {len(pdf_files)} PDFs.")
    print("Starting ingestion...\n")

    batch_documents = []
    batch_metadatas = []
    batch_ids = []

    total_chunks = 0
    processed_pdfs = 0
    failed_pdfs = []

    def save_batch():
        nonlocal total_chunks

        if not batch_documents:
            return

        embeddings = model.encode(
            batch_documents,
            batch_size=32,
            normalize_embeddings=True,
            show_progress_bar=False
        ).tolist()

        collection.upsert(
            ids=batch_ids,
            documents=batch_documents,
            metadatas=batch_metadatas,
            embeddings=embeddings
        )

        total_chunks += len(batch_documents)

        batch_documents.clear()
        batch_metadatas.clear()
        batch_ids.clear()

    for pdf_file in pdf_files:

        # Explicitly exclude the unwanted PDF.
        if pdf_file.name.lower() == "99.pdf":
            print("Skipping 99.pdf")
            continue

        try:
            reader = PdfReader(str(pdf_file))

            for page_number, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""

                for chunk_index, chunk in enumerate(split_text(text)):

                    relative_source = str(
                        pdf_file.relative_to(PDF_DIRECTORY)
                    )

                    batch_documents.append(chunk)

                    batch_metadatas.append({
                        "source": relative_source,
                        "page": page_number,
                        "chunk_index": chunk_index
                    })

                    batch_ids.append(
                        make_chunk_id(
                            relative_source,
                            page_number,
                            chunk_index
                        )
                    )

                    if len(batch_documents) >= BATCH_SIZE:
                        save_batch()

            processed_pdfs += 1
            print(
                f"Processed {processed_pdfs} PDFs: "
                f"{pdf_file.name} | Stored chunks: {total_chunks}"
            )

        except Exception as error:
            failed_pdfs.append((pdf_file.name, str(error)))
            print(f"Failed: {pdf_file.name} - {error}")

    save_batch()

    print("\n========== INGESTION COMPLETE ==========")
    print(f"PDFs processed: {processed_pdfs}")
    print(f"PDFs failed: {len(failed_pdfs)}")
    print(f"New chunks processed: {total_chunks}")
    print(f"Total chunks in ChromaDB: {collection.count()}")
    print(f"Database location: {CHROMA_DIRECTORY}")

    if failed_pdfs:
        print("\nFailed files:")
        for filename, error in failed_pdfs:
            print(f"{filename}: {error}")


if __name__ == "__main__":
    main()
