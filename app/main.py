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

setup_logging()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

@app.on_event("startup")
async def startup_event():
    init_firestore()

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"message": exc.detail["message"], "code": exc.detail["code"]}}
    )

app.include_router(auth_router, prefix=settings.API_V1_STR, tags=["Auth"])
app.include_router(users_router, prefix=settings.API_V1_STR, tags=["Users"])
app.include_router(esim_router, prefix=settings.API_V1_STR, tags=["eSIM"])
app.include_router(wallet_router, prefix=settings.API_V1_STR, tags=["Wallet"])

@app.get("/")
async def root():
    return {"message": "Vink Backend API"}
