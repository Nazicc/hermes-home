---
name: openhue
description: "Control Philips Hue lights, rooms, and scenes via the OpenHue CLI. Turn lights on/off, adjust brightness, color, color temperature, and activate scenes. NOT for: non-Hue smart home devices (use their native skill instead), or general HTTP API tasks."
category: skills
---

---
name: openhue
description: >
  Control Philips Hue lights, rooms, and scenes via the OpenHue CLI. Turn lights on/off,
  adjust brightness, color, color temperature, and activate scenes.
  Trigger signals: user asks to turn on/off lights, adjust brightness, change light color,
  control Hue scenes, manage Hue rooms.
  Anti-trigger signals: non-Hue devices (use device-native skill), general HTTP requests,
  network troubleshooting beyond Hue API.
version: 2.0.0
author: community
license: MIT
metadata:
  sources: []
  hermes:
    tags: [Smart-Home, Hue, Lights, IoT, Automation]
    related_skills: []
    quality_redlines:
      - "OpenHue CLI (hue) must be installed and hue bridge must be reachable"
      - "Light IDs must be valid — use GET /lights to enumerate first"
      - "Scene activation via PUT /groups/{id}/action; brightness is 0–254 (not 0–100)"
      - "Color commands require XY coordinates or hue/sat values — not RGB hex strings"
      - "Room/group control uses /groups endpoint; individual light control uses /lights/{id}"
---

## Trigger Checklist

**USE openhue when the user:**
- Asks to turn Hue lights on or off
- Asks to adjust brightness, color, or color temperature
- Asks to activate a Hue scene or control a room
- Asks to list available lights, rooms, or scenes

**DO NOT USE openhue when:**
- The device is not a Philips Hue product
- The task is a general HTTP API call
- The user wants to troubleshoot network connectivity to the Hue bridge

## Environment Detection

1. Check if `hue` CLI is available: `which hue`
2. Discover bridge IP: `hue discover` (if needed)
3. Authenticate: `hue auth <bridge-ip>` if no existing username
4. Verify connection: `hue lights` lists available lights

## Key API Contract (OpenHue CLI → REST API)

| Operation | Command Pattern |
|-----------|----------------|
| List lights | `hue lights` |
| List rooms/groups | `hue groups` |
| List scenes | `hue scenes` |
| Light on/off | `hue light <id> --on` / `hue light <id> --off` |
| Brightness (0–254) | `hue light <id> --bri 200` |
| Color (XY) | `hue light <id> --xy 0.5,0.4` |
| Color temp (153–500) | `hue light <id> --ct 250` |
| Activate scene | `hue scene <id>` |
| Room control | `hue group <id> --on --bri 180` |

**Underlying REST endpoints (for curl fallback):**
- Base: `http://<bridge-ip>/api/<username>`
- Lights: `/lights/{id}/state` — PUT to set state
- Groups: `/groups/{id}/action` — PUT to control room
- Scenes: `/groups/{id}/action` with scene parameter

## Quality Checklist

- [ ] Bridge is reachable on local network
- [ ] Authentication token is configured (stored by `hue auth`)
- [ ] Light/group IDs are confirmed via enumeration before control
- [ ] Brightness values are in range 0–254
- [ ] Color temperature values are in range 153–500 (Mired scale)
- [ ] Scene name/id is valid before activation
