# edge-time - Service Status

**Purpose:** Current development phase and maturity of the distributed time service.  
**Status:** Core operational / evidence-facing foundation complete  
**Last reviewed:** September 2026

## Current Phase

**Phase 1 - Authoritative Time Foundation: CORE OPERATIONAL**

The distributed authority/agent foundation and Capture Time Context contract are operational.

The service owns time-source selection, synchronization/consistency state, freshness/uncertainty reporting, and signed time attestation.

## Verified Foundation

- Authority/agent architecture
- Source observation and selection
- Freshness and uncertainty reporting
- Synchronization/consistency state
- Holdover representation
- Capture Time Context endpoint
- UTC and monotonic context
- Persistent signed/hash-chained attestation state
- Direct node-local consumption by evidence services

## Capture Time Context

`POST /time/context` creates an evidence-facing temporal context identifying selected source/observation state, UTC/monotonic position, uncertainty, freshness, synchronization/consistency state, authority information, holdover state, and attestation reference.

Context acquisition time is not automatically the exact physical sensor exposure/sample time.

## Current Boundary

The service does not currently provide controller-managed authority election/failover, production-grade holdover discipline, PPS hardware integration, GPS hardware ownership, evidence storage, AI processing, or vehicle/OBD functions.

`edge-gps` owns GNSS hardware/observations; `edge-time` consumes applicable observations and determines time context.

## Remaining Service Work

Evidence-facing refinement, broader failure/authority behavior verification, and eventual integration of stronger timing sources/policy.

Active work belongs in `sprintstatus.md`; platform-wide temporal invariants belong in project-level documentation.
