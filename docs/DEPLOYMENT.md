# Deployment

## Initial placement

| Host | edge-time role | Other services |
|---|---|---|
| spoo-lin | `combined` / primary authority | edge-controller |
| pi4nVME | `agent` | edge-gps, edge-video, edge-audio |
| pi4SSD | `agent` | edge-gps, edge-video, edge-audio |
| Future RTC/GNSS node | `agent`, optionally `combined` | local capture/sensor services |

## Important

The first MVP uses one container per host. The agent is local to the device. The authority role is enabled only on explicitly approved nodes.

Do not expose authority endpoints directly to untrusted networks. The next hardening phase should add:
- mTLS or signed service identity
- controller-issued authority configuration
- replay protection
- signed authority responses
- persistent source transition events
- chrony/GPSD integration
- PPS support
