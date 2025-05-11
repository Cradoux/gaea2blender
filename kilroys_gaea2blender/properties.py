import bpy
from .utils import _trigger_live_update, _update_displacement_strength, _update_subdivision_levels

class KilroyProperties(bpy.types.PropertyGroup):
    # Shared image paths
    start_tile_file: bpy.props.StringProperty(name="Heightmap File", subtype='FILE_PATH')
    texture_file: bpy.props.StringProperty(name="Texture File", subtype='FILE_PATH')
    roughness_file: bpy.props.StringProperty(name="Roughness File", subtype='FILE_PATH')
    normal_file: bpy.props.StringProperty(name="Normal Map File", subtype='FILE_PATH')

    # Render mode
    render_mode: bpy.props.EnumProperty(
        name="Render Mode",
        items=[('LANDSCAPE', 'Landscape', ''), ('GLOBE', 'Globe', '')],
        default='LANDSCAPE',
        update=_trigger_live_update,
    )

    # Landscape tiling
    use_tiles: bpy.props.BoolProperty(name="Use Tiled Input", default=False)
    num_rows: bpy.props.IntProperty(name="Rows", default=4, min=1)
    num_cols: bpy.props.IntProperty(name="Cols", default=4, min=1)

    # STL export
    tile_thickness: bpy.props.FloatProperty(name="Tile Thickness", default=1.0, min=0.01)
    output_dir: bpy.props.StringProperty(name="Output Dir", subtype='DIR_PATH')

    # Geometry controls (shared)
    displacement_strength: bpy.props.FloatProperty(name="Displacement Strength", default=1.0, update=_update_displacement_strength)
    subdivision_levels: bpy.props.IntProperty(name="Subdivision Levels", default=3, min=0, update=_update_subdivision_levels)
    invert_roughness_map: bpy.props.BoolProperty(name="Invert Roughness Map", default=False, update=_trigger_live_update)
    auto_update: bpy.props.BoolProperty(name="Auto Update", default=True)

    # Globe geometry
    sphere_resolution_segments: bpy.props.IntProperty(name="Segments", default=128, min=3, max=1024)
    sphere_resolution_rings: bpy.props.IntProperty(name="Rings", default=64, min=3, max=512)
    globe_radius: bpy.props.FloatProperty(name="Radius", default=5.0, min=0.01)

    # Atmosphere
    generate_atmosphere: bpy.props.BoolProperty(name="Atmosphere", default=True)
    atmosphere_density: bpy.props.FloatProperty(name="Atmosphere Density", default=0.25, min=0.0)
    atmosphere_color: bpy.props.FloatVectorProperty(name="Atmosphere Color", subtype='COLOR', default=(0.3,0.5,1.0), size=3)
    atmosphere_scale_offset: bpy.props.FloatProperty(name="Atmosphere Scale", default=1.025, min=1.0001)

    # Texture Mapping Controls (Globe)
    maintain_aspect_ratio: bpy.props.BoolProperty(
        name="Maintain Texture Aspect Ratio",
        default=True,
        description="Adjust UV mapping to maintain original image aspect ratio (otherwise stretches to 2:1)",
        update=_trigger_live_update,
    )
    polar_padding_top: bpy.props.FloatProperty(
        name="Polar Padding Top",
        subtype='PERCENTAGE', unit='NONE', precision=2,
        default=0.0, min=0.0, max=49.0,
        description="Push texture down from the north pole to reduce polar stretching",
        update=_trigger_live_update,
    )
    polar_padding_bottom: bpy.props.FloatProperty(
        name="Polar Padding Bottom",
        subtype='PERCENTAGE', unit='NONE', precision=2,
        default=0.0, min=0.0, max=49.0,
        description="Push texture up from the south pole to reduce polar stretching",
        update=_trigger_live_update,
    )
    texture_extension_mode: bpy.props.EnumProperty(
        name="Texture Extension",
        items=[
            ('EXTEND', 'Extend', 'Clamp edge pixels beyond 0-1'),
            ('REPEAT', 'Repeat', 'Tile the texture'),
            ('CLIP', 'Clip', 'Outside area becomes transparent/background'),
        ],
        default='EXTEND',
        description="How textures behave outside original UV bounds",
        update=_trigger_live_update,
    )

    # Clouds
    generate_clouds: bpy.props.BoolProperty(name="Clouds", default=True)
    cloud_scale_offset: bpy.props.FloatProperty(name="Cloud Scale", default=1.01, min=1.0001)
    cloud_displacement_strength: bpy.props.FloatProperty(name="Cloud Displacement", default=0.005, min=0.0)
    cloud_sss_scale: bpy.props.FloatProperty(name="Cloud SSS Scale", default=0.7, min=0.0)
    cloud_sss_color: bpy.props.FloatVectorProperty(name="Cloud SSS Color", subtype='COLOR', default=(1.0,1.0,1.0), size=3)
    cloud_disp_scale: bpy.props.FloatProperty(name="Cloud Disp Scale", description="Scale of displacement node in cloud material", default=1.0, min=0.0)
    # Cloud texture file name (optional override)
    cloud_texture_name: bpy.props.StringProperty(name="Cloud Texture Name", description="Filename of cloud texture within assets or absolute path", default="earth_clouds_8K.tif")

    # Globe Features - Ice Caps
    use_ice_caps: bpy.props.BoolProperty(
        name="Use Ice Caps",
        description="Enable procedural ice caps at the poles of the globe",
        default=False,
        update=_trigger_live_update,
    )
    ice_cap_north_extent: bpy.props.FloatProperty(
        name="North Ice Cap Extent",
        description="Latitude extent of the north ice cap (0.0 to 1.0, where 1.0 is full pole coverage)",
        default=0.15, min=0.0, max=1.0,
        subtype='PERCENTAGE',
        update=_trigger_live_update,
    )
    ice_cap_south_extent: bpy.props.FloatProperty(
        name="South Ice Cap Extent",
        description="Latitude extent of the south ice cap (0.0 to 1.0, where 1.0 is full pole coverage)",
        default=0.15, min=0.0, max=1.0,
        subtype='PERCENTAGE',
        update=_trigger_live_update,
    )
    ice_cap_material_icesmoothness: bpy.props.FloatProperty(
        name="Ice Smoothness",
        description="Smoothness (inverse of roughness) for the ice cap material",
        default=0.9, min=0.0, max=1.0,
        update=_trigger_live_update,
    )
    ice_cap_color: bpy.props.FloatVectorProperty(
        name="Ice Cap Color",
        subtype='COLOR',
        default=(0.95, 0.98, 1.0),
        min=0.0, max=1.0,
        size=3,
        description="Color of the ice caps",
        update=_trigger_live_update,
    )

