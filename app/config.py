
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "").strip()

    PAYSTACK_SECRET_KEY: str = os.getenv(
        "PAYSTACK_SECRET_KEY", ""
    ).strip()

    RESEND_API_KEY: str = os.getenv(
        "RESEND_API_KEY", ""
    ).strip()

    RESEND_FROM_EMAIL: str = os.getenv(
        "RESEND_FROM_EMAIL", ""
    ).strip()

    TELEGRAM_BOT_TOKEN: str = os.getenv(
        "TELEGRAM_BOT_TOKEN", ""
    ).strip()

    TELEGRAM_CHAT_ID: str = os.getenv(
        "TELEGRAM_CHAT_ID", ""
    ).strip()

    WEB_APP_URL: str = os.getenv(
        "WEB_APP_URL",
        "https://market-alert-dzas.onrender.com",
    ).strip().rstrip("/")

    APP_ENV: str = os.getenv(
        "APP_ENV", "production"
    ).strip().lower()

    LOG_LEVEL: str = os.getenv(
        "LOG_LEVEL", "INFO"
    ).strip().upper()

    def validate_database(self) -> None:
        if not self.DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is required. Configure the Neon "
                "PostgreSQL connection string in Render Environment."
            )

        if not self.DATABASE_URL.startswith(
            ("postgresql://", "postgres://")
        ):
            raise RuntimeError(
                "DATABASE_URL must be a PostgreSQL connection URL."
            )

    def validate_payments(self) -> None:
        if not self.PAYSTACK_SECRET_KEY:
            raise RuntimeError("PAYSTACK_SECRET_KEY is required.")

    def validate_email(self) -> None:
        if not self.RESEND_API_KEY:
            raise RuntimeError("RESEND_API_KEY is required.")
        if not self.RESEND_FROM_EMAIL:
            raise RuntimeError("RESEND_FROM_EMAIL is required.")

    def validate_telegram(self) -> None:
        if not self.TELEGRAM_BOT_TOKEN:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is required.")
        if not self.TELEGRAM_CHAT_ID:
            raise RuntimeError("TELEGRAM_CHAT_ID is required.")


settings = Settings()
