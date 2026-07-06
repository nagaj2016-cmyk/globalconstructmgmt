"""
NagaForge — Environment Configuration
Reads from environment variables with sensible defaults for local dev.
Set DATABASE_URL to a PostgreSQL URL in production.

Security note: SECRET_KEY and the default admin password MUST be provided via
environment variables in any non-DEBUG (production) deployment. The app refuses
to boot with insecure defaults when DEBUG is false. This keeps signing keys and
credentials out of source control.
"""
import os
import secrets as _secrets
from functools import lru_cache

# Sentinels that mark "developer never set a real value".
_DEFAULT_SECRET = "nagaforge-insecure-dev-secret-change-me"
_DEFAULT_ADMIN_PW = "admin123"


class Settings:
    # Database — defaults to SQLite for local dev, use PostgreSQL in production
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./construction.db")

    # App
    APP_NAME: str = "NagaForge"
    VERSION: str = "4.1.0"
    # DEBUG defaults to FALSE — production-safe by default. Turn on explicitly for dev.
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # JWT — single source of truth for token signing across the whole app.
    SECRET_KEY: str = os.getenv("SECRET_KEY", _DEFAULT_SECRET)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = int(os.getenv("ACCESS_TOKEN_HOURS", "8"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_DAYS", "30"))

    # CORS — comma-separated allowlist. NEVER "*" together with credentials.
    _cors_raw: str = os.getenv(
        "CORS_ORIGINS",
        "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5173",
    )
    CORS_ORIGINS: list = [o.strip() for o in _cors_raw.split(",") if o.strip()]

    # File storage
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "uploads")
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_MB", "50"))

    # Multi-tenancy — row-level isolation is always enforced now; this only
    # toggles the self-service signup flow.
    MULTI_TENANT: bool = os.getenv("MULTI_TENANT", "true").lower() == "true"

    # Default admin (bootstrap only). Password must be set via env in production.
    DEFAULT_ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", _DEFAULT_ADMIN_PW)

    # Demo account — the ONLY account that may load/reset demo data and the only
    # tenant whose seed data is visible to it.
    DEMO_USERNAME: str = os.getenv("DEMO_USERNAME", "demo")
    DEMO_PASSWORD: str = os.getenv("DEMO_PASSWORD", "demo123")

    # Default language / country used before a user profile is known.
    DEFAULT_LOCALE: str = os.getenv("DEFAULT_LOCALE", "en")
    DEFAULT_COUNTRY: str = os.getenv("DEFAULT_COUNTRY", "India")

    # Weather API (optional — used by site ops module)
    WEATHER_API_KEY: str = os.getenv("WEATHER_API_KEY", "")
    WEATHER_API_URL: str = "https://api.openweathermap.org/data/2.5/weather"

    def validate(self) -> None:
        """Fail fast on insecure production configuration."""
        problems = []
        if not self.DEBUG:
            if self.SECRET_KEY == _DEFAULT_SECRET:
                problems.append(
                    "SECRET_KEY is unset. Set the SECRET_KEY env var to a long random string."
                )
            if self.DEFAULT_ADMIN_PASSWORD == _DEFAULT_ADMIN_PW:
                problems.append(
                    "ADMIN_PASSWORD is the built-in default. Set the ADMIN_PASSWORD env var."
                )
            if "*" in self.CORS_ORIGINS:
                problems.append("CORS_ORIGINS must not be '*' in production.")
        if problems:
            raise RuntimeError(
                "Refusing to start with insecure configuration:\n  - "
                + "\n  - ".join(problems)
                + "\n\nGenerate a secret with: "
                'python -c "import secrets;print(secrets.token_urlsafe(48))"'
            )

    @staticmethod
    def suggest_secret() -> str:
        return _secrets.token_urlsafe(48)


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
