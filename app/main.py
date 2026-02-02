from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.common.logging import setup_logging
from app.common.exceptions import AppError
from app.modules.auth.router import router as auth_router
from app.modules.users.router import router as users_router
from app.modules.esim.router import router as esim_router
from app.modules.wallet.router import router as wallet_router
from app.infrastructure.firestore import init_firestore
from app.common.responses import ErrorResponse, ErrorDetail
from contextlib import asynccontextmanager

setup_logging()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_firestore()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    error_content = ErrorResponse(
        error=ErrorDetail(message=exc.detail["message"], code=exc.detail["code"])
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=error_content.dict()
    )

app.include_router(auth_router, prefix=settings.API_V1_STR, tags=["Auth"])
app.include_router(users_router, prefix=settings.API_V1_STR, tags=["Users"])
app.include_router(esim_router, prefix=settings.API_V1_STR, tags=["eSIM"])
app.include_router(wallet_router, prefix=settings.API_V1_STR, tags=["Wallet"])

@app.get("/")
async def root():
    return {"message": "Vink Backend API"}
