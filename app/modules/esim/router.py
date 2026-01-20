from fastapi import APIRouter, Depends
from app.modules.esim.service import EsimService
from app.modules.esim.schemas import (
    Esim, Tariff, ActivateRequest, 
    UpdateSettingsRequest, UsageData, TopUpEsimRequest
)
from app.core.dependencies import get_current_user, require_app_permission
from app.modules.users.schemas import User
from app.common.responses import DataResponse, ResponseBase
from typing import List

router = APIRouter()
service = EsimService()

@router.get("/esims", response_model=DataResponse[List[Esim]])
async def get_esims(
    current_user: User = Depends(require_app_permission("vink-sim"))
):
    esims = await service.get_user_esims(current_user)
    return DataResponse(data=esims)

@router.get("/esims/{id}", response_model=DataResponse[Esim])
async def get_esim_by_id(
    id: str,
    current_user: User = Depends(require_app_permission("vink-sim"))
):
    esim = await service.get_esim_by_id(current_user, id)
    return DataResponse(data=esim)

@router.post("/esims/{id}/activate")
async def activate_esim(
    id: str,
    request: ActivateRequest,
    current_user: User = Depends(require_app_permission("vink-sim"))
):
    esim = await service.activate_esim(current_user, id, request.activation_code)
    return DataResponse(data=esim)

@router.post("/esims/{id}/deactivate")
async def deactivate_esim(
    id: str,
    current_user: User = Depends(require_app_permission("vink-sim"))
):
    await service.deactivate_esim(current_user, id)
    return ResponseBase()

@router.put("/esims/{id}/settings")
async def update_esim_settings(
    id: str,
    request: UpdateSettingsRequest,
    current_user: User = Depends(require_app_permission("vink-sim"))
):
    esim = await service.update_esim_settings(current_user, id, request)
    return DataResponse(data=esim)

@router.get("/esims/{id}/usage", response_model=DataResponse[UsageData])
async def get_esim_usage(
    id: str,
    current_user: User = Depends(require_app_permission("vink-sim"))
):
    usage = await service.get_esim_usage(current_user, id)
    return DataResponse(data=usage)

@router.get("/tariffs", response_model=DataResponse[List[Tariff]])
async def get_tariffs(
    current_user: User = Depends(require_app_permission("vink-sim"))
):
    tariffs = await service.get_tariffs()
    return DataResponse(data=tariffs)

@router.post("/esims/purchase", response_model=DataResponse[Esim])
async def purchase_esim(
    current_user: User = Depends(require_app_permission("vink-sim"))
):
    esim = await service.purchase_esim(current_user)
    return DataResponse(data=esim)
