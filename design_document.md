# Spritesheet Generator for Godot — Design Recap

## Overview

This Blender add-on automates the process of rendering animated armatures into 2D spritesheets suitable for use in **Godot** (or similar 2D engines).

The tool is designed for:
- Multiple armatures stored in a collection
- Multiple actions per armature
- Multi-directional rendering (e.g. 8 directions like Factorio)
- Batch execution with progress reporting and cancellation
- Minimal manual setup per action

The workflow is split into **three major phases**:
1. Global setup (N-panel)
2. Planning & confirmation (modal popup)
3. Batch execution (modal, cancellable)

---

## Usage Requirements and Preparation

To use the Spritesheet Generator for Godot, the Blender scene must be prepared correctly. The add-on assumes a clean animation setup and does not attempt to infer or repair missing data.

All armatures that should be processed must be placed inside a single Blender Collection. This collection is selected in the add-on panel and is the only source from which armatures are gathered.

All animations must exist as proper Blender Actions. Animations that are only keyframes and were never saved or pushed as Actions will not be detected. Actions can be either the active action on the armature or referenced by NLA strips. A typical workflow is to animate, name the Action in the Action Editor, and push it to NLA.

Each armature should use a consistent rig across all actions. Meshes, bones, constraints, and drivers should not change between animations to ensure stable sprite dimensions.

The user must configure the camera, lighting, render engine, resolution, and output settings before running the batch. The add-on uses the existing render configuration and does not modify quality or engine parameters.

Action frame ranges are detected automatically from keyframes but can be overridden in the planning popup. Actions can also be disabled without modifying the underlying animation data.

Consistent naming of armatures and actions is strongly recommended so the generated spritesheets and animations map cleanly to Godot.

Optionally, a SpriteFrames resource can be generated automatically at the end of the process if enabled for an armature. This creates animations per action using the generated spritesheets.

Before running the tool, ensure that armatures are properly collected, all animations are Actions, render settings are finalized, and an output directory is set.

---

## File Structure

```
spritesheet_generator_for_godot/
├── __init__.py
├── core.py
├── ops.py
├── ui.py
├── batch_rendering.py
├── sgg_classes.py
├── pyrightconfig.json
```

### Responsibilities

- **ui.py**
  - N-panel UI (Render workspace → Sidebar → “Sprites” tab)
  - Global configuration
  - “Plan & Run Batch…” button

- **sgg_classes.py**
  - All `PropertyGroup` definitions:
    - Global settings
    - Armature planning data
    - Action planning data

- **core.py**
  - Pure helper logic (no UI):
    - Find armatures in collection
    - Find actions per armature
    - Compute action frame ranges
    - Estimate workload (frames / sheets)

- **ops.py**
  - Operators for:
    - Planning popup
    - Toggle all / none
    - User selections & validation

- **batch_rendering.py**
  - Actual batch execution
  - Modal operator with progress and cancellation
  - Rendering + spritesheet assembly

---

## Phase 1 — Global Setup (N-Panel)

Located in:
```
3D Viewport → Sidebar (N) → GodotSpriteFrames
```

### Global Settings

- **Armature Collection**
  - Collection containing armature objects to process
- **Output Directory**
  - Base folder for spritesheet output
- **Directions**
  - Number of camera directions (e.g. 8)
- **Frame Step**
  - Render every Nth frame
- **Use Action Frame Range**
  - If enabled, automatically detects start/end frames from the action
- **Renderer Recap (Read-only)**
  - Render engine
  - Resolution
  - Percentage scale

### Action

- **Plan & Run Batch…**
  - Opens the planning / confirmation popup

---

## Phase 2 — Planning & Confirmation (Modal Popup)

This phase is non-destructive and allows full inspection before rendering.

### Armatures & Actions

For each armature found in the selected collection:

- **Armature row**
  - Enable / disable armature
  - Expand / collapse its action list

- **Actions per armature**
  - Enable / disable individual actions
  - Editable:
    - Start frame
    - End frame
  - Frame ranges default to the action’s real animation keys

If an armature is disabled:
- Its actions remain visible
- All controls are disabled (non-interactable)

### Bulk Controls

- **Select All**
- **Deselect All**

Applied to:
- All armatures
- All their actions

---

## Workload Estimation

Updated live when toggles or frame ranges change.

Displayed in the popup:
- **Total frames to render**
- **Approximate number of spritesheets**
- **Estimated render time**
  - Derived from past renders when available
  - Displayed as “—” if unknown

---

## Camera Selection

- Camera picker in the planning popup
- Limits to objects of type `CAMERA`
- Selected camera becomes the active scene camera during batch execution

---

## Optional Godot Integration

### SpriteFrames Auto-Creation

Each armature row includes an optional checkbox:

**Create Godot SpriteFrames**

When enabled:
- After rendering and spritesheet assembly:
  - A `SpriteFrames` resource is automatically generated
  - Frames are assigned in correct order
  - Animations are named after the action
- Output is compatible with Godot import workflows

This is optional per armature.

---

## Phase 3 — Batch Rendering (Modal Operator)

Implemented in `batch_rendering.py`.

### Core Characteristics

- Modal execution (Blender remains responsive)
- Cancelable (ESC aborts safely)
- Progress feedback (frames rendered / total frames)
- No UI blocking

### Execution Steps

For each enabled armature:
1. For each enabled action:
2. For each direction:
   - Rotate armature (Z axis) or camera
3. For each frame (respecting frame step):
   - Set frame
   - Render still image

### Temporary Files

- Individual frame renders are stored temporarily
- After spritesheet assembly:
  - Temporary frames are deleted permanently

---

## Spritesheet Assembly

- One spritesheet per:
  `{armature}_{action}`

- Layout rules:
  - Rows represent directions
  - Frames are laid out sequentially per direction
  - “Rows per direction” configuration controls layout density

---

## Cancellation & Safety

- Canceling:
  - Stops immediately
  - Leaves already-generated spritesheets intact
  - Cleans temporary frames where possible
- Scene state is restored:
  - Active action
  - Frame number
  - Object transforms (rotation)

---

## Design Principles

- Explicit planning before execution
- Non-blocking batch operations
- Minimal user repetition
- Godot-friendly output
- Extensible architecture

---

## Current State

- Planning UI complete
- Action discovery verified
- Workload estimation in place
- Clean data separation
- Batch rendering pending
- Spritesheet packing pending
- SpriteFrames generation pending

---

## Final Goal

A robust, repeatable pipeline that lets you:

Select a collection → confirm actions → press OK → walk away →  
come back with ready-to-use spritesheets and Godot resources.
