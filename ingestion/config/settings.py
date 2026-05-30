import os
from pathlib import Path

                                                                  
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INGESTION_ROOT = PROJECT_ROOT / "ingestion"
DATA_DIR = INGESTION_ROOT / "data"
RAW_CONTENT_DIR = DATA_DIR / "raw"
DICTIONARIES_DIR = INGESTION_ROOT / "normalization" / "dictionaries"


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue

        os.environ[key] = value.strip().strip("\"'")


_load_env_file(PROJECT_ROOT / ".env")

                        
RAW_CONTENT_DIR.mkdir(parents=True, exist_ok=True)

                                                                  
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "database": os.getenv("DB_NAME", "admission"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}

                                                                  
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

                  
GEMINI_EXTRACTION_MODEL = os.getenv(
    "GEMINI_EXTRACTION_MODEL", "gemini-2.5-flash"
)


GEMINI_OCR_MODEL = os.getenv(
    "GEMINI_OCR_MODEL", "gemini-2.5-flash-lite"
)

# --- Embeddings (knowledge corpus / RAG) ---------------------------------
# gemini-embedding-001 with Matryoshka truncation to 768 dims. Changing
# EMBEDDING_DIM later requires re-embedding the whole corpus because the
# knowledge_chunks.embedding column type is fixed to vector(EMBEDDING_DIM).
GEMINI_EMBEDDING_MODEL = os.getenv(
    "GEMINI_EMBEDDING_MODEL", "gemini-embedding-001"
)
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", 768))

# --- Knowledge chunking (Phase 3) ----------------------------------------
# Structure-aware char window. ~1800 chars ≈ 512 tokens for Vietnamese.
# Spans are character offsets → deterministic → stable idempotency key.
CHUNK_SIZE = int(os.getenv("KNOWLEDGE_CHUNK_SIZE", 1800))
CHUNK_OVERLAP = int(os.getenv("KNOWLEDGE_CHUNK_OVERLAP", 256))


FETCH_TIMEOUT = int(os.getenv("FETCH_TIMEOUT", 30))
FETCH_MAX_RETRIES = int(os.getenv("FETCH_MAX_RETRIES", 3))
FETCH_RETRY_BACKOFF = float(os.getenv("FETCH_RETRY_BACKOFF", 1.5))
# Default OFF: several official .gov.vn admission sources ship broken certs.
# Set ADVISORY_FETCH_VERIFY_SSL=true to enforce verification.
FETCH_VERIFY_SSL = os.getenv("ADVISORY_FETCH_VERIFY_SSL", "false").strip().lower() in (
    "1",
    "true",
    "yes",
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

                                                                  
ADMISSION_KEYWORDS = [
    "tuyển sinh",
    "đề án",
    "chỉ tiêu",
    "xét tuyển",
    "phương thức",
    "điểm chuẩn",
    "tổ hợp môn",
    "ngành đào tạo",
    "admission",
    "enrollment",
]

                                                                  
                        
ADMISSION_YEAR = int(os.getenv("ADMISSION_YEAR", 2026))

                                         
LLM_MAX_CHUNK_SIZE = int(os.getenv("LLM_MAX_CHUNK_SIZE", 30000))
