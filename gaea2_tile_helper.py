bl_info = {
    "name": "Tile Generator Add-on",
    "blender": (2, 80, 0),
    "category": "Object",
    "description": "Generate 3D tiles for rendering or STL output with heightmaps, textures, and roughness maps",
    "author": "Your Name",
    "version": (1, 0, 0),
    "location": "View3D > Tool Shelf > Tile Generator",
    "wiki_url": "",
    "tracker_url": "",
    "support": "COMMUNITY",
}

import bpy
import os
import re


class TileGeneratorProperties(bpy.types.PropertyGroup):
    # Common Options
    num_rows: bpy.props.IntProperty(
        name="Rows",
        default=4,
        min=1,
        description="Number of rows in the tile grid. Set to 1 for a single heightmap."
    )
    num_cols: bpy.props.IntProperty(
        name="Columns",
        default=4,
        min=1,
        description="Number of columns in the tile grid. Set to 1 for a single heightmap."
    )
    displacement_strength: bpy.props.FloatProperty(
        name="Displacement Strength",
        default=1.0,
        description="Strength of the displacement applied to the plane based on the heightmap."
    )
    subdivision_levels: bpy.props.IntProperty(
        name="Subdivision Levels",
        default=3,
        min=0,
        description="Number of subdivision levels for the plane's geometry."
    )
    start_tile_file: bpy.props.StringProperty(
        name="Heightmap File",
        subtype='FILE_PATH',
        description="Path to the starting heightmap file."
    )

    # STL Workflow Options
    tile_thickness: bpy.props.FloatProperty(
        name="Tile Thickness",
        default=1.0,
        min=0.1,
        description="Thickness of the extruded STL tiles."
    )
    output_dir: bpy.props.StringProperty(
        name="Output Directory",
        subtype='DIR_PATH',
        description="Directory where STL files will be exported."
    )

    # Render Workflow Options
    texture_file: bpy.props.StringProperty(
        name="Texture File",
        subtype='FILE_PATH',
        description="Pick the first file in the set of texture tiles to match the heightmap tiles."
    )
    roughness_file: bpy.props.StringProperty(
        name="Roughness File",
        subtype='FILE_PATH',
        description="Pick the first file in the set of roughness tiles to match the heightmap tiles."
    )
    invert_roughness_map: bpy.props.BoolProperty(
        name="Invert Roughness Map",
        default=False,
        description="Invert the roughness map for each tile."
    )


def generate_texture_or_roughness_path(context, file_path, row, col):
    if not file_path:
        return None

    base_dir, start_filename = os.path.split(file_path)
    filename, ext = os.path.splitext(start_filename)

    match = re.search(r'_y(\d+)_x(\d+)', filename)
    if not match:
        return None

    prefix = filename[:match.start()]
    start_y = int(match.group(1))
    start_x = int(match.group(2))

    y = start_y + row
    x = start_x + col

    tile_filename = f"{prefix}_y{y}_x{x}{ext}"
    file_path = os.path.join(base_dir, tile_filename)

    return file_path


def prepare_plane(subdivisions, tile_thickness):
    bpy.ops.mesh.primitive_plane_add(size=1, enter_editmode=False, align='WORLD', location=(0, 0, tile_thickness))
    plane = bpy.context.object
    bpy.ops.transform.resize(value=(10, 10, 10))

    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.subdivide(number_cuts=subdivisions)
    bpy.ops.object.mode_set(mode='OBJECT')

    bpy.ops.object.select_all(action='DESELECT')
    plane.select_set(True)
    bpy.context.view_layer.objects.active = plane
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

    return plane


def assign_material(context, plane, row, col, texture_path, roughness_path, invert_roughness_map):
    material = bpy.data.materials.new(name=f"Material_{row}_{col}")
    material.use_nodes = True
    bsdf = material.node_tree.nodes.get("Principled BSDF")

    if not bsdf:
        bsdf = material.node_tree.nodes.new(type='ShaderNodeBsdfPrincipled')

    if texture_path:
        try:
            texture_img = bpy.data.images.load(texture_path)
            tex_image_node = material.node_tree.nodes.new('ShaderNodeTexImage')
            tex_image_node.image = texture_img
            material.node_tree.links.new(bsdf.inputs['Base Color'], tex_image_node.outputs['Color'])
        except RuntimeError:
            pass

    if roughness_path:
        try:
            roughness_img = bpy.data.images.load(roughness_path)
            roughness_image_node = material.node_tree.nodes.new('ShaderNodeTexImage')
            roughness_image_node.image = roughness_img

            if invert_roughness_map:
                invert_node = material.node_tree.nodes.new('ShaderNodeInvert')
                material.node_tree.links.new(invert_node.inputs['Color'], roughness_image_node.outputs['Color'])
                material.node_tree.links.new(bsdf.inputs['Roughness'], invert_node.outputs['Color'])
            else:
                material.node_tree.links.new(bsdf.inputs['Roughness'], roughness_image_node.outputs['Color'])
        except RuntimeError:
            pass

    if plane.data.materials:
        plane.data.materials[0] = material
    else:
        plane.data.materials.append(material)


