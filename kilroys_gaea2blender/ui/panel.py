import bpy
from ..utils import TILE_COLLECTION_NAME

class MainPanel(bpy.types.Panel):
    bl_label = "Gaea2Blender"
    bl_idname = "VIEW3D_PT_gaea2blender_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Gaea2Blender'

    def draw(self, context):
        layout = self.layout
        layout.label(text="Add-on loaded - UI TODO")

# register list for __init__
from . import classes
classes.append(MainPanel) 