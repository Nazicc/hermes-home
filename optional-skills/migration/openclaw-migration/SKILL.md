---
name: openclaw-migration
category: migration
metadata:
  hermes:
    tags: [migration, openclaw, claw, 3d-printing, automation, assistant]
    related_skills:
      - blender-mcp
      - parallel-cli
      - research-paper-writing
---

# OpenClaw Migration

Migrate OpenClaw — a project that controls a 3D-printed claw machine — from its original Python script (claw-controller) to an AI-assistant-based system where the agent orchestrates claw commands, camera captures, and status reporting. This skill covers the migration architecture, command schema, and safety considerations.

## Why This Works

**Concept 1: AI-Orchestrated Hardware Control via Command Abstraction.** Instead of hardcoding claw movement sequences in Python, the migration creates an abstraction layer where the agent issues high-level commands ("grab the item at position (120, 240, 50)") that are translated to stepper motor pulses and servo angles. This decouples the decision logic (which item to grab, when to grab it) from the hardware control (motor steps, timing). The agent can dynamically adapt to different item positions, reward probabilities, and game states without recompiling firmware.

**Concept 2: Multi-Layer Safety with State Validation.** The migration enforces a safety layer between the agent and the hardware. Every command passes through a validator that checks: current position vs. requested position (boundary check), motor temperature/overload state, emergency stop status, and command rate limits. If any check fails, the command is rejected with a specific error code rather than silently corrupting hardware state. This prevents the agent from commanding movements that would exceed mechanical limits.

## Migration Structure

```
┌─────────────────┐     ┌──────────────────┐     ┌────────────────┐
│  Agent/AI Layer │────▶│  Command Abstraction│────▶│ Hardware Layer │
│  (decision)     │     │  (safety validation)│     │ (motor/servo)  │
└─────────────────┘     └──────────────────┘     └────────────────┘
```

### Agent Commands (Input)

| Command | Parameters | Description |
|---------|-----------|-------------|
| `move_gantry` | `x`, `y`, `z` | Move the gantry to absolute (x, y, z) position in mm |
| `grab` | None | Close the claw (servo engage) |
| `release` | None | Open the claw (servo disengage) |
| `capture` | None | Take a camera snapshot for item detection |
| `status` | None | Return current position, claw state, motor temps |
| `home` | None | Return gantry to (0, 0, 0) home position |
| `set_speed` | `speed` | Set movement speed as percentage (10-100) |
| `emergency_stop` | None | Immediate stop (hardware-level, overrides all) |

### Safety Validation Rules

| Check | Condition | Error Code |
|-------|-----------|------------|
| Boundary | x ∈ [0, 300], y ∈ [0, 400], z ∈ [0, 150] | ERR_BOUNDS |
| Overload | Motor current < 2.5A per axis | ERR_OVERLOAD |
| Emergency | Stop button not pressed | ERR_EMSTOP |
| Rate limit | Max 5 commands/second | ERR_RATE |
| Claw state | Cannot `grab` when already grabbing | ERR_STATE |
| Movement | Cannot `move` while `emergency_stop` active | ERR_LOCKED |

## Examples

**Good: Autonomous claw game session.** The agent watches the camera feed via `capture`, uses image recognition to identify a target item's pixel coordinates, converts to gantry coordinates using a calibrated mapping function, then issues `move_gantry(x=150, y=200, z=80)`, waits for positioning confirmation, issues `grab`, waits 1 second, issues `move_gantry(x=150, y=200, z=150)` to lift, then `move_gantry(x=0, y=0, z=150)` to drop zone, and finally `release`. The entire sequence is safe because every `move_gantry` passes the boundary validator before reaching hardware.

**Good: Emergency stop under agent control.** During normal operation, the agent detects an unexpected vibration or sound via the camera/microphone. It immediately issues `emergency_stop`. The command bypasses the rate limiter and all other checks — it's the only command that hits the hardware layer unconditionally. The agent then issues `status` to confirm the system is stopped, logs the incident, and waits for human intervention before resuming.

## Original Script Architecture (Pre-Migration)

The original `claw-controller.py` was a single monolithic script:

```python
# Pre-migration architecture (pseudocode)
def main():
    while True:
        # Hardcoded sequence
        move_to(100, 100, 50)
        grab()
        move_to(200, 100, 50)
        release()
        sleep(5)
```

Problems solved by migration:
- Sequences were hardcoded — no way to adapt to changing item positions
- No safety validation — any coordinate could be sent to motors
- No status monitoring — if a motor stalled, the script continued blindly
- No camera feedback — items were grabbed blind based on assumed positions
- Single-process — could not handle concurrent capture + movement + reporting

## Anti-Patterns

**Anti-Pattern 1: Sending blind movement commands after camera capture.** A common mistake is to capture an image, identify a target position, and immediately send `move_gantry` without checking that the coordinate conversion from pixels to mm is calibrated. If the camera calibration matrix is outdated (e.g., after repositioning the camera), the agent will target the wrong physical location. Always verify the mapping: capture a reference object at a known position, confirm the pixel→mm transform matches, then proceed.

**Anti-Pattern 2: Issuing rapid grab/release without cooldown.** Hardware servos have a duty cycle limit (typically 5-10 seconds of continuous actuation before overheating). An agent that quickly alternates `grab` and `release` in a loop (e.g., testing claw mechanism) will overheat the servo within 15-20 commands. The safety layer enforces a minimum 2-second interval between consecutive claw commands, but the agent should also self-regulate: if you detect `ERR_OVERLOAD` on the claw, wait at least 30 seconds before retrying.

**Anti-Pattern 3: Assuming the gantry is at home after an emergency stop.** `emergency_stop` halts all motors immediately, which means the gantry stops wherever it is — not at (0, 0, 0). Any subsequent `move_gantry` command that assumes the current position = last-known position will calculate incorrect step counts. Always issue a `status` after an emergency stop to read real encoder positions, then re-home with `home` before resuming normal operation.

## When NOT to Use

- **Simulation-only testing without hardware**: The command abstraction works against a real physical claw machine. Without servos, motors, and a camera, the commands produce no visible effect. Use the `--dry-run` flag during development to log command intent without sending to hardware.
- **When the original claw-controller.py is sufficient**: If the claw machine operates in a fixed-location, fixed-item scenario (no AI decision-making needed), the original script is simpler and more reliable. Migration adds complexity for adaptive behavior.
- **High-speed production environments**: The safety checks add ~50ms latency per command. For applications requiring sub-50ms response times (e.g., conveyor belt sorting), direct microcontroller programming or a real-time OS is more appropriate.
- **Without physical emergency stop hardware**: The agent's `emergency_stop` command relies on network communication. If the agent process crashes or the network drops, the hardware will not auto-stop. Always install a physical emergency stop button wired directly to the motor controller.

## Controls Before Migration

Before migrating, document:
- Current motor controller specs (stepper driver model, microstepping)
- Camera position and intrinsics (calibration matrix)
- Mechanical limits (x, y, z travel range)
- Servo specs (torque, duty cycle, stall current)
- Power supply ratings (voltage, current per axis)

This documentation becomes the reference for validating that the migration's safety rules don't exceed physical limits.

## Cross-References

- **blender-mcp**: For creating 3D models of the claw machine enclosure or replacement parts
- **parallel-cli**: For running calibration sequences (e.g., test each axis through full travel range in parallel)
- **research-paper-writing**: For documenting the migration architecture and safety analysis in a formal report
