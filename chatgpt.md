# edge-time — ChatGPT Development Handoff

## Current Handoff Update — 2026-09-15

This document supersedes older statements that describe controller registration or GUI registration as incomplete.

The current `edge-time` architecture is operational and registered with `edge-controller`.

---

# 1. Operational State

Current architecture:

```text
spoo-lin
  edge-time ROLE=authority :8095
        |
        +----------------------+
        |                      |
        v                      v
pi4SSD edge-time agent   pi4nVME edge-time agent
        |                      |
   edge-gps :8096          edge-gps :8096
```

Current source priorities:

```text
spoo-lin:
    ntp,rtc,system

pi4SSD:
    authority,gnss,rtc,ntp,system

pi4nVME:
    authority,gnss,rtc,ntp,system
```

Verified:

* `spoo-lin /authority/time` returns HTTP 200.
* `spoo-lin` selects NTP.
* `pi4SSD` selects the platform authority even when GNSS is valid.
* `pi4nVME` selects the platform authority while GNSS has no valid fix.
* `edge-gps` on `pi4nVME` can receive NMEA independently of whether a valid fix exists.
* Both Pi nodes have registered `edge-time` with `edge-controller`.
* Controller status reporting works.
* Generic multi-service registration works.
* `edge-time` appears under the registered nodes in the controller GUI.

---

2. Controller Integration

edge-time uses the generic controller client:

EDGE_CONTROLLER_URL
EDGE_CONTROLLER_TIMEOUT
EDGE_NODE_ID
EDGE_SERVICE_ID
EDGE_SERVICE_NAME
EDGE_SERVICE_VERSION

The current service identity is:

service_id: edge-time
base version: 0.2.2

The currently verified deployed build is:

0.2.2-20260915.7

The controller integration remains management-plane functionality.

edge-time must remain operational if the controller is unavailable.

No edge-time-specific controller database model should be added.

Registration Behavior

Service registration is idempotent.

The service does not skip registration merely because an existing record is found.

Each registration refreshes:

service_id
name
version
endpoint scheme
endpoint port
endpoint path

This ensures that a new deployed version is reflected in the controller.

Read-Only Observation

The controller now provides generic read-only observation of registered services.

For edge-time, the controller can reach the service through its registered host-addressed endpoint.

The controller must not become the real-time timestamp provider.

edge-time remains responsible for:

time-source selection
time calculation
source provenance
uncertainty
freshness
authority interaction
local evidence-time context

---

# 3. Current Controller Relationships

```text
pi4SSD
├── edge-audio
├── edge-gps
├── edge-time
└── edge-video

pi4nVME
├── edge-audio
├── edge-gps
├── edge-time
└── edge-video
```

This confirms that the controller's generic multi-service model is functioning.

`spoo-lin` hosts both the controller and the current authority but does not need to register as a managed edge node merely because it hosts the controller.

---

4. Controller Work

The following are now primarily edge-controller responsibilities:

generic service capability reporting
generic service observation
controller GUI
time observability
authority eligibility
authority assignment
authority promotion
authority failover
generic management configuration
management audit

The edge-time service should expose the information required by these functions through generic service interfaces rather than acquiring controller-specific database structures.

The next controller-side abstraction is a generic capability model that allows the controller to discover which operational information a service exposes.

---

# 5. New Controller Integration Direction

The controller should first consume `edge-time` as a read-only observable service.

The controller should display:

```text
current platform authority
authority source
authority state
authority time

per-node current edge time
selected source
uncertainty
freshness
synchronization state

individual source observations
authority provenance
attestation
```

This should be implemented before controller-managed time changes.

---

# 6. Evidence-Time Objective

The central purpose of this work is to establish a technically verifiable timing basis for evidence.

The desired chain is:

```text
Evidence
  |
  v
Evidence service
  |
  v
Local edge-time
  |
  +-- selected source
  +-- source observation
  +-- uncertainty
  +-- freshness
  +-- synchronization state
  +-- authority identity
  |
  v
Platform authority
  |
  v
Underlying authoritative source
```

The resulting evidence metadata should eventually allow reconstruction of the timing environment at capture time.

A future common envelope may include:

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

This schema is not yet finalized.

---

# 7. Evidentiary Requirements

`edge-time` must provide more than a timestamp.

The system must be able to establish:

```text
what time was assigned
which source supplied it
whether that source was valid
how fresh the source was
what uncertainty existed
which authority supplied it
what source the authority was using
what synchronization state existed
whether holdover was active
```

This provides technical provenance and integrity support.

It does not by itself establish legal admissibility.

---

# 8. Local Evidence Rule

Evidence-producing services should obtain timing directly from their local `edge-time` service.

Preferred:

```text
edge-video
    |
    +-- local edge-time
```

```text
edge-audio
    |
    +-- local edge-time
```

Avoid:

```text
edge-video
    |
    v
edge-controller
    |
    v
edge-time
```

