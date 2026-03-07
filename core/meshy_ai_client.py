"""
Meshy AI API Client for Trivox AI Models

Cloud-based 3D generation from images and text prompts.
Docs: https://docs.meshy.ai/en
"""

import os
import time
import base64
import asyncio
import aiohttp
from typing import Optional, Dict, Any, List
from pathlib import Path
from dataclasses import dataclass
from config.settings import get_output_dir
from core.logger import get_logger, log_exception
from core.device_fingerprint import get_device_fingerprint

logger = get_logger(__name__)

from config.settings import get_web_api_url
BASE_URL = f"{get_web_api_url().rstrip('/')}/proxy/meshy_ai"


class MeshyAIError(Exception):
    """Base exception for Meshy AI API errors."""
    pass


class MeshyAIAuthError(MeshyAIError):
    """Authentication error (invalid API key)."""
    pass


class MeshyAITaskError(MeshyAIError):
    """Task creation or execution error."""
    pass


class MeshyAITimeoutError(MeshyAIError):
    """Task timeout error."""
    pass


@dataclass
class MeshyGenerationResult:
    """Result from Meshy AI 3D generation."""
    task_id: str
    status: str
    model_path: Optional[str] = None
    model_urls: Optional[Dict[str, str]] = None
    texture_urls: Optional[List[Dict[str, str]]] = None
    thumbnail_url: Optional[str] = None
    error_message: Optional[str] = None


