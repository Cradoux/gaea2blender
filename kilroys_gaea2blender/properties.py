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
        default=0.0, min=0.0, max=0.49,
        description="Push texture down from the north pole to reduce polar stretching",
        update=_trigger_live_update,
    )
    polar_padding_bottom: bpy.props.FloatProperty(
        name="Polar Padding Bottom",
        subtype='PERCENTAGE', unit='NONE', precision=2,
        default=0.0, min=0.0, max=0.49,
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