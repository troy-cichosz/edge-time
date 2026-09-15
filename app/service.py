import time

from .attestation import AttestationStore
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

        # The system source remains available as the final local
        # fallback regardless of whether it is explicitly listed
        # in source_priority.
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

        return {
            "utc": selected.utc,
            "monotonic_ns": time.monotonic_ns(),
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

    def attest(self):
        response = self.response()

        payload = {
            key: (
                value.isoformat()
                if hasattr(value, "isoformat")
                else value
            )
            for key, value in response.items()
            if key != "source_observations"
        }

        payload["observations"] = [
            observation.model_dump(mode="json")
            for observation in response["source_observations"]
        ]

        return self.attestations.append(payload)