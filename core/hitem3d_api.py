import os
import time
import base64
import mimetypes
import httpx
import asyncio
import io
import zipfile
import argparse
from typing import Optional, Dict, Any
from pathlib import Path
from config.settings import get_output_dir


class InsufficientBalanceError(Exception):
    pass


class Hitem3DAPI:
    """
    Hitem3D API client for 3D model generation from images.

    API Documentation: https://docs.hitem3d.ai/en/api/api-reference/list/create-task
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        base_url: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ):
        from config.settings import get_web_api_url
        proxy_url = f"{get_web_api_url().rstrip('/')}/proxy/hitem3d"
        
        from core.device_fingerprint import get_device_fingerprint
        self.device_fp = get_device_fingerprint()
        
        self.access_token = None
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = (base_url or proxy_url).rstrip("/")
        self.client = httpx.AsyncClient(timeout=60.0)
        self._set_access_token(access_token or "proxy_mode")

    def _set_access_token(self, access_token: Optional[str]) -> None:
        if access_token and not (self.client_id or self.client_secret):
            parsed = self._parse_compound_token(access_token)
            if parsed:
                self.client_id, self.client_secret = parsed
                self.access_token = None
                return
        self.access_token = access_token

    @staticmethod
    def _parse_compound_token(token: str) -> Optional[tuple]:
        if ":" not in token:
            return None
        client_id, client_secret = token.split(":", 1)
        if client_id and client_secret:
            return client_id.strip(), client_secret.strip()
        return None

    async def _fetch_access_token(self) -> str:
        if not self.client_id or not self.client_secret:
            raise Exception(
                "Hitem3D client_id/client_secret required to obtain access token"
            )
        basic = base64.b64encode(
            f"{self.client_id}:{self.client_secret}".encode("utf-8")
        ).decode("utf-8")
        url = f"{self.base_url}/open-api/v1/auth/token"
        headers = {
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/json",
        }
        response = await self.client.post(url, headers=headers, json={})
        if response.status_code != 200:
            raise Exception(
                f"Token request failed: {response.status_code} - {response.text}"
            )
        result = response.json()
        if result.get("code") != 200:
            message = result.get("message") or result.get("msg") or "Unknown error"
            raise Exception(f"Token request error: {message}")
        token = (result.get("data") or {}).get("accessToken")
        if not token:
            raise Exception("Token response missing accessToken")
        self.access_token = token
        return token

    async def _get_access_token(self) -> str:
        if self.access_token:
            return self.access_token
        return await self._fetch_access_token()

    async def _authorized_headers(self) -> Dict[str, str]:
        token = await self._get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "X-Device-Fingerprint": self.device_fp,
        }

    async def _request(self, method: str, url: str, **kwargs) -> httpx.Response:
        headers = kwargs.pop("headers", {})
        auth_headers = await self._authorized_headers()
        response = await self.client.request(
            method, url, headers={**headers, **auth_headers}, **kwargs
        )
        if response.status_code == 401 and self.client_id and self.client_secret:
            self.access_token = None
            auth_headers = await self._authorized_headers()
            response = await self.client.request(
                method, url, headers={**headers, **auth_headers}, **kwargs
            )
        return response

    async def create_task(
        self,
        image_path: str,
        model: str = "hitem3dv1.5",
        request_type: int = 3,  # 3 = both geometry+texture
        resolution: str = "1024",
        format_type: int = 1,  # 1 = obj format
        face_count: int = 1000000,
        callback_url: Optional[str] = None,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """
        Create a new 3D generation task.

        Args:
            image_path: Path to the input image
            model: Model version (hitem3dv1.5, hitem3dv2.0, scene-portraitv1.5, etc.)
            request_type: 1=mesh only, 2=texture only, 3=both geometry+texture
            resolution: Output resolution (512, 1024, 1536, 1536pro)
            format_type: Output format (1=obj, 2=glb, 3=stl, 4=fbx, 5=usdz)
            face_count: Number of faces (100000-2000000)
            callback_url: Optional callback URL for status updates
            progress_callback: Optional callback(percent, message) for progress updates

        Returns:
            Dict containing task_id and status
        """
        url = f"{self.base_url}/open-api/v1/submit-task"

        # Report upload start
        if progress_callback:
            progress_callback(5, f"Uploading image to Cloud API...")

        # Prepare form data
        form_data = {
            "request_type": request_type,
            "model": model,
            "resolution": resolution,
            "format": format_type,
            "face": face_count,
        }

        if callback_url:
            form_data["callback_url"] = callback_url

        # Read image file
        with open(image_path, "rb") as f:
            content_type = (
                mimetypes.guess_type(image_path)[0] or "application/octet-stream"
            )
            files = {"images": (os.path.basename(image_path), f, content_type)}

            response = await self._request("POST", url, data=form_data, files=files)

        if response.status_code != 200:
            raise Exception(
                f"API request failed: {response.status_code} - {response.text}"
            )

        result = response.json()
        if result.get("code") != 200:
            msg = result.get("msg") or "Unknown error"
            if result.get("code") == 30010000 or "balance" in str(msg).lower():
                raise InsufficientBalanceError(
                    "Cloud API balance is not enough. If you are on a trial, please contact admin at contact@trivoxaimodels.com to request trial credits."
                )
            raise Exception(f"API error: {msg}")

        # Report task created
        task_id = result["data"].get("task_id", "unknown")
        if progress_callback:
            progress_callback(10, f"Task created (ID: {task_id[:12]}...)")

        return result["data"]

    async def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get the status of a task.

        Args:
            task_id: The task ID returned by create_task

        Returns:
            Dict containing task status and result URLs
        """
        url = f"{self.base_url}/open-api/v1/query-task"

        params = {"task_id": task_id}

        response = await self._request("GET", url, params=params)

        if response.status_code != 200:
            raise Exception(
                f"API request failed: {response.status_code} - {response.text}"
            )

        result = response.json()
        if result.get("code") != 200:
            raise Exception(f"API error: {result.get('msg', 'Unknown error')}")

        return result["data"]

    async def download_model(self, download_url: str, output_path: str) -> str:
        """
        Download the generated 3D model.

        Args:
            download_url: URL to download the model from
            output_path: Local path to save the model

        Returns:
            Path to the downloaded file
        """
        # Ensure directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        for attempt in range(3):
            try:
                # Use a FRESH client for the download to avoid SSL session reuse failures
                # that happen after long polling periods
                async with httpx.AsyncClient(timeout=300.0) as fresh_client:
                    response = await fresh_client.get(download_url, follow_redirects=True)
                    response.raise_for_status()

                    content = response.content
                    if content[:4] == b"PK\x03\x04":
                        with zipfile.ZipFile(io.BytesIO(content)) as zf:
                            ext = os.path.splitext(output_path)[1].lower()
                            names = [n for n in zf.namelist() if not n.endswith("/")]
                            preferred = [n for n in names if ext and n.lower().endswith(ext)]
                            target = preferred[0] if preferred else (names[0] if names else None)
                            if not target:
                                raise Exception("Download failed: empty zip archive")
                            data = zf.read(target)
                        with open(output_path, "wb") as f:
                            f.write(data)
                        return output_path
                        
                    with open(output_path, "wb") as f:
                        f.write(content)
                    return output_path

            except httpx.HTTPError as e:
                if attempt == 2:
                    raise Exception(f"Failed to download model after 3 attempts: {str(e)}")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
            except Exception as e:
                if attempt == 2:
                    raise Exception(f"Failed to download model due to unexpected error: {str(e)}")
                await asyncio.sleep(2 ** attempt)

    async def wait_for_completion(
        self,
        task_id: str,
        poll_interval: int = 5,
        max_wait_time: int = 1800,
        progress_callback=None,
    ) -> Dict[str, Any]:
        """
        Wait for task completion with polling.

        Args:
            task_id: The task ID to wait for
            poll_interval: Seconds between status checks
            max_wait_time: Maximum seconds to wait
            progress_callback: Optional callback(percent, message) for progress updates

        Returns:
            Final task status with download URLs
        """
        start_time = time.time()
        last_progress_update = 0
        last_state = None

        # Initial progress
        if progress_callback:
            progress_callback(10, "Task submitted, waiting for processing...")

        while time.time() - start_time < max_wait_time:
            elapsed = time.time() - start_time
            status = await self.get_task_status(task_id)

            # Get current state from API response
            state = (
                status.get("state")
                or status.get("status")
                or status.get("task_status")
                or status.get("taskState")
            )

            # Calculate progress based on elapsed time (typical processing takes 2-5 minutes)
            # Progress from 15% to 90% based on elapsed time up to 10 minutes
            estimated_total = 600  # 10 minutes estimate
            progress_pct = min(90, 15 + int((elapsed / estimated_total) * 75))

            # Determine detailed status message based on state
            state_str = (
                str(state or "").lower() if not isinstance(state, (int, float)) else ""
            )
            state_int = int(state) if isinstance(state, (int, float)) else None

            # Build detailed message based on status
            if state_int is not None:
                # Numeric state codes
                if state_int == 0 or state_int == 1:
                    status_msg = "Waiting in queue..."
                elif state_int == 2 or state_int == 200:
                    status_msg = "Processing completed"
                elif state_int == 3:
                    status_msg = "Processing..."
                elif state_int == -1 or state_int == 500:
                    status_msg = "Processing failed"
                else:
                    status_msg = f"Status code: {state_int}"
            else:
                # String state
                if state_str in {"queued", "pending", "waiting"}:
                    status_msg = "Waiting in queue..."
                elif state_str in {"processing", "running", "working"}:
                    status_msg = "AI is generating 3D model..."
                elif state_str in {
                    "success",
                    "succeeded",
                    "completed",
                    "complete",
                    "finish",
                    "finished",
                    "done",
                    "ok",
                }:
                    status_msg = "Processing completed"
                elif state_str in {"failed", "error", "cancelled", "timeout"}:
                    status_msg = "Processing failed"
                elif state_str:
                    status_msg = f"Status: {state_str}"
                else:
                    status_msg = "Checking status..."

            # Update progress on state change or every 5 seconds (not 10)
            state_changed = state != last_state
            time_to_update = elapsed - last_progress_update >= 5

            if progress_callback and (
                state_changed or time_to_update or progress_pct >= 90
            ):
                # Add more descriptive stage messages for cloud processing
                stage_msg = status_msg
                if progress_pct < 15:
                    stage_msg = "🚀 Initializing cloud pipeline..."
                elif progress_pct < 40:
                    stage_msg = f"⏳ Processing on cloud ({int(elapsed)}s)"
                elif progress_pct < 70:
                    stage_msg = f"⚡ Generating 3D model ({int(elapsed)}s)"
                elif progress_pct < 95:
                    stage_msg = f"📦 Preparing download ({int(elapsed)}s)"
                else:
                    stage_msg = "✅ Waiting for completion"

                progress_callback(progress_pct, stage_msg)
                last_progress_update = elapsed
                last_state = state

            # Check completion states
            if isinstance(state, (int, float)):
                s = int(state)
                if s in (2, 200):
                    return status
                if s in (-1, 500):
                    raise Exception(
                        f"Task failed: {status.get('error', 'Unknown error')}"
                    )
            else:
                s = str(state or "").lower()
                if s in {
                    "success",
                    "succeeded",
                    "completed",
                    "complete",
                    "finish",
                    "finished",
                    "done",
                    "ok",
                }:
                    return status
                if s in {"failed", "error", "cancelled", "timeout"}:
                    raise Exception(
                        f"Task failed: {status.get('error', 'Unknown error')}"
                    )

            # Check if result URLs are available
            if any(
                k in status and status.get(k)
                for k in (
                    "url",
                    "download_url",
                    "obj_url",
                    "stl_url",
                    "glb_url",
                    "fbx_url",
                    "usdz_url",
                )
            ):
                return status

            await asyncio.sleep(poll_interval)

        raise Exception(f"Task timeout after {max_wait_time} seconds")

    async def generate_3d_model(
        self,
        image_path: str,
        output_dir: str = None,
        model_name: str = "model",
        **kwargs,
    ) -> Dict[str, str]:
        """
        Complete pipeline: create task, wait for completion, download results.

        Args:
            image_path: Path to input image
            output_dir: Directory to save outputs (default: user Documents folder)
            model_name: Base name for output files
            **kwargs: Additional arguments for create_task

        Returns:
            Dict with paths to generated files
        """
        # Use user-writable output directory if not specified
        if output_dir is None:
            output_dir = str(get_output_dir())

        # Extract progress_callback before passing to create_task
        progress_callback = kwargs.pop("progress_callback", None)

        # Create task
        task_data = await self.create_task(image_path, **kwargs)
        task_id = task_data["task_id"]

        poll_interval = kwargs.get("poll_interval", 5)
        max_wait_time = kwargs.get("max_wait_time", 1800)
        final_status = await self.wait_for_completion(
            task_id,
            poll_interval=poll_interval,
            max_wait_time=max_wait_time,
            progress_callback=progress_callback,
        )

        results = {}
        output_base = os.path.join(output_dir, model_name)

        format_type = kwargs.get("format_type")
        format_map = {1: "obj", 2: "glb", 3: "stl", 4: "fbx", 5: "usdz"}
        ext = format_map.get(format_type, "glb")

        def _guess_ext(u: str) -> str:
            ul = (u or "").lower()
            if ul.endswith(".obj"):
                return "obj"
            if ul.endswith(".stl"):
                return "stl"
            if ul.endswith(".glb"):
                return "glb"
            if ul.endswith(".fbx"):
                return "fbx"
            if ul.endswith(".usdz"):
                return "usdz"
            return ext

        if progress_callback:
            progress_callback(95, "Downloading 3D model...")

        generic_url = final_status.get("url") or final_status.get("download_url")
        if generic_url:
            gx = _guess_ext(generic_url)
            output_path = f"{output_base}.{gx}"
            await self.download_model(generic_url, output_path)
            results[gx] = output_path
        for key, kext in (
            ("obj_url", "obj"),
            ("stl_url", "stl"),
            ("glb_url", "glb"),
            ("fbx_url", "fbx"),
            ("usdz_url", "usdz"),
        ):
            u = final_status.get(key)
            if u:
                out = f"{output_base}.{kext}"
                await self.download_model(u, out)
                results[kext] = out

        if progress_callback:
            progress_callback(100, "Complete!")

        return results

    def _extract_balance_value(self, payload: Any) -> Optional[float]:
        if payload is None:
            return None
        if isinstance(payload, str):
            cleaned = payload.strip().replace(",", "")
            try:
                return float(cleaned)
            except Exception:
                return None
        if isinstance(payload, (int, float)):
            return float(payload)
        if isinstance(payload, list):
            for item in payload:
                value = self._extract_balance_value(item)
                if value is not None:
                    return value
        if isinstance(payload, dict):
            candidates = [
                "balance",
                "credit",
                "credits",
                "credit_balance",
                "credit_remain",
                "remaining",
                "remain",
                "available",
                "total_available",
                "left",
                "amount",
            ]
            for key in candidates:
                if key in payload:
                    value = payload.get(key)
                    parsed = self._extract_balance_value(value)
                    if parsed is not None:
                        return parsed
            for key, value in payload.items():
                key_lower = str(key).lower()
                if "credit" in key_lower or "balance" in key_lower:
                    if any(
                        flag in key_lower
                        for flag in (
                            "remain",
                            "remaining",
                            "available",
                            "left",
                            "total",
                        )
                    ):
                        parsed = self._extract_balance_value(value)
                        if parsed is not None:
                            return parsed
            for key in ("data", "result", "info"):
                value = self._extract_balance_value(payload.get(key))
                if value is not None:
                    return value
        return None

    async def get_balance(self) -> Dict[str, Any]:
        endpoints = [
            ("GET", "/open-api/v1/balance"),
            ("GET", "/open-api/v1/account/balance"),
            ("GET", "/open-api/v1/user/balance"),
            ("GET", "/open-api/v1/credit/balance"),
            ("GET", "/open-api/v1/credit/query"),
            ("GET", "/open-api/v1/usage/balance"),
            ("GET", "/open-api/v1/balance/query"),
            ("GET", "/open-api/v1/account/info"),
            ("GET", "/open-api/v1/user/info"),
            ("POST", "/open-api/v1/credit/query"),
            ("POST", "/open-api/v1/credit/balance"),
        ]
        for method, path in endpoints:
            url = f"{self.base_url}{path}"
            response = await self._request(method, url)
            if response.status_code == 404:
                continue
            if response.status_code != 200:
                continue
            try:
                result = response.json()
            except Exception:
                continue
            payload = result
            if isinstance(result, dict) and "data" in result:
                payload = result.get("data")
            balance = self._extract_balance_value(payload)
            if balance is not None or result:
                return {"balance": balance, "raw": result}
        return {"balance": None, "raw": None}

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def validate_access_token(self) -> bool:
        try:
            await self._get_access_token()
        except Exception:
            return False
        url = f"{self.base_url}/open-api/v1/query-task"
        response = await self._request("GET", url, params={"task_id": "__invalid__"})
        if response.status_code in (401, 403):
            return False
        return True


