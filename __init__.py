from __future__ import annotations

import bpy

from bpy.props import PointerProperty, CollectionProperty

from .sgg_classes import (
    SGG_GlobalSettings,
    SGG_ActionPlanItem,
    SGG_ArmaturePlanItem,
)
from .ui import SGG_PT_main_panel
from .ops import (
    SGG_OT_plan_and_run,
    SGG_OT_toggle_all_armatures,
    SGG_OT_toggle_armature_actions,
)
from .batch_rendering import SGG_OT_execute_batch


bl_info = {
    "name": "Spritesheet Generator for Godot",
    "author": "Dario 'iRadDev' De Vita",
    "version": (0, 1, 0),
    "blender": (4, 4, 0),
    "location": "3D Viewport > N-panel > GodotSpriteFrames",
    "description": "Batch render armature actions as spritesheets for Godot.",
    "category": "Render",
}


classes = (
    SGG_GlobalSettings,
    SGG_ActionPlanItem,
    SGG_ArmaturePlanItem,
    SGG_PT_main_panel,
    SGG_OT_plan_and_run,
    SGG_OT_toggle_all_armatures,
    SGG_OT_toggle_armature_actions,
    SGG_OT_execute_batch,
)


def register() -> None:
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.sgg_settings = PointerProperty(type=SGG_GlobalSettings)
    bpy.types.Scene.sgg_plan_armatures = CollectionProperty(type=SGG_ArmaturePlanItem)


def unregister() -> None:
    del bpy.types.Scene.sgg_plan_armatures
    del bpy.types.Scene.sgg_settings

    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
