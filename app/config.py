"""Application configuration.

Settings are read from environment variables (optionally via a `.env` file).
See `.env.example` for the variables that can be overridden.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Defaults to a local SQLite file so the project runs with zero setup.
    # Point this at Postgres/MySQL/etc. in production, e.g.:
    #   postgresql+psycopg2://user:password@localhost:5432/orders
    database_url: str = "sqlite:///./orders.db"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")


settings = Settings()
