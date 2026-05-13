import os
from pathlib import Path

                                                                  
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INGESTION_ROOT = PROJECT_ROOT / "ingestion"
DATA_DIR = INGESTION_ROOT / "data"
RAW_CONTENT_DIR = DATA_DIR / "raw"
DICTIONARIES_DIR = INGESTION_ROOT / "normalization" / "dictionaries"

                        
RAW_CONTENT_DIR.mkdir(parents=True, exist_ok=True)

                                                                  
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "database": os.getenv("DB_NAME", "admission"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "1"),
}

                                                                  
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

                  
GEMINI_EXTRACTION_MODEL = os.getenv(
    "GEMINI_EXTRACTION_MODEL", "gemini-2.5-flash"
)

                              
GEMINI_OCR_MODEL = os.getenv(
    "GEMINI_OCR_MODEL", "gemini-2.5-flash-lite"
)

                                                                  
FETCH_TIMEOUT = int(os.getenv("FETCH_TIMEOUT", 30))
FETCH_MAX_RETRIES = int(os.getenv("FETCH_MAX_RETRIES", 3))
FETCH_RETRY_BACKOFF = float(os.getenv("FETCH_RETRY_BACKOFF", 1.5))

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
