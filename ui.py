from __future__ import annotations

import bpy
from bpy.types import Panel, Context, Scene, UILayout

from .sgg_classes import SGG_GlobalSettings


class SGG_PT_main_panel(Panel):
    """Main panel for Spritesheet Generator for Godot."""
    bl_idname = "SGG_PT_main_panel"
    bl_label = "Spritesheet Generator"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "GodotSpriteFrames"

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

        if not settings.batch_running:
            # When idle: show the Plan & Run button
            layout.operator(
                "sgg.plan_and_run",
                text="Plan & Run Batch…",
                icon="SEQ_SEQUENCER",
            )
        else:
            # When running: show progress bar + small X to cancel
            row: UILayout = layout.row(align=True)

            progress = 0.0
            if settings.batch_total_frames > 0:
                progress = settings.batch_processed_frames / settings.batch_total_frames

            # Progress bar (fills most of the row)
            row.progress(
                text=f"{settings.batch_processed_frames} / {settings.batch_total_frames} frames",
                factor=progress,
                type='BAR',
            )

            # Little X button on the right
            row.operator(
                "sgg.cancel_batch",
                text="",
                icon="CANCEL",
            )
