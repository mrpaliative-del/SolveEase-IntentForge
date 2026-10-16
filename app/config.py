
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    # Persistence
    DATABASE_PATH: str = os.getenv(
        "DATABASE_PATH",
        "million_intent_firehose.db",
    )

    # Payment gateway — no fake secret fallback
    PAYSTACK_SECRET_KEY: str = os.getenv(
        "PAYSTACK_SECRET_KEY", ""
    ).strip()

    # Email fulfillment
    RESEND_API_KEY: str = os.getenv(
        "RESEND_API_KEY", ""
    ).strip()

    RESEND_FROM_EMAIL: str = os.getenv(
        "RESEND_FROM_EMAIL", ""
    ).strip()

    # Telegram monitoring
    TELEGRAM_BOT_TOKEN: str = os.getenv(
        "TELEGRAM_BOT_TOKEN", ""
    ).strip()

    TELEGRAM_CHAT_ID: str = os.getenv(
        "TELEGRAM_CHAT_ID", ""
    ).strip()

    # Public application URL
    WEB_APP_URL: str = os.getenv(
        "WEB_APP_URL",
        "https://market-alert-dzas.onrender.com",
    ).strip().rstrip("/")

    # Operational configuration
    APP_ENV: str = os.getenv(
        "APP_ENV", "production"
    ).strip().lower()

    LOG_LEVEL: str = os.getenv(
        "LOG_LEVEL", "INFO"
    ).strip().upper()

    def validate_payments(self) -> None:
        if not self.PAYSTACK_SECRET_KEY:
            raise RuntimeError(
                "PAYSTACK_SECRET_KEY is required "
                "for payment operations."
            )

    def validate_email(self) -> None:
        if not self.RESEND_API_KEY:
            raise RuntimeError(
                "RESEND_API_KEY is required "
                "for email delivery."
            )

        if not self.RESEND_FROM_EMAIL:
            raise RuntimeError(
                "RESEND_FROM_EMAIL is required "
                "for email delivery."
            )

    def validate_telegram(self) -> None:
        if not self.TELEGRAM_BOT_TOKEN:
            raise RuntimeError(
                "TELEGRAM_BOT_TOKEN is required "
                "for Telegram notifications."
            )

        if not self.TELEGRAM_CHAT_ID:
            raise RuntimeError(
                "TELEGRAM_CHAT_ID is required "
                "for Telegram notifications."
            )


settings = Settings()
