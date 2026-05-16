from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "On-Call Assistant API"
    app_version: str = "0.1.0"
    app_cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173"
    )
    data_dir: Path = Path("data")
    search_top_k: int = 5
    semantic_top_k: int = 5
    embedding_model_name: str = "BAAI/bge-small-zh-v1.5"
    embedding_query_instruction: str = "为这个句子生成表示以用于检索相关文章："
    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENAI_API_KEY", "AGENT_API_KEY"),
    )
    openai_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    openai_model: str = "gpt-4.1-mini"
    openai_temperature: float = 0.0

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.app_cors_origins.split(",")
            if origin.strip()
        ]

    @property
    def cors_allow_methods(self) -> list[str]:
        return ["GET", "POST", "OPTIONS"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
