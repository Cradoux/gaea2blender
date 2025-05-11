import bpy, os, re

TILE_COLLECTION_NAME = "KilroyLandscape"
GLOBE_COLLECTION_NAME = "KilroyGlobe"

# ---------------- collection helpers ----------------

def get_collection(name):
    return bpy.data.collections.get(name)

def ensure_collection(context, name):
    coll = get_collection(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        context.scene.collection.children.link(coll)
    return coll

# ---------------- live update callbacks -------------

def _trigger_live_update(self, context):
    # Skip if user just toggled render mode; don't auto-generate yet
    prev_mode = getattr(self, "_last_render_mode", None)
    if prev_mode != self.render_mode:
        # update stored mode and exit early (no generation)
        self._last_render_mode = self.render_mode
        return

    if not self.auto_update:
        return
    if self.render_mode == 'LANDSCAPE':
        try:
            bpy.ops.object.kilroy_refresh_landscape(all_tiles=True)
        except Exception:
            pass
    else:
        try:
            bpy.ops.object.kilroy_generate_globe()
        except Exception:
            pass

def _render_mode_changed(self, context):
    """Called only when the render_mode enum changes. Avoid heavy generation here."""
    # store last mode so later updates know
    self._last_render_mode = self.render_mode
    # Nothing else – generation occurs when user explicitly clicks generate/refresh.

def _update_displacement_strength(self, context):
    if not self.auto_update:
        return
    if self.render_mode == 'LANDSCAPE':
        coll = get_collection(TILE_COLLECTION_NAME)
        if not coll:
            return
        for obj in coll.objects:
            mod = obj.modifiers.get("Displace")
            if mod:
                mod.strength = self.displacement_strength
    else:
        coll = get_collection(GLOBE_COLLECTION_NAME)
        if not coll:
            return
        for obj in coll.objects:
            mod = obj.modifiers.get("GlobeDisplace") or obj.modifiers.get("CloudDisplace")
            if mod:
                mod.strength = self.displacement_strength if mod.name=="GlobeDisplace" else self.cloud_displacement_strength


def _update_subdivision_levels(self, context):
    if not self.auto_update:
        return
    if self.render_mode == 'LANDSCAPE':
        coll = get_collection(TILE_COLLECTION_NAME)
        if not coll:
            return
        for obj in coll.objects:
            sub = obj.modifiers.get("Subsurf")
            if sub:
                sub.levels = self.subdivision_levels
                sub.render_levels = self.subdivision_levels
    else:
        coll = get_collection(GLOBE_COLLECTION_NAME)
        if not coll:
            return
        for obj in coll.objects:
            sub = obj.modifiers.get("GlobeSubsurf")
            if sub:
                sub.levels = self.subdivision_levels
                sub.render_levels = self.subdivision_levels

# ---------------- image path helpers ----------------

def generate_texture_or_roughness_path(file_path: str, row: int, col: int):
    """Given the first file in a tiled set, return the matching tile path for the given row/col.
    The filename pattern is expected like *_y0_x0.png ."""
    if not file_path:
        return None

    base_dir, start_filename = os.path.split(file_path)
    filename, ext = os.path.splitext(start_filename)

    match = re.search(r"_y(\d+)_x(\d+)", filename)
    if not match:
        return None

    prefix = filename[:match.start()]
    start_y = int(match.group(1))
    start_x = int(match.group(2))

    y = start_y + row
    x = start_x + col

    tile_filename = f"{prefix}_y{y}_x{x}{ext}"
    return os.path.join(base_dir, tile_filename)


def generate_heightmap_path(start_tile_file: str, row: int, col: int):
    if not start_tile_file:
        return None
    base_dir, start_filename = os.path.split(start_tile_file)
    filename, ext = os.path.splitext(start_filename)
    match = re.search(r"_y(\d+)_x(\d+)", filename)
    if not match:
        return None
    prefix = filename[:match.start()]
    start_y = int(match.group(1))
    start_x = int(match.group(2))
    y = start_y + row
    x = start_x + col
    tile_filename = f"{prefix}_y{y}_x{x}{ext}"
    return os.path.join(base_dir, tile_filename)


def generate_texture_paths(props, row: int, col: int):
    heightmap_path = generate_heightmap_path(props.start_tile_file, row, col)
    texture_path = generate_texture_or_roughness_path(props.texture_file, row, col)
    roughness_path = generate_texture_or_roughness_path(props.roughness_file, row, col)
    normal_path = generate_texture_or_roughness_path(props.normal_file, row, col)
    return heightmap_path, texture_path, roughness_path, normal_path

# ---------------- geometry & material helpers ----------------


def prepare_plane(subdivisions: int, size: float = 10.0):
    bpy.ops.mesh.primitive_plane_add(size=1, enter_editmode=False)
    plane = bpy.context.object
    bpy.ops.transform.resize(value=(size, size, size))
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.subdivide(number_cuts=subdivisions)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.ops.object.transform_apply(scale=True)
    return plane


def _load_image_cached(path: str):
    if not path:
        return None
    img = bpy.data.images.get(path)
    if img is None:
        try:
            img = bpy.data.images.load(path, check_existing=True)
        except Exception:
            img = None
    return img


def assign_material(context, obj, row: int, col: int, texture_path: str, roughness_path: str, normal_path: str, invert_roughness_map: bool, material_name_override: str = None):
    """Create or update a material for obj using provided textures and addon mapping props."""
    props = context.scene.kilroy_props

    if material_name_override:
        mat_name = material_name_override
    else:
        mat_name = f"Material_{obj.name}_{row}_{col}"

    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        mat = bpy.data.materials.new(mat_name)
        # For new materials, ensure it's set for Cycles displacement if that's the intended use
        if hasattr(mat, "cycles") and props.render_mode == 'GLOBE': # Example: Globe uses shader displacement
             mat.cycles.displacement_method = 'DISPLACEMENT' # Or 'BOTH' if bump is also used from displacement texture

    mat.use_nodes = True
    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links

    # --- Ensure Core Nodes ---
    output_node = nodes.get(f"{mat_name}_MaterialOutput") or next((n for n in nodes if n.type == 'OUTPUT_MATERIAL'), None)
    if not output_node:
        output_node = nodes.new('ShaderNodeOutputMaterial')
        output_node.name = f"{mat_name}_MaterialOutput"
        output_node.location = (400, 0)

    bsdf_node = nodes.get(f"{mat_name}_PrincipledBSDF") or next((n for n in nodes if n.type == 'ShaderNodeBsdfPrincipled'), None)
    if not bsdf_node:
        bsdf_node = nodes.new('ShaderNodeBsdfPrincipled')
        bsdf_node.name = f"{mat_name}_PrincipledBSDF"
        bsdf_node.location = (0, 0)
    
    # Link BSDF to Output if not already linked
    if not output_node.inputs['Surface'].is_linked or \
       not any(link.from_node == bsdf_node for link in output_node.inputs['Surface'].links):
        # Clear existing links to surface if any
        for link in list(output_node.inputs['Surface'].links):
            links.remove(link)
        links.new(bsdf_node.outputs['BSDF'], output_node.inputs['Surface'])

    # --- Texture Coordinate and Mapping ---
    # Use the first available image for aspect ratio calculation in mapping setup.
    # This might need refinement if different images have wildly different aspects.
    ref_img_for_mapping = _load_image_cached(texture_path) or _load_image_cached(roughness_path) or _load_image_cached(normal_path)
    uv_socket = _setup_texture_mapping_nodes(nt, ref_img_for_mapping, props, base_node_name=f"{mat_name}")

    # --- Helper to manage a texture node ---
    def manage_texture_node(node_name_suffix: str, image_path: str, is_color_data: bool):
        node_name = f"{mat_name}_{node_name_suffix}"
        tex_node = nodes.get(node_name)
        img = _load_image_cached(image_path) if image_path else None

        if img:
            if not tex_node:
                tex_node = nodes.new('ShaderNodeTexImage')
                tex_node.name = node_name
                # Position new nodes reasonably
                if "BaseColor" in node_name_suffix: tex_node.location = (-400, 200)
                elif "Roughness" in node_name_suffix: tex_node.location = (-400, -50)
                elif "Normal" in node_name_suffix: tex_node.location = (-400, -300)

            if tex_node.image != img: # Update image if different or new
                tex_node.image = img
            
            # Ensure image settings are correct
            tex_node.interpolation = 'Linear'
            tex_node.extension = props.texture_extension_mode
            if hasattr(img, 'colorspace_settings'):
                 img.colorspace_settings.name = 'sRGB' if is_color_data else 'Non-Color'

            # Link UVs
            if not tex_node.inputs['Vector'].is_linked or \
               not any(link.from_socket == uv_socket for link in tex_node.inputs['Vector'].links):
                for link in list(tex_node.inputs['Vector'].links): links.remove(link)
                if uv_socket: links.new(uv_socket, tex_node.inputs['Vector'])
            
            return tex_node
        
        elif tex_node: # No image path, but node exists - remove it
            for out_socket in tex_node.outputs: # Clear links from this node
                for link in list(out_socket.links): links.remove(link)
            for in_socket in tex_node.inputs: # Clear links to this node
                for link in list(in_socket.links): links.remove(link)
            nodes.remove(tex_node)
        return None

    # --- Base Color Texture ---
    base_color_tex_node = manage_texture_node("BaseColorTex", texture_path, True)
    base_color_socket = bsdf_node.inputs['Base Color']
    if base_color_tex_node:
        if not base_color_socket.is_linked or \
           not any(link.from_node == base_color_tex_node for link in base_color_socket.links):
            for link in list(base_color_socket.links): links.remove(link)
            links.new(base_color_tex_node.outputs['Color'], base_color_socket)
    else: # No texture, ensure socket is unlinked
        for link in list(base_color_socket.links): links.remove(link)


    # --- Roughness Texture & Invert Node ---
    roughness_tex_node = manage_texture_node("RoughnessTex", roughness_path, False)
    invert_node_name = f"{mat_name}_RoughnessInvert"
    invert_node = nodes.get(invert_node_name)
    roughness_socket = bsdf_node.inputs['Roughness']

    if roughness_tex_node and invert_roughness_map:
        if not invert_node:
            invert_node = nodes.new('ShaderNodeInvert')
            invert_node.name = invert_node_name
            invert_node.location = (-200, -50)

        # Link tex to invert
        if not invert_node.inputs['Color'].is_linked or \
           not any(link.from_node == roughness_tex_node for link in invert_node.inputs['Color'].links):
            for link in list(invert_node.inputs['Color'].links): links.remove(link)
            links.new(roughness_tex_node.outputs['Color'], invert_node.inputs['Color'])
        
        # Link invert to BSDF
        if not roughness_socket.is_linked or \
           not any(link.from_node == invert_node for link in roughness_socket.links):
            for link in list(roughness_socket.links): links.remove(link)
            links.new(invert_node.outputs['Color'], roughness_socket)

    elif roughness_tex_node: # Roughness exists, but not inverting
        if invert_node: # Remove invert if it exists and was linked
            if roughness_socket.is_linked and any(link.from_node == invert_node for link in roughness_socket.links):
                 for link in list(roughness_socket.links): links.remove(link) # clear link from invert
            for link in list(invert_node.outputs['Color'].links): links.remove(link)
            for link in list(invert_node.inputs['Color'].links): links.remove(link)
            nodes.remove(invert_node)
            invert_node = None # Clear reference
        
        # Ensure direct link from tex to BSDF
        if not roughness_socket.is_linked or \
           not any(link.from_node == roughness_tex_node for link in roughness_socket.links):
            for link in list(roughness_socket.links): links.remove(link)
            links.new(roughness_tex_node.outputs['Color'], roughness_socket)
    
    else: # No roughness texture
        if invert_node: # Remove invert if it exists
            if roughness_socket.is_linked and any(link.from_node == invert_node for link in roughness_socket.links):
                 for link in list(roughness_socket.links): links.remove(link)
            for link in list(invert_node.outputs['Color'].links): links.remove(link)
            for link in list(invert_node.inputs['Color'].links): links.remove(link)
            nodes.remove(invert_node)
            invert_node = None
        # Ensure BSDF roughness is unlinked
        for link in list(roughness_socket.links): links.remove(link)


    # --- Normal Map ---
    normal_tex_node = manage_texture_node("NormalTex", normal_path, False)
    normal_map_node_name = f"{mat_name}_NormalMapNode"
    normal_map_node = nodes.get(normal_map_node_name)
    normal_socket = bsdf_node.inputs['Normal']

    if normal_tex_node:
        if not normal_map_node:
            normal_map_node = nodes.new('ShaderNodeNormalMap')
            normal_map_node.name = normal_map_node_name
            normal_map_node.location = (-200, -300)
        
        # Link tex to normal_map_node
        if not normal_map_node.inputs['Color'].is_linked or \
           not any(link.from_node == normal_tex_node for link in normal_map_node.inputs['Color'].links):
            for link in list(normal_map_node.inputs['Color'].links): links.remove(link)
            links.new(normal_tex_node.outputs['Color'], normal_map_node.inputs['Color'])
        
        # Link normal_map_node to BSDF
        if not normal_socket.is_linked or \
           not any(link.from_node == normal_map_node for link in normal_socket.links):
            for link in list(normal_socket.links): links.remove(link)
            links.new(normal_map_node.outputs['Normal'], normal_socket)
        
    else: # No normal texture
        if normal_map_node: # Remove normal map node if it exists
            if normal_socket.is_linked and any(link.from_node == normal_map_node for link in normal_socket.links):
                 for link in list(normal_socket.links): links.remove(link)
            for link in list(normal_map_node.outputs['Normal'].links): links.remove(link)
            for link in list(normal_map_node.inputs['Color'].links): links.remove(link)
            nodes.remove(normal_map_node)
            normal_map_node = None
        # Ensure BSDF normal is unlinked
        for link in list(normal_socket.links): links.remove(link)

    # Assign material to object slot
    if not obj.data.materials or obj.data.materials[0] != mat:
        obj.data.materials.clear()
        obj.data.materials.append(mat)
    elif len(obj.data.materials) > 1: # Ensure only one material if we manage it this way
        obj.data.materials.clear()
        obj.data.materials.append(mat)


def apply_displacement(obj, heightmap_img, strength: float, subdivision_levels: int, apply_modifiers=False, modifier_prefix=""):
    sub = obj.modifiers.new(f"{modifier_prefix}Subsurf", 'SUBSURF')
    sub.levels = subdivision_levels
    sub.render_levels = subdivision_levels
    sub.subdivision_type = 'SIMPLE'
    disp = obj.modifiers.new(f"{modifier_prefix}Displace", 'DISPLACE')
    tex = bpy.data.textures.new(f"{modifier_prefix}HeightmapTexture", 'IMAGE')
    tex.image = heightmap_img
    disp.texture = tex
    disp.texture_coords = 'UV'
    disp.strength = strength
    if apply_modifiers:
        bpy.ops.object.modifier_apply(modifier=sub.name)
        bpy.ops.object.modifier_apply(modifier=disp.name)

# ---------------- UV mapping helper ----------------


def _setup_texture_mapping_nodes(node_tree, reference_image, props, base_node_name: str):
    """Get, create, or update Texture Coordinate + Mapping nodes.

    Returns the Vector output socket of the Mapping node for connection to Image Texture nodes.
    """
    nodes = node_tree.nodes
    links = node_tree.links

    tex_coord_name = f"{base_node_name}_TexCoord"
    mapping_node_name = f"{base_node_name}_Mapping"

    tex_coord = nodes.get(tex_coord_name)
    if not tex_coord:
        tex_coord = nodes.new(type='ShaderNodeTexCoord')
        tex_coord.name = tex_coord_name
        tex_coord.location = (-800, 0) # Example position

    mapping = nodes.get(mapping_node_name)
    if not mapping:
        mapping = nodes.new(type='ShaderNodeMapping')
        mapping.name = mapping_node_name
        mapping.location = (-600, 0) # Example position

    mapping.vector_type = 'TEXTURE' # Or 'POINT' depending on needs, 'TEXTURE' is common for UVs

    # Compute transformations
    pad_top_frac = props.polar_padding_top / 100.0
    pad_bottom_frac = props.polar_padding_bottom / 100.0
    v_coverage = 1.0 - pad_top_frac - pad_bottom_frac
    scale_y = 1.0 / v_coverage
    loc_y = pad_bottom_frac * scale_y # Corrected: positive padding pushes image up (texture moves down)
                                                 # So loc_y should be positive if padding_bottom is positive.
                                                 # Or, more intuitively: shift texture so that 0 point starts after padding_bottom
                                                 # (padding_bottom = 0.1 means texture starts at UV Y = 0.1)
                                                 # Scale applies first, then location.
                                                 # (UV.y * scale_y) + loc_y
                                                 # If padding_bottom=0.1, scale_y=1/(1-0.1-0.1)=1.25. We want (0*1.25)+L = 0.1 => L = 0.1
                                                 # If padding_top=0.1, scale_y=1.25. We want (1*1.25)+L = 1-0.1 = 0.9 => 1.25+L=0.9 => L = -0.35
                                                 # Let's use Blender's typical mapping: Location moves the texture.
                                                 # To see padding_bottom, texture must move UP, so loc_y = props.polar_padding_bottom
                                                 # To see padding_top, texture must move DOWN from top, which is complex with scale.

    # Simplified padding logic based on common interpretation:
    # Location: (X, Y, Z) - how much to shift the texture. Positive Y shifts texture up.
    # Scale: (X, Y, Z) - how much to scale the texture.
    # Goal: map texture into region [0, padding_left ; 1-padding_right] horizontally
    #       map texture into region [0, padding_bottom ; 1-padding_top] vertically

    # Vertical:
    # Texture Y range [0,1] should map to UV Y range [padding_bottom, 1-padding_top]
    # New_Y = Old_Y * Height + Offset_Y
    # padding_bottom = 0 * Height + Offset_Y  => Offset_Y = padding_bottom
    # 1-padding_top = 1 * Height + Offset_Y => Height = 1 - padding_top - padding_bottom
    # scale_y in Mapping node is 1/Height if Height is fraction of UV space covered by texture
    # location_y in Mapping node is Offset_Y if scale is 1. If scale is applied, location is also scaled.
    # Blender mapping node: Output = (Input * Scale) + Location
    # Input Y is [0,1]. Output Y should be [padding_bottom, 1-padding_top]
    # So: padding_bottom = (0 * scale_y) + location_y  => location_y = padding_bottom
    # And: 1-padding_top = (1 * scale_y) + location_y
    #      1-padding_top = scale_y + padding_bottom
    #      scale_y = 1 - padding_top - padding_bottom

    map_scale_y = v_coverage
    map_scale_y = max(map_scale_y, 0.001)
    map_location_y = pad_bottom_frac
    
    map_scale_x = 1.0 # Default
    map_location_x = 0.0 # Default

    if props.maintain_aspect_ratio and reference_image and reference_image.size[0] > 0 and reference_image.size[1] > 0:
        img_w = float(reference_image.size[0])
        img_h = float(reference_image.size[1])
        img_aspect = img_w / img_h
        
        # Target UV aspect for equirectangular is usually 2:1 (width:height)
        # However, the _setup_texture_mapping_nodes is generic.
        # If we consider the UV space [0,1] for U and [0,1] for V.
        # The effective *display width* of the texture in this UV space will be map_scale_x.
        # The effective *display height* of the texture in this UV space will be map_scale_y.
        # We want (img_w / img_h) = (map_scale_x / map_scale_y) for the *texture itself*
        # Or, if UV space is treated as having a certain aspect (e.g. 1:1 for plane, 2:1 for sphere UVs)
        # Let's assume UV space itself is 1:1 for this calculation, adjustments for sphere UVs happen elsewhere or by convention.
        
        # If texture is wider than tall (img_aspect > 1), to fit its aspect into a square UV region (scaled by map_scale_y vertically)
        # map_scale_x should be map_scale_y * img_aspect
        # If texture is taller than wide (img_aspect < 1),
        # map_scale_x should be map_scale_y * img_aspect (still)
        
        # The existing code was:
        # sphere_uv_target_aspect = 2.0
        # map_scale_x = img_aspect / sphere_uv_target_aspect
        # map_location_x = (1.0 - map_scale_x) / 2.0
        # This seems specific to sphere mapping. Let's try to keep it general for now,
        # assuming the primary use case with aspect ratio is for equirectangular on a sphere.
        # For a plane, one might expect the texture to fill the UV space by default unless padded.

        if props.render_mode == 'GLOBE': # Apply sphere-specific aspect correction
            sphere_uv_target_aspect = 2.0 # UV space for a sphere is 2 units wide, 1 unit high effectively
            
            # If texture height (after vertical padding) covers map_scale_y of V space,
            # then texture width should cover map_scale_y * img_aspect of U space,
            # relative to a 1:1 UV grid.
            # But sphere U goes 0 to 1, representing 360 degrees. V goes 0 to 1, 180 degrees.
            # So U is "twice as wide" in terms of coverage.
            
            # Corrected logic for sphere aspect:
            # Effective UV display aspect = map_scale_x / map_scale_y (if UV grid is 1:1)
            # We want image_aspect = (map_scale_x / sphere_uv_target_aspect) / map_scale_y
            # map_scale_x = image_aspect * map_scale_y * sphere_uv_target_aspect
            
            map_scale_x = (map_scale_y * img_aspect) / sphere_uv_target_aspect
            map_scale_x = min(map_scale_x, 1.0)

            map_location_x = (1.0 - map_scale_x) / 2.0
            
            mapping.inputs['Scale'].default_value = (map_scale_x, map_scale_y, 1.0)
            mapping.inputs['Location'].default_value = (map_location_x, map_location_y, 0.0)

        else: # For LANDSCAPE or other modes, assume 1:1 UV aspect for calculation
            # If texture is wider than UV (after y scaling), scale down X.
            # If texture is narrower than UV (after y scaling), scale up X to fill, or letterbox.
            # Current props don't distinguish, so let's assume we want to fit aspect.
            # Effective V height in UV space = map_scale_y
            # Corresponding U width in UV space should be map_scale_y * img_aspect
            final_map_scale_x = map_scale_y * img_aspect
            map_location_x = (1.0 - final_map_scale_x) / 2.0 # Center

            mapping.inputs['Scale'].default_value = (final_map_scale_x, map_scale_y, 1.0)
            mapping.inputs['Location'].default_value = (map_location_x, map_location_y, 0.0)
    else: # No reference image or maintain_aspect_ratio is False
        mapping.inputs['Scale'].default_value = (1.0, map_scale_y, 1.0) # Only vertical padding scale
        mapping.inputs['Location'].default_value = (0.0, map_location_y, 0.0)


    # Link TexCoord to Mapping if not already linked
    if not mapping.inputs['Vector'].is_linked or \
       not any(link.from_node == tex_coord for link in mapping.inputs['Vector'].links):
        # Clear existing links to vector if any
        for link in list(mapping.inputs['Vector'].links):
            links.remove(link)
        links.new(tex_coord.outputs['UV'], mapping.inputs['Vector'])

    return mapping.outputs['Vector'] 