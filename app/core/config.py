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
    
    # Admin API Key
    ADMIN_API_KEY: str = "nurmekadminapi!"
    # Admin API Key (SHA-256 hash)
    ADMIN_API_KEY_HASH: str = "35b801e69c7fef51490614f09ffd50818a35d18260072eabccc65882aaa77eac"
    
    class Config:
        env_file = ".env"

settings = Settings()
