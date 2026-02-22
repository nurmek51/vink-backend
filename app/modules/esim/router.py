from fastapi import APIRouter, Depends
from app.modules.esim.service import EsimService
from app.modules.esim.schemas import (
    Esim, Tariff, ActivateRequest, 
    UpdateSettingsRequest, UsageData, TopUpEsimRequest,
    UnassignImsiRequest
)
from app.core.dependencies import get_current_user, require_app_permission, require_admin_api_key
from app.core.jwt import decode_token
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

@router.get("/esims/unassigned", response_model=DataResponse[List[Esim]])
async def get_unassigned_esims(
    _admin_key: str = Depends(require_admin_api_key)
):
    esims = await service.get_unassigned_esims()
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
async def get_tariffs():
    tariffs = await service.get_tariffs()
    return DataResponse(data=tariffs)

@router.post("/esims/purchase", response_model=DataResponse[Esim])
async def purchase_esim(
    current_user: User = Depends(require_app_permission("vink-sim"))
):
    esim = await service.purchase_esim(current_user)
    return DataResponse(data=esim)

@router.post("/esims/unassign")
async def unassign_imsi(
    request: UnassignImsiRequest,
    _admin_key: str = Depends(require_admin_api_key)
):
    await service.unassign_imsi_admin(request.imsi)
    return ResponseBase()

@router.post("/esims/internal/sync-activation-codes")
async def sync_esim_activation_codes(
    _admin_key: str = Depends(require_admin_api_key)
):
    result = await service.sync_activation_codes()
    return DataResponse(data=result)


@router.post("/esims/internal/{id}/run-autopay")
async def run_esim_autopay_internal(
    id: str,
    _admin_key: str = Depends(require_admin_api_key)
):
    result = await service.run_autopay_for_esim_admin(id)
    return DataResponse(data=result)
