# Kilroy's Gaea2Blender Addon

This Blender addon allows you to generate landscapes or globes from Gaea height and texture maps. It provides options for atmosphere, clouds, and exporting tiled landscapes to STL files.

## Installation

1.  Download the `kilroys_gaea2blender.zip` file from the repository.
2.  Open Blender and go to `Edit > Preferences > Add-ons`.
3.  Click `Install...` and select the downloaded `.zip` file.
4.  Enable the "Kilroy's Gaea2Blender" addon by checking the box next to it.

The addon will then appear in the 3D View's sidebar (`N` key) under the "Gaea2Blender" tab.

## Usage

The addon has two main modes: **Landscape** and **Globe**. You can switch between these modes at the top of the addon panel.

### Common Settings

*   **Source Images**:
    *   `Start Tile File`: The first height map file (e.g., `tile_x0_y0.png`).
    *   `Texture File`: The color texture map.
    *   `Roughness File`: The roughness map.
    *   `Normal File`: The normal map.
    *   `Surface Map Projection Type`: The projection type of your source maps (e.g., 'Equirectangular').

### Landscape Mode

This mode is for creating tiled landscapes.

*   **Landscape Tiling**:
    *   `Tiled Input`: Enable if your Gaea export is a set of tiled images.
    *   `Num Rows`: Number of rows in your tile set.
    *   `Num Cols`: Number of columns in your tile set.
*   **STL Export**:
    *   `Tile Thickness`: The thickness of the base for exported STL files.
    *   `Output Dir`: The directory where the STL files will be saved.
*   **Clouds**:
    *   `Generate Clouds`: Adds a cloud layer above the landscape.
    *   You can control the cloud texture, zoom, and offset.
*   **Atmosphere**:
    *   `Generate Atmosphere`: Adds a volumetric atmosphere effect.
    *   You can control the density and color of the atmosphere.

**Operators**:

*   `Generate Landscape`: Creates the landscape based on your settings.
*   `Refresh Landscape`: Updates the landscape with any changed settings.
*   `Export STL Tiles`: Exports the landscape tiles as individual STL files.

### Globe Mode

This mode is for creating a spherical planet from your maps.

*   **Globe Geometry**:
    *   `Segments` and `Rings`: Controls the resolution of the base sphere.
    *   `Globe Radius`: The radius of the sphere.
*   **Texture Mapping**:
    *   `Maintain Aspect Ratio`: Keeps the correct aspect ratio for the texture.
    *   `Polar Padding`: Adds padding at the poles to reduce distortion.
    *   `Texture Extension Mode`: How the texture is handled at the edges.
*   **Atmosphere**:
    *   `Generate Atmosphere`: Adds a volumetric atmosphere.
    *   Control density, color, and scale offset.
*   **Clouds**:
    *   `Generate Clouds`: Adds a cloud layer.
    *   Control scale offset, displacement, and material properties.

**Operators**:

*   `Generate Globe`: Creates the globe based on your settings.

### Shared Geometry Tweaks

These settings are available in both modes:

*   `Displacement Strength`: Controls the height of the terrain displacement.
*   `Subdivision Levels`: Sets the number of subdivisions for the mesh.
*   `Use Adaptive Subdivision`: Enables adaptive subdivision for more detail where needed.
*   `Invert Roughness Map`: Inverts the roughness map values.
*   `Auto Update`: Automatically updates the preview when a setting is changed.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details. 