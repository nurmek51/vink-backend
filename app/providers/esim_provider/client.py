import httpx
from app.core.config import settings
from app.providers.esim_provider.schemas import (
    ImsiTokenResponse, ImsiFuelResponse, ImsiInfoResponse, 
    ImsiListResponse, TopUpResponse, RevokeResponse, AssignResponse
)
from app.common.exceptions import AppError
from app.common.logging import logger
from typing import List, Optional
import json

class EsimProviderClient:
    def __init__(self):
        self.base_url = settings.IMSI_API_URL
        self.username = settings.IMSI_USERNAME
        self.password = settings.IMSI_PASSWORD
        self._token: Optional[str] = None

    async def _get_token(self) -> str:
        if self._token:
            # In a real app, check expiration
            return self._token
            
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/token",
                    data={"username": self.username, "password": self.password},
                    headers={"Content-Type": "application/x-www-form-urlencoded"}
                )
                response.raise_for_status()
                data = response.json()
                token_resp = ImsiTokenResponse(**data)
                self._token = token_resp.access_token
                return self._token
            except httpx.HTTPError as e:
                logger.error(f"Provider Auth Failed: {e}")
                raise AppError(503, "Provider unavailable")

    async def _request(self, method: str, endpoint: str, data: dict = None) -> dict:
        token = await self._get_token()
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{self.base_url}{endpoint}"
        
        async with httpx.AsyncClient() as client:
            try:
                if method == "GET":
                    response = await client.get(url, headers=headers)
                elif method == "POST":
                    response = await client.post(url, headers=headers, json=data)
                else:
                    raise ValueError(f"Unsupported method {method}")
                
                response.raise_for_status()
                
                # The API seems to return JSON strings sometimes based on the doc examples 
                # e.g. "{ ... }" wrapped in quotes? 
                # The doc says Reply example: "{ ... }"
                # If it returns a stringified JSON, we need to parse it.
                # But standard requests usually return dict. 
                # I'll assume standard JSON first, but handle string if needed.
                
                try:
                    return response.json()
                except json.JSONDecodeError:
                    # Maybe it's a stringified json?
                    return json.loads(response.text)
                    
            except httpx.HTTPError as e:
                logger.error(f"Provider Request Failed: {e} - {response.text if 'response' in locals() else ''}")
                raise AppError(502, "Provider Error")

    async def get_balance(self) -> ImsiFuelResponse:
        data = await self._request("GET", "/fuel")
        # Handle potential string response if the API is weird as per doc examples
        if isinstance(data, str):
            data = json.loads(data)
        return ImsiFuelResponse(**data)

    async def get_imsi_info(self, imsi: str) -> ImsiInfoResponse:
        data = await self._request("GET", f"/imsi/{imsi}")
        if isinstance(data, str):
            data = json.loads(data)
        return ImsiInfoResponse(**data)

    async def list_imsis(self) -> List[dict]:
        data = await self._request("GET", "/list")
        # The response is {"email": [list]}
        # We need to extract the list.
        if isinstance(data, str):
            data = json.loads(data)
        
        # Flatten the values
        all_imsis = []
        for key, value in data.items():
            if isinstance(value, list):
                all_imsis.extend(value)
        return all_imsis

    async def get_revoked_msisdns(self) -> List[str]:
        data = await self._request("GET", "/revoked")
        if isinstance(data, str):
            data = json.loads(data)
        return data

    async def assign_msisdn(self, imsi: str, msisdn: str) -> AssignResponse:
        data = await self._request("GET", f"/assign/{imsi}/{msisdn}")
        if isinstance(data, str):
            data = json.loads(data)
        return AssignResponse(**data)
