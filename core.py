from __future__ import annotations

import bpy
from typing import List, Tuple

from bpy.types import Collection, Object, Action, Armature, Scene

from .sgg_classes import SGG_ArmaturePlanItem


def find_armatures_in_collection(collection: Collection | None) -> List[Armature]:
    """Return all armature objects in the given collection (non-recursive)."""
    if collection is None:
        return []
    armatures: List[Armature] = []

    for obj in collection.objects:
        if obj.type == 'ARMATURE':
            armatures.append(obj) # type: ignore
    # return [obj for obj in collection.objects if obj.type == 'ARMATURE']
    return armatures



def find_actions_for_armature(armature: Armature) -> List[Action]:
    """Collect actions associated with an armature via NLA and animation_data.

    Strategy:
    - Look at NLA tracks: each strip's action is one candidate.
    - Also include the active action (animation_data.action) if present.
    """
    actions: List[Action] = []

    ad = armature.animation_data
    if ad is None:
        return actions

    # Active action (if any)
    if ad.action is not None and ad.action not in actions:
        actions.append(ad.action)

    # NLA actions
    nla_tracks = getattr(ad, "nla_tracks", None)
    if nla_tracks:
        for track in nla_tracks:
            for strip in track.strips:
                if strip.action and strip.action not in actions:
                    actions.append(strip.action)

    return actions


def compute_action_frame_range(action: Action) -> Tuple[int, int]:
    """Compute integer start/end frames for a given action."""
    start, end = action.frame_range
    return int(start), int(end)


def estimate_workload(
    scene: Scene,
    directions: int,
    frame_step: int,
) -> Tuple[int, int]:
    """Estimate total frames and spritesheets based on current plan.

    Returns:
        (total_frames, total_spritesheets)
    """
    total_frames = 0
    total_sheets = 0

    plan = scene.sgg_plan_armatures

    for arm_item in plan:
        if not arm_item.enabled:
            continue

        has_enabled_action = False
        for act_item in arm_item.actions:
            if not act_item.enabled:
                continue

            has_enabled_action = True
            frame_count = max(0, act_item.frame_end - act_item.frame_start + 1)
            # Apply frame step (at least 1 frame if enabled)
            if frame_step > 1 and frame_count > 0:
                # ceil division
                frame_count = (frame_count + frame_step - 1) // frame_step
            total_frames += frame_count * max(1, directions)

        if has_enabled_action:
            total_sheets += 1  # one sheet per armature/action group for now

    return total_frames, total_sheets
