import logging

from pydantic import ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


def ConfigEnvFile(path: str) -> SettingsConfigDict:
    return SettingsConfigDict(env_file=path, extra="ignore")


class Settings(BaseSettings):
    TELEGRAM_BOT_TOKEN: str
    GROQ_API_KEY: str
    SUPABASE_URL: str
    SUPABASE_KEY: str

    ENVIRONMENT: str = "development"
    RATE_LIMIT_PER_DAY: int = 50
    AUTO_CONFIRM_DELAY_SECONDS: int = 120
    BATCH_WAIT_SECONDS: int = 30
    DAILY_SUMMARY_HOUR_IST: int = 21
    WEBHOOK_URL: str | None = None
    WEBHOOK_SECRET: str | None = None

    model_config = ConfigEnvFile(".env")

    @field_validator("TELEGRAM_BOT_TOKEN")
    @classmethod
    def validate_token(cls, value: str) -> str:
        if len(value.strip()) < 20:
            raise ValueError("TELEGRAM_BOT_TOKEN is too short.")
        return value.strip()

    @field_validator("WEBHOOK_SECRET")
    @classmethod
    def validate_webhook_secret(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if stripped and len(stripped) < 10:
            raise ValueError("WEBHOOK_SECRET must be at least 10 characters when set.")
        return stripped or None

    @field_validator("ENVIRONMENT")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        allowed = {"development", "production"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}.")
        return normalized

    @field_validator("RATE_LIMIT_PER_DAY")
    @classmethod
    def validate_rate_limit(cls, value: int) -> int:
        if value < 1:
            raise ValueError("RATE_LIMIT_PER_DAY must be >= 1.")
        return value


try:
    settings = Settings()
except ValidationError:
    logger.critical("Settings validation failed during startup.", exc_info=True)
    raise SystemExit(1)
