from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from app.core.config import settings
from app.core.jwt import decode_token
from app.common.exceptions import UnauthorizedError, ForbiddenError
from app.modules.users.schemas import User
from app.modules.users.repository import UserRepository

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    token = credentials.credentials
    payload = decode_token(token)
    if payload is None:
        raise UnauthorizedError("Could not validate credentials")
    
    user_id: str = payload.get("sub")
    if user_id is None:
        raise UnauthorizedError("Invalid token payload: missing user_id")
    
    # Fetch comprehensive user data from Repository to ensure validity and freshness
    repo = UserRepository()
    user = await repo.get_user(user_id)
    
    if user is None:
        raise UnauthorizedError("User not found")
        
    return user

from datetime import datetime

def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    # Add logic to check if user is active if needed
    return current_user

def require_app_permission(app_name: str):
    def _require_app_permission(current_user: User = Depends(get_current_user)):
        if app_name not in current_user.apps_enabled:
            raise ForbiddenError(f"User does not have access to {app_name}")
        return current_user
    return _require_app_permission
