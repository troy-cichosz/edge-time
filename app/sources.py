import json
import socket
import time
import urllib.error
import urllib.request
import logging

logger = logging.getLogger(__name__)

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .config import Settings
from .models import TimeObservation


def now_utc():
    return datetime.now(timezone.utc)


def _parse_utc(value):
    if isinstance(value, datetime):
        result = value
    else:
        result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def system_observation(settings: Settings) -> TimeObservation:
    wall = now_utc()
    return TimeObservation(
        source_id="system",
        source_type="system",
        utc=wall,
        uncertainty_ms=1000.0,
        valid=settings.allow_system_source,
        observed_monotonic_ns=time.monotonic_ns(),
        observed_wall_utc=wall,
        details={"method": "local wall clock"},
    )


def file_observation(path: str, source_id: str, source_type: str) -> Optional[TimeObservation]:
    try:
        data = json.loads(Path(path).read_text())
        wall = now_utc()
        return TimeObservation(
            source_id=source_id,
            source_type=source_type,
            utc=_parse_utc(data["utc"]),
            uncertainty_ms=float(data.get("uncertainty_ms", 100.0)),
            valid=bool(data.get("valid", True)),
            observed_monotonic_ns=time.monotonic_ns(),
            observed_wall_utc=wall,
            details=data,
        )
    except (FileNotFoundError, KeyError, ValueError, TypeError, json.JSONDecodeError):
        return None


def http_observation(
    url: str,
    expected_source_id: str,
    expected_source_type: str,
    timeout: float,
) -> Optional[TimeObservation]:
    if not url:
        return None
    try:
        request = urllib.request.Request(
            url,
            method="GET",
            headers={"Accept": "application/json"},
        )
        started = time.monotonic_ns()
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        finished = time.monotonic_ns()

        if data.get("source_id") != expected_source_id:
            return None

        wall = now_utc()
        return TimeObservation(
            source_id=expected_source_id,
            source_type=expected_source_type,
            utc=_parse_utc(data["utc"]),
            uncertainty_ms=float(data.get("uncertainty_ms", 1000.0)),
            valid=bool(data.get("valid", False)),
            observed_monotonic_ns=finished,
            observed_wall_utc=wall,
            details={
                **data.get("details", {}),
                "endpoint": url,
                "request_elapsed_ms": (finished - started) / 1_000_000.0,
            },
        )
    except (OSError, urllib.error.URLError, urllib.error.HTTPError, ValueError,
            TypeError, KeyError, json.JSONDecodeError):
        return None


def gnss_observation(settings: Settings):
    url = settings.effective_gnss_url

    observation = http_observation(
        url,
        "gnss",
        "gnss",
        settings.http_timeout_seconds,
    )

    if observation is not None:
        logger.info(
            "GNSS observation acquired from %s: uncertainty_ms=%.3f",
            url,
            observation.uncertainty_ms,
        )
        return observation

    logger.warning(
        "GNSS HTTP observation unavailable from %s; attempting file fallback",
        url,
    )

    return file_observation(
        settings.gnss_observation_file,
        "gnss",
        "gnss",
    )

def rtc_observation(settings):
    return file_observation(settings.rtc_observation_file, "rtc", "rtc")


def ntp_observation(settings):
    try:
        import ntplib

        c = ntplib.NTPClient()
        r = c.request(
            settings.ntp_host,
            port=settings.ntp_port,
            version=4,
            timeout=1.5,
        )
        wall = now_utc()
        return TimeObservation(
            source_id="ntp",
            source_type="ntp",
            utc=datetime.fromtimestamp(r.tx_time, timezone.utc),
            uncertainty_ms=max(1.0, abs(r.offset) * 1000.0 + 5.0),
            valid=True,
            observed_monotonic_ns=time.monotonic_ns(),
            observed_wall_utc=wall,
            details={
                "server": settings.ntp_host,
                "offset_ms": r.offset * 1000.0,
                "delay_ms": r.delay * 1000.0,
            },
        )
    except Exception:
        return None


def hostname():
    return socket.gethostname()
