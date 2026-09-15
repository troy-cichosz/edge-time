# edge-time

Distributed platform time agent and authority service for the AI Legal Edge platform.

`edge-time` provides node-local time services and an optional platform time authority for evidence-producing edge devices.

The service is designed around:

* explicit time-source provenance
* source selection
* uncertainty
* freshness
* authority identity
* holdover behavior
* local operation when the controller is unavailable

`edge-time` is intentionally hardware-neutral. GNSS acquisition remains the responsibility of `edge-gps` or another source service.

# Current Status Update — 2026-09-15

`edge-time` is currently deployed as a three-node time architecture:

```text
spoo-lin
└── edge-time
    └── authority :8095

pi4SSD
└── edge-time
    └── agent :8095

pi4nVME
└── edge-time
    └── agent :8095
```

The current `edge-time` base version is:

```text
0.2.2
```

The currently verified deployed build is:

```text
0.2.2-20260915.7
```

## Controller Integration Status

Controller integration is operational.

Both Pi agents:

* register with `edge-controller`
* refresh their service registration
* report their current service version
* report their endpoint metadata
* publish service status
* remain operational when controller communication is unavailable

The registration operation is idempotent. Existing service registrations are refreshed rather than skipped, ensuring that a new deployed version is reflected in the controller.

## Controller Read-Only Observation

The controller can now generically observe the registered `edge-time` service through its registered host-addressed endpoint.

The observation is management-plane functionality.

`edge-time` remains responsible for its own time calculation and evidence-time context.

The controller is not inserted into the real-time timestamp path.

## Network Endpoint Model

`edge-time` registers its service endpoint as host-addressed metadata.

The controller resolves the hosting node using its configured host-resolution policy and connects to the exposed host port.

Docker container/service names are not used for cross-host service communication.

This supports both:

```text
hostname
```

and:

```text
hostname.domain
```

deployment environments.

The controller may use short hostname, domain/FQDN, or automatic fallback depending on its configuration.

## Current Boundary

The following are now complete:

```text
authority/agent architecture       VERIFIED
three-node deployment               VERIFIED
controller registration             VERIFIED
service version refresh             VERIFIED
controller status reporting         VERIFIED
generic service observation         VERIFIED
host-addressed endpoint model       VERIFIED
```

The following remain future work:

```text
full generic service capability model
complete controller time observability
time consistency validation
PPS/timepulse
GNSS sub-millisecond timing
production authority holdover
authority failover
controller-managed authority policy
final evidence timestamp envelope
cross-service evidence integration
```

The core authority/agent architecture should not be redesigned merely to implement these future management-plane capabilities.

---

# Architecture

`edge-time` operates in three roles:

* `agent` — consumes available time sources on an evidence-capable edge device
* `authority` — publishes authoritative platform time
* `combined` — provides both behaviors

Current deployment:

```text
                         pool.ntp.org
                              |
                              v
                   +----------------------+
                   |       spoo-lin       |
                   |     edge-time        |
                   |       authority      |
                   |       :8095           |
                   +----------+-----------+
                              |
                       /authority/time
                       _______|_______
                      /               \
                     v                 v
            +----------------+ +----------------+
            |    pi4SSD      | |    pi4nVME     |
            |   edge-time    | |   edge-time    |
            |     agent      | |     agent      |
            |     :8095      | |     :8095      |
            +-------+--------+ +-------+--------+
                    |                  |
               edge-gps           edge-gps
                  :8096              :8096
```

The controller is the platform management/policy owner.

`edge-time` does not independently elect arbitrary platform authorities.

---

# Current Authority

Current authority:

```text
spoo-lin
edge-time
ROLE=authority
port=8095
authority_id=spoo-lin.spoocannon.com
```

Current authority source:

```text
NTP
```

Current authority chain:

```text
edge-time authority
      |
      +-- NTP
```

---

# Current Agents

```text
pi4SSD
edge-time ROLE=agent
edge-gps :8096

pi4nVME
edge-time ROLE=agent
edge-gps :8096
```

Current agent source priority:

```text
authority
gnss
rtc
ntp
system
```

Both current Pi agents select the platform authority when it is valid.

Local GNSS remains valuable as an independent observation and fallback source even when authority is selected.

---

# Verified Operational State

## spoo-lin

Verified:

* authority role active
* `/authority/time` returns HTTP 200
* authority observation is valid
* NTP is selected

## pi4SSD

Verified:

* authority reachable
* local GNSS reachable
* local GNSS has produced valid fixes
* local NTP available
* authority selected over local GNSS
* `/time` reports `selected_source: authority`
* state is `SYNCHRONIZED`

## pi4nVME

Verified:

* authority reachable
* local NTP available
* GNSS service receives NMEA
* GNSS currently may have no valid satellite fix
* authority remains selected
* `/time` reports `selected_source: authority`
* state is `SYNCHRONIZED`

