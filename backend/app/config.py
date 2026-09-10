from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Adaptive Cache System"
    app_version: str = "0.1.0"
    cache_backend: str = "inmemory"
    data_backend: str = "simulated"
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "adaptive_cache"
    database_user: str = "adaptive"
    database_password: str = "adaptive"
    database_url: str | None = None

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
