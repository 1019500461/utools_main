from functools import cached_property
import ssl
from urllib.parse import parse_qs, unquote, urlparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_title: str = "utools-main"
    database_url: str = Field(default="", alias="DATABASE_URL")
    database_ssl_root_cert: str = Field(default="", alias="DATABASE_SSL_ROOT_CERT")
    secret_key: str = Field(default="change-me-in-env", alias="SECRET_KEY")
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = Field(default=60 * 24 * 7, alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES")
    cors_origins: list[str] = Field(default=["http://localhost:5173", "http://127.0.0.1:5173"], alias="CORS_ORIGINS")

    @cached_property
    def tortoise_orm(self) -> dict:
        return {
            "connections": {"default": self._build_database_config()},
            "apps": {
                "models": {
                    "models": ["app.modules.user.models", "app.modules.role.models"],
                    "default_connection": "default",
                }
            },
            "use_tz": False,
            "timezone": "Asia/Shanghai",
        }

    def _build_database_config(self) -> dict:
        if not self.database_url:
            raise RuntimeError("DATABASE_URL is required. Copy .env.example to .env and fill PostgreSQL settings.")

        parsed = urlparse(self.database_url)
        query = parse_qs(parsed.query)
        ssl_mode = query.get("sslmode", query.get("ssl", ["false"]))[0].lower()
        return {
            "engine": "tortoise.backends.asyncpg",
            "credentials": {
                "host": parsed.hostname,
                "port": parsed.port or 5432,
                "user": unquote(parsed.username or ""),
                "password": unquote(parsed.password or ""),
                "database": parsed.path.lstrip("/") or "postgres",
                "ssl": self._build_ssl_context(ssl_mode),
            },
        }

    def _build_ssl_context(self, ssl_mode: str) -> ssl.SSLContext | bool:
        if ssl_mode not in {"1", "true", "yes", "require", "verify-ca", "verify-full"}:
            return False

        context = ssl.create_default_context()
        root_cert = self.database_ssl_root_cert.strip().replace("\\n", "\n")
        if root_cert:
            context.load_verify_locations(cadata=root_cert)
        if ssl_mode == "verify-ca":
            context.check_hostname = False
        return context


settings = Settings()
TORTOISE_ORM = settings.tortoise_orm if settings.database_url else {}
