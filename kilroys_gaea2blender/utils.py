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


def assign_material(context, obj, row: int, col: int, texture_path: str, roughness_path: str, normal_path: str, invert_roughness_map: bool):
    mat = bpy.data.materials.new(name=f"Material_{row}_{col}")
    mat.use_nodes = True
    nt = mat.node_tree
    nodes = nt.nodes
    links = nt.links
    # clear default nodes
    for n in list(nodes):
        nodes.remove(n)
    output = nodes.new('ShaderNodeOutputMaterial')
    bsdf = nodes.new('ShaderNodeBsdfPrincipled')
    links.new(bsdf.outputs['BSDF'], output.inputs['Surface'])

    if texture_path:
        img = _load_image_cached(texture_path)
        if img:
            tex = nodes.new('ShaderNodeTexImage')
            tex.image = img
            links.new(tex.outputs['Color'], bsdf.inputs['Base Color'])

    if roughness_path:
        img_r = _load_image_cached(roughness_path)
        if img_r:
            tex_r = nodes.new('ShaderNodeTexImage')
            tex_r.image = img_r
            if invert_roughness_map:
                inv = nodes.new('ShaderNodeInvert')
                links.new(tex_r.outputs['Color'], inv.inputs['Color'])
                links.new(inv.outputs['Color'], bsdf.inputs['Roughness'])
            else:
                links.new(tex_r.outputs['Color'], bsdf.inputs['Roughness'])

    if normal_path:
        img_n = _load_image_cached(normal_path)
        if img_n:
            tex_n = nodes.new('ShaderNodeTexImage')
            tex_n.image = img_n
            if hasattr(tex_n.image, 'colorspace_settings'):
                tex_n.image.colorspace_settings.name = 'Non-Color'
            normal = nodes.new('ShaderNodeNormalMap')
            links.new(tex_n.outputs['Color'], normal.inputs['Color'])
            links.new(normal.outputs['Normal'], bsdf.inputs['Normal'])

    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
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