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
        """Synchronize scene.sgg_plan_armatures with current armatures/actions.

        This preserves existing user edits (enabled flags, frame ranges, reverse
        flags, expansion state) and only adds/removes items as needed.
        """
        collection = settings.armature_collection
        plan = scene.sgg_plan_armatures

        self.report({'INFO'}, "[SGG] Syncing plan with scene...")

        if collection is None:
            return

        # Current armatures from the chosen collection
        armatures = core.find_armatures_in_collection(collection)
        armature_set = set(armatures)

        # Map existing plan items by armature object
        existing_arms_by_obj: dict[Object, SGG_ArmaturePlanItem] = {}
        for arm_item in plan:
            arm_item: SGG_ArmaturePlanItem
            if arm_item.armature is not None:
                existing_arms_by_obj[arm_item.armature] = arm_item

        # Ensure we have a plan item for each current armature
        for obj in armatures:
            arm_item = existing_arms_by_obj.get(obj) # type: ignore
            if arm_item is None:
                # New armature in the scene/collection: create a fresh plan item
                arm_item = plan.add()
                arm_item.armature = obj
                arm_item.name = obj.name
                arm_item.enabled = True
                arm_item.ui_expanded = True

            # Sync actions for this armature
            actions = core.find_actions_for_armature(obj)  # type: ignore[assignment]
            actions_set = set(actions)

            # Map existing action plan items by Action datablock
            existing_actions_by_action: dict[Action, SGG_ActionPlanItem] = {}
            for act_item in arm_item.actions:
                act_item: SGG_ActionPlanItem
                if act_item.action is not None:
                    existing_actions_by_action[act_item.action] = act_item

            # Ensure we have an action plan item for each current action
            seen_actions: set[Action] = set()
            for action in actions:
                act_item = existing_actions_by_action.get(action) # type: ignore
                if act_item is None:
                    # New action found: create a fresh plan entry with default range
                    act_item = arm_item.actions.add()
                    act_item.action = action
                    act_item.name = action.name
                    act_item.enabled = False  # new actions start disabled
                    start, end = core.compute_effective_action_frame_range(obj, action)
                    act_item.frame_start = start
                    act_item.frame_end = end
                    # reverse_playback and other flags keep their default values
                seen_actions.add(action)

            # Remove action items whose underlying Action no longer exists / used
            for idx in reversed(range(len(arm_item.actions))):
                act_item = arm_item.actions[idx]
                if act_item.action is None or act_item.action not in seen_actions:
                    arm_item.actions.remove(idx)

        # Remove armature plan items whose armature is no longer valid / in collection
        for idx in reversed(range(len(plan))):
            arm_item = plan[idx]
            if arm_item.armature is None or arm_item.armature not in armature_set:
                plan.remove(idx)



    def draw(self, context: Context) -> None:
        layout = self.layout
        scene: Scene = context.scene
        settings: SGG_GlobalSettings = scene.sgg_settings  # type: ignore[attr-defined]
        plan = scene.sgg_plan_armatures

        layout.label(text="Batch Plan", icon="VIEWZOOM")

        # ------------------------------------------------------
        # Top row: Workload, Renderer recap, Output summary
        # ------------------------------------------------------
        total_frames, total_sheets = core.estimate_workload(
            scene,
            directions=settings.directions,
            frame_step=settings.frame_step,
        )
        max_w, max_h = core.estimate_max_sheet_size(
            scene,
            directions=settings.directions,
            frame_step=settings.frame_step,
        )

        top_row = layout.row(align=True)

        # Workload box
        summary_box = top_row.box()
        summary_box.label(text="Workload", icon="SETTINGS")
        summary_box.label(text=f"Frames: {total_frames}")
        summary_box.label(text=f"Spritesheets: {total_sheets}")
        if max_w > 0 and max_h > 0:
            summary_box.label(text=f"Max sheet: {max_w} x {max_h}")
        else:
            summary_box.label(text="Max sheet: —")

        # Last-frame render time (if known)
        if hasattr(settings, "last_frame_render_seconds"):
            if settings.last_frame_render_seconds > 0.0:
                summary_box.label(
                    text=f"Last frame: {settings.last_frame_render_seconds:.2f} s"
                )
            else:
                summary_box.label(text="Last frame: —")

        # Renderer recap
        render_box = top_row.box()
        render_box.label(text="Renderer", icon="RENDER_STILL")
        render = scene.render
        render_box.label(text=f"Engine: {render.engine}")
        render_box.label(
            text=f"Res: {render.resolution_x} x {render.resolution_y} @ {render.resolution_percentage}%"
        )

        # Output summary
        output_box = top_row.box()
        output_box.label(text="Output", icon="FILE_FOLDER")
        output_box.label(text=bpy.path.abspath(settings.output_dir))
        output_box.label(
            text=f"Directions: {settings.directions}, Step: {settings.frame_step}"
        )

        layout.separator()

        # --- Camera selection ---
        cam_box = layout.box()
        cam_box.label(text="Camera", icon="CAMERA_DATA")
        cam_box.prop(self, "camera")
        
        layout.separator()
        
        # ------------------------------------------------------
        # Armatures & actions list (with bulk controls inside)
        # ------------------------------------------------------
        box = layout.box()
        header_row = box.row(align=True)
        header_row.label(text="Armatures & Actions")

        # Bulk select/deselect all INSIDE this panel
        bulk_row = header_row.row(align=True)
        op = bulk_row.operator(
            "sgg.toggle_all_armatures",
            text="",
            icon="CHECKBOX_HLT",
        )
        op.enable = True
        op = bulk_row.operator(
            "sgg.toggle_all_armatures",
            text="",
            icon="CHECKBOX_DEHLT",
        )
        op.enable = False

        if not plan:
            box.label(text="No armatures/actions found. Check the collection.", icon="ERROR")
        else:
            for arm_index, arm_item in enumerate(plan):
                # Armature row (checkbox + collapse triangle + name + small summary)
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
                if hasattr(bpy.ops.sgg, "toggle_armature_actions"):
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

                        # Optional: reverse flag, if you added it earlier
                        if hasattr(act_item, "reverse_playback"):
                            act_row.prop(
                                act_item,
                                "reverse_playback",
                                text="",
                                icon="ARROW_LEFTRIGHT",
                            )

                        act_row.prop(act_item, "frame_start", text="Start")
                        act_row.prop(act_item, "frame_end", text="End")


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
