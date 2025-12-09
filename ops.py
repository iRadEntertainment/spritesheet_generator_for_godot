from __future__ import annotations

import bpy
from typing import Set

from bpy.types import (
    Operator,
    Context,
    Event,
    Scene,
    WindowManager,
    Object,
    Armature,
    Action,
)
from bpy.props import BoolProperty, PointerProperty, IntProperty

from .sgg_classes import (
    SGG_GlobalSettings,
    SGG_ArmaturePlanItem,
    SGG_ActionPlanItem,
)
from . import core


def _camera_poll(self, obj: Object) -> bool:
    """Poll function to limit camera pointer to camera objects."""
    return obj.type == 'CAMERA'


class SGG_OT_plan_and_run(Operator):
    """Plan and run the spritesheet batch export."""
    bl_idname = "sgg.plan_and_run"
    bl_label = "Plan & Run Spritesheet Batch"
    bl_options = {'REGISTER'}

    camera: PointerProperty(
        name="Camera",
        type=bpy.types.Object,
        poll=_camera_poll,
        description="Camera to use for the batch render",
    )

    def invoke(self, context: Context, event: Event):
        scene: Scene = context.scene
        settings: SGG_GlobalSettings = scene.sgg_settings

        self.report({'INFO'}, "[SGG-Plan and run] Invoked!")

        # Build/refresh the planning data on the scene
        self._build_plan(scene, settings)
        
        # Set default camera:
        # - Prefer the scene camera if it is a camera object
        # - Otherwise, fall back to the first camera found in the scene
        cam = scene.camera
        if cam is None or cam.type != 'CAMERA':
            for obj in scene.objects:
                if obj.type == 'CAMERA':
                    cam = obj
                    break

        if cam is not None:
            self.camera = cam

        wm: WindowManager = context.window_manager
        return wm.invoke_props_dialog(self, width=800)


    def _build_plan(self, scene: Scene, settings: SGG_GlobalSettings) -> None:
        """Populate scene.sgg_plan_armatures based on current settings."""
        collection = settings.armature_collection
        plan = scene.sgg_plan_armatures

        # Clear previous plan
        self.report({'INFO'}, "[SGG] Building plan...")
        plan.clear()

        if collection is None:
            return

        armatures = core.find_armatures_in_collection(collection)

        for obj in armatures:
            actions = core.find_actions_for_armature(obj) # type: ignore
            if not actions:
                continue

            arm_item: SGG_ArmaturePlanItem = plan.add()
            arm_item.enabled = False
            arm_item.name = obj.name
            arm_item.armature = obj

            for action in actions:
                act_item: SGG_ActionPlanItem = arm_item.actions.add()
                act_item.enabled = False
                act_item.name = action.name
                act_item.action = action

                start, end = core.compute_effective_action_frame_range(obj, action)
                act_item.frame_start = start
                act_item.frame_end = end


    def draw(self, context: Context) -> None:
        layout = self.layout
        scene: Scene = context.scene
        settings: SGG_GlobalSettings = scene.sgg_settings
        plan = scene.sgg_plan_armatures

        # --- Title ---
        # layout.label(text="Batch Plan", icon="VIEWZOOM")

        # --- Workload summary ---
        total_frames, total_sheets = core.estimate_workload(
            scene,
            directions=settings.directions,
            frame_step=settings.frame_step,
        )

        summary_box = layout.box()
        summary_box.label(text="Workload Summary")
        summary_box.label(text=f"Total frames: {total_frames}")
        summary_box.label(text=f"Spritesheets: {total_sheets}")

        # Last-frame render time (if known)
        if settings.last_frame_render_seconds > 0.0:
            summary_box.label(
                text=f"Last frame render: {settings.last_frame_render_seconds:.2f} s"
            )
        else:
            summary_box.label(text="Last frame render: —")

        layout.separator()

        # --- Global bulk controls ---
        row = layout.row(align=True)
        row.operator(
            "sgg.toggle_all_armatures",
            text="Select All",
            icon="CHECKBOX_HLT",
        ).enable = True
        row.operator(
            "sgg.toggle_all_armatures",
            text="Deselect All",
            icon="CHECKBOX_DEHLT",
        ).enable = False

        layout.separator()

        # --- Camera selection ---
        cam_box = layout.box()
        cam_box.label(text="Camera")
        cam_box.prop(self, "camera")

        layout.separator()

        # --- Armatures & actions list ---

        box = layout.box()
        box.label(text="Armatures & Actions")

        if not plan:
            box.label(text="No armatures/actions found. Check the collection.", icon="ERROR")
        else:
            for arm_index, arm_item in enumerate(plan):
                # Armature row (checkbox + collapse triangle + name + summary + per-armature toggles)
                arm_row = box.row(align=True)

                # Armature enabled checkbox
                arm_row.prop(arm_item, "enabled", text="")

                # Collapse/expand toggle with triangle icon
                sub = arm_row.row(align=True)
                icon = 'TRIA_DOWN' if arm_item.ui_expanded else 'TRIA_RIGHT'
                sub.prop(
                    arm_item,
                    "ui_expanded",
                    text="",
                    icon=icon,
                    emboss=False,
                )

                # Armature name
                sub.label(text=arm_item.name, icon="ARMATURE_DATA")

                # Actions summary: how many actions are enabled
                total_actions = len(arm_item.actions)
                enabled_actions = sum(1 for a in arm_item.actions if a.enabled)
                summary_text = f"{enabled_actions}/{total_actions} actions"
                arm_row.label(text=summary_text)

                # Per-armature select / deselect all actions
                ops_row = arm_row.row(align=True)
                op = ops_row.operator(
                    "sgg.toggle_armature_actions",
                    text="",
                    icon="CHECKBOX_HLT",
                )
                op.enable = True
                op.armature_index = arm_index

                op = ops_row.operator(
                    "sgg.toggle_armature_actions",
                    text="",
                    icon="CHECKBOX_DEHLT",
                )
                op.enable = False
                op.armature_index = arm_index

                # Actions for this armature
                actions_col = box.column(align=True)
                # Disable the whole actions block when the armature is disabled
                actions_col.enabled = arm_item.enabled

                if arm_item.ui_expanded:
                    for act_item in arm_item.actions:
                        act_row = actions_col.row(align=True)
                        act_row.separator(factor=2.0)

                        # Checkbox shows the action name so clicking the text toggles it
                        act_row.prop(
                            act_item,
                            "enabled",
                            text=act_item.name,
                            icon="ACTION",
                        )

                        # Reversed playback toggle (for later Godot SpriteFrames use)
                        act_row.prop(
                            act_item,
                            "reverse_playback",
                            text="",
                            icon="ARROW_LEFTRIGHT",
                        )

                        act_row.prop(act_item, "frame_start", text="Start")
                        act_row.prop(act_item, "frame_end", text="End")

        layout.separator()


    def execute(self, context: Context) -> Set[str]:
        scene: Scene = context.scene

        if self.camera is not None:
            scene.camera = self.camera

        self.report({'INFO'}, "[SGG] Planning complete, starting batch execution (placeholder).")

        # For now, just call the execution operator directly.
        bpy.ops.sgg.execute_batch('EXEC_DEFAULT')

        return {'FINISHED'}


