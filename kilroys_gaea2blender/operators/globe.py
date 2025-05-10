import bpy, os
from ..utils import (
    GLOBE_COLLECTION_NAME,
    ensure_collection,
    assign_material,
    apply_displacement,
    _load_image_cached,
    _setup_texture_mapping_nodes,
)


class KILROY_OT_generate_globe(bpy.types.Operator):
    """Generate or refresh a globe sphere using current images"""
    bl_idname = "object.kilroy_generate_globe"
    bl_label = "Generate Globe"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        props = context.scene.kilroy_props

        if not props.start_tile_file:
            self.report({'WARNING'}, "Please select a heightmap image first.")
            return {'CANCELLED'}

        globe_coll = ensure_collection(context, GLOBE_COLLECTION_NAME)

        # Remove existing objects in collection to avoid duplicates
        for obj in list(globe_coll.objects):
            bpy.data.objects.remove(obj, do_unlink=True)

        # Create the sphere
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=props.sphere_resolution_segments,
            ring_count=props.sphere_resolution_rings,
            radius=props.globe_radius,
            align='WORLD',
            location=(0, 0, 0),
        )
        globe = context.active_object
        globe.name = "GeneratedGlobe"
        bpy.ops.object.shade_smooth()

        # Move exclusively to collection
        for coll in globe.users_collection:
            if coll != globe_coll:
                coll.objects.unlink(globe)
        if globe.name not in globe_coll.objects:
            globe_coll.objects.link(globe)
        if globe.name in context.scene.collection.objects:
            context.scene.collection.objects.unlink(globe)

        # Load heightmap image
        heightmap_img = _load_image_cached(props.start_tile_file)
        if heightmap_img and hasattr(heightmap_img, 'colorspace_settings'):
            heightmap_img.colorspace_settings.name = 'Non-Color'

        # Add modifiers
        if props.subdivision_levels > 0:
            sub = globe.modifiers.new("GlobeSubsurf", 'SUBSURF')
            sub.levels = props.subdivision_levels
            sub.render_levels = props.subdivision_levels
        if heightmap_img:
            apply_displacement(
                globe,
                heightmap_img,
                props.displacement_strength,
                props.subdivision_levels,
                apply_modifiers=False,
                modifier_prefix="Globe",
            )

        # Material
        assign_material(
            context,
            globe,
            0,
            0,
            props.texture_file,
            props.roughness_file,
            props.normal_file,
            props.invert_roughness_map,
        )

        # ---------------- Atmosphere ----------------
        if props.generate_atmosphere:
            bpy.ops.object.select_all(action='DESELECT')
            globe.select_set(True)
            context.view_layer.objects.active = globe
            bpy.ops.object.duplicate(linked=False)
            atmo = context.active_object
            atmo.name = "GeneratedAtmosphere"
            for m in list(atmo.modifiers):
                atmo.modifiers.remove(m)
            atmo.scale = (props.atmosphere_scale_offset,) * 3
            bpy.ops.object.transform_apply(scale=True)

            mat_atmo = bpy.data.materials.new("AtmosphereMaterial")
            mat_atmo.use_nodes = True
            nodes = mat_atmo.node_tree.nodes
            links = mat_atmo.node_tree.links
            for n in nodes:
                nodes.remove(n)
            out = nodes.new('ShaderNodeOutputMaterial')
            scatter = nodes.new('ShaderNodeVolumeScatter')
            scatter.inputs['Color'].default_value = (*props.atmosphere_color, 1)
            scatter.inputs['Density'].default_value = props.atmosphere_density
            links.new(scatter.outputs['Volume'], out.inputs['Volume'])
            if atmo.data.materials:
                atmo.data.materials[0] = mat_atmo
            else:
                atmo.data.materials.append(mat_atmo)
            if atmo.name not in globe_coll.objects:
                globe_coll.objects.link(atmo)
            if atmo.name in context.scene.collection.objects:
                context.scene.collection.objects.unlink(atmo)

        # ---------------- Clouds ----------------
        if props.generate_clouds:
            bpy.ops.object.select_all(action='DESELECT')
            globe.select_set(True)
            context.view_layer.objects.active = globe
            bpy.ops.object.duplicate(linked=False)
            clouds = context.active_object
            clouds.name = "GeneratedClouds"
            for m in list(clouds.modifiers):
                clouds.modifiers.remove(m)
            clouds.scale = (props.cloud_scale_offset,) * 3
            bpy.ops.object.transform_apply(scale=True)

            # Try to locate cloud texture relative to add-on or blend file
            addon_dir = os.path.dirname(os.path.abspath(__file__))
            addon_root = os.path.dirname(addon_dir)
            potential_paths = []

            cloud_filename = props.cloud_texture_name.strip()
            if cloud_filename:
                # Prefer explicit filename over defaults
                # Absolute path first
                if os.path.isabs(cloud_filename):
                    potential_paths.append(cloud_filename)
                # assets folder inside addon
                potential_paths.append(os.path.join(addon_root, 'assets', cloud_filename))
                # addon root
                potential_paths.append(os.path.join(addon_root, cloud_filename))
                # blend file dir
                if bpy.data.filepath:
                    potential_paths.append(os.path.join(os.path.dirname(bpy.data.filepath), cloud_filename))
            # Always add fallback default names
            potential_paths.extend([
                os.path.join(addon_root, 'assets', 'earth_clouds_8K.tif'),
                os.path.join(addon_root, 'assets', 'earth_clouds.png'),
            ])
            cloud_img = None
            for p in potential_paths:
                if os.path.exists(p):
                    cloud_img = _load_image_cached(p)
                    if cloud_img:
                        if hasattr(cloud_img, 'colorspace_settings'):
                            cloud_img.colorspace_settings.name = 'Non-Color'
                        break

            # Material for clouds
            cloud_mat = bpy.data.materials.new("CloudMaterial")
            cloud_mat.use_nodes = True
            # Ensure Cycles uses displacement and bump
            if hasattr(cloud_mat, "cycles"):
                cloud_mat.cycles.displacement_method = 'BOTH'
            n = cloud_mat.node_tree.nodes
            l = cloud_mat.node_tree.links
            for nd in list(n):
                n.remove(nd)
            out = n.new('ShaderNodeOutputMaterial')
            mix = n.new('ShaderNodeMixShader')
            trans = n.new('ShaderNodeBsdfTransparent')
            sss = n.new('ShaderNodeSubsurfaceScattering')
            sss.inputs['Color'].default_value = (*props.cloud_sss_color, 1)
            sss.inputs['Scale'].default_value = props.cloud_sss_scale
            sss.inputs['Radius'].default_value = (1.0,1.0,1.0)
            l.new(trans.outputs['BSDF'], mix.inputs[1])
            l.new(sss.outputs['BSSRDF'], mix.inputs[2])
            l.new(mix.outputs['Shader'], out.inputs['Surface'])
            if cloud_img:
                uv_socket = _setup_texture_mapping_nodes(cloud_mat.node_tree, cloud_img, props)

                tex = n.new('ShaderNodeTexImage')
                tex.image = cloud_img
                tex.interpolation = 'Linear'
                tex.extension = props.texture_extension_mode
                l.new(uv_socket, tex.inputs['Vector'])

                # Use COLOR output for factor regardless of alpha channel
                l.new(tex.outputs['Color'], mix.inputs['Fac'])

                # Displacement node
                disp_node = n.new('ShaderNodeDisplacement')
                disp_node.inputs['Scale'].default_value = props.cloud_disp_scale
                l.new(tex.outputs['Color'], disp_node.inputs['Height'])
                l.new(disp_node.outputs['Displacement'], out.inputs['Displacement'])
            else:
                mix.inputs['Fac'].default_value = 0.0

            # Optional geometry displacement modifier on cloud mesh
            if cloud_img and props.cloud_displacement_strength > 0.0:
                disp_mod = clouds.modifiers.new('CloudDisplace', 'DISPLACE')
                texd = bpy.data.textures.new('CloudDispTex', 'IMAGE')
                texd.image = cloud_img
                disp_mod.texture = texd
                disp_mod.texture_coords = 'UV'
                disp_mod.strength = props.cloud_displacement_strength

            # Replace any existing materials on the cloud mesh with the new cloud material
            clouds.data.materials.clear()
            clouds.data.materials.append(cloud_mat)

            if clouds.name not in globe_coll.objects:
                globe_coll.objects.link(clouds)
            if clouds.name in context.scene.collection.objects:
                context.scene.collection.objects.unlink(clouds)

        self.report({'INFO'}, "Globe generated")
        return {'FINISHED'}


classes = [KILROY_OT_generate_globe] 