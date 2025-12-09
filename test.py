# What worked in the first attempt:
# - PNG-first pipeline
# - Frames rendered as individual PNG files
# - Spritesheet assembled afterwards from disk
# - No reliance on compositor or render layers
# - This approach is validated and should remain the base
# - Spritesheet assembly logic
# - Manual pixel copy into a single image
# - Correct handling of Blender’s bottom-left origin
# - Output was correct and usable in-engine
# - These are known-good and should be reused conceptually.

# What was missing / broken (and already addressed in new design)
# - No armature swapping safety
# - No reliable action switching
# - Blocking execute() -> Blender freeze
# - No cancellation
# - No planning / preview stage
# - No per-action control
# - No direction system
# - No workload estimation

# All of that is already solved architecturally in the new design.

bl_info = {
    "name": "Sprite Sheet Exporter for Godot",
    "author": "Dario 'iRad' De Vita",
    "version": (0, 1, 0),
    "blender": (4, 4, 0),
    "location": "3D View > N-panel > Sprites",
    "description": "Export armature actions as sprite sheets for 2D games.",
    "category": "Render",
}

import bpy
import os
import math
from bpy.props import (
    PointerProperty,
    StringProperty,
    IntProperty,
    BoolProperty,
)

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def get_armatures_in_collection(collection):
    """Return all armature objects in a collection (non-recursive)."""
    if collection is None:
        return []
    return [obj for obj in collection.objects if obj.type == 'ARMATURE']


def get_actions_from_nla(obj):
    """
    Collect actions from an armature's NLA tracks.
    This assumes each action you care about is placed in a strip.
    """
    actions = []
    ad = obj.animation_data
    if not ad or not ad.nla_tracks:
        return actions

    for track in ad.nla_tracks:
        for strip in track.strips:
            if strip.action and strip.action not in actions:
                actions.append(strip.action)
    return actions


def render_frames_for_action(context, obj, action, frame_start, frame_end, frame_step, res_x, res_y, output_dir):
    """
    Render all frames for one action of one armature to separate PNG files.
    Returns a list of file paths for those frames.
    """
    scene = context.scene
    render = scene.render

    # Save original settings
    old_res_x = render.resolution_x
    old_res_y = render.resolution_y
    old_filepath = render.filepath
    old_action = None
    if obj.animation_data:
        old_action = obj.animation_data.action

    # Apply our settings
    render.resolution_x = res_x
    render.resolution_y = res_y

    if not obj.animation_data:
        obj.animation_data_create()
    obj.animation_data.action = action

    frame_paths = []

    for frame in range(frame_start, frame_end + 1, frame_step):
        scene.frame_set(frame)
        filename = f"{obj.name}_{action.name}_{frame:04d}.png"
        path = os.path.join(output_dir, filename)
        render.filepath = path

        bpy.ops.render.render(write_still=True)
        frame_paths.append(path)

    # Restore original settings
    render.resolution_x = old_res_x
    render.resolution_y = old_res_y
    render.filepath = old_filepath
    if obj.animation_data:
        obj.animation_data.action = old_action

    return frame_paths


