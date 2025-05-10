import bpy
# utils import may be useful for collection constants in future but currently unused

class MainPanel(bpy.types.Panel):
    bl_label = "Gaea2Blender"
    bl_idname = "VIEW3D_PT_gaea2blender_main"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Gaea2Blender'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.kilroy_props

        # Render mode switch
        layout.prop(props, "render_mode", expand=True)

        # Common file section
        col = layout.column(align=True)
        col.label(text="Source Images:")
        col.prop(props, "start_tile_file")
        col.prop(props, "texture_file")
        col.prop(props, "roughness_file")
        col.prop(props, "normal_file")

        # Landscape-specific settings
        if props.render_mode == 'LANDSCAPE':
            box = layout.box()
            box.label(text="Landscape Tiling:")
            box.prop(props, "use_tiles", text="Tiled Input")
            if props.use_tiles:
                row = box.row(align=True)
                row.prop(props, "num_rows")
                row.prop(props, "num_cols")

            box = layout.box()
            box.label(text="STL Export:")
            box.prop(props, "tile_thickness")
            box.prop(props, "output_dir")

            # Operators
            layout.operator("object.kilroy_generate_landscape", text="Generate Landscape")
            layout.operator("object.kilroy_refresh_landscape", text="Refresh Landscape")
            layout.operator("object.kilroy_export_stl_tiles", text="Export STL Tiles")

        # Globe-specific settings
        else:
            box = layout.box()
            box.label(text="Globe Geometry:")
            row = box.row(align=True)
            row.prop(props, "sphere_resolution_segments", text="Segments")
            row.prop(props, "sphere_resolution_rings", text="Rings")
            box.prop(props, "globe_radius")

            box = layout.box()
            box.label(text="Atmosphere:")
            box.prop(props, "generate_atmosphere")
            if props.generate_atmosphere:
                box.prop(props, "atmosphere_density")
                box.prop(props, "atmosphere_color")
                box.prop(props, "atmosphere_scale_offset")

            box = layout.box()
            box.label(text="Clouds:")
            box.prop(props, "generate_clouds")
            if props.generate_clouds:
                box.prop(props, "cloud_scale_offset")
                box.prop(props, "cloud_displacement_strength")
                box.prop(props, "cloud_disp_scale", text="Material Disp Scale")
                box.prop(props, "cloud_sss_scale")
                box.prop(props, "cloud_sss_color")
                box.prop(props, "cloud_texture_name", text="Texture File")

            # Operators
            layout.operator("object.kilroy_generate_globe", text="Generate Globe")

        # Geometry adjustments (shared)
        box = layout.box()
        box.label(text="Geometry Tweaks:")
        box.prop(props, "displacement_strength")
        box.prop(props, "subdivision_levels")

        box.prop(props, "invert_roughness_map")
        layout.prop(props, "auto_update")

# register list for __init__
# The ui.__init__ module will import this module first and collect MainPanel 