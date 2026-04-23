from pydantic import BaseModel
from typing import Optional, Any


class ErrorResponse(BaseModel):
    detail: str


class SuccessResponse(BaseModel):
    message: str
    data: Optional[Any] = None
