"""
Enhanced TripoSR integration for Trivox AI Models.
Direct Python calls instead of subprocess for better control and error handling.
"""

import os
import torch
import numpy as np
from PIL import Image
from pathlib import Path
from typing import Optional, Dict
from dataclasses import dataclass
from config.settings import get_output_dir


@dataclass
class TripoSRResult:
    """Result from TripoSR local generation."""
    success: bool
    model_path: Optional[str] = None
    texture_path: Optional[str] = None
    error_message: Optional[str] = None
    generation_time: float = 0.0


class TripoSRDirect:
    """
    Direct TripoSR integration (no subprocess).
    Loads the TSR model directly into Python process.
    """

    def __init__(
        self,
        pretrained_model: str = "stabilityai/TripoSR",
        device: Optional[str] = None,
        chunk_size: int = 8192,
        mc_resolution: int = 256,
    ):
        self.pretrained_model = pretrained_model
        self.device = device or ("cuda:0" if torch.cuda.is_available() else "cpu")
        self.chunk_size = chunk_size
        self.mc_resolution = mc_resolution
        self._model = None
        self._rembg_session = None

    def _load_model(self):
        """Lazy-load TSR model."""
        if self._model is None:
            from tsr.system import TSR
            self._model = TSR.from_pretrained(
                self.pretrained_model,
                config_name="config.yaml",
                weight_name="model.ckpt",
            )
            self._model.renderer.set_chunk_size(self.chunk_size)
            self._model.to(self.device)
        return self._model

    def _preprocess_image(self, image_path: str, foreground_ratio: float = 0.85) -> Image.Image:
        """Remove background and normalize image."""
        import rembg
        from tsr.utils import remove_background, resize_foreground

        if self._rembg_session is None:
            self._rembg_session = rembg.new_session()

        image = Image.open(image_path)
        image = remove_background(image, self._rembg_session)
        image = resize_foreground(image, foreground_ratio)

        arr = np.array(image).astype(np.float32) / 255.0
        arr = arr[:, :, :3] * arr[:, :, 3:4] + (1 - arr[:, :, 3:4]) * 0.5
        return Image.fromarray((arr * 255.0).astype(np.uint8))

    def generate(
        self,
        image_path: str,
        output_dir: str = None,
        model_name: str = "model",
        format_type: str = "obj",
        bake_texture: bool = False,
        texture_resolution: int = 2048,
        foreground_ratio: float = 0.85,
        progress_callback=None,
    ) -> TripoSRResult:
        """
        Generate 3D model from image.

        Args:
            image_path: Path to input image
            output_dir: Output directory (default: user Documents)
            model_name: Base name for output files
            format_type: 'obj' or 'glb'
            bake_texture: Use UV-mapped texture instead of vertex colors
            texture_resolution: Resolution for baked texture atlas
            foreground_ratio: Size of foreground relative to image
            progress_callback: fn(stage, percent, message)

        Returns:
            TripoSRResult with model path and status
        """
        import time
        start = time.time()
        output_dir = output_dir or str(get_output_dir())
        os.makedirs(output_dir, exist_ok=True)

        try:
            # Step 1: Load model
            if progress_callback:
                progress_callback("Loading Local AI model...", 10, None)
            model = self._load_model()

            # Step 2: Preprocess
            if progress_callback:
                progress_callback("Preprocessing image...", 20, None)
            image = self._preprocess_image(image_path, foreground_ratio)

            # Step 3: Inference
            if progress_callback:
                progress_callback("Running inference...", 30, None)
            with torch.no_grad():
                scene_codes = model([image], device=self.device)

            # Step 4: Mesh extraction
            if progress_callback:
                progress_callback("Extracting mesh...", 60, None)
            meshes = model.extract_mesh(
                scene_codes,
                use_vertex_colors=not bake_texture,
                resolution=self.mc_resolution,
            )

            mesh_path = os.path.join(output_dir, f"{model_name}.{format_type}")
            texture_path = None

            # Step 5: Export
            if bake_texture:
                if progress_callback:
                    progress_callback("Baking texture...", 75, None)
                import xatlas
                from tsr.bake_texture import bake_texture as bake_fn

                bake_out = bake_fn(meshes[0], model, scene_codes[0], texture_resolution)
                xatlas.export(
                    mesh_path,
                    meshes[0].vertices[bake_out["vmapping"]],
                    bake_out["indices"],
                    bake_out["uvs"],
                    meshes[0].vertex_normals[bake_out["vmapping"]],
                )
                texture_path = os.path.join(output_dir, f"{model_name}_texture.png")
                Image.fromarray(
                    (bake_out["colors"] * 255.0).astype(np.uint8)
                ).transpose(Image.FLIP_TOP_BOTTOM).save(texture_path)
            else:
                if progress_callback:
                    progress_callback("Exporting mesh...", 85, None)
                meshes[0].export(mesh_path)

            if progress_callback:
                progress_callback("Complete", 100, None)

            return TripoSRResult(
                success=True,
                model_path=mesh_path,
                texture_path=texture_path,
                generation_time=time.time() - start,
            )

        except Exception as e:
            return TripoSRResult(
                success=False,
                error_message=str(e),
                generation_time=time.time() - start,
            )
