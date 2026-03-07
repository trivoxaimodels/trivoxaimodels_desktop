import os
import time
import shutil
from pathlib import Path
from typing import Optional

import numpy as np
import trimesh

from core.inference.model_manager import ModelManager
from core.postprocess.cleanup import clean_mesh
from core.exporter import export_mesh
from config.settings import get_output_dir


# Quality presets: "draft" = fast cleanup only; others use AdvancedMeshProcessor
QUALITY_LEVELS = ("draft", "standard", "high", "production")


def run_pipeline(
    image,
    name: str = "model",
    output_dir: str = None,
    quality: str = "standard",
    scale: float = 1.0,
    colorize_from_image: bool = True,
    progress_callback=None,
) -> dict:
    """
    Run the full image → mesh → exports pipeline and return paths plus timing stats.

    Args:
        image: Input image path or loaded image for inference.
        name: Base name for output files (no extension).
        output_dir: Directory for OBJ, STL, GLB outputs (default: user Documents folder).
        quality: Mesh quality preset: "draft", "standard", "high", "production".
                 "draft" = fast cleanup only; others use advanced mesh processing.
        scale: Scale factor applied to mesh before export (default 1.0).

    Returns:
        Dict with "obj", "stl", "glb" paths and "stats" (timing). JSON-serialisable.
    """
    if quality not in QUALITY_LEVELS:
        quality = "standard"

    # Use user-writable output directory if not specified
    if output_dir is None:
        output_dir = str(get_output_dir())

    os.makedirs(output_dir, exist_ok=True)

    t0 = time.perf_counter()

    def _report(stage, pct, msg):
        if progress_callback:
            try:
                progress_callback(stage, pct, msg)
            except Exception:
                pass

    _report("init", 2, "Initializing model manager...")
    manager = ModelManager()

    t_infer_start = time.perf_counter()
    _report(
        "load_and_infer",
        5,
        "Loading image and running 3D inference (this is the longest stage)...",
    )

    # Start a heartbeat thread to update progress during the long inference
    # (TripoSR subprocess blocks for 2-5+ minutes with no output)
    import threading

    _infer_done = threading.Event()

    def _heartbeat():
        """Gradually increment progress from 5% → 60% over time."""
        import math

        start = time.perf_counter()
        while not _infer_done.is_set():
            elapsed = time.perf_counter() - start
            # Exponential curve: approaches 60% asymptotically
            # At 60s → ~25%, at 120s → ~40%, at 240s → ~52%, at 300s → ~55%
            pct = 5 + 55 * (1 - math.exp(-elapsed / 180))
            minutes = int(elapsed // 60)
            secs = int(elapsed % 60)
            _report(
                "load_and_infer",
                round(pct, 1),
                f"TripoSR processing... ({minutes}m {secs:02d}s elapsed)",
            )
            if _infer_done.wait(timeout=15):  # Update every 15 seconds
                break

    heartbeat_thread = threading.Thread(target=_heartbeat, daemon=True)
    heartbeat_thread.start()

    try:
        infer_result = manager.run(image)
    finally:
        _infer_done.set()
        heartbeat_thread.join(timeout=2)

    fallback_info = None
    textured_assets = None
    if isinstance(infer_result, dict) and "mesh" in infer_result:
        mesh = infer_result["mesh"]
        fallback_info = {k: v for k, v in infer_result.items() if k != "mesh"}
        textured_assets = (
            infer_result.get("textured_assets")
            if isinstance(infer_result.get("textured_assets"), dict)
            else None
        )
    else:
        mesh = infer_result
    t_infer_end = time.perf_counter()
    _report(
        "load_and_infer_done",
        75,
        f"Inference complete ({round(t_infer_end - t_infer_start, 1)}s). Preparing mesh...",
    )

    t_cleanup_start = time.perf_counter()
    if textured_assets:
        _report("cleanup", 80, "Textured assets available, skipping mesh cleanup...")
        t_cleanup_end = time.perf_counter()
    else:
        _report(
            "cleanup",
            78,
            "Cleaning raw mesh (removing noise vertices, degenerate faces)...",
        )
        mesh = clean_mesh(mesh)
        if quality != "draft":
            _report(
                "advanced_processing",
                82,
                f"Running advanced mesh processor (quality: {quality})...",
            )
            from core.postprocess.advanced_mesh_processor import (
                AdvancedMeshProcessor,
                ProcessingConfig,
                MeshQualityLevel,
            )

            level = MeshQualityLevel(quality)
            config = ProcessingConfig(quality_level=level)
            if quality in ("high", "production"):
                config.repair_holes = False
            processor = AdvancedMeshProcessor(config)
            mesh = processor.process(mesh)
            _report(
                "advanced_processing_done", 88, "Advanced mesh processing complete."
            )
        t_cleanup_end = time.perf_counter()

    if colorize_from_image and not textured_assets:
        _report("colorize", 90, "Applying vertex colors from input image...")
        mesh = _apply_vertex_colors_from_image(mesh, image)
        # Also generate a proper UV texture from the input image
        _report("texture_gen", 91, "Generating UV texture from input image...")
        try:
            texture_result = _generate_texture_for_mesh(mesh, image, output_dir, name)
            if texture_result:
                textured_assets = texture_result
                _report("texture_gen_done", 92, "Texture generated successfully.")
            else:
                _report(
                    "texture_gen_skip",
                    92,
                    "Texture generation skipped (vertex colors only).",
                )
        except Exception as tex_err:
            print(f"[Pipeline] Texture generation failed (non-fatal): {tex_err}")
            _report(
                "texture_gen_skip",
                92,
                "Texture generation failed, using vertex colors.",
            )

    t_export_start = time.perf_counter()
    _report("export", 93, f"Exporting 3D files (OBJ, STL, GLB) to {output_dir}...")
    obj_path = os.path.join(output_dir, f"{name}.obj")
    stl_path = os.path.join(output_dir, f"{name}.stl")
    glb_path = os.path.join(output_dir, f"{name}.glb")
    if textured_assets and textured_assets.get("obj"):
        obj_src = Path(textured_assets["obj"])
        mtl_src = Path(textured_assets["mtl"]) if textured_assets.get("mtl") else None
        tex_src = (
            Path(textured_assets["texture"]) if textured_assets.get("texture") else None
        )
        obj_path = os.path.join(output_dir, f"{name}.obj")
        mtl_name = f"{name}.mtl"
        tex_name = tex_src.name if tex_src else None

        # Copy files (skip if same file - happens when texture gen writes to output_dir)
        if str(obj_src.resolve()) != str(Path(obj_path).resolve()):
            shutil.copy2(obj_src, obj_path)
        if mtl_src and mtl_src.exists():
            mtl_path = os.path.join(output_dir, mtl_name)
            if str(mtl_src.resolve()) != str(Path(mtl_path).resolve()):
                shutil.copy2(mtl_src, mtl_path)
            if tex_src and tex_src.exists():
                tex_path = os.path.join(output_dir, tex_name)
                if str(tex_src.resolve()) != str(Path(tex_path).resolve()):
                    shutil.copy2(tex_src, tex_path)
                _rewrite_mtl_texture(mtl_path, tex_name)
            _rewrite_obj_mtllib(obj_path, mtl_name)
        loaded = trimesh.load(obj_path, process=False)
        if isinstance(loaded, trimesh.Scene):
            loaded.export(glb_path)
            mesh_for_stl = loaded.dump(concatenate=True)
        else:
            loaded.export(glb_path)
            mesh_for_stl = loaded
        mesh_for_stl.export(stl_path)
    else:
        export_mesh(mesh, obj_path, scale=scale)
        export_mesh(mesh, stl_path, scale=scale)
        export_mesh(mesh, glb_path, scale=scale)

    # Apply orientation correction based on input image
    mesh = _apply_orientation_correction(mesh, image, obj_path)
    missing = []
    for path in (obj_path, stl_path, glb_path):
        if not os.path.isfile(path):
            missing.append(path)
            continue
        if os.path.getsize(path) == 0:
            missing.append(path)
    if missing:
        raise RuntimeError(f"Export failed, missing outputs: {', '.join(missing)}")
    t_export_end = time.perf_counter()
    _report("done", 100, "All files exported successfully.")

    t1 = time.perf_counter()

    stats = {
        "total_seconds": round(t1 - t0, 3),
        "stages": {
            "load_and_infer": round(t_infer_end - t_infer_start, 3),
            "cleanup": round(t_cleanup_end - t_cleanup_start, 3),
            "export": round(t_export_end - t_export_start, 3),
        },
    }

    result = {
        "obj": obj_path,
        "stl": stl_path,
        "glb": glb_path,
        "stats": stats,
        "quality": quality,
    }
    if fallback_info:
        result["fallback_info"] = fallback_info
    return result


def _detect_background_and_dominant(arr_float):
    """
    Detect the background color (from image corners) and the dominant
    foreground color.  Returns (bg_color, fg_color, fg_mask) where
    fg_mask is True for pixels that are NOT background.
    """
    h, w = arr_float.shape[:2]
    # Sample corner pixels (5×5 patches at each corner)
    patch = 5
    corners = np.concatenate(
        [
            arr_float[:patch, :patch].reshape(-1, 3),
            arr_float[:patch, -patch:].reshape(-1, 3),
            arr_float[-patch:, :patch].reshape(-1, 3),
            arr_float[-patch:, -patch:].reshape(-1, 3),
        ],
        axis=0,
    )
    bg_color = np.median(corners, axis=0)  # robust estimate

    # Foreground mask: pixels that differ from background by threshold
    diff = np.sqrt(((arr_float - bg_color) ** 2).sum(axis=2))
    threshold = 0.15  # ~15% color difference
    fg_mask = diff > threshold

    # Dominant foreground color: mean of foreground pixels
    if fg_mask.sum() > 10:
        fg_pixels = arr_float[fg_mask]
        fg_color = fg_pixels.mean(axis=0)
    else:
        fg_color = arr_float.mean(axis=(0, 1))

    return bg_color, fg_color, fg_mask


def _apply_vertex_colors_from_image(mesh, image_path):
    """
    Project the input image's colors onto mesh vertices using multi-axis
    projection with background-aware blending.  Background pixels are
    replaced with the object's dominant color so the mesh doesn't have
    ugly white/gray patches.
    """
    if not isinstance(image_path, str) or not os.path.isfile(image_path):
        return mesh
    try:
        from PIL import Image
        import open3d as o3d

        img = Image.open(image_path).convert("RGB")
        arr = np.asarray(img).astype(np.float64) / 255.0
        if arr.ndim != 3:
            return mesh
        h, w = arr.shape[:2]
        if h == 0 or w == 0:
            return mesh
        verts = np.asarray(mesh.vertices)
        if verts.size == 0:
            return mesh

        # Detect background and get dominant foreground color
        bg_color, fg_color, fg_mask = _detect_background_and_dominant(arr)

        # Replace background pixels with dominant foreground color
        arr_clean = arr.copy()
        arr_clean[~fg_mask] = fg_color

        # Compute normals for blending weights
        mesh.compute_vertex_normals()
        normals = np.asarray(mesh.vertex_normals)

        # Normalize vertex positions to [0, 1]
        mins = verts.min(axis=0)
        maxs = verts.max(axis=0)
        spans = maxs - mins
        spans[spans == 0] = 1.0
        normalized = (verts - mins) / spans

        def _sample(u_coords, v_coords):
            """Sample cleaned image at normalized UV coords."""
            px = np.clip(np.round(u_coords * (w - 1)).astype(int), 0, w - 1)
            py = np.clip(np.round((1.0 - v_coords) * (h - 1)).astype(int), 0, h - 1)
            return arr_clean[py, px, :3]

        # Project from 3 orthographic views:
        front_colors = _sample(normalized[:, 0], normalized[:, 1])  # XY
        side_colors = _sample(normalized[:, 2], normalized[:, 1])  # ZY
        top_colors = _sample(normalized[:, 0], normalized[:, 2])  # XZ

        # Weight by normal alignment (abs for both directions)
        w_front = np.abs(normals[:, 2])  # |Nz|
        w_side = np.abs(normals[:, 0])  # |Nx|
        w_top = np.abs(normals[:, 1])  # |Ny|

        total = w_front + w_side + w_top
        total[total == 0] = 1.0
        w_front = (w_front / total)[:, np.newaxis]
        w_side = (w_side / total)[:, np.newaxis]
        w_top = (w_top / total)[:, np.newaxis]

        colors = front_colors * w_front + side_colors * w_side + top_colors * w_top
        colors = np.clip(colors, 0.0, 1.0)

        mesh.vertex_colors = o3d.utility.Vector3dVector(colors)
        print(
            f"[Pipeline] Vertex colors applied (bg={bg_color.round(2)}, fg={fg_color.round(2)})"
        )
        return mesh
    except Exception as e:
        print(f"[Pipeline] Vertex color failed: {e}")
        return mesh


def _generate_texture_for_mesh(mesh, image_path, output_dir, name):
    """
    Generate a proper UV-mapped texture for the mesh from the input image.

    Creates:
      - {name}_texture.png  — the texture atlas
      - {name}.mtl           — material file referencing the texture
      - {name}.obj           — OBJ with UV coords and mtllib reference

    Returns dict with paths if successful, None otherwise.
    """
    try:
        from PIL import Image
        import open3d as o3d
        import trimesh

        img = Image.open(image_path).convert("RGB")
        tex_size = 1024  # texture atlas resolution

        # Convert open3d mesh to trimesh for UV unwrapping
        verts = np.asarray(mesh.vertices)
        faces = np.asarray(mesh.triangles)
        if verts.size == 0 or faces.size == 0:
            return None

        tri_mesh = trimesh.Trimesh(vertices=verts, faces=faces)

        # Generate UV coordinates via triplanar projection
        # For each face, pick the dominant axis normal and project UVs
        mesh.compute_triangle_normals()
        face_normals = np.asarray(mesh.triangle_normals)

        # Per-face dominant axis: 0=X (side), 1=Y (top), 2=Z (front)
        dominant = np.argmax(np.abs(face_normals), axis=1)

        mins = verts.min(axis=0)
        maxs = verts.max(axis=0)
        spans = maxs - mins
        spans[spans == 0] = 1.0

        # Normalize positions
        norm_verts = (verts - mins) / spans

        # Build UV per face-vertex (3 UVs per face)
        n_faces = len(faces)

        # Create a simple atlas layout: divide texture into 3 regions
        # Left third: front/back (Z dominant) → X,Y mapping
        # Middle third: side (X dominant)     → Z,Y mapping
        # Right third: top/bottom (Y dominant) → X,Z mapping

        uvs = np.zeros((n_faces * 3, 2), dtype=np.float64)
        face_vertex_indices = np.arange(n_faces * 3).reshape(n_faces, 3)

        for fi in range(n_faces):
            v0, v1, v2 = faces[fi]
            nv = [norm_verts[v0], norm_verts[v1], norm_verts[v2]]
            d = dominant[fi]

            if d == 2:  # Front/back → use X, Y → left third of atlas
                for vi, nvi in enumerate(nv):
                    uvs[fi * 3 + vi] = [nvi[0] / 3.0, nvi[1]]
            elif d == 0:  # Side → use Z, Y → middle third of atlas
                for vi, nvi in enumerate(nv):
                    uvs[fi * 3 + vi] = [nvi[2] / 3.0 + 1.0 / 3.0, nvi[1]]
            else:  # Top/bottom → use X, Z → right third of atlas
                for vi, nvi in enumerate(nv):
                    uvs[fi * 3 + vi] = [nvi[0] / 3.0 + 2.0 / 3.0, nvi[2]]

        # Detect background and replace with dominant object color
        img_orig = np.asarray(img)
        arr_float = img_orig.astype(np.float64) / 255.0
        bg_color, fg_color, fg_mask = _detect_background_and_dominant(arr_float)

        # Create a cleaned version where background is replaced with fg color
        img_clean = img_orig.copy()
        fg_color_uint8 = (fg_color * 255).astype(np.uint8)
        img_clean[~fg_mask] = fg_color_uint8

        h_orig, w_orig = img_clean.shape[:2]

        # Bake the texture using vectorized numpy (no pixel loop!)
        px_grid = np.arange(tex_size)
        py_grid = np.arange(tex_size)
        px_mesh, py_mesh = np.meshgrid(px_grid, py_grid)

        u_grid = px_mesh / (tex_size - 1)
        v_grid = 1.0 - py_mesh / (tex_size - 1)

        # Determine atlas region and compute source UV
        img_u = np.where(
            u_grid < 1.0 / 3.0,
            u_grid * 3.0,  # front region
            np.where(
                u_grid < 2.0 / 3.0,
                (u_grid - 1.0 / 3.0) * 3.0,  # side region
                (u_grid - 2.0 / 3.0) * 3.0,  # top region
            ),
        )
        img_v = v_grid  # same for all regions

        sx = np.clip((img_u * (w_orig - 1)).astype(int), 0, w_orig - 1)
        sy = np.clip(((1.0 - img_v) * (h_orig - 1)).astype(int), 0, h_orig - 1)

        tex = img_clean[sy, sx]  # uses background-cleaned image

        # Save texture
        tex_path = os.path.join(output_dir, f"{name}_texture.png")
        Image.fromarray(tex).save(tex_path, "PNG")

        # Write OBJ with UVs
        obj_path = os.path.join(output_dir, f"{name}.obj")
        mtl_name = f"{name}.mtl"
        mtl_path = os.path.join(output_dir, mtl_name)
        tex_name = f"{name}_texture.png"

        with open(obj_path, "w", encoding="utf-8") as f:
            f.write(f"# Generated by Trivox AI Models\n")
            f.write(f"mtllib {mtl_name}\n")
            f.write(f"usemtl material0\n\n")

            # Vertices
            for v in verts:
                f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

            # Vertex normals
            mesh.compute_vertex_normals()
            normals_arr = np.asarray(mesh.vertex_normals)
            for n in normals_arr:
                f.write(f"vn {n[0]:.6f} {n[1]:.6f} {n[2]:.6f}\n")

            # Texture coordinates
            for uv in uvs:
                f.write(f"vt {uv[0]:.6f} {uv[1]:.6f}\n")

            # Faces (1-indexed)
            for fi in range(n_faces):
                v0, v1, v2 = faces[fi] + 1  # OBJ is 1-indexed
                vt0 = fi * 3 + 1
                vt1 = fi * 3 + 2
                vt2 = fi * 3 + 3
                f.write(f"f {v0}/{vt0}/{v0} {v1}/{vt1}/{v1} {v2}/{vt2}/{v2}\n")

        # Write MTL
        with open(mtl_path, "w", encoding="utf-8") as f:
            f.write("# Generated by Trivox AI Models\n")
            f.write("newmtl material0\n")
            f.write("Ka 0.2 0.2 0.2\n")
            f.write("Kd 1.0 1.0 1.0\n")
            f.write("Ks 0.1 0.1 0.1\n")
            f.write("Ns 20.0\n")
            f.write("d 1.0\n")
            f.write(f"map_Kd {tex_name}\n")

        print(f"[Pipeline] Texture saved: {tex_path} ({tex_size}x{tex_size})")
        return {
            "obj": obj_path,
            "mtl": mtl_path,
            "texture": tex_path,
        }

    except Exception as e:
        print(f"[Pipeline] Texture gen failed: {e}")
        return None


def _rewrite_obj_mtllib(obj_path: str, mtl_name: str) -> None:
    try:
        with open(obj_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        updated = []
        replaced = False
        for line in lines:
            if line.lower().startswith("mtllib "):
                updated.append(f"mtllib {mtl_name}\n")
                replaced = True
            else:
                updated.append(line)
        if not replaced:
            updated.insert(0, f"mtllib {mtl_name}\n")
        with open(obj_path, "w", encoding="utf-8") as f:
            f.writelines(updated)
    except Exception:
        return


def _rewrite_mtl_texture(mtl_path: str, texture_name: str) -> None:
    try:
        with open(mtl_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        updated = []
        replaced = False
        for line in lines:
            low = line.lower()
            if (
                low.startswith("map_kd ")
                or low.startswith("map_ka ")
                or low.startswith("map_ke ")
            ):
                updated.append(f"map_Kd {texture_name}\n")
                replaced = True
            else:
                updated.append(line)
        if not replaced:
            updated.append(f"\nmap_Kd {texture_name}\n")
        with open(mtl_path, "w", encoding="utf-8") as f:
            f.writelines(updated)
    except Exception:
        return


def _apply_orientation_correction(mesh, image, obj_path: str):
    """
    Analyze input image to detect dominant orientation and apply rotation to mesh.

    This ensures the 3D model's orientation matches the input image's composition.
    """
    try:
        from PIL import Image
        import numpy as np

        # Load image
        if isinstance(image, (str, Path)):
            img = Image.open(image).convert("RGB")
        elif hasattr(image, "convert"):
            img = image.convert("RGB")
        else:
            return mesh  # Cannot analyze, return as-is

        # Convert to grayscale for edge detection
        gray = img.convert("L")
        img_array = np.array(gray)

        # Detect edges using simple gradient
        dx = np.diff(img_array, axis=1)
        dy = np.diff(img_array, axis=0)

        # Count horizontal vs vertical edge strengths
        horizontal_strength = np.sum(np.abs(dx))
        vertical_strength = np.sum(np.abs(dy))

        # Determine if image is more horizontal or vertical
        is_horizontal = horizontal_strength > vertical_strength

        # Load the exported mesh and apply rotation
        if os.path.exists(obj_path):
            loaded = trimesh.load(obj_path, process=False)

            if isinstance(loaded, trimesh.Scene):
                # For scenes, apply to each geometry
                for geom in loaded.geometry.values():
                    _rotate_mesh_by_orientation(geom, is_horizontal)
                # Re-export with rotation
                loaded.export(obj_path)
            else:
                _rotate_mesh_by_orientation(loaded, is_horizontal)
                loaded.export(obj_path)

    except Exception as e:
        print(f"[Pipeline] Orientation correction skipped: {e}")

    return mesh


def _rotate_mesh_by_orientation(mesh, is_horizontal: bool):
    """
    Rotate mesh based on detected image orientation.

    If image is horizontal-dominant (object lying flat), rotate mesh to align with Y-up.
    If image is vertical-dominant (object standing up), keep mesh as-is.
    """
    if is_horizontal:
        # Rotate -90 degrees around X axis to make mesh lie flat (like in reference image)
        angle = -np.pi / 2  # -90 degrees
        cos_a = np.cos(angle)
        sin_a = np.sin(angle)

        # Rotation matrix around X axis
        rotation = np.array([[1, 0, 0], [0, cos_a, -sin_a], [0, sin_a, cos_a]])

        # Apply rotation to vertices
        vertices = mesh.vertices
        rotated = vertices @ rotation.T
        mesh.vertices = rotated

        # Also rotate normals if they exist
        if hasattr(mesh, "vertex_normals") and mesh.vertex_normals is not None:
            normals = mesh.vertex_normals
            rotated_normals = normals @ rotation.T
            mesh.vertex_normals = rotated_normals
