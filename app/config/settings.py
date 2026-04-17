from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/app_db"
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"
    SECRET_KEY: str = "YOUR-SUPER-SECRET-KEY-REPLACE-IN-PRODUCTION"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_REGION: str = "us-east-1"
    SES_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str | None = None
    AWS_SES_SENDER: str | None = None
    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ORIGINS: str = "https://www.fasigms.africa,https://admin.fasigms.africa,https://dev.admin.fasigms.africa,https://dev.fasigms.africa,http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins_list(self) -> list[str]:
        """Parses the comma-separated CORS_ORIGINS string into a list of stripped origins."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

settings = Settings()