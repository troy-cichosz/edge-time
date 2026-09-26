import socket
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="EDGE_TIME_",
        case_sensitive=False,
        extra="ignore",
    )

    role: str = "agent"
    host: str = "0.0.0.0"
    port: int = 8095

    device_id: str = ""
    node_id: str = ""

    authority_url: str = ""
    authority_id: str = ""

    gnss_url: str = ""
    gnss_host: str = ""
    gnss_port: int = 8096
    gnss_path: str = "/observation"

    source_priority: str = "authority,gnss,rtc,ntp,system"

    allow_system_source: bool = True
    allow_holdover: bool = True
    max_uncertainty_ms: float = 500.0
    consistency_threshold_ms: float = 500.0

    # Age of the selected source observation determines freshness.
    # These thresholds describe provenance quality; they do not change
    # source selection or synchronization state.
    freshness_stale_ms: float = 5000.0
    freshness_expired_ms: float = 30000.0

    state_dir: str = "/state"
    gnss_observation_file: str = "/state/gnss.json"
    rtc_observation_file: str = "/state/rtc.json"

    ntp_host: str = "pool.ntp.org"
    ntp_port: int = 123

    poll_seconds: int = 5

    attestation_key: str = "/state/identity.key"

    http_timeout_seconds: float = 2.0

    @property
    def priorities(self) -> List[str]:
        return [
            x.strip()
            for x in self.source_priority.split(",")
            if x.strip()
        ]

    @property
    def effective_device_id(self) -> str:
        return self.device_id or self.node_id or socket.gethostname()

    @property
    def is_authority(self) -> bool:
        return self.role.lower() in {"authority", "combined"}

    @property
    def effective_gnss_host(self) -> str:
        return self.gnss_host or self.effective_device_id

    @property
    def effective_gnss_url(self) -> str:
        if self.gnss_url:
            return self.gnss_url

        path = self.gnss_path
        if not path.startswith("/"):
            path = f"/{path}"

        return (
            f"http://{self.effective_gnss_host}:"
            f"{self.gnss_port}{path}"
        )
