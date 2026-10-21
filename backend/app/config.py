from functools import lru_cache

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://loan:loan_local@localhost:5432/loan"
    aws_region: str = Field(
        default="ap-south-1", validation_alias=AliasChoices("AWS_REGION", "AWS_DEFAULT_REGION", "aws_region")
    )
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
    n8n_ses_enabled: bool = False
    llm_enabled: bool = False
    gemini_api_key: str = ""
    gemini_model: str = Field(default="", pattern=r"^[A-Za-z0-9._-]*$")
    llm_max_calls_per_process: int = Field(default=3, ge=0, le=20)
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
