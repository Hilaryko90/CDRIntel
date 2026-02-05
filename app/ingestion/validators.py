ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".json", ".zip"}
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB

def validate_file(filename: str, size: int):
    ext = filename.lower().rsplit(".", 1)[-1]
    if f".{ext}" not in ALLOWED_EXTENSIONS:
        raise ValueError("Unsupported file type")

    if size > MAX_FILE_SIZE:
        raise ValueError("File too large")
