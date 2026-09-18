# edge-time / edge-gps Phase 1 deployment

## Roles

- spoo-lin: `EDGE_TIME_ROLE=combined`, `EDGE_TIME_AUTHORITY_ID=spoo-lin`
- pi4nVME: `EDGE_TIME_ROLE=agent`, `EDGE_TIME_AUTHORITY_URL=http://spoo-lin:8095`, `EDGE_TIME_GNSS_URL=http://pi4nVME:8096/observation`
- pi4SSD: `EDGE_TIME_ROLE=agent`, `EDGE_TIME_AUTHORITY_URL=http://spoo-lin:8095`, `EDGE_TIME_GNSS_URL=http://pi4SSD:8096/observation`

The authority does not automatically elect itself or any other node. The role remains deployment/controller policy.

## Validation

On each GPS-equipped Pi:

    curl -i http://127.0.0.1:8096/health
    curl -i http://127.0.0.1:8096/observation

On spoo-lin:

    curl -s http://127.0.0.1:8095/health
    curl -s http://127.0.0.1:8095/authority
    curl -s http://127.0.0.1:8095/authority/time

On each Pi:

    curl -s http://spoo-lin:8095/authority/time
    curl -s http://127.0.0.1:8095/status
    curl -s http://127.0.0.1:8095/time/sources

Expected hierarchy on GPS-equipped agents:

    authority -> gnss -> rtc -> ntp -> system

Expected hierarchy on the initial authority:

    gnss -> rtc -> ntp -> system

If authority becomes unavailable, agents must fall back locally and report `local_fallback` or `HOLDOVER`; they must not fabricate an authority source.
