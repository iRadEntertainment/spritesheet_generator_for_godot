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

        cam_box = layout.box()
        cam_box.label(text="Camera", icon="CAMERA_DATA")
        cam_box.prop(settings, "camera")

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
            row = layout.row(align=True)

            progress = 0.0
            if settings.batch_total_frames > 0:
                progress = settings.batch_processed_frames / settings.batch_total_frames

            row.progress(
                text=f"{settings.batch_processed_frames} / {settings.batch_total_frames} frames",
                factor=progress,
                type='BAR',
            )

            row.operator(
                "sgg.cancel_batch",
                text="",
                icon="CANCEL",
            )

            # Extra info inside an info box: action, direction, frame, ETA
            box = layout.box()
            box.label(text="Batch Info", icon="INFO")

            info_col = box.column(align=True)

            # Current action / armature
            if settings.current_action_name and settings.total_actions > 0:
                action_idx = settings.current_action_index + 1  # human-friendly
                info_col.label(
                    text=(
                        f"Action ({action_idx}/{settings.total_actions}): "
                        f"{settings.current_action_name}"
                    )
                )
            elif settings.current_action_name:
                info_col.label(text=f"Action: {settings.current_action_name}")
            else:
                info_col.label(text="Action: -")

            if settings.current_armature_name:
                info_col.label(text=f"Armature: {settings.current_armature_name}")
            else:
                info_col.label(text="Armature: -")

            # Direction info
            if settings.current_direction_count > 0:
                dir_idx = settings.current_direction_index + 1  # 1-based for humans
                dir_text = f"Direction: {dir_idx}/{settings.current_direction_count}"
            else:
                dir_text = "Direction: -"
            info_col.label(text=dir_text)

            # Frame info
            if settings.current_frame > 0:
                info_col.label(text=f"Frame: {settings.current_frame}")
            else:
                info_col.label(text="Frame: -")

            # ETA based on last_frame_render_seconds
            eta_text = "-"
            remaining_frames = max(
                0,
                settings.batch_total_frames - settings.batch_processed_frames,
            )
            if (
                remaining_frames > 0
                and getattr(settings, "last_frame_render_seconds", 0.0) > 0.0
            ):
                eta_seconds = remaining_frames * settings.last_frame_render_seconds
                minutes = int(eta_seconds // 60)
                seconds = int(eta_seconds % 60)
                eta_text = f"{minutes:02d}:{seconds:02d}"

            info_col.label(text=f"ETA: {eta_text}")