def make_spritesheet_from_frames(frame_paths, frame_w, frame_h, frames_per_row, output_path):
    """
    Load the rendered frame images and pack them into a single spritesheet.
    """
    if not frame_paths:
        return

    num_frames = len(frame_paths)
    cols = frames_per_row if frames_per_row > 0 else num_frames
    cols = min(cols, num_frames)
    rows = math.ceil(num_frames / cols)

    sheet_w = frame_w * cols
    sheet_h = frame_h * rows

    # Create sheet
    sheet = bpy.data.images.new(
        name="SpriteSheetTemp",
        width=sheet_w,
        height=sheet_h,
        alpha=True,
        float_buffer=False,
    )

    # Initialize transparent pixels
    sheet_pixels = [0.0] * (sheet_w * sheet_h * 4)

    # Fill sheet
    for idx, path in enumerate(frame_paths):
        col = idx % cols
        row = rows - 1 - (idx // cols)  # flip vertically (Blender images origin is bottom-left)

        try:
            img = bpy.data.images.load(path)
        except RuntimeError:
            print(f"Could not load image: {path}")
            continue

        img_width = img.size[0]
        img_height = img.size[1]

        if img_width != frame_w or img_height != frame_h:
            print(f"Warning: {path} size {img_width}x{img_height} != expected {frame_w}x{frame_h}")
        
        frame_pixels = list(img.pixels[:])

        # Copy row by row into sheet
        for fy in range(frame_h):
            sy = row * frame_h + fy
            frame_row_start = fy * frame_w * 4
            frame_row_end = frame_row_start + frame_w * 4

            sheet_row_start = (sy * sheet_w + col * frame_w) * 4
            sheet_row_end = sheet_row_start + frame_w * 4

            sheet_pixels[sheet_row_start:sheet_row_end] = frame_pixels[frame_row_start:frame_row_end]

        # Optionally remove the image datablock from memory
        bpy.data.images.remove(img)

    sheet.pixels = sheet_pixels

    # Save sheet
    sheet.filepath_raw = output_path
    sheet.file_format = 'PNG'
    sheet.save()

    # Optionally keep sheet in memory as datablock with a nicer name
    sheet.name = os.path.basename(output_path)


# -------------------------------------------------------------------
# Properties on Scene
# -------------------------------------------------------------------

class SpriteSheetSettings(bpy.types.PropertyGroup):
    collection: PointerProperty(
        name="Armature Collection",
        type=bpy.types.Collection,
        description="Collection containing armatures to export"
    )

    output_dir: StringProperty(
        name="Output Directory",
        subtype='DIR_PATH',
        default="//spritesheets/",
        description="Directory where spritesheets will be saved"
    )

    use_action_range: BoolProperty(
        name="Use Action Frame Range",
        default=True,
        description="Use each action's own frame range"
    )

    custom_frame_start: IntProperty(
        name="Custom Start",
        default=1,
        min=0,
        description="Custom start frame if not using action range"
    )

    custom_frame_end: IntProperty(
        name="Custom End",
        default=24,
        min=0,
        description="Custom end frame if not using action range"
    )

    frame_step: IntProperty(
        name="Frame Step",
        default=1,
        min=1,
        description="Render every Nth frame (1 = every frame)"
    )

    frame_width: IntProperty(
        name="Frame Width",
        default=256,
        min=1,
        description="Width of each sprite frame in pixels"
    )

    frame_height: IntProperty(
        name="Frame Height",
        default=256,
        min=1,
        description="Height of each sprite frame in pixels"
    )

    frames_per_row: IntProperty(
        name="Frames per Row",
        default=8,
        min=1,
        description="How many frames per row in the spritesheet"
    )

    delete_frames_after: BoolProperty(
        name="Delete Individual Frames",
        default=False,
        description="Delete raw frame PNGs after spritesheet is created"
    )


# -------------------------------------------------------------------
# Operator
# -------------------------------------------------------------------

class SPRITE_OT_export_sheets(bpy.types.Operator):
    bl_idname = "sprite.export_sheets"
    bl_label = "Export Sprite Sheets"
    bl_description = "Export each armature action in the collection as a spritesheet"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        scene = context.scene
        settings = scene.sprite_sheet_settings

        collection = settings.collection
        if collection is None:
            self.report({'ERROR'}, "No collection selected")
            return {'CANCELLED'}

        output_dir = bpy.path.abspath(settings.output_dir)
        os.makedirs(output_dir, exist_ok=True)

        armatures = get_armatures_in_collection(collection)
        if not armatures:
            self.report({'ERROR'}, "No armatures in the selected collection")
            return {'CANCELLED'}

        for obj in armatures:
            actions = get_actions_from_nla(obj)

            if not actions:
                self.report({'WARNING'}, f"No NLA actions found for {obj.name}")
                continue

            for action in actions:
                if settings.use_action_range:
                    f_start, f_end = action.frame_range
                    frame_start = int(f_start)
                    frame_end = int(f_end)
                else:
                    frame_start = settings.custom_frame_start
                    frame_end = settings.custom_frame_end

                if frame_end < frame_start:
                    self.report(
                        {'WARNING'},
                        f"Invalid frame range for {action.name} on {obj.name}, skipping"
                    )
                    continue

                self.report(
                    {'INFO'},
                    f"Rendering {obj.name} - {action.name} frames {frame_start}-{frame_end} step {settings.frame_step}"
                )

                frame_paths = render_frames_for_action(
                    context,
                    obj,
                    action,
                    frame_start,
                    frame_end,
                    settings.frame_step,
                    settings.frame_width,
                    settings.frame_height,
                    output_dir
                )

                # Build spritesheet
                sheet_name = f"{obj.name}_{action.name}_sheet.png"
                sheet_path = os.path.join(output_dir, sheet_name)

                make_spritesheet_from_frames(
                    frame_paths,
                    settings.frame_width,
                    settings.frame_height,
                    settings.frames_per_row,
                    sheet_path
                )

                # Optionally clean up frame images
                if settings.delete_frames_after:
                    for p in frame_paths:
                        try:
                            os.remove(p)
                        except OSError:
                            pass

        self.report({'INFO'}, "Sprite sheet export finished")
        return {'FINISHED'}


# -------------------------------------------------------------------
# UI Panel
# -------------------------------------------------------------------

class SPRITE_PT_export_panel(bpy.types.Panel):
    bl_label = "Sprite Sheet Exporter"
    bl_idname = "SPRITE_PT_export_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Sprites'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        settings = scene.sprite_sheet_settings

        col = layout.column(align=True)
        col.label(text="Source")
        col.prop(settings, "collection")
        col.prop(settings, "output_dir")

        layout.separator()

        col = layout.column(align=True)
        col.label(text="Animation Range")
        col.prop(settings, "use_action_range")
        if not settings.use_action_range:
            row = col.row(align=True)
            row.prop(settings, "custom_frame_start")
            row.prop(settings, "custom_frame_end")
        col.prop(settings, "frame_step")

        layout.separator()

        col = layout.column(align=True)
        col.label(text="Sprite Frame")
        row = col.row(align=True)
        row.prop(settings, "frame_width")
        row.prop(settings, "frame_height")
        col.prop(settings, "frames_per_row")
        col.prop(settings, "delete_frames_after")

        layout.separator()
        layout.operator("sprite.export_sheets", icon="RENDER_ANIMATION")


# -------------------------------------------------------------------
# Registration
# -------------------------------------------------------------------

classes = (
    SpriteSheetSettings,
    SPRITE_OT_export_sheets,
    SPRITE_PT_export_panel,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.sprite_sheet_settings = PointerProperty(type=SpriteSheetSettings)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.sprite_sheet_settings


if __name__ == "__main__":
    register()
