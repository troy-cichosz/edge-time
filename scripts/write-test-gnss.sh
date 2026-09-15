#!/bin/sh
mkdir -p state
date -u -Iseconds | awk '{printf "{\"utc\":\"%s\",\"valid\":true,\"uncertainty_ms\":50}\n",$0}' > state/gnss.json
