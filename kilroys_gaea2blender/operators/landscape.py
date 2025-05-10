import bpy, os
from ..utils import (
    TILE_COLLECTION_NAME,
    ensure_collection,
    prepare_plane,
    assign_material,
    apply_displacement,
    generate_texture_paths,
    generate_heightmap_path,
    _load_image_cached,
)


class KILROY_OT_generate_landscape(bpy.types.Operator):
    """Generate tiled planes for rendering workflow"""
    bl_idname = "object.kilroy_generate_landscape"
    bl_label = "Generate Landscape"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.kilroy_props
        rows = props.num_rows if props.use_tiles else 1
        cols = props.num_cols if props.use_tiles else 1
        single_heightmap = not props.use_tiles or (rows == 1 and cols == 1)

        tiles_coll = ensure_collection(context, TILE_COLLECTION_NAME)
        # Clear existing objects
        for obj in list(tiles_coll.objects):
            bpy.data.objects.remove(obj, do_unlink=True)

        for row in range(rows):
            for col in range(cols):
                result = self._generate_tile(context, row, col, single_heightmap)
                if result == {'CANCELLED'}:
                    return result
        self.report({'INFO'}, "Landscape generated")
        return {'FINISHED'}

    def _generate_tile(self, context, row: int, col: int, single_heightmap: bool):
        props = context.scene.kilroy_props

        if single_heightmap:
            heightmap_path = props.start_tile_file
            texture_path = props.texture_file
            roughness_path = props.roughness_file
            normal_path = props.normal_file
        else:
            heightmap_path, texture_path, roughness_path, normal_path = generate_texture_paths(props, row, col)
            if not heightmap_path:
                self.report({'ERROR'}, "Failed to build heightmap path for tile")
                return {'CANCELLED'}

        heightmap_img = _load_image_cached(heightmap_path)
        if not heightmap_img:
            self.report({'ERROR'}, f"Cannot load heightmap: {heightmap_path}")
            return {'CANCELLED'}

        plane = prepare_plane(100, size=10)
        plane["tile_rc"] = (row, col)

        tiles_coll = ensure_collection(context, TILE_COLLECTION_NAME)
        tiles_coll.objects.link(plane)
        if plane.name in context.scene.collection.objects:
            context.scene.collection.objects.unlink(plane)

        apply_displacement(
            plane,
            heightmap_img,
            props.displacement_strength,
            props.subdivision_levels,
            apply_modifiers=False,
        )

        assign_material(
            context,
            plane,
            row,
            col,
            texture_path,
            roughness_path,
            normal_path,
            props.invert_roughness_map,
        )

        # Arrange tiles in grid
        plane.location.x = col * 10
        plane.location.y = -row * 10
        return {'FINISHED'}


class KILROY_OT_refresh_landscape(bpy.types.Operator):
    """Refresh displacement/subsurf or materials on existing tiles"""
    bl_idname = "object.kilroy_refresh_landscape"
    bl_label = "Refresh Landscape"
    bl_options = {"REGISTER", "UNDO"}

    all_tiles: bpy.props.BoolProperty(default=True, options={'HIDDEN'})

    def execute(self, context):
        coll = bpy.data.collections.get(TILE_COLLECTION_NAME)
        if not coll or not coll.objects:
            self.report({'WARNING'}, "No generated tiles found. Generate tiles first.")
            return {'CANCELLED'}
        props = context.scene.kilroy_props

        wm = context.window_manager
        wm.progress_begin(0, len(coll.objects))

        for idx, plane in enumerate(coll.objects):
            wm.progress_update(idx)
            if "tile_rc" not in plane:
                continue
            row, col = plane["tile_rc"]

            rows = props.num_rows if props.use_tiles else 1
            cols = props.num_cols if props.use_tiles else 1
            single_heightmap = not props.use_tiles or (rows == 1 and cols == 1)

            if single_heightmap:
                heightmap_path = props.start_tile_file
                texture_path = props.texture_file
                roughness_path = props.roughness_file
                normal_path = props.normal_file
            else:
                heightmap_path, texture_path, roughness_path, normal_path = generate_texture_paths(props, row, col)

            heightmap_img = _load_image_cached(heightmap_path)
            if not heightmap_img:
                continue

            # Update modifiers
            subsurf = plane.modifiers.get("Subsurf")
            if subsurf:
                subsurf.levels = props.subdivision_levels
                subsurf.render_levels = props.subdivision_levels
            disp = plane.modifiers.get("Displace")
            if disp:
                disp.strength = props.displacement_strength
                if disp.texture is None:
                    tex = bpy.data.textures.new("HeightmapTexture", 'IMAGE')
                    disp.texture = tex
                disp.texture.image = heightmap_img

            assign_material(
                context,
                plane,
                row,
                col,
                texture_path,
                roughness_path,
                normal_path,
                props.invert_roughness_map,
            )

        wm.progress_end()
        self.report({'INFO'}, "Landscape refreshed")
        return {'FINISHED'}