A lack of GNSS fix is an `edge-gps` receiver state and is not by itself an `edge-time` failure.

---

# Time Source Hierarchy

Default intended priority:

```text
1. authority
2. GNSS
3. RTC
4. NTP
5. system
```

The selected source is determined by configured priority and source validity.

Other source observations are retained rather than discarded.

This distinction is essential for evidentiary provenance.

---

# Provenance

An `edge-time` response should not be treated as an opaque UTC timestamp.

The timing context should establish:

```text
selected time
selected source
source observation
source validity
source freshness
uncertainty
synchronization state
authority identity
authority source
```

Example conceptual chain:

```text
edge-time agent
    |
    +-- selected source: authority
          |
          +-- authority: spoo-lin
                |
                +-- selected source: NTP
```

If local GNSS is available:

```text
edge-time agent
    |
    +-- selected source: authority
    |
    +-- GNSS observation: retained
    |
    +-- local NTP observation: retained
```

This allows later reconstruction of the timing environment.

---

## Controller Integration

`edge-time` uses the generic `edge-controller` node/service model.

The controller does not require an `edge-time`-specific database structure.

Current integration:

```text
spoo-lin
└── edge-time
    └── authority

pi4SSD
└── edge-time
    └── agent

pi4nVME
└── edge-time
    └── agent
```

The Pi agents register using the generic service registration interface.

Registration includes:

```text
service_id
name
version
endpoint scheme
endpoint port
endpoint health path
```

Registration is refreshed on successful controller registration. This allows deployed service versions and endpoint metadata to remain current.

The controller can perform generic read-only service observation against the registered endpoint.

The controller resolves the node's network address independently of the logical node identity.

The controller's host-resolution policy supports:

```text
short
domain
auto
```

with an optional configured domain.

`edge-time` remains independent of the controller for real-time time selection and operation.


---

# Controller Responsibilities

The controller may eventually own:

```text
authority eligibility
authority assignment
authority promotion
authority removal
authority failover
source policy
configuration
audit
```

The controller must not become the real-time timestamp provider.

`edge-time` remains responsible for:

```text
source collection
source validation
source selection
time response
uncertainty
freshness
authority operation
holdover
```

---

# API

Default port:

```text
8095
```

## Health

```text
GET /health
```

Returns health, role, and device identity.

## Status

```text
GET /status
```

Returns current time-engine status.

## Current Time

```text
GET /time
```

Returns:

* selected UTC
* selected monotonic time where available
* selected source
* authority mode
* state
* uncertainty
* device identity
* authority identity
* source observations

## Source Observations

```text
GET /time/sources
```

Forces a source collection cycle and returns individual observations.

## Attestation

```text
GET /time/attestation
```

Returns local time attestation information when configured.

## Authority

```text
GET /authority
```

Returns authority configuration and state.

## Authority Time

```text
GET /authority/time
```

Returns authoritative platform time.

A non-authority instance returns HTTP 409.

## Authority Configuration

```text
PUT /authority
```

Updates configured authority identity/URL.

Authority policy remains a controller responsibility.

---

# Evidence Architecture

`edge-time` is not an evidence recorder.

It is a timing and provenance service for evidence-producing services such as:

* `edge-video`
* `edge-audio`
* future sensors
* future vehicle/edge capture services

The intended evidence architecture is:

```text
Evidence service
      |
      +-- obtains timing context from local edge-time
      |
      +-- records timestamp/provenance
      |
      +-- hashes/manifests evidence locally
```

The controller must not become a real-time timestamp broker.

The evidence path remains local-first.

---

# Evidence Timestamp / Provenance Envelope

A future common evidence envelope should be capable of carrying information such as:

```text
evidence_id
device_id
capture_timestamp_utc
capture_monotonic
time_service
selected_source
authority_id
source_timestamp
uncertainty
freshness
synchronization_state
attestation
evidence_hash
manifest_id
```

The exact schema is not yet finalized.

This envelope must eventually be shared by:

```text
edge-video
edge-audio
future sensors
future vehicle evidence
```

The purpose is to allow an investigator to reconstruct the timing basis used when evidence was captured.

This provides technical provenance and integrity support. It does not by itself establish legal admissibility.

---

# Current Controller Direction

The controller is now expected to provide read-only operational visibility into `edge-time` before it is permitted to change time configuration.

The first controller integration should display:

```text
platform authority
authority source
current authority time

per-node current edge time
selected source
uncertainty
freshness
synchronization state

source observations
authority provenance
attestation
```

Only after this information is verified should controller-managed time configuration be introduced.

---

# Failure and Holdover Testing

The time system must eventually be tested under:

```text
authority available
authority unavailable

GNSS valid
GNSS unavailable

NTP available
NTP unavailable

multiple sources available
fallback-only operation

authority holdover
source freshness expiration
uncertainty threshold exceeded

controller unavailable
```

The controller must not be required for continued local time operation.

---

