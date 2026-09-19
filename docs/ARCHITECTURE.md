# Architecture

`edge-time` provides distributed time selection and timing provenance for evidence-producing edge services.

## Logical Roles

1. **Source adapters** — GNSS, RTC, NTP, system clock, and platform authority observations.
2. **Time agent** — local source selection, fallback, existing holdover behavior, uncertainty, freshness, and monotonic correlation.
3. **Authority service** — platform-designated distribution point for the current timing architecture.
4. **Capture Time Context** — evidence-facing contract that binds the selected timing state to a capture/acquisition instant and its cryptographic attestation.

The controller remains the management/policy/registration/audit plane. It is not a timestamp broker.

## Local Evidence Path

Evidence services obtain timing directly from the edge-time instance on their hosting node:

```text
edge-video / edge-audio / future sensor
                |
                v
        local edge-time
                |
                +-- selected source
                +-- source observation
                +-- uncertainty
                +-- freshness
                +-- synchronization state
                +-- authority provenance
                +-- consistency
                +-- holdover
                +-- attestation
```

Cross-node HTTP uses the hosting node hostname/address and host-exposed port, not Docker service/container names.

## Capture Time Context

`POST /time/context` creates one Capture Time Context and one associated persistent attestation.

The context contains:

```text
context_id
capture_utc
capture_monotonic_ns
device_id
selected_source
source_observation
uncertainty_ms
freshness
freshness_age_ms
synchronization_state
authority_id
authority_source
consistency_state
consistency_offset_ms
consistency_uncertainty_ms
consistency_threshold_ms
holdover_state
attestation_sequence
attestation_record_hash
attestation_signature
```

`context_id` is a per-capture correlation identifier. It does not replace the persistent device identity or attestation sequence.

`capture_utc` represents the edge-time capture/acquisition instant. The selected source observation is advanced from its own monotonic observation position to the context monotonic position using the local monotonic clock.

This must not be described as physical camera exposure time unless an evidence service separately defines and records the sensor/frame capture position.

## Freshness

Freshness is based on monotonic age of the selected source observation at context creation.

Default configuration:

```text
EDGE_TIME_FRESHNESS_STALE_MS=5000
EDGE_TIME_FRESHNESS_EXPIRED_MS=30000
```

States:

```text
FRESH
STALE
EXPIRED
```

Freshness describes provenance quality and does not independently alter source selection or synchronization state.

## Synchronization and Holdover

Existing synchronization states remain authoritative for the current engine behavior:

```text
SYNCHRONIZED
DEGRADED
UNSYNCHRONIZED
HOLDOVER
```

Capture Time Context exposes holdover separately as:

```text
NOT_HOLDOVER
HOLDOVER
```

No production holdover-discipline policy is introduced by this contract.

## Authority and Consistency

The authority identity and selected authority source are provenance fields. Capture Time Context does not elect or change the authority.

The context also carries the existing consistency measurement:

```text
consistency_state
consistency_offset_ms
consistency_uncertainty_ms
consistency_threshold_ms
```

The consistency measurement is observational/provenance data and does not discipline the operating-system clock.

## Attestation Association

Each Capture Time Context is associated with a new signed, hash-chained attestation record.

The context stores:

```text
attestation_sequence
attestation_record_hash
attestation_signature
```

The attestation record stores the same `context_id`.

This keeps the context useful to evidence services while retaining the independent persistent attestation chain.

## Existing Source Input Contracts

GNSS JSON:

```json
{ "utc": "...", "valid": true, "uncertainty_ms": 50, "...": "..." }
```

RTC JSON uses the same basic shape.

These file inputs remain compatibility/integration adapters. GNSS hardware logic remains in `edge-gps`.

## Persistent State

Container:

```text
/state
```

Host:

```text
/data/services/state
```

Persistent identity and attestation state must survive normal restart, container recreation, and redeployment.
