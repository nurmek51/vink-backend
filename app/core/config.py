from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "Vink Backend"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = "nurmek-vink-dev"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 days
    
    # Firebase
    FIREBASE_CREDENTIALS_PATH: str = "vink-testik.json"
    
    # Provider (Imsimarket)
    IMSI_API_URL: str = "https://mit.imsipay.com/b2b"
    IMSI_USERNAME: str = "flextest@notmail.com"
    IMSI_PASSWORD: str = "33mRC6E1R"
    
    # Mock OTP
    MOCK_OTP_CODE: str = "123456"
    
    # Admin API Key (SHA-256 hash)
    ADMIN_API_KEY_HASH: str = "941ca676050c99429ad77bf8b8f796ce8036ee98fb185b0d6c0d2834a3eb4b2f"
    
    class Config:
        env_file = ".env"

settings = Settings()
