"""Application settings.

All configuration comes from environment variables (and an optional ``.env`` file). Values are
validated at startup. Secrets are ``SecretStr`` and are never logged or returned by any endpoint.
No Claude model identifier is defined in code: ``ANTHROPIC_MODEL`` must be configured.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(StrEnum):
    development = "development"
    test = "test"
    staging = "staging"
    production = "production"


class BackendMode(StrEnum):
    demo = "demo"  # engine-hosted DEMO DATA (development only)
    marg = "marg"  # real MARG backend - BLOCKED until the OpenAPI compatibility audit


class DbBackend(StrEnum):
    postgres = "postgres"
    sqlite = "sqlite"  # local development / tests only


EFFORT_LEVELS = {"low", "medium", "high", "xhigh", "max"}


class ConfigurationError(RuntimeError):
    """Raised when configuration is invalid. Messages never contain secret values."""


def parse_pricing(raw: str) -> dict[str, tuple[float, float]]:
    """Parse ``model=input/output;model=input/output`` (USD per million tokens)."""
    pricing: dict[str, tuple[float, float]] = {}
    if not raw.strip():
        return pricing
    for entry in raw.split(";"):
        entry = entry.strip()
        if not entry:
            continue
        try:
            model, prices = entry.split("=", 1)
            input_price, output_price = prices.split("/", 1)
            pricing[model.strip()] = (float(input_price), float(output_price))
        except ValueError as exc:
            raise ValueError(f"Malformed LLM_PRICING entry: {entry!r}") from exc
    return pricing


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    # The .env path is anchored to the project root so it is found regardless of the working directory.
    # Real environment variables still take precedence over .env values.
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    # Application
    app_env: AppEnv = AppEnv.development
    log_level: str = "INFO"
    log_format: str = "json"
    default_timezone: str = "Asia/Kolkata"
    engine_api_key: SecretStr | None = None  # if set, /api/v1 requires the X-API-Key header

    # AI provider
    ai_enabled: bool = True
    ai_provider: str = "nvidia"
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = ""
    anthropic_effort: str = ""
    anthropic_max_output_tokens: int = Field(default=16000, ge=256, le=128000)
    anthropic_timeout_seconds: float = Field(default=120.0, gt=0)
    anthropic_max_retries: int = Field(default=3, ge=0, le=10)
    anthropic_refusal_fallback: str = "default"  # "default" | "off"

    # NVIDIA-hosted OpenAI-compatible inference
    nvidia_api_key: SecretStr | None = None
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "nvidia/nemotron-3.5-lightning-30b-a3b"
    nvidia_max_output_tokens: int = Field(default=16000, ge=256, le=128000)
    nvidia_timeout_seconds: float = Field(default=120.0, gt=0)
    nvidia_max_retries: int = Field(default=3, ge=0, le=10)

    # OpenRouter provider
    openrouter_api_key: SecretStr | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = ""
    openrouter_max_output_tokens: int = Field(default=16000, ge=256, le=128000)
    openrouter_timeout_seconds: float = Field(default=120.0, gt=0)
    openrouter_max_retries: int = Field(default=3, ge=0, le=10)
    openrouter_fallback_models: str = ""
    llm_daily_token_budget_per_mentor: int = Field(default=200_000, ge=0)
    llm_daily_token_budget_global: int = Field(default=5_000_000, ge=0)
    llm_pricing: str = ""

    # Data protection
    pseudonymisation_key: SecretStr | None = None

    # Engine database (engine-owned only; never the MARG database)
    db_backend: DbBackend = DbBackend.postgres
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "marg_mentor_intelligence"
    db_user: str = "marg_mie_app"
    db_password: SecretStr | None = None
    db_schema: str = "mie"
    db_test_schema: str = "mie_test"
    db_forbidden_names: str = "marg_db,postgres,template0,template1"
    sqlite_path: str = "./mie_dev.sqlite3"

    # MARG backend integration
    backend_mode: BackendMode = BackendMode.demo
    # BACKEND_MODE=marg: MARG backend service API (see docs/INTEGRATION.md)
    marg_backend_url: str = "http://localhost:8000"
    marg_backend_service_key: SecretStr | None = None
    marg_backend_timeout_seconds: float = Field(default=30.0, gt=0, le=300)

    # Provisional identity (development only; final roles come from the MARG audit)
    dev_auth_header_enabled: bool = True
    # Trusted-gateway identity: the MARG backend (holder of ENGINE_API_KEY)
    # authenticates the mentor and asserts X-Actor-Ref. Identity headers are
    # accepted ONLY together with a valid engine API key. Allowed in production.
    trusted_gateway_identity: bool = False
    dev_supervisor_roles: str = "dev_supervisor"

    # Planning parameters (deterministic services)
    deadline_horizon_days: int = Field(default=14, ge=1)
    dependency_points_per_blocked_task: int = Field(default=25, ge=0, le=100)
    workload_high_threshold: float = 80.0
    workload_overload_threshold: float = 100.0
    visit_duration_minutes: int | None = None  # used for visit suggestions only if configured
    proposal_ttl_hours: int = Field(default=72, ge=1)

    # ---------------------------------------------------------------- validators
    @field_validator("engine_api_key", mode="before")
    @classmethod
    def _valid_engine_api_key(cls, value: Any) -> Any:
        """An explicitly provided but empty key is a configuration error (fail closed).

        Without this, ``ENGINE_API_KEY=`` (or a line holding only a comment) produced an empty secret
        that no request could ever match. Surrounding whitespace is removed; the value is never echoed.
        """
        if value is None:
            return None
        raw = value.get_secret_value() if isinstance(value, SecretStr) else str(value)
        cleaned = raw.strip()
        if not cleaned:
            raise ValueError(
                "ENGINE_API_KEY is present but empty. Set a non-empty value, or remove the line "
                "to run without API-key checks."
            )
        return cleaned

    @field_validator("default_timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Unknown timezone: {value!r}") from exc
        return value

    @field_validator("ai_provider")
    @classmethod
    def _valid_provider(cls, value: str) -> str:
        val = value.strip().lower()
        if val not in {"anthropic", "openrouter", "nvidia"}:
            raise ValueError(f"AI_PROVIDER must be 'anthropic', 'openrouter' or 'nvidia', got {value!r}")
        return val

    @field_validator("anthropic_effort")
    @classmethod
    def _valid_effort(cls, value: str) -> str:
        value = value.strip()
        if value and value not in EFFORT_LEVELS:
            raise ValueError(f"ANTHROPIC_EFFORT must be one of {sorted(EFFORT_LEVELS)} or empty")
        return value

    @field_validator("anthropic_refusal_fallback")
    @classmethod
    def _valid_fallback(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"default", "off"}:
            raise ValueError("ANTHROPIC_REFUSAL_FALLBACK must be 'default' or 'off'")
        return value

    @field_validator("llm_pricing")
    @classmethod
    def _valid_pricing(cls, value: str) -> str:
        parse_pricing(value)
        return value

    @model_validator(mode="after")
    def _cross_field_rules(self) -> Settings:
        if self.db_name.strip().lower() in self.forbidden_db_names:
            raise ValueError(f"DB_NAME {self.db_name!r} is forbidden for the Mentor Intelligence Engine")
        if self.backend_mode is BackendMode.marg:
            if self.marg_backend_service_key is None or not self.marg_backend_service_key.get_secret_value().strip():
                raise ValueError("BACKEND_MODE=marg requires MARG_BACKEND_SERVICE_KEY")
            if not self.marg_backend_url.strip():
                raise ValueError("BACKEND_MODE=marg requires MARG_BACKEND_URL")
        if self.trusted_gateway_identity and self.engine_api_key is None:
            raise ValueError("TRUSTED_GATEWAY_IDENTITY=true requires ENGINE_API_KEY")
        if self.dev_auth_header_enabled and self.app_env in {AppEnv.staging, AppEnv.production}:
            raise ValueError("DEV_AUTH_HEADER_ENABLED must be false outside development/test")
        if self.db_backend is DbBackend.sqlite and self.app_env in {AppEnv.staging, AppEnv.production}:
            raise ValueError("DB_BACKEND=sqlite is only allowed in development/test")
        if self.ai_enabled:
            provider = self.ai_provider.strip().lower()
            if provider == "anthropic":
                if self.anthropic_api_key is None or not self.anthropic_api_key.get_secret_value().strip():
                    raise ValueError("AI_ENABLED=true with AI_PROVIDER=anthropic requires ANTHROPIC_API_KEY")
                if not self.anthropic_model.strip():
                    raise ValueError("AI_ENABLED=true with AI_PROVIDER=anthropic requires ANTHROPIC_MODEL (no model is hardcoded)")

            elif provider == "openrouter":
                if self.openrouter_api_key is None or not self.openrouter_api_key.get_secret_value().strip():
                    raise ValueError("AI_ENABLED=true with AI_PROVIDER=openrouter requires OPENROUTER_API_KEY")
                if not self.openrouter_model.strip():
                    raise ValueError("AI_ENABLED=true with AI_PROVIDER=openrouter requires OPENROUTER_MODEL (no model is hardcoded)")
            elif provider == "nvidia":
                if self.nvidia_api_key is None or not self.nvidia_api_key.get_secret_value().strip():
                    raise ValueError("AI_ENABLED=true with AI_PROVIDER=nvidia requires NVIDIA_API_KEY")
                if not self.nvidia_model.strip():
                    raise ValueError("AI_ENABLED=true with AI_PROVIDER=nvidia requires NVIDIA_MODEL")
            else:
                raise ValueError(f"Unsupported AI_PROVIDER {self.ai_provider!r}")





        if self.app_env is not AppEnv.test:
            key = self.pseudonymisation_key.get_secret_value() if self.pseudonymisation_key else ""
            if len(key) < 32:
                raise ValueError("PSEUDONYMISATION_KEY must be set (at least 32 characters)")
        if self.db_backend is DbBackend.postgres and self.app_env is not AppEnv.test:
            if self.db_password is None or not self.db_password.get_secret_value():
                raise ValueError("DB_BACKEND=postgres requires DB_PASSWORD")
        return self

    # ---------------------------------------------------------------- helpers
    @property
    def forbidden_db_names(self) -> set[str]:
        return {n.strip().lower() for n in self.db_forbidden_names.split(",") if n.strip()}

    @property
    def pricing(self) -> dict[str, tuple[float, float]]:
        return parse_pricing(self.llm_pricing)

    @property
    def supervisor_roles(self) -> set[str]:
        return {r.strip() for r in self.dev_supervisor_roles.split(",") if r.strip()}

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.default_timezone)

    def describe(self) -> dict[str, Any]:
        """Safe configuration summary for diagnostics. Never includes secret values."""
        return {
            "app_env": self.app_env.value,
            "backend_mode": self.backend_mode.value,
            "backend_mode_note": "DEMO DATA - development only"
            if self.backend_mode is BackendMode.demo
            else "",
            "db_backend": self.db_backend.value,
            "db_name": self.db_name if self.db_backend is DbBackend.postgres else "sqlite (local)",
            "db_schema": self.db_schema if self.db_backend is DbBackend.postgres else None,
            "ai_enabled": self.ai_enabled,
            "ai_provider": self.ai_provider,
            "nvidia_api_key": "configured" if self.nvidia_api_key else "not configured",
            "nvidia_model": self.nvidia_model,
            "anthropic_model_configured": bool(self.anthropic_model.strip()),
            "anthropic_api_key": "configured" if self.anthropic_api_key else "not configured",
            "engine_api_key": "configured" if self.engine_api_key else "not configured",
            "default_timezone": self.default_timezone,
        }


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValueError as exc:  # pydantic ValidationError subclasses ValueError
        raise ConfigurationError(_safe_validation_message(exc)) from None


def _safe_validation_message(exc: ValueError) -> str:
    """Render validation errors without echoing input values (which may be secrets)."""
    errors = getattr(exc, "errors", None)
    if callable(errors):
        parts = []
        for err in errors():
            loc = ".".join(str(p) for p in err.get("loc", ())) or "settings"
            parts.append(f"{loc}: {err.get('msg', 'invalid value')}")
        return "Invalid configuration - " + "; ".join(parts)
    return "Invalid configuration"
