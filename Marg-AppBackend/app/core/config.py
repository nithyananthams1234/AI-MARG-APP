
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "MARG Backend"
    app_env: str = "development"
    debug: bool = False
    sql_echo: bool = False
    api_v1_prefix: str = "/api/v1"

    # Comma-separated list of allowed browser origins (Expo web, deployed frontend).
    cors_origins: str = "http://localhost:8081,http://localhost:19006"

    database_url: str
    # Disable connection pooling (tests run each case in a fresh event loop).
    database_nullpool: bool = False

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 14

    # Login brute-force protection (per client IP + email, in-process).
    login_rate_limit_attempts: int = 10
    login_rate_limit_window_seconds: int = 300

    # AI configuration
    # classroom_coach: MARG Classroom Coach service (local LLM + RAG)  [default]
    # openai:          legacy direct OpenAI path (kept, disabled by default)
    ai_provider: str = "classroom_coach"
    ai_model: str = "gpt-4o-mini"
    ai_api_key: str | None = None
    ai_timeout_seconds: int = 60

    # Classroom Coach service (educational LLM + RAG)
    classroom_coach_url: str = "http://localhost:8001"
    classroom_coach_api_key: str | None = None
    classroom_coach_timeout_seconds: float = 180.0

    # Mentor Intelligence (Claude-powered mentor workflow engine)
    # Backend -> MI: base URL + MI's ENGINE_API_KEY
    mentor_intelligence_url: str = "http://localhost:8002"
    mentor_intelligence_api_key: str | None = None
    mentor_intelligence_timeout_seconds: float = 180.0
    # MI -> backend: key MI presents on /integrations/mentor-intelligence/*
    mentor_intelligence_service_key: str | None = None
    # Planning defaults used when a mentor profile does not define them.
    mentor_default_timezone: str = "Asia/Kolkata"
    mentor_default_work_start: str = "09:00"
    mentor_default_work_end: str = "17:00"
    mentor_default_working_days: str = "1,2,3,4,5,6"  # ISO weekdays, Mon-Sat
    visit_default_duration_minutes: int = 180

    # Process AI jobs immediately inside the API process (in addition to the
    # standalone worker). Keeps the demo working without a separate worker.
    ai_inline_processing: bool = True

    # Reminder notifications (tasks/visits/steps due, follow-ups to verify).
    reminders_inline: bool = True
    reminders_interval_minutes: int = 10

    # AI embedding configuration
    ai_embedding_model: str = "text-embedding-3-small"
    ai_embedding_dimensions: int = 1536

    # Evidence storage: "local" (development) or "s3" (production; any
    # S3-compatible object store).
    storage_backend: str = "local"

    # Local evidence storage configuration
    storage_local_path: str = "storage/evidence"
    max_upload_size_mb: int = 10

    # S3-compatible storage configuration (STORAGE_BACKEND=s3)
    storage_endpoint_url: str | None = None
    storage_access_key: str | None = None
    storage_secret_key: str | None = None
    storage_bucket_name: str = "marg-evidence"
    storage_region: str = "ap-south-1"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


    @model_validator(mode="after")
    def _production_rules(self) -> "Settings":
        if self.app_env.lower() == "production":
            if self.storage_backend != "s3":
                raise ValueError("STORAGE_BACKEND must be 's3' in production (container disks are ephemeral)")
            if len(self.jwt_secret_key) < 32:
                raise ValueError("JWT_SECRET_KEY must be at least 32 characters in production")
            if self.debug or self.sql_echo:
                raise ValueError("DEBUG and SQL_ECHO must be false in production")
            if any(o.startswith("http://") and "localhost" not in o for o in self.cors_origin_list):
                raise ValueError("CORS_ORIGINS must use https:// in production")
        if self.storage_backend not in ("local", "s3"):
            raise ValueError("STORAGE_BACKEND must be 'local' or 's3'")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


settings = Settings()
