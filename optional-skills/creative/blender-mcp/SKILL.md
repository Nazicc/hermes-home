---
name: blender-mcp
category: creativity
metadata:
  hermes:
    tags: [blender, 3d, modeling, mcp, automation]
    related_skills:
      - hermes-agent-mcp-integration
      - parallel-cli
---

# Blender MCP Control

Control Blender 3D via the Model Context Protocol (MCP) — create, manipulate, and render 3D scenes programmatically through natural language commands routed to Blender's Python API.

## Why This Works

**Concept 1: Natural Language to Blender Python Bridge.** Blender's native interface requires either clicking through a complex GUI or writing Python scripts using `bpy` (Blender Python API). The Blender MCP server translates natural language requests ("create a red cube with rounded edges") into the corresponding `bpy` command chain (`bpy.ops.mesh.primitive_cube_add()`, then modify vertices and apply materials). This removes the barrier of memorizing Blender's API while still producing authorable, deterministic results.

**Concept 2: MCP Tool Pattern for 3D Operations.** Each Blender operation (create object, apply material, set camera, render) maps to an MCP tool with typed parameters. The tool schema constrains inputs to valid ranges (e.g., `location: [0, 0, 0]` must be three floats, `scale: {x, y, z}` must be positive), which prevents the most common Blender scripting errors (out-of-bounds transforms, invalid material names, missing required arguments).

## Available Tools

| Tool | Description |
|------|-------------|
| `create_object` | Create primitive mesh (cube, sphere, cylinder, plane, torus, cone, icosphere) |
| `set_material` | Apply or create a material (color, roughness, metallic) |
| `transform_object` | Move, rotate, or scale an object |
| `delete_object` | Remove an object from the scene |
| `set_camera` | Position and orient the scene camera |
| `add_light` | Add a light source (point, sun, spot, area) |
| `render_scene` | Render the current scene to an image file |
| `export_scene` | Export to .blend, .obj, .fbx, or .glb |
| `list_objects` | List all objects in the current scene |

## Examples

**Good: Creating a procedural scene from a description.** Prompt: "Create a simple product shot: a metallic blue sphere on a reflective surface, lit from above." The MCP server decomposes this into: `create_object(type="sphere", location=[0, 0, 0.5])` → `set_material(object="Sphere", color=[0.1, 0.3, 0.9], metallic=0.9, roughness=0.2)` → `create_object(type="plane", location=[0, 0, 0], scale=[5, 5, 1])` → `add_light(type="sun", location=[5, 5, 10])` → `set_camera(location=[3, -3, 2])` → `render_scene(output="product_shot.png")`. Result: a render-ready scene from one high-level prompt.

**Good: Batch rendering variations.** Use **parallel-cli** to spawn multiple Blender MCP sessions, each rendering a different material variation of the same model. Each sub-agent sets a different material color, renders, and saves the output. In 30 seconds you have 10 render variants for a design review, instead of manually tweaking materials one at a time.

## Anti-Patterns

**Anti-Pattern 1: Forgetting to start Blender in background mode.** The MCP server connects to a running Blender process. If Blender isn't running in background mode (`blender --background`), or if the wrong Blender file is loaded, tool calls silently fail or modify the wrong scene. Always run `blender --background your_scene.blend` in a separate terminal or process before calling any MCP tools.

**Anti-Pattern 2: Chaining destructive operations without saving.** Each tool call that modifies geometry (scale, delete, transform) can produce unintended cumulative effects if the scene state isn't saved between calls. For complex multi-step scenes, save checkpoints with `export_scene(format="blend", path="checkpoint.blend")` between major operations so you can roll back without rebuilding from scratch.

## When NOT to Use

- **Real-time animation or game engine work**: MCP calls involve network round-trips (even localhost) that introduce latency unsuitable for frame-by-frame animation. Use Blender's built-in animation tools or direct Python scripting.
- **Complex geometry modeling (sculpting, retopology)**: MCP tool calls are best for high-level operations (create, transform, material). Fine-grained mesh editing (vertex-by-vertex, sculpting) has too much overhead per call. Use the Blender GUI directly.
- **When Blender isn't installed**: The MCP server is a thin wrapper — all operations execute in Blender. Verify `blender --version` works before attempting any MCP tool call.
- **For projects needing non-destructive workflow with modifiers and geometry nodes**: Complex modifier stacks and geometry node setups are better authored in the Blender GUI than via scripted MCP calls.

## Cross-References

- **hermes-agent-mcp-integration**: How MCP servers connect to the agent — fundamental setup for Blender MCP
- **parallel-cli**: For batch rendering and parallel scene generation workflows using Blender