def generate_heightmap_path(context, row, col):
    props = context.scene.tile_generator_props

    base_dir, start_filename = os.path.split(props.start_tile_file)
    filename, ext = os.path.splitext(start_filename)

    match = re.search(r'_y(\d+)_x(\d+)', filename)
    if not match:
        return None

    prefix = filename[:match.start()]
    start_y = int(match.group(1))
    start_x = int(match.group(2))

    y = start_y + row
    x = start_x + col

    tile_filename = f"{prefix}_y{y}_x{x}{ext}"
    heightmap_path = os.path.join(base_dir, tile_filename)

    return heightmap_path


def generate_texture_paths(context, row, col):
    props = context.scene.tile_generator_props

    heightmap_path = generate_heightmap_path(context, row, col)
    texture_path = generate_texture_or_roughness_path(context, props.texture_file, row, col)
    roughness_path = generate_texture_or_roughness_path(context, props.roughness_file, row, col)

    return heightmap_path, texture_path, roughness_path


def apply_displacement(plane, heightmap_img, displacement_strength, subdivision_levels, apply_modifiers=False):
    # Add the Subsurf modifier
    mod_subsurf = plane.modifiers.new("Subsurf", 'SUBSURF')
    mod_subsurf.levels = subdivision_levels
    mod_subsurf.render_levels = subdivision_levels
    mod_subsurf.subdivision_type = 'SIMPLE'

    # Add the Displace modifier
    mod_displace = plane.modifiers.new("Displace", 'DISPLACE')
    mod_displace.mid_level = 0
    mod_displace.texture = bpy.data.textures.new(name="HeightmapTexture", type='IMAGE')
    mod_displace.texture.image = heightmap_img
    mod_displace.texture_coords = 'UV'
    mod_displace.strength = displacement_strength
    mod_displace.texture.extension = 'EXTEND'

    # Apply modifiers only if we're in the STL workflow
    if apply_modifiers:
        bpy.ops.object.modifier_apply(modifier=mod_subsurf.name)
        bpy.ops.object.modifier_apply(modifier=mod_displace.name)


class OBJECT_OT_generate_render_tiles(bpy.types.Operator):
    bl_idname = "object.generate_render_tiles"
    bl_label = "Generate Render Tiles"
    bl_description = "Generate tiles for rendering with textures and roughness maps"

    def execute(self, context):
        props = context.scene.tile_generator_props
        single_heightmap = props.num_rows == 1 and props.num_cols == 1

        for row in range(props.num_rows):
            for col in range(props.num_cols):
                result = self.generate_tile_for_render(context, row=row, col=col, single_heightmap=single_heightmap)
                if result == {'CANCELLED'}:
                    return result

        return {'FINISHED'}

    def generate_tile_for_render(self, context, row=0, col=0, single_heightmap=False):
        props = context.scene.tile_generator_props
        subdivisions = 100  # Fixed subdivisions

        if single_heightmap:
            heightmap_path = props.start_tile_file
            texture_path = props.texture_file
            roughness_path = props.roughness_file
        else:
            heightmap_path, texture_path, roughness_path = generate_texture_paths(context, row, col)
            if not heightmap_path:
                return {'CANCELLED'}

        try:
            heightmap_img = bpy.data.images.load(heightmap_path)
        except RuntimeError:
            return {'CANCELLED'}

        plane = prepare_plane(subdivisions, tile_thickness=0)

        # Apply displacement without applying the modifiers (keep for render workflow)
        apply_displacement(plane, heightmap_img, props.displacement_strength, props.subdivision_levels, apply_modifiers=False)

        # Assign textures and materials if they exist
        assign_material(context, plane, row, col, texture_path, roughness_path, props.invert_roughness_map)

        # Translate the tiles to the correct location for rendering
        plane.location.x = col * 10
        plane.location.y = -row * 10

        # Leave the plane in the scene for rendering
        plane.select_set(True)
        bpy.context.view_layer.objects.active = plane

        return {'FINISHED'}


