bl_info = {
    "name": "Kilroy's Gaea2Blender",
    "blender": (2, 80, 0),
    "category": "Object",
    "author": "Kilroy",
    "version": (2, 0, 0),
    "description": "Generate Landscapes or Globes from Gaea height/texture maps, with optional atmosphere and clouds.",
    "support": "COMMUNITY",
    "location": "View3D > Sidebar > Kilroy Gaea2Blender",
}

import importlib, bpy
from . import properties

# ensure properties always loaded first
importlib.reload(properties)


def _gather_classes():
    """Import sub-modules lazily and collect their classes list."""
    from . import operators, ui  # local import avoids circular issue
    importlib.reload(operators)
    importlib.reload(ui)
    return (
        properties.KilroyProperties,
        *operators.classes,
        ui.MainPanel,
    )


def register():
    classes = _gather_classes()
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.kilroy_props = bpy.props.PointerProperty(type=properties.KilroyProperties)


def unregister():
    classes = _gather_classes()
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.kilroy_props


if __name__ == "__main__":
    register() 