class MeshyAIClient:
    """
    Meshy AI API client for 3D model generation.

    Supports:
    - Image-to-3D (single image)
    - Text-to-3D (preview + refine pipeline)
    - Multi-Image-to-3D (2-6 views)
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        timeout: int = 300,
        max_retries: int = 3,
    ):
        self.api_key = api_key or "proxy_mode"
        self.device_fp = get_device_fingerprint()
        self.base_url = BASE_URL
        self.timeout = timeout
        self.max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None

    # ── Session Management ──────────────────────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={
                    "X-Device-Fingerprint": self.device_fp,
                    "Content-Type": "application/json",
                },
            )
        return self._session

    async def _request(
        self, method: str, endpoint: str, json_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"
        for attempt in range(self.max_retries):
            try:
                async with session.request(method, url, json=json_data) as resp:
                    if resp.status == 401:
                        raise MeshyAIAuthError("Invalid API key")
                    if resp.status == 429:
                        wait = 2 ** attempt
                        logger.warning(f"Rate limited, waiting {wait}s...")
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                    return await resp.json()
            except aiohttp.ClientError as e:
                if attempt == self.max_retries - 1:
                    raise MeshyAIError(f"Request failed: {e}")
                await asyncio.sleep(1)
        raise MeshyAIError("Max retries exceeded")

    # ── Image-to-3D ─────────────────────────────────────────────

    async def create_image_to_3d_task(
        self,
        image_path: str,
        ai_model: str = "latest",
        topology: str = "triangle",
        target_polycount: int = 30000,
        enable_pbr: bool = True,
        should_remesh: bool = False,
        should_texture: bool = True,
    ) -> str:
        """Create an Image-to-3D task. Returns task_id."""
        # Convert local image to base64 data URI
        with open(image_path, "rb") as f:
            img_data = base64.b64encode(f.read()).decode("utf-8")
        ext = Path(image_path).suffix.lower().replace(".", "")
        if ext == "jpg":
            ext = "jpeg"
        image_url = f"data:image/{ext};base64,{img_data}"

        payload = {
            "image_url": image_url,
            "ai_model": ai_model,
            "topology": topology,
            "target_polycount": target_polycount,
            "enable_pbr": enable_pbr,
            "should_remesh": should_remesh,
            "should_texture": should_texture,
        }
        result = await self._request("POST", "/openapi/v1/image-to-3d", payload)
        return result["result"]

    async def get_image_to_3d_task(self, task_id: str) -> Dict[str, Any]:
        """Get status of an Image-to-3D task."""
        return await self._request("GET", f"/openapi/v1/image-to-3d/{task_id}")

    # ── Text-to-3D ──────────────────────────────────────────────

    async def create_text_to_3d_preview(
        self,
        prompt: str,
        negative_prompt: str = "",
        ai_model: str = "latest",
        should_remesh: bool = True,
    ) -> str:
        """Create a Text-to-3D preview task. Returns task_id."""
        payload = {
            "mode": "preview",
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "ai_model": ai_model,
            "should_remesh": should_remesh,
        }
        result = await self._request("POST", "/openapi/v2/text-to-3d", payload)
        return result["result"]

    async def create_text_to_3d_refine(
        self,
        preview_task_id: str,
        enable_pbr: bool = True,
        texture_prompt: str = "",
    ) -> str:
        """Create a Text-to-3D refine task. Returns task_id."""
        payload = {
            "mode": "refine",
            "preview_task_id": preview_task_id,
            "enable_pbr": enable_pbr,
        }
        if texture_prompt:
            payload["texture_prompt"] = texture_prompt
        result = await self._request("POST", "/openapi/v2/text-to-3d", payload)
        return result["result"]

    async def get_text_to_3d_task(self, task_id: str) -> Dict[str, Any]:
        """Get status of a Text-to-3D task."""
        return await self._request("GET", f"/openapi/v2/text-to-3d/{task_id}")

    # ── Polling & Download ──────────────────────────────────────

    async def wait_for_task(
        self,
        task_id: str,
        task_type: str = "image-to-3d",
        poll_interval: int = 5,
        max_wait: int = 600,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """Poll task until completion. Returns final task object."""
        get_fn = (
            self.get_image_to_3d_task
            if task_type == "image-to-3d"
            else self.get_text_to_3d_task
        )
        start = time.time()
        while time.time() - start < max_wait:
            task = await get_fn(task_id)
            status = task.get("status", "UNKNOWN")
            progress = task.get("progress", 0)

            if progress_callback:
                progress_callback(f"Cloud API: {status}", progress, None)

            if status == "SUCCEEDED":
                return task
            if status in ("FAILED", "CANCELED"):
                raise MeshyAITaskError(
                    task.get("task_error", {}).get("message", "Task failed")
                )
            await asyncio.sleep(poll_interval)

        raise MeshyAITimeoutError(f"Task {task_id} timed out after {max_wait}s")

    async def download_model(
        self,
        model_url: str,
        output_path: str,
    ) -> str:
        """Download a model file from Meshy CDN. Returns local path."""
        session = await self._get_session()
        async with session.get(model_url) as resp:
            resp.raise_for_status()
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(8192):
                    f.write(chunk)
        return output_path

    # ── Full Pipeline ───────────────────────────────────────────

    async def generate_3d_from_image(
        self,
        image_path: str,
        output_dir: str = None,
        model_name: str = "model",
        format_type: str = "glb",
        progress_callback=None,
        max_wait: int = 600,
        **kwargs,
    ) -> MeshyGenerationResult:
        """
        Full pipeline: image → create task → poll → download.
        Returns MeshyGenerationResult with local model path.
        """
        output_dir = output_dir or str(get_output_dir())
        os.makedirs(output_dir, exist_ok=True)

        if progress_callback:
            progress_callback("Creating Cloud API task...", 5, None)

        task_id = await self.create_image_to_3d_task(image_path, **kwargs)

        task = await self.wait_for_task(
            task_id, "image-to-3d", progress_callback=progress_callback,
            max_wait=max_wait,
        )

        model_urls = task.get("model_urls", {})
        download_url = model_urls.get(format_type) or model_urls.get("glb")

        if not download_url:
            return MeshyGenerationResult(
                task_id=task_id, status="FAILED",
                error_message="No download URL in response",
            )

        output_path = os.path.join(output_dir, f"{model_name}.{format_type}")
        await self.download_model(download_url, output_path)

        if progress_callback:
            progress_callback("Download complete", 100, None)

        return MeshyGenerationResult(
            task_id=task_id,
            status="SUCCEEDED",
            model_path=output_path,
            model_urls=model_urls,
            texture_urls=task.get("texture_urls"),
            thumbnail_url=task.get("thumbnail_url"),
        )

    async def generate_3d_from_text(
        self,
        prompt: str,
        output_dir: str = None,
        model_name: str = "model",
        format_type: str = "glb",
        enable_pbr: bool = True,
        progress_callback=None,
        max_wait: int = 900,
    ) -> MeshyGenerationResult:
        """
        Full text-to-3D pipeline: preview → poll → refine → poll → download.
        """
        output_dir = output_dir or str(get_output_dir())
        os.makedirs(output_dir, exist_ok=True)

        # Step 1: Preview
        if progress_callback:
            progress_callback("Creating preview...", 5, None)
        preview_id = await self.create_text_to_3d_preview(prompt)
        await self.wait_for_task(
            preview_id, "text-to-3d",
            progress_callback=lambda s, p, m: (
                progress_callback(f"Preview: {s}", p // 2, m)
                if progress_callback else None
            ),
            max_wait=max_wait // 2,
        )

        # Step 2: Refine
        if progress_callback:
            progress_callback("Refining model...", 50, None)
        refine_id = await self.create_text_to_3d_refine(
            preview_id, enable_pbr=enable_pbr
        )
        task = await self.wait_for_task(
            refine_id, "text-to-3d",
            progress_callback=lambda s, p, m: (
                progress_callback(f"Refine: {s}", 50 + p // 2, m)
                if progress_callback else None
            ),
            max_wait=max_wait // 2,
        )

        # Step 3: Download
        model_urls = task.get("model_urls", {})
        download_url = model_urls.get(format_type) or model_urls.get("glb")

        if not download_url:
            return MeshyGenerationResult(
                task_id=refine_id, status="FAILED",
                error_message="No download URL in response",
            )

        output_path = os.path.join(output_dir, f"{model_name}.{format_type}")
        await self.download_model(download_url, output_path)

        return MeshyGenerationResult(
            task_id=refine_id,
            status="SUCCEEDED",
            model_path=output_path,
            model_urls=model_urls,
            texture_urls=task.get("texture_urls"),
            thumbnail_url=task.get("thumbnail_url"),
        )

    # ── Cleanup ─────────────────────────────────────────────────

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def validate_api_key(self) -> bool:
        """Validate API key by listing tasks."""
        try:
            await self._request("GET", "/openapi/v1/image-to-3d?page_size=1")
            return True
        except MeshyAIAuthError:
            return False
