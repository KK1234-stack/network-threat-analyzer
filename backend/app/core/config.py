from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # JWT
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # MLflow
    MLFLOW_TRACKING_URI: str = "/app/mlruns"

    # Admin
    ADMIN_EMAIL: str = ""

    # App
    ENV: str = "development"

    class Config:
        env_file = ".env"


settings = Settings()
