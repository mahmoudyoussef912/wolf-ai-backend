import base64
import io
import os

from PyPDF2 import PdfReader
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {"pdf", "txt", "png", "jpg", "jpeg", "webp"}
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

MIME_MAP = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}


def allowed_file(filename: str) -> bool:
    """Return True if the filename has an allowed extension."""
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS


def process_file(file_storage):
    """Process an uploaded file and return structured data."""
    safe_filename = secure_filename(file_storage.filename)
    if not safe_filename:
        raise ValueError("Invalid filename provided.")

    if "." not in safe_filename:
        raise ValueError("File must have an extension.")

    ext = safe_filename.rsplit(".", 1)[1].lower()

    if ext == "pdf":
        return _process_pdf(file_storage, safe_filename)
    elif ext == "txt":
        return _process_text(file_storage, safe_filename)
    elif ext in IMAGE_EXTENSIONS:
        return _process_image(file_storage, safe_filename, ext)
    else:
        raise ValueError(f"Unsupported file type: {ext}")


def _process_pdf(file_storage, filename):
    file_bytes = file_storage.read()
    reader = PdfReader(io.BytesIO(file_bytes))
    text_parts = []

    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text_parts.append(page_text)

    extracted_text = "\n\n".join(text_parts)
    if not extracted_text.strip():
        extracted_text = "[PDF contained no extractable text]"

    return {
        "type": "pdf",
        "filename": filename,
        "content": extracted_text,
        "page_count": len(reader.pages),
    }


def _process_text(file_storage, filename):
    content = file_storage.read().decode("utf-8", errors="replace")
    return {
        "type": "text",
        "filename": filename,
        "content": content,
    }


def _process_image(file_storage, filename, ext):
    image_bytes = file_storage.read()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")
    return {
        "type": "image",
        "filename": filename,
        "content": image_b64,
        "mime_type": MIME_MAP.get(ext, "image/png"),
    }
