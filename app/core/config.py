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
    
    class Config:
        env_file = ".env"

settings = Settings()
