"""Simplified file format detection via magic bytes only (no Defender/ClamAV)."""

ALLOWED_FORMATS = {"pdf", "epub", "txt"}


def detect_format(header_bytes: bytes) -> str:
    if header_bytes.startswith(b"%PDF-"):
        return "pdf"
    if header_bytes.startswith(b"PK\x03\x04"):
        return "epub"
    if b"\x00" not in header_bytes:
        return "txt"
    return "unknown"


def verify_file_format(header_bytes: bytes, expected_format: str = "") -> dict:
    detected = detect_format(header_bytes[:4096])
    expected = str(expected_format or "").lower().lstrip(".")
    if detected not in ALLOWED_FORMATS:
        raise ValueError("文件不是有效的 PDF、EPUB 或 TXT")
    if expected in ALLOWED_FORMATS and expected != detected:
        raise ValueError(f"文件真实格式为 {detected.upper()}, 与标称格式不一致")
    return {"format": detected}
