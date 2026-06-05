from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "SecureCore Bank"
    DATABASE_URL: str = "sqlite:///./securecore_bank.db"
    # NOTE: Will be used when we implement JWT/session. Keep it deterministic for dev.
    SECRET_KEY: str = "dev-only-change-me"


settings = Settings()
