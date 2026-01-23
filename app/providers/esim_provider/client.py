import httpx
from app.core.config import settings
from app.providers.esim_provider.schemas import (
    ImsiTokenResponse, ImsiFuelResponse, ImsiInfoResponse, 
    ImsiListResponse, ImsiListItem, TopUpResponse, RevokeResponse, AssignResponse
)
from app.common.exceptions import AppError
from app.common.logging import logger
from typing import List, Optional, Dict
import json
import time
import csv
import io

class EsimProviderClient:
    def __init__(self):
        self.base_url = settings.IMSI_API_URL
        self.username = settings.IMSI_USERNAME
        self.password = settings.IMSI_PASSWORD
        self._token: Optional[str] = None
        self._token_expires_at: Optional[float] = None

    async def _get_token(self) -> str:
        # Check if token exists and is valid (with 60s buffer)
        if self._token and self._token_expires_at:
            if time.time() < (self._token_expires_at - 60):
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
                # Set expiration time (current time + expires_in)
                self._token_expires_at = time.time() + token_resp.expires_in
                return self._token
            except httpx.HTTPError as e:
                logger.error(f"Provider Auth Failed: {e}")
                raise AppError(503, "Provider unavailable")

    async def _request(self, method: str, endpoint: str, data: dict = None, retry_auth: bool = True) -> dict:
        token = await self._get_token()
        url = f"{self.base_url}{endpoint}"
        
        headers = {
            "Authorization": f"Bearer {token}"
        }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                if method == "GET":
                    response = await client.get(url, headers=headers)
                elif method == "POST":
                    response = await client.post(url, headers=headers, json=data)
                else:
                    raise ValueError(f"Unsupported method {method}")
                
                # Retrieve new token if unauthorized
                if response.status_code == 401 and retry_auth:
                    logger.warning(f"Provider Token Expired (401). Retrying request: {url}")
                    self._token = None
                    self._token_expires_at = 0
                    return await self._request(method, endpoint, data, retry_auth=False)

                response.raise_for_status()
                
                try:
                    return response.json()
                except json.JSONDecodeError:
                    return json.loads(response.text)
                    
            except httpx.HTTPError as e:
                status_code = response.status_code if 'response' in locals() else 502
                error_text = response.text if 'response' in locals() else str(e)
                logger.error(f"Provider Request Failed: {e} | URL: {url} | Details: {error_text}")
                # Sometimes 4xx errors return valid JSON body with error info
                # We should propagate specific errors if possible
                raise AppError(status_code, "Provider Error")

    async def get_balance(self) -> ImsiFuelResponse:
        # Provider Endpoint: GET /fuel
        data = await self._request("GET", "/fuel")
        if isinstance(data, str):
            data = json.loads(data)
        return ImsiFuelResponse(**data)

    async def get_imsi_info(self, imsi: str) -> ImsiInfoResponse:
        # Provider Endpoint: GET /imsi/{imsi}
        data = await self._request("GET", f"/imsi/{imsi}")
        # API Doc says: returns Dict stringified
        if isinstance(data, str):
            data = json.loads(data)
        return ImsiInfoResponse(**data)

    async def list_imsis(self) -> List[ImsiListItem]:
        # Provider Endpoint: GET /list
        data = await self._request("GET", "/list")
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse list response: {data}")
                return []
        
        all_imsis = []
        for key, value in data.items():
            if isinstance(value, list):
                for item in value:
                    try:
                        if isinstance(item, dict):
                            all_imsis.append(ImsiListItem(**item))
                        elif isinstance(item, list) and len(item) >= 3:
                            all_imsis.append(ImsiListItem(
                                imsi=str(item[0]),
                                msisdn=str(item[1]),
                                balance=float(item[2])
                            ))
                    except Exception as e:
                        logger.error(f"Failed to parse IMSI item {item}: {e}")
        return all_imsis

    async def top_up(self, imsi: str, amount: float) -> TopUpResponse:
        # Provider Endpoint: GET /topup/{imsi}/{amount}
        url = f"/topup/{imsi}/{amount}"
        data = await self._request("GET", url)
        if isinstance(data, str):
            data = json.loads(data)
        
        resp = TopUpResponse(**data)
        if resp.NOT_ADDED is not None or resp.REASON:
            error_msg = resp.REASON or "Top-up failed at provider"
            logger.error(f"Provider Top-up Failed: {error_msg} | IMSI: {imsi} | Data: {data}")
            raise AppError(400, f"Provider error: {error_msg}")
            
        return resp

    async def get_revoked_msisdns(self) -> List[str]:
        # Provider Endpoint: GET /revoked
        data = await self._request("GET", "/revoked")
        if isinstance(data, str):
            data = json.loads(data)
        return data

    async def assign_msisdn(self, imsi: str, msisdn: str) -> AssignResponse:
        # Provider Endpoint: GET /assign/{imsi}/{msisdn}
        data = await self._request("GET", f"/assign/{imsi}/{msisdn}")
        if isinstance(data, str):
            data = json.loads(data)
        return AssignResponse(**data)
    
    async def revoke_msisdn(self, imsi: str) -> RevokeResponse:
        # Provider Endpoint: GET /revoke/{imsi}
        data = await self._request("GET", f"/revoke/{imsi}")
        if isinstance(data, str):
            data = json.loads(data)
        return RevokeResponse(**data)

    async def fetch_esim_snapshots(self) -> List[Dict[str, str]]:
        """
        Fetches eSIM snapshot CSV and returns a list of dictionaries with ICCID and ACTIVATION CODE.
        """
        token = await self._get_token()
        url = f"{self.base_url}/esimssnapshot"
        headers = {
            "Authorization": f"Bearer {token}"
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.get(url, headers=headers)
                
                if response.status_code == 401:
                    logger.warning("Provider Token Expired (401) during snapshot. Retrying...")
                    self._token = None
                    self._token_expires_at = 0
                    token = await self._get_token()
                    headers["Authorization"] = f"Bearer {token}"
                    response = await client.get(url, headers=headers)

                response.raise_for_status()

                content = response.text
                if not content:
                    return []

                results = []
                csv_file = io.StringIO(content)
                reader = csv.DictReader(csv_file)
                
                for row in reader:
                    row_clean = {k.strip(): v for k, v in row.items() if k}
                    iccid = row_clean.get("ICCID")
                    activation_code = row_clean.get("ACTIVATION CODE")
                    
                    if iccid and activation_code:
                        results.append({
                            "iccid": iccid,
                            "activation_code": activation_code
                        })
                
                return results

            except httpx.HTTPError as e:
                logger.error(f"Provider Snapshot Failed: {e}")
                raise AppError(503, "Failed to fetch eSIM snapshot from provider")
            except Exception as e:
                logger.error(f"Snapshot Parsing Error: {e}")
                raise AppError(500, "Failed to parse provider response")
