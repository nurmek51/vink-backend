from typing import Any, Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")

class ResponseBase(BaseModel):
    success: bool = True
    message: str = "Success"
    meta: Optional[dict] = None

class DataResponse(ResponseBase, Generic[T]):
    data: Optional[T] = None

class ErrorDetail(BaseModel):
    message: str
    code: Any

class ErrorResponse(BaseModel):
    error: ErrorDetail
