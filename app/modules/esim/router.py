from fastapi import APIRouter, Depends
from app.modules.esim.service import EsimService
from app.modules.esim.schemas import Esim, Tariff, PurchaseRequest
from app.core.dependencies import get_current_user, require_app_permission
from app.modules.users.schemas import User
from app.common.responses import DataResponse
from typing import List

router = APIRouter()
service = EsimService()

@router.get("/esims", response_model=DataResponse[List[Esim]])
async def get_esims(
    current_user: User = Depends(require_app_permission("vink-sim"))
):
    esims = await service.get_user_esims(current_user)
    return DataResponse(data=esims)

@router.get("/tariffs", response_model=DataResponse[List[Tariff]])
async def get_tariffs(
    current_user: User = Depends(require_app_permission("vink-sim"))
):
    tariffs = await service.get_tariffs()
    return DataResponse(data=tariffs)

@router.post("/esim/purchase", response_model=DataResponse[Esim])
async def purchase_esim(
    request: PurchaseRequest,
    current_user: User = Depends(require_app_permission("vink-sim"))
):
    esim = await service.purchase_esim(current_user, request.tariff_id)
    return DataResponse(data=esim)
