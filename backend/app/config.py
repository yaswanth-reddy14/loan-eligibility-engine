from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://loan:loan_local@localhost:5432/loan"
    aws_region: str = "ap-south-1"
    s3_endpoint: str | None = "http://localhost:9000"
    s3_public_endpoint: str | None = "http://localhost:9000"
    s3_bucket: str = "loan-uploads"
    api_token: str = Field(min_length=24)
    workflow_secret: str = Field(min_length=24)
    n8n_url: str = "http://localhost:5678"
    email_delivery_mode: str = "preview"
    notification_test_inbox: str = "demo@loan.test"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    ses_sender: str = ""
    demo_mode: bool = True
    max_upload_bytes: int = 20 * 1024 * 1024
    batch_size: int = 500
    frontend_dir: str = "frontend"

    @model_validator(mode="after")
    def safe_mode(self) -> "Settings":
        if self.email_delivery_mode not in {"preview", "test"}:
            raise ValueError("Only preview and allowlisted test delivery are supported")
        from email_validator import validate_email

        validate_email(self.notification_test_inbox, check_deliverability=False, test_environment=True)
        return self


@lru_cache
def settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # Required secrets are loaded from the environment.
