import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Vink Backend"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = "nurmek-vink-dev"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 # 1 hour
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30 # 30 days
    BACKEND_CORS_ORIGINS: List[str] = [
        "https://vink-sim.vercel.app",
        "http://localhost:3000",
    ]
    
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
    
    # Twilio
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_SERVICE_SID: Optional[str] = None
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

settings = Settings()

def debug_env_vars():
    """Prints all environment variables in a safe way for debugging."""
    print(f"--- ENVIRONMENT DEBUG ---")
    print(f"CWD: {os.getcwd()}")
    try:
        print(f"FILES IN CWD: {os.listdir('.')}")
    except Exception as e:
        print(f"Error listing CWD: {e}")
    
    if os.path.exists(".env"):
        print(".env file exists")
        try:
            with open(".env", "r") as f:
                lines = f.readlines()
                print(f".env content (masked):")
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        val = val.strip().strip('"').strip("'")
                        masked_val = val[:4] + "****" if len(val) > 4 else "****"
                        print(f"  {key}={masked_val}")
                    else:
                        print(f"  (Line without =): {line}")
        except Exception as e:
            print(f"Error reading .env: {e}")
    else:
        print(".env file NOT FOUND")
        
    print(f"Settings loaded in Python:")
    for key in ["TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_SERVICE_SID"]:
        val = getattr(settings, key)
        print(f"  {key}={'FOUND' if val else 'MISSING'}")
    print(f"-------------------------")

# Run debug on import
debug_env_vars()
