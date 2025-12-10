# from __future__ import annotations

import bpy
from bpy.types import PropertyGroup
from bpy.props import (
    PointerProperty,
    StringProperty,
    IntProperty,
    BoolProperty,
    CollectionProperty,
    FloatProperty,
)


class SGG_GlobalSettings(PropertyGroup):
    """Global settings for Spritesheet Generator."""

    armature_collection: PointerProperty(
        name="Armature Collection",
        type=bpy.types.Collection,
        description="Collection containing the armatures to process",
    )

    output_dir: StringProperty(
        name="Output Directory",
        subtype='DIR_PATH',
        default="//spritesheets/",
        description="Base folder for generated spritesheets",
    )

    directions: IntProperty(
        name="Directions",
        default=8,
        min=1,
        max=64,
        description="Number of view directions (e.g. 8 for N, NE, E, ...)",
    )

    frame_step: IntProperty(
        name="Frame Step",
        default=1,
        min=1,
        description="Render every Nth frame (1 = every frame)",
    )

    use_action_range: BoolProperty(
        name="Use Action Frame Range",
        default=True,
        description="Use each action's own frame range by default",
    )

    last_frame_render_seconds: FloatProperty(
        name="Last Frame Render Time",
        default=0.0,
        min=0.0,
        description=(
            "Duration in seconds of the most recently measured single-frame render "
            "in this Blender session. Used for time estimation."
        ),
    )

    delete_frame_pngs: BoolProperty(
        name="Delete Frame PNGs",
        default=True,
        description=(
            "Delete individual per-frame PNG files after spritesheets have been "
            "assembled. Uses permanent deletion (files will not be moved to the OS "
            "trash/recycle bin)."
        ),
    )

    batch_running: BoolProperty(
        name="Batch Running",
        default=False,
        description="True while a batch render is running",
    )

    batch_cancel_requested: BoolProperty(
        name="Cancel Batch",
        default=False,
        description="Set to request cancellation of the current batch",
    )

    batch_total_frames: IntProperty(
        name="Total Frames",
        default=0,
        min=0,
        description="Total number of frames that will be rendered in the current batch",
    )

    batch_processed_frames: IntProperty(
        name="Processed Frames",
        default=0,
        min=0,
        description="Number of frames rendered so far in the current batch",
    )

    current_armature_name: StringProperty(
        name="Current Armature",
        default="",
        description="Name of the armature currently being rendered in the batch",
    )

    current_action_name: StringProperty(
        name="Current Action",
        default="",
        description="Name of the action currently being rendered in the batch",
    )

    current_direction_index: IntProperty(
        name="Current Direction Index",
        default=0,
        min=0,
        description="Zero-based index of the current direction being rendered",
    )

    current_direction_count: IntProperty(
        name="Direction Count",
        default=0,
        min=0,
        description="Total number of directions in this batch",
    )

    current_frame: IntProperty(
        name="Current Frame",
        default=0,
        description="Current frame index being rendered in the batch",
    )

    current_action_index: IntProperty(
        name="Current Action Index",
        default=0,
        min=0,
        description="Zero-based index of the current action in the batch",
    )

    total_actions: IntProperty(
        name="Total Actions",
        default=0,
        min=0,
        description="Total number of actions in the current batch",
    )


class SGG_ActionPlanItem(PropertyGroup):
    """Planning data for a single action of an armature."""

    enabled: BoolProperty(
        name="Enabled",
        default=True,
        description="Include this action in the batch",
    )

    name: StringProperty(
        name="Action Name",
        default="",
    )

    frame_start: IntProperty(
        name="Start",
        default=1,
        description="Start frame for this action",
    )

    frame_end: IntProperty(
        name="End",
        default=24,
        description="End frame for this action",
    )

    action: PointerProperty(
        name="Action",
        type=bpy.types.Action,
        description="Underlying Blender Action datablock",
    )
    reverse_playback: BoolProperty(
        name="Reverse",
        default=False,
        description=(
            "Play this action in reverse order when generating Godot SpriteFrames. "
            "Does not affect rendered images, only playback order."
        ),
    )


class SGG_ArmaturePlanItem(PropertyGroup):
    """Planning data for a single armature and its actions."""

    enabled: BoolProperty(
        name="Enabled",
        default=True,
        description="Include this armature in the batch",
    )

    ui_expanded: BoolProperty(
        name="Expanded",
        default=True,
        description="Expand/collapse actions for this armature in the plan UI",
    )

    name: StringProperty(
        name="Armature Name",
        default="",
    )

    armature: PointerProperty(
        name="Armature",
        type=bpy.types.Object,
        description="Armature object",
    )

    actions: CollectionProperty(
        name="Actions",
        type=SGG_ActionPlanItem,
    )
