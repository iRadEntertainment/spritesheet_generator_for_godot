from __future__ import annotations

import bpy
from dataclasses import dataclass
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


def compute_effective_action_frame_range(
    armature: Armature,
    action: Action,
) -> Tuple[int, int]:
    """Compute start/end frames as used on the armature, respecting NLA strip offsets.

    If the action is used in an NLA strip on this armature, the strip's frame range
    is used. Otherwise, fall back to the raw action.frame_range.
    """
    ad = armature.animation_data
    nla_tracks = getattr(ad, "nla_tracks", None) if ad is not None else None

    if nla_tracks:
        for track in nla_tracks:
            for strip in track.strips:
                if strip.action == action:
                    start = int(strip.frame_start)
                    end = int(strip.frame_end)
                    return start, end

    # Fallback: use the action's own frame range
    return compute_action_frame_range(action)


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

# -------------------------------------------------------------------
# Execution plan (pure Python, built from the scene plan)
# -------------------------------------------------------------------


@dataclass(frozen=True)
class FrameRangePlan:
    """Immutable frame range with a step."""

    start: int
    end: int
    step: int

    def frames(self) -> range:
        """Iterate over all frame indices in this range."""
        step = max(1, self.step)
        if self.end < self.start:
            return range(0)
        return range(self.start, self.end + 1, step)


@dataclass(frozen=True)
class ActionExecPlan:
    """Execution-ready data for a single (armature, action, frame range)."""

    armature_obj: Object
    action: Action
    frame_range: FrameRangePlan


@dataclass(frozen=True)
class BatchExecPlan:
    """Frozen execution plan used by the modal batch renderer."""

    actions: List[ActionExecPlan]
    directions: int

    @classmethod
    def from_scene(cls, scene: Scene, directions: int, frame_step: int) -> "BatchExecPlan":
        """Build an immutable execution plan from the current planning data."""
        actions: List[ActionExecPlan] = []

        # Safety: directions and frame_step should never be less than 1
        directions = max(1, int(directions))
        step = max(1, int(frame_step))

        for arm_item in getattr(scene, "sgg_plan_armatures", []):
            arm_item: SGG_ArmaturePlanItem

            if not arm_item.enabled:
                continue

            arm_obj = arm_item.armature
            if arm_obj is None or arm_obj.type != 'ARMATURE':
                continue

            for act_item in arm_item.actions:
                if not act_item.enabled or act_item.action is None:
                    continue

                start = int(act_item.frame_start)
                end = int(act_item.frame_end)
                if end < start:
                    # Ignore invalid ranges; they should already be prevented by the UI,
                    # but we keep this check for robustness.
                    continue

                frame_range = FrameRangePlan(
                    start=start,
                    end=end,
                    step=step,
                )

                actions.append(
                    ActionExecPlan(
                        armature_obj=arm_obj,
                        action=act_item.action,
                        frame_range=frame_range,
                    )
                )

        return cls(actions=actions, directions=directions)
