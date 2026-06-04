
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DOUBAO_API_KEY: str
    DOUBAO_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"
    DOUBAO_MODEL: str
    DOUBAO_CODE_MODEL: str
    LLM_TIMEOUT: float = 30.0
    LLM_MAX_RETRIES: int = 1
    LLM_MAX_TOKENS: int = 256

    LOG_DIR: str = "./logs"
    STRATEGY_DIR: str = "./strategies"

    DEFAULT_PLAYERS: int = 6


settings = Settings()
