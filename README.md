# edge-time

`edge-time` is the distributed timing and timing-provenance service for the AI Legal Edge Platform.

It provides local time selection, authority/agent synchronization, source observations, consistency measurements, persistent cryptographic attestation, and an evidence-facing **Capture Time Context**.

## Current Status

The authority/agent architecture is operational and is the foundation for the next evidence-integration phase.

Verified capabilities include:

```text
authority/agent operation
source selection
GNSS observation integration
time observations
source observations
uncertainty
synchronization state
authority provenance
time consistency
persistent state
persistent cryptographic identity
Ed25519 signatures
SHA-256 attestation hashing
attestation hash chaining
chain verification
restart persistence
tamper detection
Capture Time Context generation
```

Do not redesign the authority/agent model without runtime evidence demonstrating a requirement.

---

## Platform Boundary

`edge-controller` is the management/policy/registration/configuration plane. Audit logging for evidence-affecting management changes is a project architectural requirement, but is not currently implemented by the controller.

`edge-time` is the distributed timing and timing-provenance plane.

Evidence-producing services obtain time from their **local** `edge-time` instance:

```text
edge-video
    |
    +-- local edge-time

edge-audio
    |
    +-- local edge-time
```

The controller is not a timestamp broker.

Cross-service HTTP uses the hosting node hostname/address and host-exposed port. Docker service/container names are not used for cross-host communication.

---

## Existing APIs

```text
GET  /health
GET  /status
GET  /time
GET  /time/sources
GET  /time/attestation
GET  /time/consistency
GET  /authority
GET  /authority/time
PUT  /authority
POST /time/context
```

`/time/consistency` measures local timing against the configured authority. The default consistency threshold is 500 ms and is configurable with:

```text
EDGE_TIME_CONSISTENCY_THRESHOLD_MS
```

---

# Capture Time Context

`POST /time/context` creates one evidence-facing Capture Time Context.

It is intentionally a `POST`, rather than a `GET`, because context creation also creates a new persistent, signed, hash-chained attestation record.

An evidence-producing service should request the context at the capture event and retain the returned context with the evidence artifact it is creating.

Conceptual flow:

```text
real-world capture
       |
       v
edge-video / edge-audio / future sensor service
       |
       | POST /time/context
       v
local edge-time
       |
       +-- selected source
       +-- source observation
       +-- UTC capture timestamp
       +-- monotonic capture position
       +-- uncertainty
       +-- freshness
       +-- synchronization state
       +-- authority identity/source
       +-- consistency state
       +-- holdover state
       +-- signed attestation reference
       |
       v
local evidence artifact
```

## Context Contract

The response contains:

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

### `context_id`

A UUID generated for each Capture Time Context. It is a correlation identifier for the context/evidence relationship.

It is not the cryptographic identity of the device and does not replace the attestation sequence or hash chain.

### `capture_utc`

The UTC timestamp supplied for the context acquisition instant.

The selected source observation has its own timestamp and monotonic observation position. `edge-time` advances the selected source timestamp to the context response monotonic position using the local monotonic clock.

This is an **edge-time capture/acquisition timestamp**. It must not be described as the physical camera exposure time unless the evidence service supplies a separately defined sensor/frame capture position.

### `capture_monotonic_ns`

The local monotonic position associated with `capture_utc`.

It is useful for ordering and for future mapping of sensor-specific capture positions. It is not a globally comparable timestamp.

### `source_observation`

The complete selected `TimeObservation`, including its source identity, source type, source UTC, uncertainty, validity, observation monotonic position, observation wall time, and source details.

### `uncertainty_ms`

The selected source's reported temporal uncertainty. It is an estimate of timing uncertainty, not a claim that the timestamp has equivalent measurement precision.

Advancing a source observation to the context position does not currently add a modeled clock-drift term. Future versions may add such a model if required.

### Freshness

Freshness is based on the monotonic age of the selected source observation at context creation.

Configured thresholds:

```text
EDGE_TIME_FRESHNESS_STALE_MS   default 5000 ms
EDGE_TIME_FRESHNESS_EXPIRED_MS default 30000 ms
```

States:

```text
FRESH
STALE
EXPIRED
```

Freshness is provenance information. It does not itself change source selection or synchronization state.

### Synchronization state

Current states remain:

```text
SYNCHRONIZED
DEGRADED
UNSYNCHRONIZED
HOLDOVER
```

`HOLDOVER` is the existing engine behavior when no currently valid configured source is available and an in-memory previous observation is used.

This is not yet a production holdover discipline policy.

### Authority provenance

`authority_id` identifies the authority associated with the selected timing path when available.

`authority_source` identifies the authority's selected local source, such as `ntp`.

The context does not elect or change the authority.

### Consistency

The context records the current authority-consistency result:

```text
consistency_state
consistency_offset_ms
consistency_uncertainty_ms
consistency_threshold_ms
```

The consistency measurement is provenance/observability data. It does not discipline the operating-system clock and does not perform authority election.

### Holdover

The context records:

```text
NOT_HOLDOVER
HOLDOVER
```

No new production holdover policy is introduced by Capture Time Context.

### Attestation association

Each context creation creates one attestation and returns:

```text
attestation_sequence
attestation_record_hash
attestation_signature
```

The attestation record also contains `context_id`.

This creates a bidirectional correlation:

```text
Capture Time Context
       |
       +-- sequence
       +-- record_hash
       +-- signature

Attestation record
       |
       +-- context_id
```

The attestation remains independently sequenced and hash-chained.

---

## Attestation

`GET /time/attestation` continues to create a current signed time-attestation record.

Records are persisted under:

```text
/state/attestations.jsonl
/state/sequence
/state/identity.key
```

The Ed25519 identity must survive normal restart, container recreation, and redeployment.

The attestation establishes:

```text
record integrity
signature verification
sequence continuity
hash-chain continuity
device identity continuity
```

It does not prove external-source truth, scene truth, or legal admissibility.

---

## Existing Time Model

`TimeObservation` represents an observation from one source:

```text
source_id
source_type
utc
uncertainty_ms
valid
details
observed_monotonic_ns
observed_wall_utc
```

`TimeResponse` continues to expose the selected timing state and all collected source observations through `/time` and `/status`.

Capture Time Context is an additive evidence-facing contract; it does not replace the existing time/source APIs.

---

## Persistent State

Persistent state is stored in the configured service state directory.

The container default is:

```text
/state
```

The host-side persistent mount is deployment-specific and is intentionally not part of the service contract.

Current state files:

```text
identity.key
attestations.jsonl
sequence
gnss.json
rtc.json
```

---

## Operational Boundary

`edge-time` does not implement:

- GNSS hardware acquisition
- PPS hardware implementation
- controller-managed authority election/failover
- production holdover discipline
- multi-camera orchestration
- USB camera support
- AI analysis
- evidence repository management
- vehicle/OBD service

These are separate service or future platform concerns.

## Integration Boundary

The primary evidence consumers of Capture Time Context are `edge-video`, `edge-audio`, and future evidence-producing services.

The project-level evidence architecture defines how temporal context relates to Evidence, Observation, Event, Timeline, provenance, integrity, and derivatives.

## Definition of Done

This timing boundary is complete when:

```text
context identity is explicit
timestamp semantics are explicit
source provenance is explicit
uncertainty semantics are explicit
freshness semantics are explicit
synchronization semantics are explicit
authority provenance is explicit
consistency semantics are explicit
holdover semantics are explicit
attestation association is explicit

implementation exists
automated tests pass
containers build successfully
runtime is verified on the deployed nodes
documentation is current
```