class KILROY_OT_export_stl_tiles(bpy.types.Operator):
    """Generate tiles with modifiers applied and export as STL files"""
    bl_idname = "object.kilroy_export_stl_tiles"
    bl_label = "Export STL Tiles"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.kilroy_props
        rows = props.num_rows if props.use_tiles else 1
        cols = props.num_cols if props.use_tiles else 1
        single_heightmap = not props.use_tiles or (rows == 1 and cols == 1)

        export_dir = props.output_dir or os.path.dirname(props.start_tile_file)
        os.makedirs(export_dir, exist_ok=True)

        for row in range(rows):
            for col in range(cols):
                result = self._generate_tile(context, row, col, single_heightmap, export_dir)
                if result == {'CANCELLED'}:
                    return result
        self.report({'INFO'}, "STL tiles exported")
        return {'FINISHED'}

    def _generate_tile(self, context, row, col, single_heightmap, export_dir):
        props = context.scene.kilroy_props
        if single_heightmap:
            heightmap_path = props.start_tile_file
        else:
            heightmap_path = generate_heightmap_path(props.start_tile_file, row, col)
            if not heightmap_path:
                self.report({'ERROR'}, "Heightmap path missing for STL tile")
                return {'CANCELLED'}

        heightmap_img = _load_image_cached(heightmap_path)
        if not heightmap_img:
            return {'CANCELLED'}

        plane = prepare_plane(100, size=10)
        apply_displacement(
            plane,
            heightmap_img,
            props.displacement_strength,
            props.subdivision_levels,
            apply_modifiers=True,
        )

        # Extrude tile thickness
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.extrude_region_move(TRANSFORM_OT_translate={"value": (0, 0, -props.tile_thickness * 2)})
        bpy.ops.object.mode_set(mode='OBJECT')

        # Flatten bottom
        bpy.ops.object.transform_apply(location=True)
        for v in plane.data.vertices:
            if v.co.z < 0:
                v.co.z = 0

        # Recalculate normals
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.normals_make_consistent(inside=False)
        bpy.ops.object.mode_set(mode='OBJECT')

        # Export STL
        output_filename = f"tile_y{row}_x{col}.stl" if not single_heightmap else "landscape.stl"
        export_path = os.path.join(export_dir, output_filename)
        bpy.ops.object.select_all(action='DESELECT')
        plane.select_set(True)
        context.view_layer.objects.active = plane
        try:
            # Requires the built-in STL addon (io_mesh_stl) to be enabled
            bpy.ops.export_mesh.stl(filepath=export_path, use_selection=True, global_scale=10)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export STL: {e}")
            return {'CANCELLED'}

        bpy.ops.object.delete()
        return {'FINISHED'}


classes = [
    KILROY_OT_generate_landscape,
    KILROY_OT_refresh_landscape,
    KILROY_OT_export_stl_tiles,
] 