class SGG_OT_toggle_all_armatures(Operator):
    """Enable or disable all armatures (and their actions) in the current plan."""
    bl_idname = "sgg.toggle_all_armatures"
    bl_label = "Toggle All Armatures"
    bl_options = {'INTERNAL'}

    enable: BoolProperty(
        name="Enable",
        default=True,
    )

    def execute(self, context: Context) -> Set[str]:
        scene: Scene = context.scene
        plan = scene.sgg_plan_armatures

        for arm_item in plan:
            arm_item.enabled = self.enable
            for act_item in arm_item.actions:
                act_item.enabled = self.enable

        return {'FINISHED'}


class SGG_OT_toggle_armature_actions(Operator):
    """Enable or disable all actions for a single armature in the plan."""
    bl_idname = "sgg.toggle_armature_actions"
    bl_label = "Toggle Armature Actions"
    bl_options = {'INTERNAL'}

    armature_index: IntProperty(
        name="Armature Index",
        default=-1,
        description="Index of the armature in the planning collection",
    )

    enable: BoolProperty(
        name="Enable",
        default=False,
    )

    def execute(self, context: Context) -> Set[str]:
        scene: Scene = context.scene
        plan = scene.sgg_plan_armatures

        if self.armature_index < 0 or self.armature_index >= len(plan):
            return {'CANCELLED'}

        arm_item: SGG_ArmaturePlanItem = plan[self.armature_index]
        for act_item in arm_item.actions:
            act_item.enabled = self.enable

        return {'FINISHED'}
