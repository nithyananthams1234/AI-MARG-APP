from pathlib import Path
from pypdf import PdfReader


PDF_DIRECTORY = Path("data/pdfs")

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200


def split_text(text: str):
    """Split text into overlapping chunks."""
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


def process_pdfs():
    pdf_files = list(PDF_DIRECTORY.rglob("*.pdf"))

    all_chunks = []
    total_pages = 0
    pages_with_text = 0
    pages_without_text = 0
    failed_files = []

    print(f"Found {len(pdf_files)} PDF files.\n")

    for pdf_file in pdf_files:
        try:
            reader = PdfReader(str(pdf_file))

            for page_number, page in enumerate(reader.pages, start=1):
                total_pages += 1

                text = page.extract_text() or ""

                if not text.strip():
                    pages_without_text += 1
                    continue

                pages_with_text += 1

                chunks = split_text(text)

                for chunk_index, chunk in enumerate(chunks):
                    all_chunks.append({
                        "text": chunk,
                        "source": pdf_file.name,
                        "page": page_number,
                        "chunk_index": chunk_index
                    })

        except Exception as error:
            failed_files.append({
                "file": pdf_file.name,
                "error": str(error)
            })

    print("\n========== PDF PROCESSING REPORT ==========")
    print(f"Total PDFs: {len(pdf_files)}")
    print(f"Total pages: {total_pages}")
    print(f"Pages with extractable text: {pages_with_text}")
    print(f"Pages without extractable text: {pages_without_text}")
    print(f"Total text chunks: {len(all_chunks)}")
    print(f"Failed PDFs: {len(failed_files)}")

    if failed_files:
        print("\nFailed files:")
        for item in failed_files:
            print(f"- {item['file']}: {item['error']}")

    return all_chunks


if __name__ == "__main__":
    process_pdfs()