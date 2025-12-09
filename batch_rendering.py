from __future__ import annotations

import bpy
from typing import Set

from bpy.types import Operator, Context, Scene

from .sgg_classes import SGG_GlobalSettings


class SGG_OT_execute_batch(Operator):
    """Execute the spritesheet batch rendering (placeholder)."""
    bl_idname = "sgg.execute_batch"
    bl_label = "Execute Spritesheet Batch"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context: Context) -> Set[str]:
        scene: Scene = context.scene
        settings: SGG_GlobalSettings = scene.sgg_settings  # type: ignore[attr-defined]

        # This is just a stub for now – later we'll:
        # - Build a detailed plan (armatures, actions, directions, frames)
        # - Run a modal operator with progress & cancel
        # - Use rendering helpers from core.py
        self.report(
            {'INFO'},
            f"[SGG] Execute batch placeholder: directions={settings.directions}, frame_step={settings.frame_step}",
        )
        print(
            f"[SGG] Execute batch placeholder called. "
            f"Collection={settings.armature_collection}, "
            f"Output={settings.output_dir}"
        )

        return {'FINISHED'}
