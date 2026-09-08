from io import BytesIO

from pypdf import PdfReader


def parse_pdf(data: bytes) -> list[tuple[int, str]]:
    """Extract page text; scanned/image PDFs require OCR outside this lab."""
    if not data.startswith(b"%PDF-"):
        raise ValueError("Upload a valid PDF file")
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported")
        if len(reader.pages) > 200:
            raise ValueError("PDF must have at most 200 pages")
        pages = [(number, page.extract_text() or "")
                 for number, page in enumerate(reader.pages, 1)]
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("PDF could not be parsed") from exc
    if not any(text.strip() for _, text in pages):
        raise ValueError("PDF has no extractable text; run OCR first")
    if sum(len(text) for _, text in pages) > 1000000:
        raise ValueError("Extracted text exceeds 1 million characters")
    return pages