The controller should not become a timestamp broker.

---

# 9. Authority Policy

`edge-time` provides the authority mechanism.

The controller will eventually provide the policy.

Potential controller operations:

```text
assign authority
remove authority
promote authority
fail over authority
configure authority endpoint
configure allowed authorities
```

`edge-time` remains responsible for actually operating the authority and returning authoritative time.

---

# 10. Source Policy

Current priority:

```text
authority
gnss
rtc
ntp
system
```

The controller may eventually manage this priority.

`edge-time` must continue validating the resulting configuration and must not blindly accept an invalid source policy.

---

# 11. Failure Testing

Before controller-managed configuration is enabled, the platform should test:

```text
authority available
authority unavailable

GNSS valid
GNSS unavailable

NTP available
NTP unavailable

authority + GNSS
authority + NTP
GNSS + NTP
NTP only
system only

authority holdover
source freshness expiration
uncertainty threshold exceeded
controller unavailable
```

Expected source transitions and provenance must be recorded.

---

# 12. Holdover

Holdover is an important future evidentiary property.

When the authoritative source disappears, `edge-time` must distinguish:

```text
fresh authoritative time
```

from:

```text
held-over time
```

The timing context should expose:

```text
holdover active
holdover start
last authoritative observation
age of authoritative observation
estimated uncertainty
```

The exact production policy is not finalized.

---

# 13. GNSS/PPS

Current GNSS integration uses `edge-gps`.

`edge-time` should continue consuming GNSS observations through the service API rather than directly operating GNSS hardware.

Future PPS/timepulse integration is expected to improve precision.

Do not implement hardware-specific GNSS logic in `edge-time`.

---

# 14. API

Current APIs:

```text
GET /health
GET /status
GET /time
GET /time/sources
GET /time/attestation
GET /authority
GET /authority/time
PUT /authority
```

The controller should use these APIs for observation and eventual management.

---

# 15. Network Rule

Inter-service HTTP uses node hostname/IP and exposed host port.

Correct:

```text
http://spoo-lin.spoocannon.com:8095/authority/time
http://pi4SSD:8096/observation
http://pi4nVME:8096/observation
```

Do not use Docker container/service names for cross-service endpoints.

---

# 16. Controller Independence

`edge-time` must continue operating normally when:

```text
edge-controller is unavailable
controller database is unavailable
controller GUI is unavailable
```

Controller registration/status reporting is supplemental management functionality.

The real-time time-selection path must remain independent.

---

17. Current Development Priority

The current edge-time core architecture should not be redesigned.

Priority is:

1. Preserve authority/agent architecture.

2. Support controller read-only observability.

3. Define the generic edge-time capability/observation contract.

4. Improve freshness/time-quality semantics.

5. Improve holdover semantics.

6. Improve GNSS/PPS precision.

7. Finalize evidence timestamp/provenance envelope.

8. Integrate edge-video.

9. Integrate edge-audio.

10. Automate authority/source failure testing.

11. Support controller-managed policy after validation.

The controller observation foundation is now implemented.

The remaining work is expanding the information exposed through that foundation, not redesigning the registration architecture.
---

# 18. Current Limitations

Not yet complete:

```text
PPS/timepulse
GNSS sub-millisecond timing
production authority holdover policy
full authority failover
final evidence timestamp envelope
complete cross-service evidence integration
complete controller-managed authority assignment
comprehensive automated integration tests
```

These are known limitations, not reasons to redesign the current working architecture.

---

# 19. Current Handoff State
edge-time authority/agent architecture: OPERATIONAL
spoo-lin authority:                     VERIFIED
pi4SSD agent:                           VERIFIED
pi4nVME agent:                          VERIFIED

authority selection:                    VERIFIED
GNSS integration:                       VERIFIED

controller registration:                VERIFIED
controller status reporting:            VERIFIED
controller GUI registration:            VERIFIED
generic multi-service registration:     VERIFIED
service version refresh:                VERIFIED

generic controller observation:         VERIFIED
host-addressed observation:             VERIFIED
short/domain/auto host resolution:      VERIFIED

controller read-only foundation:        VERIFIED
full edge-time observability:           NEXT
generic capability model:               NEXT
time consistency validation:            NEXT

evidence timestamp envelope:            NEXT
cross-service evidence integration:     NOT COMPLETE

PPS/timepulse:                           NOT IMPLEMENTED
authority failover:                     NOT IMPLEMENTED
production holdover:                    NOT COMPLETE
controller authority assignment:        NOT COMPLETE

---

# 20. Important Boundary

Do not move controller policy into edge-time.

Do not make the controller the timestamp provider.

Do not add edge-time-specific database structures to the controller unless the generic service model demonstrably cannot represent the requirement.

Do not modify the working authority/agent architecture without runtime evidence demonstrating a need.

The current controller foundation is sufficient to proceed with generic service capability and read-only observability work.

---