class KilroyPanel(bpy.types.Panel):
    bl_label = "Gaea2Blender Controls"
    bl_idname = "VIEW3D_PT_kilroy_gaea2blender"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Gaea2Blender' # This will be the tab name in the N-panel

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.kilroy_props # Assuming 'kilroy_props' is registered on the scene

        layout.label(text="Kilroy's Gaea to Blender")
        layout.separator()

        # Render Mode
        layout.prop(props, "render_mode", expand=True)
        layout.separator()

        # Common Image Inputs
        box_images = layout.box()
        box_images.label(text="Image Inputs:")
        box_images.prop(props, "start_tile_file", text="Heightmap")
        box_images.prop(props, "texture_file", text="Color/Texture")
        box_images.prop(props, "roughness_file", text="Roughness")
        box_images.prop(props, "normal_file", text="Normal Map")
        
        layout.separator()

        # Material & Geometry
        box_material_geom = layout.box()
        box_material_geom.label(text="Material & Geometry:")
        box_material_geom.prop(props, "displacement_strength")
        box_material_geom.prop(props, "subdivision_levels")
        box_material_geom.prop(props, "invert_roughness_map")
        
        if props.render_mode == 'GLOBE':
            layout.separator()
            box_globe = layout.box()
            box_globe.label(text="Globe Specifics:")
            box_globe.prop(props, "globe_radius")
            box_globe.prop(props, "sphere_resolution_segments", text="Segments")
            box_globe.prop(props, "sphere_resolution_rings", text="Rings")
            
            layout.separator()
            box_globe_features = layout.box()
            box_globe_features.label(text="Globe Features:")
            box_globe_features.prop(props, "generate_atmosphere")
            if props.generate_atmosphere:
                sub = box_globe_features.box()
                sub.prop(props, "atmosphere_density")
                sub.prop(props, "atmosphere_color")
                sub.prop(props, "atmosphere_scale_offset", text="Scale")

            box_globe_features.prop(props, "generate_clouds")
            if props.generate_clouds:
                sub = box_globe_features.box()
                sub.prop(props, "cloud_texture_name", text="Cloud Map")
                sub.prop(props, "cloud_scale_offset", text="Scale")
                sub.prop(props, "cloud_displacement_strength", text="Mesh Displacement")
                sub.prop(props, "cloud_disp_scale", text="Shader Displacement")
                sub.prop(props, "cloud_sss_color", text="SSS Color")
                sub.prop(props, "cloud_sss_scale", text="SSS Scale")

            box_globe_features.prop(props, "use_ice_caps")
            if props.use_ice_caps:
                sub = box_globe_features.box()
                sub.prop(props, "ice_cap_north_extent", text="North Extent")
                sub.prop(props, "ice_cap_south_extent", text="South Extent")
                sub.prop(props, "ice_cap_color", text="Ice Color")
                sub.prop(props, "ice_cap_material_icesmoothness", text="Ice Smoothness")

            layout.separator()
            box_uv = layout.box()
            box_uv.label(text="Globe UV Mapping:")
            box_uv.prop(props, "maintain_aspect_ratio")
            box_uv.prop(props, "polar_padding_top", text="Padding Top")
            box_uv.prop(props, "polar_padding_bottom", text="Padding Bottom")
            box_uv.prop(props, "texture_extension_mode", text="Extension")

        elif props.render_mode == 'LANDSCAPE':
            layout.separator()
            box_landscape = layout.box()
            box_landscape.label(text="Landscape Tiling:")
            box_landscape.prop(props, "use_tiles")
            if props.use_tiles:
                row = box_landscape.row()
                row.prop(props, "num_rows")
                row.prop(props, "num_cols")
            
            # Placeholder for STL related props if you want them in this main panel
            # box_stl = layout.box()
            # box_stl.label(text="STL Export (Landscape):")
            # box_stl.prop(props, "tile_thickness")
            # box_stl.prop(props, "output_dir")


        layout.separator()
        layout.prop(props, "auto_update")

# It's assumed that registration and unregistration of KilroyProperties 
# and KilroyPanel are handled in your __init__.py or main addon file.
# For example:
# bpy.utils.register_class(KilroyProperties)
# bpy.types.Scene.kilroy_props = bpy.props.PointerProperty(type=KilroyProperties)
# bpy.utils.register_class(KilroyPanel)
#
# And in unregister:
# bpy.utils.unregister_class(KilroyPanel)
# del bpy.types.Scene.kilroy_props
# bpy.utils.unregister_class(KilroyProperties) 