class OBJECT_OT_generate_stl_tiles(bpy.types.Operator):
    bl_idname = "object.generate_stl_tiles"
    bl_label = "Generate STL Tiles"
    bl_description = "Generate STL tiles based on the provided heightmaps"

    def execute(self, context):
        props = context.scene.tile_generator_props
        single_heightmap = props.num_rows == 1 and props.num_cols == 1

        for row in range(props.num_rows):
            for col in range(props.num_cols):
                result = self.generate_tile_for_stl(context, row=row, col=col, single_heightmap=single_heightmap)
                if result == {'CANCELLED'}:
                    return result

        return {'FINISHED'}

    def generate_tile_for_stl(self, context, row=0, col=0, single_heightmap=False):
        props = context.scene.tile_generator_props
        subdivisions = 100  # Fixed subdivisions

        if single_heightmap:
            heightmap_path = props.start_tile_file
        else:
            heightmap_path = generate_heightmap_path(context, row, col)
            if not heightmap_path:
                return {'CANCELLED'}

        try:
            heightmap_img = bpy.data.images.load(heightmap_path)
        except RuntimeError:
            return {'CANCELLED'}

        plane = prepare_plane(subdivisions, tile_thickness=props.tile_thickness)

        # Apply displacement and modifiers in STL workflow (apply modifiers here)
        apply_displacement(plane, heightmap_img, props.displacement_strength, props.subdivision_levels, apply_modifiers=True)

        # Apply transforms to ensure global coordinates are used
        bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

        # Extrude for STL
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value": (0, 0, -props.tile_thickness * 2)})
        bpy.ops.object.mode_set(mode='OBJECT')

        # Flatten the base of the tile using global coordinates
        bpy.ops.object.transform_apply(location=True)  # Ensure transformations are applied
        for vertex in plane.data.vertices:
            if vertex.co.z < 0:
                vertex.co.z = 0

        # Normalize (Recalculate) normals to ensure they are consistent
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode='OBJECT')

        # Export the STL with a scale factor of 10
        output_filename = os.path.splitext(os.path.basename(heightmap_path))[0] + ".stl"
        export_path = os.path.join(props.output_dir, output_filename)
        bpy.ops.object.select_all(action='DESELECT')
        plane.select_set(True)
        bpy.context.view_layer.objects.active = plane

        # Apply scale on export
        bpy.ops.wm.stl_export(filepath=export_path, apply_modifiers=True, export_selected_objects=True, global_scale=10)

        # Remove the plane after export
        bpy.ops.object.delete()

        return {'FINISHED'}


class VIEW3D_PT_tile_generator(bpy.types.Panel):
    bl_label = "Tile Generator"
    bl_idname = "VIEW3D_PT_tile_generator"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Tile Generator'

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        props = scene.tile_generator_props

        layout.label(text="Common Options")
        layout.prop(props, "num_rows")
        layout.prop(props, "num_cols")
        layout.prop(props, "displacement_strength")
        layout.prop(props, "subdivision_levels")
        layout.prop(props, "start_tile_file")

        layout.separator()
        layout.label(text="STL Workflow", icon="MODIFIER")
        box_stl = layout.box()
        box_stl.prop(props, "tile_thickness")
        box_stl.prop(props, "output_dir")
        box_stl.operator("object.generate_stl_tiles", text="Generate STL Tiles")

        layout.separator()
        layout.label(text="Render Workflow", icon="RENDER_STILL")
        box_render = layout.box()
        box_render.prop(props, "texture_file")
        box_render.prop(props, "roughness_file")
        box_render.prop(props, "invert_roughness_map")
        box_render.operator("object.generate_render_tiles", text="Generate Render Tiles")


def register():
    bpy.utils.register_class(TileGeneratorProperties)
    bpy.utils.register_class(OBJECT_OT_generate_stl_tiles)
    bpy.utils.register_class(OBJECT_OT_generate_render_tiles)
    bpy.utils.register_class(VIEW3D_PT_tile_generator)
    bpy.types.Scene.tile_generator_props = bpy.props.PointerProperty(type=TileGeneratorProperties)


def unregister():
    bpy.utils.unregister_class(TileGeneratorProperties)
    bpy.utils.unregister_class(OBJECT_OT_generate_stl_tiles)
    bpy.utils.unregister_class(OBJECT_OT_generate_render_tiles)
    bpy.utils.unregister_class(VIEW3D_PT_tile_generator)
    del bpy.types.Scene.tile_generator_props


if __name__ == "__main__":
    register()
