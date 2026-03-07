"""
Neural4D API Client for Trivox AI Models

Cloud-based 3D generation from images and text prompts.
API v1.2 — https://www.neural4d.com/api
"""

import os
import time
import asyncio
import aiohttp
from typing import Optional, Dict, Any, List
from pathlib import Path
from dataclasses import dataclass
from config.settings import get_output_dir, get_web_api_url
from core.device_fingerprint import get_device_fingerprint
from core.logger import get_logger, log_exception

logger = get_logger(__name__)

BASE_URL = f"{get_web_api_url().rstrip('/')}/proxy/neural4d"


class Neural4DError(Exception):
    """Base exception for Neural4D API errors."""
    pass


class Neural4DAuthError(Neural4DError):
    """Authentication error."""
    pass


class Neural4DTaskError(Neural4DError):
    """Task creation or execution error."""
    pass


class Neural4DTimeoutError(Neural4DError):
    """Task timeout error."""
    pass


@dataclass
class Neural4DGenerationResult:
    """Result from Neural4D 3D generation."""
    uuid: str
    status: int  # 0=success, 1=generating, 2=failed, 3=queued
    model_path: Optional[str] = None
    model_url: Optional[str] = None
    image_url: Optional[str] = None
    error_message: Optional[str] = None


class Neural4DClient:
    """
    Neural4D API client for 3D model generation.

    Supports:
    - Text-to-3D (prompt-based)
    - Image-to-3D (matting → generate pipeline)
    - Chibi/cute style models
    - Format conversion (glb, fbx, obj, stl, blend, usdz)
    - Balance and progress queries
    """

    def __init__(
        self,
        api_token: Optional[str] = None,
        timeout: int = 300,
        max_retries: int = 3,
    ):
        self.api_token = api_token or os.getenv("NEURAL4D_API_TOKEN", "")
        self.base_url = BASE_URL
        self.timeout = timeout
        self.max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None

    # ── Session Management ──────────────────────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=self.timeout),
                headers={"Authorization": f"Bearer {self.api_token}"},
            )
        return self._session

    async def _post_json(
        self, endpoint: str, data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """POST with JSON body."""
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"
        for attempt in range(self.max_retries):
            try:
                async with session.post(
                    url, json=data or {},
                    headers={"Content-Type": "application/json"},
                ) as resp:
                    if resp.status == 401:
                        raise Neural4DAuthError("Invalid API token")
                    resp.raise_for_status()
                    result = await resp.json()
                    # Neural4D may return code=None for success with message
                    code = result.get("code")
                    message = result.get("message", "")
                    # Success if code is 200, or if code is None but message indicates success
                    if code not in (200, None) and "success" not in message.lower():
                        raise Neural4DError(
                            f"API error code {code}: {message}"
                        )
                    return result.get("data", result)  # Return data or full result
            except aiohttp.ClientError as e:
                if attempt == self.max_retries - 1:
                    raise Neural4DError(f"Request failed: {e}")
                await asyncio.sleep(1)
        raise Neural4DError("Max retries exceeded")

    async def _post_form(
        self, endpoint: str, file_path: str, field_name: str = "image",
        extra_fields: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """POST with multipart/form-data (file upload)."""
        session = await self._get_session()
        url = f"{self.base_url}{endpoint}"
        data = aiohttp.FormData()
        data.add_field(
            field_name,
            open(file_path, "rb"),
            filename=Path(file_path).name,
        )
        if extra_fields:
            for k, v in extra_fields.items():
                data.add_field(k, str(v))

        async with session.post(url, data=data) as resp:
            if resp.status == 401:
                raise Neural4DAuthError("Invalid API token")
            resp.raise_for_status()
            result = await resp.json()
            if result.get("code") != 200:
                raise Neural4DError(
                    f"API error: {result.get('message', 'Unknown')}"
                )
            return result.get("data", {})

    # ── Text-to-3D ──────────────────────────────────────────────

    async def generate_from_text(
        self,
        prompt: str,
        model_count: int = 1,
        disable_pbr: bool = False,
    ) -> List[str]:
        """Generate 3D model(s) from text. Returns list of UUIDs."""
        data = await self._post_json("/api/generateModelWithText", {
            "prompt": prompt,
            "modelCount": model_count,
            "disablePbr": 1 if disable_pbr else 0,
        })
        return data.get("uuids", [])

    # ── Image-to-3D Pipeline ────────────────────────────────────

    async def matting_image(self, image_path: str) -> str:
        """Upload image for background removal. Returns requestId."""
        data = await self._post_form("/api/mattingImage", image_path)
        return data["requestId"]

    async def get_matted_result(self, request_id: str) -> Dict[str, Any]:
        """Get matting result. Returns fileKeys and mattedImageUrls."""
        return await self._post_json("/api/getMattedResult", {
            "requestId": request_id,
        })

    async def wait_for_matting(
        self, request_id: str, poll_interval: int = 3, max_wait: int = 120
    ) -> str:
        """Poll matting until ready. Returns first fileKey."""
        start = time.time()
        while time.time() - start < max_wait:
            try:
                result = await self.get_matted_result(request_id)
                file_keys = result.get("fileKeys", [])
                if file_keys:
                    return file_keys[0]
            except Neural4DError:
                pass  # Not ready yet
            await asyncio.sleep(poll_interval)
        raise Neural4DTimeoutError("Matting timed out")

    async def generate_from_image_key(
        self,
        file_key: str,
        model_count: int = 1,
        disable_pbr: bool = False,
    ) -> List[str]:
        """Generate 3D model from matted image fileKey. Returns UUIDs."""
        data = await self._post_json("/api/generateModelWithImage", {
            "fileKey": file_key,
            "modelCount": model_count,
            "disablePbr": 1 if disable_pbr else 0,
        })
        return data.get("uuids", [])

    # ── Model Retrieval & Polling ───────────────────────────────

    async def retrieve_model(self, uuid: str) -> Dict[str, Any]:
        """Get model status and URLs. Returns codeStatus, modelUrl, imageUrl."""
        return await self._post_json("/api/retrieveModel", {"uuid": uuid})

    async def query_progress(self, uuid: str) -> str:
        """Query job progress. Returns progress string like '75%'."""
        data = await self._post_json("/api/queryJobProgress", {"uuid": uuid})
        return data.get("progress", "0%")

    async def wait_for_model(
        self,
        uuid: str,
        poll_interval: int = 5,
        max_wait: int = 300,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """Poll until model is ready. Returns model data with modelUrl."""
        start = time.time()
        while time.time() - start < max_wait:
            result = await self.retrieve_model(uuid)
            code_status = result.get("codeStatus", -1)

            if progress_callback:
                progress_str = await self.query_progress(uuid)
                pct = int(progress_str.replace("%", "") or 0)
                progress_callback(f"Cloud API: {progress_str}", pct, None)

            if code_status == 0:  # Success
                return result
            if code_status == 2:  # Failed
                raise Neural4DTaskError("Model generation failed")

            await asyncio.sleep(poll_interval)

        raise Neural4DTimeoutError(f"Model {uuid} timed out after {max_wait}s")

    # ── Format Conversion ───────────────────────────────────────

    async def convert_format(
        self,
        uuid: str,
        model_type: str = "glb",
        model_size: int = 2,
    ) -> str:
        """Convert model to desired format. Returns download URL."""
        start = time.time()
        while time.time() - start < 120:
            data = await self._post_json("/api/convertToFormat", {
                "uuid": uuid,
                "modelType": model_type,
                "modelSize": model_size,
            })
            if data.get("statusType") == 0 and data.get("modelUrl"):
                return data["modelUrl"]
            await asyncio.sleep(3)
        raise Neural4DTimeoutError("Format conversion timed out")

    # ── Download ────────────────────────────────────────────────

    async def download_model(self, model_url: str, output_path: str) -> str:
        """Download model file to local path."""
        session = await self._get_session()
        async with session.get(model_url) as resp:
            resp.raise_for_status()
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                async for chunk in resp.content.iter_chunked(8192):
                    f.write(chunk)
        return output_path

    # ── Full Pipelines ──────────────────────────────────────────

    async def generate_3d_from_image(
        self,
        image_path: str,
        output_dir: str = None,
        model_name: str = "model",
        format_type: str = "glb",
        progress_callback=None,
        max_wait: int = 600,
    ) -> Neural4DGenerationResult:
        """
        Full Image-to-3D pipeline:
        matting → wait → generate → wait → convert → download.
        """
        output_dir = output_dir or str(get_output_dir())
        os.makedirs(output_dir, exist_ok=True)

        # Step 1: Matting
        if progress_callback:
            progress_callback("Removing background...", 5, None)
        request_id = await self.matting_image(image_path)

        # Step 2: Wait for matting
        if progress_callback:
            progress_callback("Processing image...", 15, None)
        file_key = await self.wait_for_matting(request_id)

        # Step 3: Generate
        if progress_callback:
            progress_callback("Generating 3D model...", 25, None)
        uuids = await self.generate_from_image_key(file_key, model_count=1)
        if not uuids:
            return Neural4DGenerationResult(
                uuid="", status=2, error_message="No model UUID returned"
            )

        # Step 4: Wait for model
        model_data = await self.wait_for_model(
            uuids[0], progress_callback=progress_callback, max_wait=max_wait
        )

        # Step 5: Convert format if needed
        if format_type != "glb":
            if progress_callback:
                progress_callback(f"Converting to {format_type}...", 85, None)
            model_url = await self.convert_format(uuids[0], format_type)
        else:
            model_url = model_data.get("modelUrl", "")

        if not model_url:
            return Neural4DGenerationResult(
                uuid=uuids[0], status=2,
                error_message="No model URL available",
            )

        # Step 6: Download
        output_path = os.path.join(output_dir, f"{model_name}.{format_type}")
        await self.download_model(model_url, output_path)

        if progress_callback:
            progress_callback("Download complete", 100, None)

        return Neural4DGenerationResult(
            uuid=uuids[0],
            status=0,
            model_path=output_path,
            model_url=model_url,
            image_url=model_data.get("imageUrl"),
        )

    async def generate_3d_from_text(
        self,
        prompt: str,
        output_dir: str = None,
        model_name: str = "model",
        format_type: str = "glb",
        progress_callback=None,
        max_wait: int = 600,
    ) -> Neural4DGenerationResult:
        """
        Full Text-to-3D pipeline:
        generate → wait → convert → download.
        """
        output_dir = output_dir or str(get_output_dir())
        os.makedirs(output_dir, exist_ok=True)

        # Step 1: Generate
        if progress_callback:
            progress_callback("Generating from text...", 10, None)
        uuids = await self.generate_from_text(prompt, model_count=1)
        if not uuids:
            return Neural4DGenerationResult(
                uuid="", status=2, error_message="No UUID returned"
            )

        # Step 2: Wait
        model_data = await self.wait_for_model(
            uuids[0], progress_callback=progress_callback, max_wait=max_wait
        )

        # Step 3: Convert if needed
        if format_type != "glb":
            if progress_callback:
                progress_callback(f"Converting to {format_type}...", 85, None)
            model_url = await self.convert_format(uuids[0], format_type)
        else:
            model_url = model_data.get("modelUrl", "")

        # Step 4: Download
        output_path = os.path.join(output_dir, f"{model_name}.{format_type}")
        await self.download_model(model_url, output_path)

        if progress_callback:
            progress_callback("Download complete", 100, None)

        return Neural4DGenerationResult(
            uuid=uuids[0],
            status=0,
            model_path=output_path,
            model_url=model_url,
            image_url=model_data.get("imageUrl"),
        )

    # ── Utilities ───────────────────────────────────────────────

    async def get_balance(self) -> Dict[str, Any]:
        """Query account points/balance.
        
        Returns the full API response. The balance/points may be in:
        - response["points"] 
        - response["data"]["points"]
        - Or other keys depending on API version
        """
        result = await self._post_json("/api/queryPointsInfo")
        # Log for debugging
        logger.info(f"Neural4D balance response: {result}")
        return result

    async def check_human_image(self, image_path: str) -> bool:
        """Check if image contains a human portrait."""
        data = await self._post_form("/api/checkHumanImage", image_path)
        return data.get("result", False)

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def validate_api_token(self) -> bool:
        """Validate token by querying balance."""
        try:
            await self.get_balance()
            return True
        except Neural4DAuthError:
            return False
