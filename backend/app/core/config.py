from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):

    DATABASE_URL: str
    POSTGRES_USER:str
    POSTGRES_PASSWORD:str
    POSTGRES_DB:str
    PGADMIN_DEFAULT_EMAIL:str
    PGADMIN_DEFAULT_PASSWORD:str
    REDIS_HOST: str
    REDIS_PORT: str
    
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Email
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: str
    MAIL_SERVER: str
    VERIFICATION_CODE_EXPIRE_HOUR: int = 24

    class Config:
        env_file = ".env"


@lru_cache
def get_settings():
    return Settings()