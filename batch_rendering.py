from __future__ import annotations

import bpy
from typing import Set

from bpy.types import Operator, Context, Scene

from .sgg_classes import SGG_GlobalSettings
from .core import BatchExecPlan


class SGG_OT_execute_batch(Operator):
    """Execute the spritesheet batch rendering based on the current plan."""
    bl_idname = "sgg.execute_batch"
    bl_label = "Execute Spritesheet Batch"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context: Context) -> Set[str]:
        scene: Scene = context.scene
        settings: SGG_GlobalSettings = scene.sgg_settings

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

        # Simple debug / verification: count total actions and frames.
        total_actions = len(plan.actions)
        total_frames = 0
        for action_plan in plan.actions:
            frame_count = len(list(action_plan.frame_range.frames()))
            total_frames += frame_count * plan.directions

        self.report(
            {'INFO'},
            (
                f"[SGG] Built execution plan: "
                f"{total_actions} action group(s), "
                f"{plan.directions} direction(s), "
                f"~{total_frames} frame renders."
            ),
        )
        print(
            f"[SGG] Execute batch plan summary:\n"
            f"  Actions: {total_actions}\n"
            f"  Directions: {plan.directions}\n"
            f"  Estimated frame renders: {total_frames}\n"
            f"  Collection: {settings.armature_collection}\n"
            f"  Output dir: {settings.output_dir!r}"
        )

        # TODO (next steps):
        # - Turn this into a modal operator
        # - Iterate over plan.actions / plan.directions
        # - Render frames and assemble spritesheets
        return {'FINISHED'}

