from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    anthropic_api_key: str = Field("", env="ANTHROPIC_API_KEY")  # unused (SDK uses local Claude Code auth)
    claude_model: str = Field("", env="CLAUDE_MODEL")  # empty → use Claude Code default

    database_url: str = Field("sqlite:///./portfolio.db", env="DATABASE_URL")

    admin_token: str = Field(..., env="ADMIN_TOKEN")

    daily_run_hour: int = Field(16, env="DAILY_RUN_HOUR")
    daily_run_minute: int = Field(30, env="DAILY_RUN_MINUTE")

    email_enabled: bool = Field(False, env="EMAIL_ENABLED")
    smtp_host: str = Field("smtp.gmail.com", env="SMTP_HOST")
    smtp_port: int = Field(587, env="SMTP_PORT")
    smtp_user: str = Field("", env="SMTP_USER")
    smtp_password: str = Field("", env="SMTP_PASSWORD")
    email_to: str = Field("", env="EMAIL_TO")

    telegram_enabled: bool = Field(False, env="TELEGRAM_ENABLED")
    telegram_bot_enabled: bool = Field(False, env="TELEGRAM_BOT_ENABLED")
    telegram_bot_token: str = Field("", env="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field("", env="TELEGRAM_CHAT_ID")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
