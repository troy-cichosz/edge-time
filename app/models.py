from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime

class TimeObservation(BaseModel):
    source_id: str
    source_type: str
    utc: datetime
    uncertainty_ms: float = 1000.0
    valid: bool = True
    details: dict[str, Any] = Field(default_factory=dict)
    observed_monotonic_ns: int
    observed_wall_utc: datetime

class TimeResponse(BaseModel):
    utc: datetime
    monotonic_ns: int
    selected_source: str
    authority_mode: str
    state: str
    uncertainty_ms: float
    device_id: str
    authority_id: Optional[str] = None
    source_observations: list[TimeObservation] = Field(default_factory=list)

class Attestation(BaseModel):
    record_type: str = "time_attestation"
    sequence: int
    device_id: str
    created_utc: datetime
    selected_source: str
    utc: datetime
    monotonic_ns: int
    state: str
    uncertainty_ms: float
    observations: list[dict[str, Any]]
    previous_hash: Optional[str] = None
    record_hash: str
    signature: Optional[str] = None
    public_key: Optional[str] = None
