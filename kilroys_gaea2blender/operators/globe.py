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

    # Define names for the objects
    GLOBE_OBJ_NAME = "GeneratedGlobe"
    ATMOSPHERE_OBJ_NAME = "GeneratedAtmosphere"
    CLOUDS_OBJ_NAME = "GeneratedClouds"
    
    # Define material names
    GLOBE_MAT_NAME = "KilroyGlobeMaterial" # Changed from dynamic
    ATMOSPHERE_MAT_NAME = "KilroyAtmosphereMaterial"
    CLOUDS_MAT_NAME = "KilroyCloudMaterial"


    def execute(self, context):
        props = context.scene.kilroy_props

        if not props.start_tile_file:
            self.report({'WARNING'}, "Please select a heightmap image first.")
            return {'CANCELLED'}

        globe_coll = ensure_collection(context, GLOBE_COLLECTION_NAME)

        # --- Get or Create Main Globe ---
        globe = globe_coll.objects.get(self.GLOBE_OBJ_NAME)
        if globe is None:
            # Create the sphere
            bpy.ops.mesh.primitive_uv_sphere_add(
                segments=props.sphere_resolution_segments,
                ring_count=props.sphere_resolution_rings,
                radius=props.globe_radius,
                align='WORLD',
                location=(0, 0, 0),
            )
            globe = context.active_object
            globe.name = self.GLOBE_OBJ_NAME
            bpy.ops.object.shade_smooth()

            # Move exclusively to collection
            for coll in globe.users_collection:
                if coll != globe_coll:
                    coll.objects.unlink(globe)
            if globe.name not in globe_coll.objects:
                globe_coll.objects.link(globe)
            if globe.name in context.scene.collection.objects: # Should not happen if created fresh
                context.scene.collection.objects.unlink(globe)
            
            # Add modifiers only on creation
            if props.subdivision_levels > 0:
                sub = globe.modifiers.new("GlobeSubsurf", 'SUBSURF')
            # Shader displacement will be handled below / in material update
        else:
            # Object exists, update it
            # For now, radius change requires recreation due to primitive_uv_sphere_add
            # We can update scale if radius is the only factor, but segments/rings are complex.
            # Let's assume segments/rings don't change often for live update.
            # If props.globe_radius is significantly different, consider full recreate or more complex mesh update.
            # For simplicity now, we'll just update scale based on radius
            # A more robust way would be to store original radius and scale factor.
            if globe.dimensions.x != props.globe_radius * 2: # Basic check
                 globe.scale = (props.globe_radius / (globe.dimensions.x / 2), ) * 3 # Approx
                 bpy.ops.object.select_all(action='DESELECT')
                 globe.select_set(True)
                 context.view_layer.objects.active = globe
                 bpy.ops.object.transform_apply(scale=True)


        # Update subdivision modifier
        sub_modifier = globe.modifiers.get("GlobeSubsurf")
        if props.subdivision_levels > 0:
            if not sub_modifier:
                sub_modifier = globe.modifiers.new("GlobeSubsurf", 'SUBSURF')
            sub_modifier.levels = props.subdivision_levels
            sub_modifier.render_levels = props.subdivision_levels
        elif sub_modifier: # levels are 0, remove if exists
            globe.modifiers.remove(sub_modifier)

        # Load heightmap image (always needed for material and displacement)
        heightmap_img = _load_image_cached(props.start_tile_file)
        if heightmap_img and hasattr(heightmap_img, 'colorspace_settings'):
            heightmap_img.colorspace_settings.name = 'Non-Color'

        # --- Globe Material ---
        # assign_material will be modified to get or create nodes
        assign_material(
            context,
            globe,
            0, # row/col not relevant for globe single material
            0,
            props.texture_file,
            props.roughness_file,
            props.normal_file,
            props.invert_roughness_map,
            material_name_override=self.GLOBE_MAT_NAME 
        )

        # --- Shader displacement for globe surface ---
        if heightmap_img and globe.data.materials and globe.data.materials[0]:
            mat = globe.data.materials[0]
            nt = mat.node_tree
            nodes = nt.nodes
            links = nt.links
            
            output_node = next((n for n in nodes if n.type == 'OUTPUT_MATERIAL'), None)
            if output_node: # Ensure output node exists
                disp_node = None
                # Try to find existing displacement node by name or type
                if "KilroyGlobeDisplacement" in nodes:
                    disp_node = nodes["KilroyGlobeDisplacement"]
                else:
                    # Find by link to output (less reliable if multiple displacements)
                    for link in output_node.inputs['Displacement'].links:
                        if link.from_node.type == 'DISPLACEMENT':
                            disp_node = link.from_node
                            disp_node.name = "KilroyGlobeDisplacement" # Name it for future
                            break
                
                tex_height_node = None
                # Try to find existing heightmap texture node by name or image
                if "KilroyHeightmapTexture" in nodes:
                    tex_height_node = nodes["KilroyHeightmapTexture"]
                    if tex_height_node.image != heightmap_img: # Image changed
                        tex_height_node.image = heightmap_img
                else:
                    # Find by image if name not set (e.g. from older version)
                    for node in nodes:
                        if isinstance(node, bpy.types.ShaderNodeTexImage) and node.image == heightmap_img and "Height" in [l.to_socket.name for l in node.outputs['Color'].links]:
                             tex_height_node = node
                             tex_height_node.name = "KilroyHeightmapTexture" # Name it
                             break
                
                if tex_height_node is None and heightmap_img : # Create if not found
                    uv_socket = _setup_texture_mapping_nodes(nt, heightmap_img, props, base_node_name=self.GLOBE_MAT_NAME)
                    tex_height_node = nodes.new('ShaderNodeTexImage')
                    tex_height_node.name = "KilroyHeightmapTexture"
                    tex_height_node.image = heightmap_img
                    if hasattr(heightmap_img, 'colorspace_settings'): # Should be set already but double check
                        heightmap_img.colorspace_settings.name = 'Non-Color'
                    tex_height_node.interpolation = 'Linear'
                    tex_height_node.extension = props.texture_extension_mode
                    links.new(uv_socket, tex_height_node.inputs['Vector'])

                if disp_node is None and output_node: # Create displacement node if not found
                    disp_node = nodes.new('ShaderNodeDisplacement')
                    disp_node.name = "KilroyGlobeDisplacement"
                    links.new(disp_node.outputs['Displacement'], output_node.inputs['Displacement'])
                
                if disp_node:
                    disp_node.inputs['Scale'].default_value = props.displacement_strength
                    if tex_height_node: # Link height texture to displacement
                        # Clear existing link to height if any
                        for link in list(disp_node.inputs['Height'].links):
                            links.remove(link)
                        links.new(tex_height_node.outputs['Color'], disp_node.inputs['Height'])
                    elif not heightmap_img: # No heightmap, disconnect or set scale to 0
                         disp_node.inputs['Scale'].default_value = 0.0

                # Mix ice heightmap if enabled
                if props.use_ice_caps:
                    ice_hm_path = None
                    addon_dir = os.path.dirname(os.path.abspath(__file__))
                    addon_root = os.path.dirname(addon_dir)
                    for p in [os.path.join(addon_root, 'assets', 'ice_hm.png')]:
                        if os.path.exists(p):
                            ice_hm_path = p
                            break
                    if ice_hm_path:
                        ice_hm_img = _load_image_cached(ice_hm_path)
                        if ice_hm_img:
                            ice_hm_node = nodes.get('IceHMTexture') or nodes.new('ShaderNodeTexImage')
                            ice_hm_node.name = 'IceHMTexture'
                            ice_hm_node.image = ice_hm_img
                            ice_hm_node.interpolation = 'Linear'
                            ice_hm_node.extension = props.texture_extension_mode
                            # link uv
                            if not ice_hm_node.inputs['Vector'].is_linked:
                                links.new(uv_socket, ice_hm_node.inputs['Vector'])
                            mix_hm = nodes.get('IceHeightMix') or nodes.new('ShaderNodeMixRGB')
                            mix_hm.name = 'IceHeightMix'
                            mix_hm.blend_type = 'LIGHTEN'
                            # connect
                            for l in list(mix_hm.inputs['Color1'].links): links.remove(l)
                            links.new(tex_height_node.outputs['Color'], mix_hm.inputs['Color1'])
                            for l in list(mix_hm.inputs['Color2'].links): links.remove(l)
                            links.new(ice_hm_node.outputs['Color'], mix_hm.inputs['Color2'])
                            # link to displacement
                            for l in list(disp_node.inputs['Height'].links): links.remove(l)
                            links.new(mix_hm.outputs['Color'], disp_node.inputs['Height'])

        # --- Ice Caps (color overlay) ---
        if props.use_ice_caps and globe.data.materials:
            ice_colour_path = None
            addon_dir = os.path.dirname(os.path.abspath(__file__))
            addon_root = os.path.dirname(addon_dir)
            for p in [os.path.join(addon_root, 'assets', 'ice_colour.png'),
                      os.path.join(addon_root, 'assets', 'ice_color.png')]:
                if os.path.exists(p):
                    ice_colour_path = p
                    break
            if ice_colour_path:
                ice_img = _load_image_cached(ice_colour_path)
                if ice_img:
                    mat = globe.data.materials[0]
                    nt = mat.node_tree
                    nodes = nt.nodes
                    links = nt.links
                    # existing base color tex node previously named MaterialName_BaseColorTex maybe
                    base_tex_node = nodes.get(f"{self.GLOBE_MAT_NAME}_BaseColorTex")
                    ice_tex_node = nodes.get("IceColourTex")
                    if not ice_tex_node:
                        ice_tex_node = nodes.new('ShaderNodeTexImage')
                        ice_tex_node.name = "IceColourTex"
                        ice_tex_node.image = ice_img
                        ice_tex_node.interpolation = 'Linear'
                        ice_tex_node.extension = props.texture_extension_mode
                        # Use same UV mapping socket as base color
                        if base_tex_node and base_tex_node.inputs['Vector'].is_linked:
                            uv_src = base_tex_node.inputs['Vector'].links[0].from_socket
                            links.new(uv_src, ice_tex_node.inputs['Vector'])
                    # mix node
                    mix_node = nodes.get("IceColourMix")
                    if not mix_node:
                        mix_node = nodes.new('ShaderNodeMixRGB')
                        mix_node.name = "IceColourMix"
                        mix_node.blend_type = 'LIGHTEN'
                        mix_node.location = (-50, 200)
                    # Ensure links: base into Color1, ice into Color2, output to BSDF Base Color
                    if base_tex_node:
                        for link in list(mix_node.inputs['Color1'].links): links.remove(link)
                        links.new(base_tex_node.outputs['Color'], mix_node.inputs['Color1'])
                    for link in list(mix_node.inputs['Color2'].links): links.remove(link)
                    links.new(ice_tex_node.outputs['Color'], mix_node.inputs['Color2'])

                    bsdf = next((n for n in nodes if n.type=='BSDF_PRINCIPLED'), None)
                    if bsdf:
                        for link in list(bsdf.inputs['Base Color'].links): links.remove(link)
                        links.new(mix_node.outputs['Color'], bsdf.inputs['Base Color'])


        # ---------------- Atmosphere ----------------
        atmo = globe_coll.objects.get(self.ATMOSPHERE_OBJ_NAME)
        if props.generate_atmosphere:
            if atmo is None:
                # Duplicate globe for base mesh, then modify
                bpy.ops.object.select_all(action='DESELECT')
                globe.select_set(True)
                context.view_layer.objects.active = globe
                bpy.ops.object.duplicate(linked=False)
                atmo = context.active_object
                atmo.name = self.ATMOSPHERE_OBJ_NAME
                
                for m in list(atmo.modifiers): # Remove all modifiers from duplicated
                    atmo.modifiers.remove(m)
                
                # Link to collection
                if atmo.name not in globe_coll.objects:
                    globe_coll.objects.link(atmo)
                for coll in atmo.users_collection: # Remove from other collections
                    if coll != globe_coll:
                        coll.objects.unlink(atmo)

            # Update scale
            expected_scale = props.atmosphere_scale_offset
            if abs(atmo.scale.x - expected_scale) > 0.0001: # Check if update needed
                atmo.scale = (expected_scale,) * 3
                #bpy.ops.object.transform_apply(scale=True) # Applying scale breaks relative sizing to globe if globe itself is scaled

            # Get or create atmosphere material
            mat_atmo = bpy.data.materials.get(self.ATMOSPHERE_MAT_NAME)
            if mat_atmo is None:
                mat_atmo = bpy.data.materials.new(self.ATMOSPHERE_MAT_NAME)
                mat_atmo.use_nodes = True
                nodes = mat_atmo.node_tree.nodes
                links = mat_atmo.node_tree.links
                for n_rem in list(nodes): nodes.remove(n_rem) # Clear default nodes
                
                output_node = nodes.new('ShaderNodeOutputMaterial')
                scatter_node = nodes.new('ShaderNodeVolumeScatter')
                scatter_node.name = "AtmosphereScatter"
                links.new(scatter_node.outputs['Volume'], output_node.inputs['Volume'])
            
            # Assign material if not already assigned or different
            if not atmo.data.materials or atmo.data.materials[0] != mat_atmo:
                atmo.data.materials.clear()
                atmo.data.materials.append(mat_atmo)

            # Update material parameters
            scatter_node = mat_atmo.node_tree.nodes.get("AtmosphereScatter")
            if scatter_node:
                scatter_node.inputs['Color'].default_value = (*props.atmosphere_color, 1)
                scatter_node.inputs['Density'].default_value = props.atmosphere_density
        
        elif atmo is not None: # Not props.generate_atmosphere but atmo object exists
            bpy.data.objects.remove(atmo, do_unlink=True)
            atmo = None # Clear reference


        # ---------------- Clouds ----------------
        clouds = globe_coll.objects.get(self.CLOUDS_OBJ_NAME)
        if props.generate_clouds:
            # Load cloud texture image
            cloud_img = None
            addon_dir = os.path.dirname(os.path.abspath(__file__))
            addon_root = os.path.dirname(addon_dir) #kilroys_gaea2blender
            potential_paths = []
            cloud_filename = props.cloud_texture_name.strip()

            if cloud_filename:
                if os.path.isabs(cloud_filename): potential_paths.append(cloud_filename)
                potential_paths.append(os.path.join(addon_root, 'assets', cloud_filename))
                potential_paths.append(os.path.join(addon_root, cloud_filename))
                if bpy.data.filepath:
                    potential_paths.append(os.path.join(os.path.dirname(bpy.data.filepath), cloud_filename))
            
            potential_paths.extend([ # Fallbacks
                os.path.join(addon_root, 'assets', 'earth_clouds_8K.tif'),
                os.path.join(addon_root, 'assets', 'earth_clouds.png'),
            ])

            for p in potential_paths:
                if os.path.exists(p):
                    cloud_img = _load_image_cached(p)
                    if cloud_img:
                        if hasattr(cloud_img, 'colorspace_settings'): # Cloud textures are usually color
                            cloud_img.colorspace_settings.name = 'sRGB' if cloud_img.is_float else 'Non-Color' # Non-Color for masks/alpha
                        break
            
            if clouds is None:
                bpy.ops.object.select_all(action='DESELECT')
                globe.select_set(True) # Duplicate from main globe
                context.view_layer.objects.active = globe
                bpy.ops.object.duplicate(linked=False)
                clouds = context.active_object
                clouds.name = self.CLOUDS_OBJ_NAME
                for m in list(clouds.modifiers): clouds.modifiers.remove(m) # Remove all modifiers
                
                # Link to collection
                if clouds.name not in globe_coll.objects:
                    globe_coll.objects.link(clouds)
                for coll in clouds.users_collection:
                    if coll != globe_coll:
                        coll.objects.unlink(coll)
            
            # Update scale
            expected_cloud_scale = props.cloud_scale_offset
            if abs(clouds.scale.x - expected_cloud_scale) > 0.0001:
                clouds.scale = (expected_cloud_scale,) * 3
                #bpy.ops.object.transform_apply(scale=True) # Avoid applying if globe is also scaled relatively

            # Get or create cloud material
            cloud_mat = bpy.data.materials.get(self.CLOUDS_MAT_NAME)
            if cloud_mat is None:
                cloud_mat = bpy.data.materials.new(self.CLOUDS_MAT_NAME)
                cloud_mat.use_nodes = True
                if hasattr(cloud_mat, "cycles"): cloud_mat.cycles.displacement_method = 'BOTH'
                
                nodes = cloud_mat.node_tree.nodes
                links = cloud_mat.node_tree.links
                for n_rem in list(nodes): nodes.remove(n_rem)

                out_node = nodes.new('ShaderNodeOutputMaterial')
                mix_shader = nodes.new('ShaderNodeMixShader')
                mix_shader.name = "CloudMixShader"
                trans_bsdf = nodes.new('ShaderNodeBsdfTransparent')
                trans_bsdf.name = "CloudTransparentBSDF"
                sss_bsdf = nodes.new('ShaderNodeSubsurfaceScattering')
                sss_bsdf.name = "CloudSSS_BSDF"
                
                links.new(trans_bsdf.outputs['BSDF'], mix_shader.inputs[1]) # Check input indices for mix shader based on preference
                links.new(sss_bsdf.outputs['BSSRDF'], mix_shader.inputs[2])
                links.new(mix_shader.outputs['Shader'], out_node.inputs['Surface'])

            if not clouds.data.materials or clouds.data.materials[0] != cloud_mat:
                clouds.data.materials.clear()
                clouds.data.materials.append(cloud_mat)

            # Update cloud material parameters
            nt_cloud = cloud_mat.node_tree
            nodes_cloud = nt_cloud.nodes
            links_cloud = nt_cloud.links
            
            sss_node = nodes_cloud.get("CloudSSS_BSDF")
            if sss_node:
                sss_node.inputs['Color'].default_value = (*props.cloud_sss_color, 1)
                sss_node.inputs['Scale'].default_value = props.cloud_sss_scale
                sss_node.inputs['Radius'].default_value = (1.0,1.0,1.0) # Default or make prop if needed

            mix_shader_node = nodes_cloud.get("CloudMixShader")
            cloud_tex_node = nodes_cloud.get("CloudTextureNode")

            if cloud_img:
                if cloud_tex_node is None:
                    uv_socket = _setup_texture_mapping_nodes(nt_cloud, None, props, base_node_name=f"{self.CLOUDS_MAT_NAME}_CloudTex") # Use generic UV setup for clouds
                    cloud_tex_node = nodes_cloud.new('ShaderNodeTexImage')
                    cloud_tex_node.name = "CloudTextureNode"
                    cloud_tex_node.interpolation = 'Linear' # Or 'Cubic' for smoother clouds
                    cloud_tex_node.extension = props.texture_extension_mode # Use same as globe for consistency
                    links_cloud.new(uv_socket, cloud_tex_node.inputs['Vector'])
                
                if cloud_tex_node.image != cloud_img:
                    cloud_tex_node.image = cloud_img
                
                if mix_shader_node: # Link alpha/color to mix factor
                    for link in list(mix_shader_node.inputs['Fac'].links): links_cloud.remove(link)
                    # Always drive mix factor with the brightness of color data
                    links_cloud.new(cloud_tex_node.outputs['Color'], mix_shader_node.inputs['Fac'])
                
                # Shader-based displacement for clouds (on material output)
                out_node_cloud = nodes_cloud.get('Material Output') or nodes_cloud.get('ShaderNodeOutputMaterial')
                cloud_disp_node = nodes_cloud.get("CloudShaderDisplacement")
                if out_node_cloud:
                    if cloud_disp_node is None:
                        cloud_disp_node = nodes_cloud.new('ShaderNodeDisplacement')
                        cloud_disp_node.name = "CloudShaderDisplacement"
                        links_cloud.new(cloud_disp_node.outputs['Displacement'], out_node_cloud.inputs['Displacement'])
                    
                    cloud_disp_node.inputs['Scale'].default_value = props.cloud_disp_scale # Make sure this prop exists
                    # Link cloud texture (color or alpha) to height
                    for link in list(cloud_disp_node.inputs['Height'].links): links_cloud.remove(link)
                    links_cloud.new(cloud_tex_node.outputs['Color'], cloud_disp_node.inputs['Height'])


            elif cloud_tex_node: # No cloud_img, but node exists - remove it and its links
                nt_cloud.nodes.remove(cloud_tex_node)
                if mix_shader_node: mix_shader_node.inputs['Fac'].default_value = 0.0 # Make fully SSS/transparent depending on setup
            elif mix_shader_node: # No image and no tex node
                 mix_shader_node.inputs['Fac'].default_value = 0.0


            # Optional geometry displacement modifier on cloud mesh
            disp_mod_clouds = clouds.modifiers.get('CloudDisplace')
            if cloud_img and props.cloud_displacement_strength > 0.0:
                if disp_mod_clouds is None:
                    disp_mod_clouds = clouds.modifiers.new('CloudDisplace', 'DISPLACE')
                    # Texture for modifier needs to be a bpy.data.texture, not just image
                    cloud_disp_tex = bpy.data.textures.get("CloudDisplacementTexture")
                    if cloud_disp_tex is None:
                        cloud_disp_tex = bpy.data.textures.new('CloudDisplacementTexture', 'IMAGE')
                    disp_mod_clouds.texture = cloud_disp_tex

                if disp_mod_clouds.texture: # Ensure texture image is set
                     disp_mod_clouds.texture.image = cloud_img
                disp_mod_clouds.texture_coords = 'UV' # Or other if needed
                disp_mod_clouds.strength = props.cloud_displacement_strength
            elif disp_mod_clouds: # Condition to remove/disable modifier
                clouds.modifiers.remove(disp_mod_clouds)
                
        elif clouds is not None: # Not props.generate_clouds but cloud object exists
            bpy.data.objects.remove(clouds, do_unlink=True)
            clouds = None

        # Remove non-specified objects from the collection
        for obj in list(globe_coll.objects):
            is_globe = obj.name == self.GLOBE_OBJ_NAME
            is_atmo = obj.name == self.ATMOSPHERE_OBJ_NAME and props.generate_atmosphere
            is_clouds = obj.name == self.CLOUDS_OBJ_NAME and props.generate_clouds
            if not (is_globe or is_atmo or is_clouds):
                bpy.data.objects.remove(obj, do_unlink=True)


        self.report({'INFO'}, "Globe processed")
        return {'FINISHED'}


classes = [KILROY_OT_generate_globe] 