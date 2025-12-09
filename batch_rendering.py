from __future__ import annotations

import bpy
import os
import time
from typing import Set, Optional, Dict, Iterator

from bpy.types import Operator, Context, Scene, Object

from .sgg_classes import SGG_GlobalSettings
from .core import BatchExecPlan, ActionExecPlan


class SGG_OT_execute_batch(Operator):
    """Execute the spritesheet batch rendering as a modal operator."""
    bl_idname = "sgg.execute_batch"
    bl_label = "Execute Spritesheet Batch"
    bl_options = {'REGISTER', 'INTERNAL'}

    # Internal state for modal execution
    _plan: Optional[BatchExecPlan]
    _action_index: int
    _direction_index: int
    _frame_iter: Optional[Iterator[int]]
    _current_action_plan: Optional[ActionExecPlan]
    _timer: Optional[bpy.types.Timer]
    _original_frame: int
    _original_filepath: str
    _original_actions: Dict[Object, object]
    _output_dir: str
    _frame_paths: Dict[tuple[int, int], list[str]]  # (action_idx, direction_idx) -> [paths]

    def execute(self, context: Context) -> Set[str]:
        """Initialize the batch and start modal execution."""
        scene: Scene = context.scene
        settings: SGG_GlobalSettings = scene.sgg_settings  # type: ignore[attr-defined]

        # Build an immutable execution plan from the current planning data.
        plan = BatchExecPlan.from_scene(
            scene=scene,
            directions=settings.directions,
            frame_step=settings.frame_step,
        )

        if not plan.actions:
            self.report(
                {'WARNING'},
                "No enabled armatures/actions in the current plan.",
            )
            return {'CANCELLED'}

        # Resolve and create output directory
        self._output_dir = bpy.path.abspath(settings.output_dir)
        os.makedirs(self._output_dir, exist_ok=True)

        # Store plan and initialize indices
        self._plan = plan
        self._action_index = 0
        self._direction_index = 0
        self._frame_iter = None
        self._current_action_plan = None
        self._frame_paths = {}

        # Save original scene state
        self._original_frame = scene.frame_current
        self._original_filepath = scene.render.filepath

        # Save original active actions per armature used in the plan
        self._original_actions = {}
        for action_plan in plan.actions:
            arm_obj = action_plan.armature_obj
            if arm_obj not in self._original_actions:
                ad = arm_obj.animation_data
                self._original_actions[arm_obj] = ad.action if ad else None

        # Set up modal timer
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.0, window=context.window)
        wm.modal_handler_add(self)

        total_actions = len(plan.actions)
        self.report(
            {'INFO'},
            (
                f"[SGG] Starting batch: "
                f"{total_actions} action group(s), "
                f"{plan.directions} direction(s)."
            ),
        )

        return {'RUNNING_MODAL'}

    def modal(self, context: Context, event) -> Set[str]:
        # Allow user to cancel with ESC
        if event.type == 'ESC':
            self._finish_batch(context, cancelled=True)
            self.report({'WARNING'}, "Batch rendering cancelled by user.")
            return {'CANCELLED'}

        # We only do work on timer events
        if event.type != 'TIMER':
            return {'PASS_THROUGH'}

        if self._plan is None:
            self._finish_batch(context, cancelled=True)
            return {'CANCELLED'}

        scene: Scene = context.scene
        settings: SGG_GlobalSettings = scene.sgg_settings  # type: ignore[attr-defined]

        # Render a single frame step. If no more work, we're done.
        has_more = self._advance_step(scene, settings)
        if not has_more:
            self._finish_batch(context, cancelled=False)
            self.report({'INFO'}, "[SGG] Batch rendering completed.")
            return {'FINISHED'}

        return {'RUNNING_MODAL'}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _advance_step(
        self,
        scene: Scene,
        settings: SGG_GlobalSettings,
    ) -> bool:
        """Render one frame. Returns False if there is no more work."""
        next_item = self._next_frame()
        if next_item is None:
            return False

        action_plan, direction_index, frame = next_item
        self._render_frame(scene, settings, action_plan, direction_index, frame)
        return True

    def _next_frame(self) -> Optional[tuple[ActionExecPlan, int, int]]:
        """Iterate over (action, direction, frame) triples."""
        if self._plan is None:
            return None

        while True:
            # If we don't have a current action plan, move to the next one
            if self._current_action_plan is None:
                if self._action_index >= len(self._plan.actions):
                    return None  # All actions processed
                self._current_action_plan = self._plan.actions[self._action_index]
                self._direction_index = 0
                self._frame_iter = None

            # If we've exhausted directions for this action, move to next action
            if self._direction_index >= self._plan.directions:
                self._action_index += 1
                self._current_action_plan = None
                continue

            # If we don't have a frame iterator yet, create one
            if self._frame_iter is None:
                self._frame_iter = iter(self._current_action_plan.frame_range.frames())

            try:
                frame = next(self._frame_iter)
                return self._current_action_plan, self._direction_index, frame
            except StopIteration:
                # No more frames for this direction; move to the next direction
                self._frame_iter = None
                self._direction_index += 1
                continue

    def _render_frame(
        self,
        scene: Scene,
        settings: SGG_GlobalSettings,
        action_plan: ActionExecPlan,
        direction_index: int,
        frame: int,
    ) -> None:
        """Render a single frame for the given action/direction/frame triple.

        Also measures the single-frame render time and stores it in
        settings.last_frame_render_seconds for use in the planning summary.
        """
        arm_obj = action_plan.armature_obj
        action = action_plan.action

        # Ensure the correct action is active on the armature
        if not arm_obj.animation_data:
            arm_obj.animation_data_create()
        arm_obj.animation_data.action = action

        # TODO: apply camera/armature rotation based on direction_index

        # Set the frame
        scene.frame_set(frame)

        render = scene.render

        # Build output filepath
        safe_arm_name = arm_obj.name.replace(" ", "_")
        safe_action_name = action.name.replace(" ", "_")
        filename = f"{safe_arm_name}_{safe_action_name}_dir{direction_index:02d}_frame{frame:04d}.png"
        filepath = os.path.join(self._output_dir, filename)

        # Temporarily override render.filepath
        old_filepath = render.filepath
        render.filepath = filepath

        # Measure single-frame render time
        start = time.perf_counter()
        bpy.ops.render.render(write_still=True)
        elapsed = time.perf_counter() - start

        # Store last frame render time for UI summary
        settings.last_frame_render_seconds = float(elapsed)

        # Restore original filepath
        render.filepath = old_filepath

        # Remember this frame path for later spritesheet packing
        key = (self._action_index, direction_index)
        self._frame_paths.setdefault(key, []).append(filepath)


    def _assemble_spritesheets(self, context: Context) -> None:
        """Build spritesheets from the rendered frame PNGs.

        Strategy:
        - One spritesheet per (armature, action)
        - Directions become rows
        - Frames become columns
        """
        if self._plan is None:
            return

        scene: Scene = context.scene
        settings: SGG_GlobalSettings = scene.sgg_settings  # type: ignore[attr-defined]

        # Group frame paths by action index, then by direction index
        # actions_group[action_index][direction_index] -> [paths]
        actions_group: Dict[int, Dict[int, list[str]]] = {}
        for (action_index, direction_index), frame_paths in self._frame_paths.items():
            if not frame_paths:
                continue
            actions_group.setdefault(action_index, {})[direction_index] = frame_paths

        for action_index, dirs_dict in actions_group.items():
            if action_index < 0 or action_index >= len(self._plan.actions):
                continue

            action_plan = self._plan.actions[action_index]
            arm_obj = action_plan.armature_obj
            action = action_plan.action

            # Sort directions so rows are in a stable order (0..N-1)
            direction_indices = sorted(dirs_dict.keys())
            if not direction_indices:
                continue

            # Use the first direction + first frame to infer frame size
            first_dir = direction_indices[0]
            first_paths = dirs_dict[first_dir]
            if not first_paths:
                continue

            try:
                first_img = bpy.data.images.load(first_paths[0])
            except RuntimeError:
                print(f"[SGG] Could not load first frame image: {first_paths[0]}")
                continue

            frame_w, frame_h = first_img.size
            bpy.data.images.remove(first_img)

            # Assume all directions have same frame count; use the max to be safe
            max_frames = max(len(paths) for paths in dirs_dict.values())
            if max_frames == 0:
                continue

            cols = max_frames
            rows = len(direction_indices)

            sheet_w = frame_w * cols
            sheet_h = frame_h * rows

            sheet = bpy.data.images.new(
                name="SGG_SpriteSheetTemp",
                width=sheet_w,
                height=sheet_h,
                alpha=True,
                float_buffer=False,
            )

            # Initialize transparent pixels
            sheet_pixels = [0.0] * (sheet_w * sheet_h * 4)

            # Fill the sheet: each direction is one row, each frame is one column
            for row_idx, dir_idx in enumerate(direction_indices):
                frame_paths = dirs_dict[dir_idx]
                for col_idx, path in enumerate(frame_paths):
                    if col_idx >= cols:
                        break

                    try:
                        img = bpy.data.images.load(path)
                    except RuntimeError:
                        print(f"[SGG] Could not load frame image: {path}")
                        continue

                    img_width, img_height = img.size
                    if img_width != frame_w or img_height != frame_h:
                        print(
                            f"[SGG] Warning: {path} size {img_width}x{img_height} "
                            f"!= expected {frame_w}x{frame_h}"
                        )

                    frame_pixels = list(img.pixels[:]) # type: ignore

                    # Blender image origin is bottom-left, so flip vertically:
                    dest_row = rows - 1 - row_idx

                    for fy in range(frame_h):
                        sy = dest_row * frame_h + fy
                        frame_row_start = fy * frame_w * 4
                        frame_row_end = frame_row_start + frame_w * 4

                        sheet_row_start = (sy * sheet_w + col_idx * frame_w) * 4
                        sheet_row_end = sheet_row_start + frame_w * 4

                        sheet_pixels[sheet_row_start:sheet_row_end] = frame_pixels[
                            frame_row_start:frame_row_end
                        ]

                    bpy.data.images.remove(img)

            sheet.pixels = sheet_pixels

            # Build spritesheet filepath, one per (armature, action)
            safe_arm_name = arm_obj.name.replace(" ", "_")
            safe_action_name = action.name.replace(" ", "_")
            sheet_filename = f"{safe_arm_name}_{safe_action_name}_sheet.png"
            sheet_path = os.path.join(self._output_dir, sheet_filename)

            sheet.filepath_raw = sheet_path
            sheet.file_format = 'PNG'
            sheet.save()
            sheet.name = sheet_filename

            # Permanently delete individual frames if requested
            if getattr(settings, "delete_frame_pngs", False):
                for paths in dirs_dict.values():
                    for p in paths:
                        try:
                            os.remove(p)
                        except OSError:
                            pass


    def _finish_batch(self, context: Context, cancelled: bool) -> None:
        """Restore scene state, optionally pack spritesheets, and remove the modal timer."""
        scene: Scene = context.scene
        render = scene.render

        # If we completed successfully, build spritesheets from rendered frames
        if not cancelled:
            self._assemble_spritesheets(context)

        # Restore original frame
        if hasattr(self, "_original_frame"):
            scene.frame_set(self._original_frame)

        # Restore original filepath
        if hasattr(self, "_original_filepath"):
            render.filepath = self._original_filepath

        # Restore original actions per armature
        if hasattr(self, "_original_actions"):
            for arm_obj, original_action in self._original_actions.items():
                if arm_obj and arm_obj.animation_data:
                    arm_obj.animation_data.action = original_action

        # Remove modal timer
        wm = context.window_manager
        if getattr(self, "_timer", None) is not None:
            wm.event_timer_remove(self._timer) # type: ignore
            self._timer = None

        # Clear plan references
        self._plan = None
        self._frame_iter = None
        self._current_action_plan = None
        self._frame_paths = {}
