import time
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .attestation import AttestationStore
from .models import CaptureTimeContext
from .sources import (
    gnss_observation,
    ntp_observation,
    rtc_observation,
    system_observation,
    http_observation,
)


class TimeEngine:
    def __init__(self, settings):
        self.settings = settings
        self.attestations = AttestationStore(settings)
        self.last = None
        self.last_state = "STARTING"
        self.observations = []

    def collect(self, include_authority=True):
        obs = []

        priorities = set(self.settings.priorities)

        if include_authority and "authority" in priorities:
            if self.settings.authority_url:
                authority_url = (
                    self.settings.authority_url.rstrip("/")
                    + "/authority/time"
                )

                authority = http_observation(
                    authority_url,
                    "authority",
                    "authority",
                    self.settings.http_timeout_seconds,
                )

                if authority:
                    obs.append(authority)

        if "gnss" in priorities:
            observation = gnss_observation(self.settings)
            if observation:
                obs.append(observation)

        if "rtc" in priorities:
            observation = rtc_observation(self.settings)
            if observation:
                obs.append(observation)

        if "ntp" in priorities:
            observation = ntp_observation(self.settings)
            if observation:
                obs.append(observation)

        # The system source remains available as the final local fallback.
        obs.append(system_observation(self.settings))

        self.observations = obs
        return obs

    def select(self, include_authority=True):
        obs = self.collect(include_authority=include_authority)

        by = {
            observation.source_id: observation
            for observation in obs
            if observation.valid
        }

        selected = None

        for name in self.settings.priorities:
            if not include_authority and name == "authority":
                continue

            if name in by:
                selected = by[name]
                break

        if selected is None and self.settings.allow_holdover and self.last is not None:
            self.last_state = "HOLDOVER"
            return self.last, self.last_state

        if selected is None:
            selected = system_observation(self.settings)
            self.last_state = "UNSYNCHRONIZED"
            return selected, self.last_state

        self.last = selected
        self.last_state = (
            "SYNCHRONIZED"
            if selected.uncertainty_ms <= self.settings.max_uncertainty_ms
            else "DEGRADED"
        )

        return selected, self.last_state

    def response(self):
        selected, state = self.select()
        response_monotonic = time.monotonic_ns()

        # The selected observation is timestamped at its own observation
        # point. Advance it to the response/capture point using the local
        # monotonic clock. This makes the UTC value represent the instant
        # at which edge-time supplied the context, rather than the HTTP
        # response latency alone. It remains an estimate subject to the
        # source uncertainty and any unmodeled local clock drift.
        delta_ns = max(
            0,
            response_monotonic - selected.observed_monotonic_ns,
        )
        response_utc = selected.utc + timedelta(
            microseconds=delta_ns / 1000.0
        )

        return {
            "utc": response_utc,
            "monotonic_ns": response_monotonic,
            "selected_source": selected.source_id,
            "authority_mode": (
                "platform"
                if selected.source_id == "authority"
                else "local_fallback"
            ),
            "state": state,
            "uncertainty_ms": selected.uncertainty_ms,
            "device_id": self.settings.effective_device_id,
            "authority_id": self.settings.authority_id or None,
            "source_observations": self.observations,
        }

    def authority_response(self):
        selected, state = self.select(include_authority=False)

        return {
            "source_id": "authority",
            "source_type": "authority",
            "utc": selected.utc,
            "uncertainty_ms": selected.uncertainty_ms,
            "valid": selected.valid,
            "observed_monotonic_ns": time.monotonic_ns(),
            "observed_wall_utc": selected.observed_wall_utc,
            "authority_id": (
                self.settings.authority_id
                or self.settings.effective_device_id
            ),
            "authority_role": self.settings.role,
            "selected_local_source": selected.source_id,
            "state": state,
            "details": {
                "device_id": self.settings.effective_device_id,
                "source_observation": selected.model_dump(mode="json"),
            },
        }

    def consistency_response(self):
        observed_at = time.monotonic_ns()

        if self.settings.is_authority:
            selected, state = self.select(include_authority=False)

            return {
                "device_id": self.settings.effective_device_id,
                "role": "authority",
                "observed_monotonic_ns": observed_at,
                "local": {
                    "utc": selected.utc,
                    "selected_source": selected.source_id,
                    "state": state,
                    "uncertainty_ms": selected.uncertainty_ms,
                },
                "authority": {
                    "authority_id": (
                        self.settings.authority_id
                        or self.settings.effective_device_id
                    ),
                    "reachable": True,
                    "utc": selected.utc,
                    "uncertainty_ms": selected.uncertainty_ms,
                },
                "measurement": None,
                "consistency": {
                    "state": "AUTHORITY",
                    "offset_ms": 0.0,
                    "uncertainty_ms": selected.uncertainty_ms,
                    "within_threshold": True,
                    "threshold_ms": self.settings.consistency_threshold_ms,
                },
            }

        if not self.settings.authority_url:
            selected, state = self.select()

            return {
                "device_id": self.settings.effective_device_id,
                "role": self.settings.role,
                "observed_monotonic_ns": observed_at,
                "local": {
                    "utc": selected.utc,
                    "selected_source": selected.source_id,
                    "state": state,
                    "uncertainty_ms": selected.uncertainty_ms,
                },
                "authority": {
                    "authority_id": self.settings.authority_id or None,
                    "reachable": False,
                    "utc": None,
                    "uncertainty_ms": None,
                },
                "measurement": None,
                "consistency": {
                    "state": "NO_AUTHORITY",
                    "offset_ms": None,
                    "uncertainty_ms": None,
                    "within_threshold": False,
                    "threshold_ms": self.settings.consistency_threshold_ms,
                },
            }

        authority_url = (
            self.settings.authority_url.rstrip("/")
            + "/authority/time"
        )

        started_monotonic = time.monotonic_ns()
        started_wall = time.time_ns()

        authority = http_observation(
            authority_url,
            "authority",
            "authority",
            self.settings.http_timeout_seconds,
        )

        finished_monotonic = time.monotonic_ns()
        finished_wall = time.time_ns()

        selected, state = self.select()

        started_datetime = datetime.fromtimestamp(
            started_wall / 1_000_000_000,
            timezone.utc,
        )
        finished_datetime = datetime.fromtimestamp(
            finished_wall / 1_000_000_000,
            timezone.utc,
        )

        measurement = {
            "request_started_wall_utc": started_datetime,
            "request_finished_wall_utc": finished_datetime,
            "round_trip_ms": (
                finished_monotonic - started_monotonic
            ) / 1_000_000.0,
        }

        if authority is None:
            return {
                "device_id": self.settings.effective_device_id,
                "role": self.settings.role,
                "observed_monotonic_ns": observed_at,
                "local": {
                    "utc": selected.utc,
                    "selected_source": selected.source_id,
                    "state": state,
                    "uncertainty_ms": selected.uncertainty_ms,
                },
                "authority": {
                    "authority_id": self.settings.authority_id or None,
                    "reachable": False,
                    "utc": None,
                    "uncertainty_ms": None,
                },
                "measurement": measurement,
                "consistency": {
                    "state": "AUTHORITY_UNREACHABLE",
                    "offset_ms": None,
                    "uncertainty_ms": None,
                    "within_threshold": False,
                    "threshold_ms": self.settings.consistency_threshold_ms,
                },
            }

        round_trip_ms = measurement["round_trip_ms"]
        midpoint_ns = (started_monotonic + finished_monotonic) // 2
        midpoint_wall = started_datetime + (
            finished_datetime - started_datetime
        ) / 2

        offset_ms = (
            midpoint_wall - authority.utc
        ).total_seconds() * 1000.0

        measurement_uncertainty_ms = (
            authority.uncertainty_ms + (round_trip_ms / 2.0)
        )

        within_threshold = (
            abs(offset_ms) <= self.settings.consistency_threshold_ms
        )

        measurement.update(
            {
                "midpoint_wall_utc": midpoint_wall,
                "midpoint_monotonic_ns": midpoint_ns,
                "offset_ms": offset_ms,
                "uncertainty_ms": measurement_uncertainty_ms,
            }
        )

        return {
            "device_id": self.settings.effective_device_id,
            "role": self.settings.role,
            "observed_monotonic_ns": observed_at,
            "local": {
                "utc": selected.utc,
                "selected_source": selected.source_id,
                "state": state,
                "uncertainty_ms": selected.uncertainty_ms,
            },
            "authority": {
                "authority_id": self.settings.authority_id or None,
                "reachable": True,
                "utc": authority.utc,
                "observed_wall_utc": authority.observed_wall_utc,
                "uncertainty_ms": authority.uncertainty_ms,
                "source": authority.details.get("selected_local_source"),
            },
            "measurement": measurement,
            "consistency": {
                "state": (
                    "CONSISTENT"
                    if within_threshold
                    else "OUT_OF_THRESHOLD"
                ),
                "offset_ms": offset_ms,
                "uncertainty_ms": measurement_uncertainty_ms,
                "within_threshold": within_threshold,
                "threshold_ms": self.settings.consistency_threshold_ms,
            },
        }

    @staticmethod
    def freshness_for(observation, now_monotonic_ns, settings):
        age_ms = max(
            0.0,
            (now_monotonic_ns - observation.observed_monotonic_ns)
            / 1_000_000.0,
        )

        if age_ms <= settings.freshness_stale_ms:
            state = "FRESH"
        elif age_ms <= settings.freshness_expired_ms:
            state = "STALE"
        else:
            state = "EXPIRED"

        return state, age_ms

    def attest_response(self, response, context_id=None):
        payload = {
            key: (
                value.isoformat()
                if hasattr(value, "isoformat")
                else value
            )
            for key, value in response.items()
            if key != "source_observations"
        }

        payload["record_type"] = "time_attestation"
        payload["created_utc"] = datetime.now(timezone.utc).isoformat()
        payload["observations"] = [
            observation.model_dump(mode="json")
            for observation in response["source_observations"]
        ]

        if context_id is not None:
            payload["context_id"] = str(context_id)

        return self.attestations.append(payload)

    def attest(self):
        response = self.response()
        return self.attest_response(response)

    def capture_context(self):
        context_id = uuid4()
        response = self.response()
        selected = next(
            observation
            for observation in response["source_observations"]
            if observation.source_id == response["selected_source"]
        )

        now_monotonic_ns = response["monotonic_ns"]
        freshness, freshness_age_ms = self.freshness_for(
            selected,
            now_monotonic_ns,
            self.settings,
        )

        consistency = self.consistency_response()
        authority = next(
            (
                observation
                for observation in response["source_observations"]
                if observation.source_id == "authority"
            ),
            None,
        )

        authority_source = None
        if authority is not None:
            authority_source = authority.details.get(
                "selected_local_source"
            )

        attestation = self.attest_response(
            response,
            context_id=context_id,
        )

        return CaptureTimeContext(
            context_id=context_id,
            capture_utc=response["utc"],
            capture_monotonic_ns=response["monotonic_ns"],
            device_id=response["device_id"],
            selected_source=response["selected_source"],
            source_observation=selected,
            uncertainty_ms=response["uncertainty_ms"],
            freshness=freshness,
            freshness_age_ms=freshness_age_ms,
            synchronization_state=response["state"],
            authority_id=(
                response["authority_id"]
                or (
                    authority.details.get("authority_id")
                    if authority is not None
                    else None
                )
            ),
            authority_source=authority_source,
            consistency_state=consistency["consistency"]["state"],
            consistency_offset_ms=consistency["consistency"].get(
                "offset_ms"
            ),
            consistency_uncertainty_ms=consistency["consistency"].get(
                "uncertainty_ms"
            ),
            consistency_threshold_ms=consistency["consistency"].get(
                "threshold_ms"
            ),
            holdover_state=(
                "HOLDOVER"
                if response["state"] == "HOLDOVER"
                else "NOT_HOLDOVER"
            ),
            attestation_sequence=attestation["sequence"],
            attestation_record_hash=attestation["record_hash"],
            attestation_signature=attestation.get("signature"),
        )
