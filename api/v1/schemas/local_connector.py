from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ConnectorClaimRequest(BaseModel):
    pairing_code: str = Field(..., min_length=6, max_length=6)
    device_name: str = Field("DSA Local Connector", min_length=1, max_length=128)


class ConnectorHeartbeatRequest(BaseModel):
    models: List[str] = Field(default_factory=list, max_length=50)


class ConnectorJobCompleteRequest(BaseModel):
    result: Dict[str, Any]
