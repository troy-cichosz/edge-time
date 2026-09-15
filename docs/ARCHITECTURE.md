# Architecture

edge-time has three logical roles:

1. Source adapters: GNSS, RTC, NTP, system clock, authority.
2. Time agent: local source selection, fallback, holdover, uncertainty and monotonic correlation.
3. Authority service: platform-designated distribution point.

The controller owns policy and approved authority-node configuration. Devices retain the last policy and continue offline.

Current source input contracts:
- GNSS JSON: `{ "utc": "...", "valid": true, "uncertainty_ms": 50, ... }`
- RTC JSON: same shape.
These files are temporary integration adapters until edge-gps exposes a native time-observation endpoint.
