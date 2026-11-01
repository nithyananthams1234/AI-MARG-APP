from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    APP_NAME: str = "MARG Classroom Coach"
    APP_ENV: str = "development"

    # NVIDIA-hosted OpenAI-compatible inference.
    NVIDIA_API_KEY: SecretStr | None = None
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_MODEL: str = "nvidia/nemotron-3.5-lightning-30b-a3b"
    NVIDIA_TIMEOUT_SECONDS: float = 180.0
    NVIDIA_TEMPERATURE: float = 0.2
    NVIDIA_MAX_ANSWER_TOKENS: int = 8192
    NVIDIA_MAX_ANALYSIS_TOKENS: int = 2600

    # Embeddings + vector store (unchanged: MiniLM-L6-v2 + ChromaDB).
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    CHROMA_PATH: str = "./data/chroma_db"
    COLLECTION_NAME: str = "marg_classroom_knowledge"
    PDF_DIRECTORY: str = "./data/pdfs"
    TITLE_MAPPING_FILE: str = "./data/pdfs/rename_mapping.csv"

    # Retrieval tuning.
    RETRIEVAL_TOP_K: int = 5
    RETRIEVAL_FETCH_K: int = 30  # over-fetch, then de-duplicate / diversify
    RETRIEVAL_MAX_PER_DOCUMENT: int = 2
    # Cosine distance above which a chunk is considered irrelevant.
    RETRIEVAL_MAX_DISTANCE: float = 0.60  # calibrated: on-topic <=0.40, off-topic >=0.75

    # Service-to-service authentication (MARG backend -> Coach).
    # Required when APP_ENV=production.
    COACH_API_KEY: str | None = None

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8-sig",  # tolerate a UTF-8 BOM in .env
        case_sensitive=True,
        extra="ignore",
    )

    def resolve(self, path: str) -> Path:
        p = Path(path)
        return p if p.is_absolute() else (BASE_DIR / p).resolve()

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"


settings = Settings()