# Configuration

Important settings include:

```text
EDGE_TIME_ROLE=agent
EDGE_TIME_HOST=0.0.0.0
EDGE_TIME_PORT=8095

EDGE_TIME_DEVICE_ID=
EDGE_TIME_NODE_ID=

EDGE_TIME_AUTHORITY_URL=
EDGE_TIME_AUTHORITY_ID=

EDGE_TIME_GNSS_URL=
EDGE_TIME_GNSS_HOST=
EDGE_TIME_GNSS_PORT=8096
EDGE_TIME_GNSS_PATH=/observation

EDGE_TIME_SOURCE_PRIORITY=authority,gnss,rtc,ntp,system

EDGE_TIME_ALLOW_SYSTEM_SOURCE=true
EDGE_TIME_ALLOW_HOLDOVER=true
EDGE_TIME_MAX_UNCERTAINTY_MS=500

EDGE_TIME_HTTP_TIMEOUT_SECONDS=2.0

EDGE_TIME_STATE_DIR=/var/lib/edge-time
EDGE_TIME_GNSS_OBSERVATION_FILE=/var/lib/edge-time/gnss.json
EDGE_TIME_RTC_OBSERVATION_FILE=/var/lib/edge-time/rtc.json

EDGE_TIME_NTP_HOST=pool.ntp.org
EDGE_TIME_NTP_PORT=123

EDGE_TIME_POLL_SECONDS=5

EDGE_TIME_ATTESTATION_KEY=/var/lib/edge-time/identity.key

EDGE_CONTROLLER_URL=
EDGE_CONTROLLER_TIMEOUT=5

EDGE_SERVICE_ID=edge-time
EDGE_SERVICE_NAME=edge-time
EDGE_SERVICE_VERSION=0.3.0
```

Effective device identity is derived from:

```text
EDGE_TIME_DEVICE_ID
        |
        v
EDGE_TIME_NODE_ID
        |
        v
host/container hostname
```

The deployment uses:

```text
uts: host
```

so the container hostname corresponds to the hosting node.

---

# Network Architecture

Inter-service HTTP uses the hosting node's hostname/IP and exposed host port.

Correct:

```text
http://spoo-lin.spoocannon.com:8095/authority/time
http://pi4SSD:8096/observation
http://pi4nVME:8096/observation
```

Do not use Docker container/service names as cross-service endpoints.

---

## Current Limitations

The current implementation does not yet:

* discipline the Linux system clock
* provide PPS/timepulse synchronization
* provide GNSS-derived sub-millisecond timing
* implement full authority election/failover
* provide production authority holdover policy
* provide complete evidence timestamp policy
* provide the finalized common evidence timestamp envelope
* provide complete service authentication/authorization
* expose the complete time-service capability/observability model through the controller

The following are **no longer limitations**:

* controller registration
* controller service version registration
* controller service status reporting
* controller GUI service registration
* generic host-addressed controller observation


---

## Development Priorities

The next priorities are:

1. Support generic controller read-only observability.
2. Define the `edge-time` capability/observation contract.
3. Expose time quality, source, uncertainty, freshness, synchronization state, and provenance through that generic model.
4. Validate time consistency across the authority and agents.
5. Improve authority freshness and holdover semantics.
6. Integrate higher-precision GNSS/PPS sources.
7. Define the common evidence timestamp/provenance envelope.
8. Integrate that envelope with `edge-video`, `edge-audio`, and future evidence services.
9. Add automated integration tests for authority/agent operation and source failure.
10. Support controller-managed policy after the read-only and evidence-integrity phases are validated.


---

# Docker

The service is containerized with Docker Compose.

Current characteristics:

```text
container_name: edge-time
restart: unless-stopped
uts: host
```

Default port:

```text
8095:8095
```

Persistent state:

```text
./state:/var/lib/edge-time
```

---

# Status

Current platform:

```text
spoo-lin
  edge-time authority
       |
       +----------------+
       |                |
       v                v
    pi4SSD           pi4nVME
  edge-time agent  edge-time agent
```

Current status:

```text
authority operation:                  VERIFIED
authority source selection:           VERIFIED
pi4SSD agent:                         VERIFIED
pi4nVME agent:                        VERIFIED
GNSS integration:                     VERIFIED
controller registration:              VERIFIED
controller status reporting:          VERIFIED
generic multi-service registration:   VERIFIED

controller read-only observability:   NEXT
time consistency validation:          NEXT
evidence timestamp envelope:          NEXT
cross-service evidence integration:   NEXT

PPS/timepulse:                         NOT IMPLEMENTED
authority failover:                   NOT IMPLEMENTED
production holdover policy:           NOT COMPLETE
controller authority assignment:      NOT COMPLETE
```

`edge-time` is now sufficiently operational that the next major management-plane work belongs primarily in `edge-controller`.

Do not move authority-policy logic into `edge-time` merely to make controller integration easier.
