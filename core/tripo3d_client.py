"""
Tripo3D API Integration Module for Trivox AI Models

Production-ready client for Tripo3D API with support for:
- Image-to-3D generation
- Text-to-3D generation
- Multi-view-to-3D generation
- Model format conversion (obj, glb, stl, fbx, usdz)
- Animation/rigging support
- Model refinement
- Style transfer
- Async/await support
- Progress callbacks
- Comprehensive error handling

Official Python SDK: tripo3d
API Keys format: tsk_*
"""

import os
import time
import asyncio
import base64
import mimetypes
from typing import Optional, Dict, Any, List, Callable, Union, BinaryIO
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import aiohttp
from config.settings import get_output_dir
import aiofiles

from core.logger import get_logger, log_exception

logger = get_logger(__name__)


class Tripo3DError(Exception):
    """Base exception for Tripo3D API errors."""

    pass


class Tripo3DAuthError(Tripo3DError):
    """Authentication error (invalid API key)."""

    pass


class Tripo3DInsufficientBalanceError(Tripo3DError):
    """Insufficient balance/credits error."""

    pass


class Tripo3DTaskError(Tripo3DError):
    """Task creation or execution error."""

    pass


class Tripo3DTimeoutError(Tripo3DError):
    """Task timeout error."""

    pass


class ModelVersion(str, Enum):
    """Available Tripo3D model versions."""

    V2_5 = "v2.5-20250123"  # Default, latest
    V2_0 = "v2.0-20240919"
    V1_4 = "v1.4-20240625"


