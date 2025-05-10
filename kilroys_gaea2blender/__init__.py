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
        try:
            bpy.utils.register_class(cls)
        except ValueError:
            # If the class is already registered from a previous enable in this session,
            # unregister it first and then register again so the latest code is used.
            try:
                bpy.utils.unregister_class(cls)
            except Exception:
                pass
            bpy.utils.register_class(cls)
    bpy.types.Scene.kilroy_props = bpy.props.PointerProperty(type=properties.KilroyProperties)


def unregister():
    classes = _gather_classes()
    for cls in reversed(classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            # It may already be unregistered or never registered; ignore.
            pass
    del bpy.types.Scene.kilroy_props


if __name__ == "__main__":
    register() 