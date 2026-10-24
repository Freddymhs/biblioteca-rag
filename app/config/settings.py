from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Env validation with pydantic-settings — equivalent to Joi in JS.
    Reads from .env automatically. Fails fast if required vars are missing.
    """

    # Required
    DATABASE_URL: str
    SECRET_KEY: str

    # Optional with defaults
    APP_NAME: str = "template-fastapi"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = []  # e.g. ["https://app.example.com"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Singleton — import this everywhere instead of re-instantiating
settings = Settings()  # type: ignore[call-arg]