class TaskStatus(str, Enum):
    """Task status values."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OutputFormat(str, Enum):
    """Supported output formats."""

    OBJ = "obj"
    GLB = "glb"
    STL = "stl"
    FBX = "fbx"
    USDZ = "usdz"


class AnimationStyle(str, Enum):
    """Animation/rigging styles."""

    HUMAN = "human"
    QUADRUPED = "quadruped"
    FLYING = "flying"
    SWIMMING = "swimming"


class StyleType(str, Enum):
    """Model stylization types."""

    CARTOON = "cartoon"
    CLAY = "clay"
    SKETCH = "sketch"
    PIXEL = "pixel"
    ANIME = "anime"
    REALISTIC = "realistic"


@dataclass
class Tripo3DTask:
    """Represents a Tripo3D generation task."""

    task_id: str
    status: TaskStatus
    type: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    progress: int = 0
    result_urls: Dict[str, str] = field(default_factory=dict)
    error_message: Optional[str] = None
    model_version: str = ModelVersion.V2_5
    credit_cost: float = 0.0

    @property
    def is_complete(self) -> bool:
        """Check if task is complete (success or failed)."""
        return self.status in (
            TaskStatus.SUCCESS,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        )

    @property
    def is_success(self) -> bool:
        """Check if task completed successfully."""
        return self.status == TaskStatus.SUCCESS


@dataclass
class Tripo3DBalance:
    """Represents account balance information."""

    total_credits: float
    used_credits: float
    remaining_credits: float
    currency: str = "USD"

    @property
    def has_credits(self) -> bool:
        """Check if there are remaining credits."""
        return self.remaining_credits > 0


@dataclass
class GenerationResult:
    """Result from 3D generation."""

    task_id: str
    status: TaskStatus
    model_path: Optional[str] = None
    texture_path: Optional[str] = None
    all_files: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


ProgressCallback = Callable[[str, int, Optional[str]], None]


class Tripo3DClient:
    """
    Production-ready Tripo3D API client.

    Features:
    - Image-to-3D, Text-to-3D, Multi-view generation
    - Format conversion, animation, refinement, stylization
    - Async support with progress callbacks
    - Automatic retry logic
    - Comprehensive error handling

    Usage:
        client = Tripo3DClient(api_key="tsk_...")

        # Image to 3D
        result = await client.image_to_model("image.jpg")

        # Text to 3D
        result = await client.text_to_model("a red sports car")

        # With progress callback
        def on_progress(task_id, progress, message):
            print(f"Progress: {progress}% - {message}")

        result = await client.image_to_model(
            "image.jpg",
            progress_callback=on_progress
        )
    """

    # Refactored for Web Proxy
    from config.settings import get_web_api_url
    BASE_URL = f"{get_web_api_url().rstrip('/')}/proxy/tripo3d"
    API_VERSION = ""

    # Credit costs per operation (approximate)
    CREDIT_COSTS = {
        "image_to_model": 20,
        "text_to_model": 25,
        "multiview_to_model": 30,
        "convert_model": 5,
        "animate_model": 10,
        "refine_model": 15,
        "stylize_model": 15,
    }

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: int = 300,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize Tripo3D client.

        Args:
            api_key: Tripo3D API key (starts with 'tsk_')
            base_url: Optional custom API base URL
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
            retry_delay: Delay between retries in seconds
        """
        # Proxy architecture means api_key isn't strictly Tripo's anymore - the web app handles it.
        # But we pass the user's Device Fingerprint so the Web App can verify balance and credits.
        from core.device_fingerprint import get_device_fingerprint
        self.api_key = api_key or "proxy_mode"
        self.device_fp = get_device_fingerprint()
        
        self.base_url = (base_url or self.BASE_URL).rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._session: Optional[aiohttp.ClientSession] = None

        self._validate_api_key()

        logger.info(
            "Tripo3D client initialized",
            context={
                "base_url": self.base_url,
                "timeout": timeout,
                "max_retries": max_retries,
            },
        )

    def _validate_api_key(self) -> None:
        """API Validation is deferred to Web Proxy."""
        pass

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    "X-Device-Fingerprint": self.device_fp,
                    "Content-Type": "application/json",
                    "User-Agent": "ImageTo3D-Pro/1.0",
                },
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            )
        return self._session

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        files: Optional[Dict] = None,
        params: Optional[Dict] = None,
        retry_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Make HTTP request to Tripo3D API with retry logic.

        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint path
            data: JSON data payload
            files: Files to upload
            params: URL parameters
            retry_count: Current retry attempt

        Returns:
            Response data as dictionary
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        session = await self._get_session()

        try:
            if files:
                # Multipart form data for file uploads
                form_data = aiohttp.FormData()
                for key, (filename, file_data, content_type) in files.items():
                    form_data.add_field(
                        key,
                        file_data,
                        filename=filename,
                        content_type=content_type,
                    )

                # Add other form fields
                if data:
                    for key, value in data.items():
                        form_data.add_field(key, str(value))

                async with session.post(url, data=form_data) as response:
                    return await self._handle_response(response)
            else:
                # JSON request
                async with session.request(
                    method, url, json=data, params=params
                ) as response:
                    return await self._handle_response(response)

        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if retry_count < self.max_retries:
                logger.warning(
                    f"Request failed, retrying ({retry_count + 1}/{self.max_retries}): {e}"
                )
                await asyncio.sleep(self.retry_delay * (retry_count + 1))
                return await self._make_request(
                    method, endpoint, data, files, params, retry_count + 1
                )
            raise Tripo3DError(f"Request failed after {self.max_retries} retries: {e}")

    async def _handle_response(
        self, response: aiohttp.ClientResponse
    ) -> Dict[str, Any]:
        """Handle API response and errors."""
        try:
            data = await response.json()
        except Exception:
            text = await response.text()
            data = {"message": text}

        if response.status == 401:
            error_msg = data.get("message", data.get("error", "")).lower()
            if "expired" in error_msg or "login" in error_msg:
                raise Tripo3DAuthError(
                    "API key expired or invalid. Note: Free Wallet credits cannot be used via API. "
                    "You need API Wallet credits (shown as 0/100 in your account). "
                    "Please add paid credits or use Hitem3D API instead."
                )
            raise Tripo3DAuthError("Invalid API key or authentication failed")

        if response.status == 402:
            raise Tripo3DInsufficientBalanceError(
                "Insufficient API Wallet balance. Note: Free Wallet credits (600 available) "
                "cannot be used via API - only API Wallet credits work. "
                "Please add credits to your API Wallet or use Hitem3D API instead."
            )

        if response.status == 429:
            raise Tripo3DError("Rate limit exceeded. Please try again later.")

        if not response.ok:
            error_msg = data.get("message", data.get("error", "Unknown error"))
            # Improve error messages for common issues
            error_lower = error_msg.lower()
            if "expired" in error_lower or "login" in error_lower:
                raise Tripo3DAuthError(
                    "API authentication failed. Note: Free Wallet credits cannot be used via API. "
                    "You have 600 Free Wallet credits but 0 API Wallet credits. "
                    "Please add paid credits to your API Wallet or use Hitem3D API instead."
                )
            raise Tripo3DError(f"API error ({response.status}): {error_msg}")

        return data

    async def get_balance(self) -> Tripo3DBalance:
        """
        Get current account balance.

        Returns:
            Tripo3DBalance with credit information
        """
        logger.debug("Fetching account balance")

        # According to Tripo3D API docs, the endpoint is /user/balance
        # But the API might return 404 if the user doesn't have API wallet credits
        # Try the task endpoint first to validate the API key works
        try:
            # First try to get user info to validate API key
            data = await self._make_request("GET", "/user/balance")
            logger.info(f"Tripo3D balance response: {data}")
            
            balance_data = data.get("data", data)
            
            balance = Tripo3DBalance(
                total_credits=float(balance_data.get("total", 0)),
                used_credits=float(balance_data.get("used", 0)),
                remaining_credits=float(balance_data.get("remaining", 0)),
                currency=balance_data.get("currency", "USD"),
            )
            
            logger.info(
                "Balance retrieved",
                context={
                    "remaining": balance.remaining_credits,
                    "currency": balance.currency,
                },
            )
            return balance
        except Exception as e:
            error_str = str(e)
            # If 404, the API key might be valid but balance endpoint not available
            if "404" in error_str:
                logger.warning("Tripo3D balance endpoint returned 404 - API key may not have API wallet access")
                # Return a balance that indicates manual setup needed
                raise Tripo3DError(
                    "Tripo3D balance API not accessible. This usually means:\n"
                    "1. Your API key is valid but doesn't have API Wallet credits\n"
                    "2. Tripo3D requires paid API credits (not Free Wallet credits)\n"
                    "Please check your Tripo3D account at https://platform.tripo3d.ai\n"
                    "You can manually enter credits in the admin panel."
                )
            raise

    @log_exception
    async def image_to_model(
        self,
        image_path: Union[str, Path, BinaryIO],
        model_version: ModelVersion = ModelVersion.V2_5,
        output_format: OutputFormat = OutputFormat.GLB,
        pbr: bool = True,
        texture_resolution: int = 1024,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> GenerationResult:
        """
        Generate 3D model from a single image.

        Args:
            image_path: Path to image file or file-like object
            model_version: Model version to use
            output_format: Desired output format
            pbr: Generate PBR materials
            texture_resolution: Texture resolution (512, 1024, 2048)
            progress_callback: Optional callback for progress updates

        Returns:
            GenerationResult with task info and file paths
        """
        logger.info(
            "Starting image-to-model generation",
            context={
                "model_version": model_version,
                "output_format": output_format,
                "pbr": pbr,
            },
        )

        # Prepare image data
        if isinstance(image_path, (str, Path)):
            image_path = Path(image_path)
            if not image_path.exists():
                raise Tripo3DError(f"Image file not found: {image_path}")

            content_type = mimetypes.guess_type(str(image_path))[0] or "image/jpeg"
            with open(image_path, "rb") as f:
                file_data = f.read()
            filename = image_path.name
        else:
            file_data = image_path.read()
            filename = "image.jpg"
            content_type = "image/jpeg"

        # Create task
        files = {
            "image": (filename, file_data, content_type),
        }

        data = {
            "model_version": model_version,
            "output_format": output_format,
            "pbr": pbr,
            "texture_resolution": texture_resolution,
        }

        response = await self._make_request(
            "POST", "/task/image-to-model", data=data, files=files
        )

        task_id = response["data"]["task_id"]
        logger.info(f"Task created: {task_id}")

        # Wait for completion
        task = await self._wait_for_completion(
            task_id, progress_callback=progress_callback
        )

        # Download results
        download_paths = await self._download_task_models(task, output_dir=None)

        return GenerationResult(
            task_id=task_id,
            status=task.status,
            model_path=download_paths.get(output_format.value),
            texture_path=download_paths.get("texture"),
            all_files=download_paths,
            metadata={
                "model_version": model_version,
                "pbr": pbr,
                "texture_resolution": texture_resolution,
            },
        )

    @log_exception
    async def text_to_model(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        model_version: ModelVersion = ModelVersion.V2_5,
        output_format: OutputFormat = OutputFormat.GLB,
        pbr: bool = True,
        texture_resolution: int = 1024,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> GenerationResult:
        """
        Generate 3D model from text description.

        Args:
            prompt: Text description of desired 3D model
            negative_prompt: Things to avoid in generation
            model_version: Model version to use
            output_format: Desired output format
            pbr: Generate PBR materials
            texture_resolution: Texture resolution
            progress_callback: Optional callback for progress updates

        Returns:
            GenerationResult with task info and file paths
        """
        logger.info(
            "Starting text-to-model generation",
            context={
                "prompt": prompt[:100],
                "model_version": model_version,
            },
        )

        data = {
            "prompt": prompt,
            "model_version": model_version,
            "output_format": output_format,
            "pbr": pbr,
            "texture_resolution": texture_resolution,
        }

        if negative_prompt:
            data["negative_prompt"] = negative_prompt

        response = await self._make_request("POST", "/task/text-to-model", data=data)

        task_id = response["data"]["task_id"]
        logger.info(f"Task created: {task_id}")

        task = await self._wait_for_completion(
            task_id, progress_callback=progress_callback
        )

        download_paths = await self._download_task_models(task, output_dir=None)

        return GenerationResult(
            task_id=task_id,
            status=task.status,
            model_path=download_paths.get(output_format.value),
            texture_path=download_paths.get("texture"),
            all_files=download_paths,
            metadata={
                "prompt": prompt,
                "model_version": model_version,
                "pbr": pbr,
            },
        )

    @log_exception
    async def multiview_to_model(
        self,
        image_paths: List[Union[str, Path]],
        model_version: ModelVersion = ModelVersion.V2_5,
        output_format: OutputFormat = OutputFormat.GLB,
        pbr: bool = True,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> GenerationResult:
        """
        Generate 3D model from multiple view images.

        Args:
            image_paths: List of image file paths (2-6 images recommended)
            model_version: Model version to use
            output_format: Desired output format
            pbr: Generate PBR materials
            progress_callback: Optional callback for progress updates

        Returns:
            GenerationResult with task info and file paths
        """
        if len(image_paths) < 2:
            raise Tripo3DError(
                "At least 2 images are required for multiview generation"
            )

        if len(image_paths) > 6:
            logger.warning(f"More than 6 images provided. Using first 6.")
            image_paths = image_paths[:6]

        logger.info(
            "Starting multiview-to-model generation",
            context={
                "num_images": len(image_paths),
                "model_version": model_version,
            },
        )

        # Prepare files
        files = {}
        for i, path in enumerate(image_paths):
            path = Path(path)
            if not path.exists():
                raise Tripo3DError(f"Image file not found: {path}")

            content_type = mimetypes.guess_type(str(path))[0] or "image/jpeg"
            with open(path, "rb") as f:
                file_data = f.read()

            files[f"image_{i}"] = (path.name, file_data, content_type)

        data = {
            "model_version": model_version,
            "output_format": output_format,
            "pbr": pbr,
        }

        response = await self._make_request(
            "POST", "/task/multiview-to-model", data=data, files=files
        )

        task_id = response["data"]["task_id"]
        logger.info(f"Task created: {task_id}")

        task = await self._wait_for_completion(
            task_id, progress_callback=progress_callback
        )

        download_paths = await self._download_task_models(task, output_dir=None)

        return GenerationResult(
            task_id=task_id,
            status=task.status,
            model_path=download_paths.get(output_format.value),
            texture_path=download_paths.get("texture"),
            all_files=download_paths,
            metadata={
                "num_images": len(image_paths),
                "model_version": model_version,
                "pbr": pbr,
            },
        )

    async def get_task(self, task_id: str) -> Tripo3DTask:
        """
        Get task status and details.

        Args:
            task_id: Task ID to check

        Returns:
            Tripo3DTask with current status
        """
        response = await self._make_request("GET", f"/task/{task_id}")

        data = response.get("data", response)

        return Tripo3DTask(
            task_id=task_id,
            status=TaskStatus(data.get("status", "queued")),
            type=data.get("type", "unknown"),
            created_at=datetime.fromisoformat(
                data.get("created_at", datetime.utcnow().isoformat())
            ),
            completed_at=datetime.fromisoformat(data["completed_at"])
            if data.get("completed_at")
            else None,
            progress=data.get("progress", 0),
            result_urls=data.get("result", {}),
            error_message=data.get("error"),
            model_version=data.get("model_version", ModelVersion.V2_5),
            credit_cost=data.get("credit_cost", 0.0),
        )

    async def _wait_for_completion(
        self,
        task_id: str,
        poll_interval: int = 5,
        max_wait_time: int = 1800,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Tripo3DTask:
        """
        Poll task until completion.

        Args:
            task_id: Task ID to wait for
            poll_interval: Seconds between status checks
            max_wait_time: Maximum seconds to wait
            progress_callback: Optional callback for progress updates

        Returns:
            Completed Tripo3DTask
        """
        logger.info(f"Waiting for task completion: {task_id}")
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            task = await self.get_task(task_id)

            if progress_callback:
                progress_callback(task_id, task.progress, task.status.value)

            if task.is_complete:
                if task.is_success:
                    logger.info(
                        f"Task completed successfully: {task_id}",
                        context={"duration": time.time() - start_time},
                    )
                    return task
                else:
                    raise Tripo3DTaskError(
                        f"Task failed: {task.error_message or 'Unknown error'}"
                    )

            logger.debug(
                f"Task {task_id} progress: {task.progress}%",
                context={"status": task.status.value},
            )

            await asyncio.sleep(poll_interval)

        raise Tripo3DTimeoutError(
            f"Task timeout after {max_wait_time} seconds: {task_id}"
        )

    async def _download_task_models(
        self,
        task: Tripo3DTask,
        output_dir: Optional[Union[str, Path]] = None,
    ) -> Dict[str, str]:
        """
        Download all models from a completed task.

        Args:
            task: Completed Tripo3DTask
            output_dir: Directory to save files (None for temp dir)

        Returns:
            Dictionary mapping format to file path
        """
        if output_dir is None:
            output_dir = get_output_dir()
        else:
            output_dir = Path(output_dir)

        output_dir.mkdir(parents=True, exist_ok=True)

        downloaded = {}

        for format_name, url in task.result_urls.items():
            if not url:
                continue

            # Determine file extension
            if format_name == "texture":
                ext = ".png"
            elif format_name in [f.value for f in OutputFormat]:
                ext = f".{format_name}"
            else:
                ext = ".bin"

            filename = f"{task.task_id}_{format_name}{ext}"
            filepath = output_dir / filename

            logger.debug(f"Downloading {format_name}: {url}")

            session = await self._get_session()
            async with session.get(url) as response:
                if response.status == 200:
                    async with aiofiles.open(filepath, "wb") as f:
                        await f.write(await response.read())
                    downloaded[format_name] = str(filepath)
                    logger.info(f"Downloaded: {filepath}")
                else:
                    logger.error(f"Failed to download {format_name}: {response.status}")

        return downloaded

    async def download_task_models(
        self,
        task: Union[str, Tripo3DTask],
        output_dir: Union[str, Path],
    ) -> Dict[str, str]:
        """
        Download models for a task.

        Args:
            task: Task ID or Tripo3DTask object
            output_dir: Directory to save files

        Returns:
            Dictionary mapping format to file path
        """
        if isinstance(task, str):
            task = await self.get_task(task)

        return await self._download_task_models(task, output_dir)

    async def convert_model(
        self,
        task_id: str,
        output_format: OutputFormat,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> GenerationResult:
        """
        Convert existing model to different format.

        Args:
            task_id: Original task ID
            output_format: Target format
            progress_callback: Optional callback for progress updates

        Returns:
            GenerationResult with converted model
        """
        logger.info(
            f"Converting model {task_id} to {output_format}",
        )

        data = {
            "task_id": task_id,
            "output_format": output_format.value,
        }

        response = await self._make_request("POST", "/task/convert", data=data)

        new_task_id = response["data"]["task_id"]
        logger.info(f"Conversion task created: {new_task_id}")

        task = await self._wait_for_completion(
            new_task_id, progress_callback=progress_callback
        )

        download_paths = await self._download_task_models(task, output_dir=None)

        return GenerationResult(
            task_id=new_task_id,
            status=task.status,
            model_path=download_paths.get(output_format.value),
            all_files=download_paths,
            metadata={
                "original_task": task_id,
                "output_format": output_format.value,
                "operation": "convert",
            },
        )

    async def animate_model(
        self,
        task_id: str,
        rig_type: AnimationStyle = AnimationStyle.HUMAN,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> GenerationResult:
        """
        Add animation/rigging to a model.

        Args:
            task_id: Original task ID
            rig_type: Type of rigging (human, quadruped, etc.)
            progress_callback: Optional callback for progress updates

        Returns:
            GenerationResult with animated model
        """
        logger.info(
            f"Adding animation to model {task_id}",
            context={"rig_type": rig_type},
        )

        data = {
            "task_id": task_id,
            "rig_type": rig_type.value,
        }

        response = await self._make_request("POST", "/task/animate", data=data)

        new_task_id = response["data"]["task_id"]
        logger.info(f"Animation task created: {new_task_id}")

        task = await self._wait_for_completion(
            new_task_id, progress_callback=progress_callback
        )

        download_paths = await self._download_task_models(task, output_dir=None)

        return GenerationResult(
            task_id=new_task_id,
            status=task.status,
            model_path=download_paths.get("glb"),
            all_files=download_paths,
            metadata={
                "original_task": task_id,
                "rig_type": rig_type.value,
                "operation": "animate",
            },
        )

    async def refine_model(
        self,
        task_id: str,
        iterations: int = 1,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> GenerationResult:
        """
        Refine/enhance model quality.

        Args:
            task_id: Original task ID
            iterations: Number of refinement iterations
            progress_callback: Optional callback for progress updates

        Returns:
            GenerationResult with refined model
        """
        logger.info(
            f"Refining model {task_id}",
            context={"iterations": iterations},
        )

        data = {
            "task_id": task_id,
            "iterations": iterations,
        }

        response = await self._make_request("POST", "/task/refine", data=data)

        new_task_id = response["data"]["task_id"]
        logger.info(f"Refinement task created: {new_task_id}")

        task = await self._wait_for_completion(
            new_task_id, progress_callback=progress_callback
        )

        download_paths = await self._download_task_models(task, output_dir=None)

        return GenerationResult(
            task_id=new_task_id,
            status=task.status,
            model_path=download_paths.get("glb"),
            all_files=download_paths,
            metadata={
                "original_task": task_id,
                "iterations": iterations,
                "operation": "refine",
            },
        )

    async def stylize_model(
        self,
        task_id: str,
        style: StyleType,
        strength: float = 0.8,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> GenerationResult:
        """
        Apply style transfer to a model.

        Args:
            task_id: Original task ID
            style: Style to apply (cartoon, clay, etc.)
            strength: Style strength (0.0-1.0)
            progress_callback: Optional callback for progress updates

        Returns:
            GenerationResult with stylized model
        """
        logger.info(
            f"Stylizing model {task_id}",
            context={"style": style, "strength": strength},
        )

        data = {
            "task_id": task_id,
            "style": style.value,
            "strength": max(0.0, min(1.0, strength)),
        }

        response = await self._make_request("POST", "/task/stylize", data=data)

        new_task_id = response["data"]["task_id"]
        logger.info(f"Stylization task created: {new_task_id}")

        task = await self._wait_for_completion(
            new_task_id, progress_callback=progress_callback
        )

        download_paths = await self._download_task_models(task, output_dir=None)

        return GenerationResult(
            task_id=new_task_id,
            status=task.status,
            model_path=download_paths.get("glb"),
            all_files=download_paths,
            metadata={
                "original_task": task_id,
                "style": style.value,
                "strength": strength,
                "operation": "stylize",
            },
        )

    async def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a running task.

        Args:
            task_id: Task ID to cancel

        Returns:
            True if cancelled successfully
        """
        logger.info(f"Cancelling task: {task_id}")

        try:
            await self._make_request("POST", f"/task/{task_id}/cancel")
            logger.info(f"Task cancelled: {task_id}")
            return True
        except Tripo3DError as e:
            logger.error(f"Failed to cancel task: {e}")
            return False

    async def list_tasks(
        self,
        limit: int = 20,
        offset: int = 0,
        status: Optional[TaskStatus] = None,
    ) -> List[Tripo3DTask]:
        """
        List recent tasks.

        Args:
            limit: Maximum number of tasks to return
            offset: Pagination offset
            status: Filter by status

        Returns:
            List of Tripo3DTask objects
        """
        params = {
            "limit": limit,
            "offset": offset,
        }

        if status:
            params["status"] = status.value

        response = await self._make_request("GET", "/tasks", params=params)

        tasks = []
        for task_data in response.get("data", []):
            tasks.append(
                Tripo3DTask(
                    task_id=task_data["task_id"],
                    status=TaskStatus(task_data.get("status", "queued")),
                    type=task_data.get("type", "unknown"),
                    created_at=datetime.fromisoformat(
                        task_data.get("created_at", datetime.utcnow().isoformat())
                    ),
                    completed_at=datetime.fromisoformat(task_data["completed_at"])
                    if task_data.get("completed_at")
                    else None,
                    progress=task_data.get("progress", 0),
                    result_urls=task_data.get("result", {}),
                    error_message=task_data.get("error"),
                    model_version=task_data.get("model_version", ModelVersion.V2_5),
                    credit_cost=task_data.get("credit_cost", 0.0),
                )
            )

        return tasks

    async def validate_api_key(self) -> bool:
        """
        Validate the API key by checking balance.

        Returns:
            True if API key is valid
        """
        try:
            await self.get_balance()
            return True
        except Tripo3DAuthError:
            return False
        except Exception as e:
            logger.error(f"API validation error: {e}")
            return False

    async def close(self) -> None:
        """Close HTTP session and cleanup resources."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.debug("Tripo3D client session closed")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()


# Convenience functions for non-async usage

import functools


def run_async(coro):
    """Run async coroutine in sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're in an async context, schedule the coroutine
            return asyncio.create_task(coro)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(coro)


class Tripo3DSyncClient:
    """
    Synchronous wrapper for Tripo3DClient.

    For users who prefer synchronous code:

        client = Tripo3DSyncClient(api_key="tsk_...")
        result = client.image_to_model("image.jpg")
    """

    def __init__(self, *args, **kwargs):
        self._async_client = Tripo3DClient(*args, **kwargs)

    def __getattr__(self, name):
        attr = getattr(self._async_client, name)
        if asyncio.iscoroutinefunction(attr):

            @functools.wraps(attr)
            def wrapper(*args, **kwargs):
                return run_async(attr(*args, **kwargs))

            return wrapper
        return attr

    def close(self):
        """Close the client."""
        run_async(self._async_client.close())

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


__all__ = [
    # Client classes
    "Tripo3DClient",
    "Tripo3DSyncClient",
    # Exceptions
    "Tripo3DError",
    "Tripo3DAuthError",
    "Tripo3DInsufficientBalanceError",
    "Tripo3DTaskError",
    "Tripo3DTimeoutError",
    # Enums
    "ModelVersion",
    "TaskStatus",
    "OutputFormat",
    "AnimationStyle",
    "StyleType",
    # Data classes
    "Tripo3DTask",
    "Tripo3DBalance",
    "GenerationResult",
    # Type alias
    "ProgressCallback",
]
