from __future__ import annotations

import bpy
from bpy.types import Panel, Context, Scene

from .sgg_classes import SGG_GlobalSettings


class SGG_PT_main_panel(Panel):
    """Main panel for Spritesheet Generator for Godot."""
    bl_idname = "SGG_PT_main_panel"
    bl_label = "Spritesheet Generator"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Sprites"

    def draw(self, context: Context) -> None:
        layout = self.layout
        scene: Scene = context.scene
        settings: SGG_GlobalSettings = scene.sgg_settings

        # --- Batch setup ---
        layout.label(text="Batch Setup", icon="RENDER_STILL")

        col = layout.column(align=True)
        col.prop(settings, "armature_collection")
        col.prop(settings, "output_dir")

        layout.separator()

        col = layout.column(align=True)
        col.prop(settings, "directions")
        col.prop(settings, "frame_step")
        col.prop(settings, "use_action_range")

        box = layout.box()
        box.label(text="Output")
        box.prop(settings, "output_dir")
        box.prop(
            settings,
            "delete_frame_pngs",
            text="Delete frame PNGs after packing",
        )

        layout.separator()

        # --- Renderer recap (read-only) ---
        box = layout.box()
        box.label(text="Renderer Recap", icon="INFO")

        render = scene.render
        box.label(text=f"Engine: {render.engine}")
        box.label(text=f"Resolution: {render.resolution_x} x {render.resolution_y}")
        box.label(text=f"Percentage: {render.resolution_percentage}%")

        layout.separator()

        # --- Plan & Run button ---
        layout.operator(
            "sgg.plan_and_run",
            text="Plan & Run Batch…",
            icon="SEQ_SEQUENCER",
        )
