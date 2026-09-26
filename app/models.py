from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


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
    context_id: Optional[UUID] = None
    previous_hash: Optional[str] = None
    record_hash: str
    signature: Optional[str] = None
    public_key: Optional[str] = None


class CaptureTimeContext(BaseModel):
    """Evidence-facing timing contract returned by local edge-time."""

    context_id: UUID
    capture_utc: datetime
    capture_monotonic_ns: int

    device_id: str

    selected_source: str
    source_observation: TimeObservation
    uncertainty_ms: float
    freshness: str
    freshness_age_ms: float
    synchronization_state: str

    authority_id: Optional[str] = None
    authority_source: Optional[str] = None
    consistency_state: str
    consistency_offset_ms: Optional[float] = None
    consistency_uncertainty_ms: Optional[float] = None
    consistency_threshold_ms: Optional[float] = None

    holdover_state: str

    attestation_sequence: int
    attestation_record_hash: str
    attestation_signature: Optional[str] = None