def repair_output_dir(output_dir: str = None) -> Dict[str, int]:
    # Use user-writable output directory if not specified
    if output_dir is None:
        output_dir = str(get_output_dir())

    exts = {".obj", ".stl", ".glb", ".fbx", ".usdz"}
    fixed = 0
    skipped = 0
    failed = 0
    for path in Path(output_dir).glob("*"):
        if not path.is_file() or path.suffix.lower() not in exts:
            continue
        data = path.read_bytes()
        if data[:4] != b"PK\x03\x04":
            skipped += 1
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                names = [n for n in zf.namelist() if not n.endswith("/")]
                preferred = [
                    n for n in names if n.lower().endswith(path.suffix.lower())
                ]
                target = preferred[0] if preferred else (names[0] if names else None)
                if not target:
                    raise Exception("empty zip archive")
                content = zf.read(target)
            path.write_bytes(content)
            fixed += 1
        except Exception:
            failed += 1
    return {"fixed": fixed, "skipped": skipped, "failed": failed}


def _main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("repair-output")
    p.add_argument("--dir", default=str(get_output_dir()))
    args = parser.parse_args()
    if args.cmd == "repair-output":
        result = repair_output_dir(args.dir)
        print(
            f"fixed={result['fixed']} skipped={result['skipped']} failed={result['failed']}"
        )


if __name__ == "__main__":
    _main()
