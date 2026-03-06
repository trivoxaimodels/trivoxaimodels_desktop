import os
import time
import platform
import psutil
from typing import Dict, Any, Optional
from pathlib import Path
import asyncio
import json
from datetime import datetime

from core.hitem3d_api import Hitem3DAPI
from config.settings import get_output_dir


def run_pipeline(
    image_path: str,
    name: str = "model",
    use_api: bool = False,
    api_token: Optional[str] = None,
    api_model: str = "hitem3dv1.5",
    api_resolution: str = "1024",
    api_format: str = "glb",
    output_dir: str = None,
    quality: str = "standard",
    scale: float = 1.0,
    **kwargs,
) -> dict:
    """
    Unified pipeline that supports both local processing and Cloud API.

    Args:
        image_path: Path to input image
        name: Base name for output files
        use_api: Whether to use Cloud API (True) or local processing (False)
        api_token: Cloud API access token (required if use_api=True)
        api_model: Cloud model to use (standard, high_quality, etc.)
        api_resolution: Output resolution for API (512, 1024, 1536, 1536pro)
        output_dir: Output directory for local pipeline (default: user Documents folder)
        quality: Local mesh quality: "draft", "standard", "high", "production"
        scale: Scale factor for exported mesh (local only)
        **kwargs: Additional arguments passed to local pipeline or API

    Returns:
        Dict with paths to generated files and processing stats
    """
    # Use user-writable output directory if not specified
    if output_dir is None:
        output_dir = str(get_output_dir())

    if use_api:
        credentials = resolve_hitem3d_credentials(api_token)
        if not (
            credentials["access_token"]
            or (credentials["client_id"] and credentials["client_secret"])
        ):
            raise ValueError("Cloud API credentials are required when use_api=True")
        return asyncio.run(
            _run_api_pipeline(
                image_path,
                name,
                credentials,
                api_model,
                api_resolution,
                api_format,
                **kwargs,
            )
        )
    else:
        return _run_local_pipeline(
            image_path,
            name,
            output_dir=output_dir,
            quality=quality,
            scale=scale,
            **kwargs,
        )


async def run_pipeline_async(
    image_path: str,
    name: str = "model",
    use_api: bool = False,
    api_token: Optional[str] = None,
    api_model: str = "hitem3dv1.5",
    api_resolution: str = "1024",
    api_format: str = "glb",
    output_dir: str = None,
    quality: str = "standard",
    scale: float = 1.0,
    progress_callback=None,
    **kwargs,
) -> dict:
    """
    Async-safe pipeline entrypoint for FastAPI.
    """
    # Use user-writable output directory if not specified
    if output_dir is None:
        output_dir = str(get_output_dir())

    if use_api:
        credentials = resolve_hitem3d_credentials(api_token)
        if not (
            credentials["access_token"]
            or (credentials["client_id"] and credentials["client_secret"])
        ):
            raise ValueError("Cloud API credentials are required when use_api=True")
        return await _run_api_pipeline(
            image_path,
            name,
            credentials,
            api_model,
            api_resolution,
            api_format,
            progress_callback=progress_callback,
            **kwargs,
        )
    else:
        return await asyncio.to_thread(
            _run_local_pipeline,
            image_path,
            name,
            output_dir=output_dir,
            quality=quality,
            scale=scale,
            progress_callback=progress_callback,
            **kwargs,
        )


def _run_local_pipeline(
    image_path: str,
    name: str,
    output_dir: str = None,
    quality: str = "standard",
    scale: float = 1.0,
    progress_callback=None,
    **kwargs,
) -> dict:
    """
    Run the local processing pipeline with enhanced error handling.

    Args:
        image_path: Path to input image
        name: Base name for output files
        output_dir: Output directory for mesh files
        quality: Mesh quality preset (draft, standard, high, production)
        scale: Scale factor for export
        **kwargs: Additional arguments for local pipeline

    Returns:
        Dict with paths and stats
    """
    # Use user-writable output directory if not specified
    if output_dir is None:
        output_dir = str(get_output_dir())

    t0 = time.perf_counter()
    try:
        from core.pipeline import run_pipeline as local_pipeline
    except Exception as exc:
        return {
            "error": f"Local processing failed to initialize: {exc}",
            "error_message": f"Local processing failed to initialize: {exc}",
            "obj": "",
            "stl": "",
            "glb": "",
            "stats": {
                "total_seconds": 0,
                "stages": {"load_and_infer": 0, "cleanup": 0, "export": 0},
            },
            "processing_method": "local",
            "api_used": False,
            "system_info": {},
        }

    local_min_required = 4.0  # Raised from 2.5 — TripoSR realistically needs 4GB+
    system_info: Dict[str, Any] = {}
    try:
        mem = psutil.virtual_memory()
        system_info = {
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "ram_total_gb": round(mem.total / (1024**3), 2),
            "ram_available_gb": round(mem.available / (1024**3), 2),
            "ram_required_gb": local_min_required,
        }
    except Exception:
        system_info = {}

    pre_warning = None
    if (
        system_info.get("ram_available_gb") is not None
        and system_info["ram_available_gb"] < local_min_required
    ):
        pre_warning = (
            f"Low available RAM detected for local processing ({system_info['ram_available_gb']}GB available). "
            f"TripoSR requires at least {local_min_required}GB RAM. "
            "Switching mesh quality to Draft for stability."
        )
        quality = "draft"

    try:
        result = local_pipeline(
            image_path,
            name,
            output_dir=output_dir,
            quality=quality,
            scale=scale,
            progress_callback=progress_callback,
            **kwargs,
        )

        # TripoSR no longer returns fallback sphere meshes — it raises
        # TripoSRError instead.  So if we get here, we have a real mesh.

        # Add processing method info (must come before warning logic)
        result["processing_method"] = "local"
        result["api_used"] = False
        if system_info:
            result["system_info"] = system_info

        texture_warning = (
            "Local processing bakes a simple texture map from the input "
            "image (not full PBR materials). Use Cloud API for highest "
            "quality textures."
        )
        if pre_warning:
            result["warning"] = pre_warning
        if result.get("processing_method") == "local":
            existing = result.get("warning", "")
            if existing:
                result["warning"] = f"{existing} {texture_warning}"
            else:
                result["warning"] = texture_warning

        t1 = time.perf_counter()

        return result

    except Exception as e:
        # Import the custom error class (might not be available if init failed)
        triposr_error = None
        try:
            from core.inference.triposr import TripoSRError

            if isinstance(e, TripoSRError):
                triposr_error = e
        except ImportError:
            pass

        if triposr_error:
            # Specific TripoSR failure — provide targeted guidance
            reason = triposr_error.reason
            if progress_callback:
                try:
                    progress_callback(
                        "error",
                        0,
                        f"TripoSR failed ({reason}): {str(triposr_error)[:120]}",
                    )
                except Exception:
                    pass
            error_msg = str(triposr_error)
        else:
            # Generic pipeline failure
            if progress_callback:
                try:
                    progress_callback("error", 0, f"Processing failed: {str(e)[:120]}")
                except Exception:
                    pass
            error_msg = f"Local processing failed: {str(e)}"

        return {
            "error": error_msg,
            "error_message": error_msg,
            "obj": "",
            "stl": "",
            "glb": "",
            "stats": {
                "total_seconds": round(time.perf_counter() - t0, 3),
                "stages": {"load_and_infer": 0, "cleanup": 0, "export": 0},
            },
            "processing_method": "local",
            "api_used": False,
            "system_info": system_info,
        }


async def _run_api_pipeline(
    image_path: str,
    name: str,
    credentials: Dict[str, Optional[str]],
    api_model: str,
    api_resolution: str,
    api_format: str,
    **kwargs,
) -> dict:
    """
    Run the Cloud API pipeline.

    Args:
        image_path: Path to input image
        name: Base name for output files
        api_token: Cloud API access token
        api_model: Cloud model to use
        api_resolution: Output resolution
        **kwargs: Additional arguments for API

    Returns:
        Dict with paths and stats
    """
    import trimesh
    import os

    t0 = time.perf_counter()

    # Wrap progress callback to adapt signature
    # Hitem3D API calls: callback(percent, message)
    # UI expects: callback(stage, percent, message)
    # The callback must be awaited if it's an async function
    original_callback = kwargs.get("progress_callback")
    wrapped_callback = None

    if original_callback:

        def _wrapped_progress(percent, message):
            original_callback("api", percent, message)

        wrapped_callback = _wrapped_progress
        kwargs["progress_callback"] = wrapped_callback

    # Initialize API client
    from core.unified_api import Unified3DAPI, APICredentials, APIPlatform
    
    # Check if credentials is a dict or string
    if isinstance(credentials, dict):
        access_token = credentials.get("access_token")
        client_id = credentials.get("client_id")
        client_secret = credentials.get("client_secret")
        
        # Create credentials with proper fields
        if access_token:
            unified_credentials = APICredentials(
                api_key=access_token,
                access_token=access_token,
                platform=APIPlatform.TRIPO3D
            )
        elif client_id and client_secret:
            unified_credentials = APICredentials(
                api_key=f"{client_id}:{client_secret}",
                client_id=client_id,
                client_secret=client_secret,
                platform=APIPlatform.HITEM3D
            )
        else:
            api_token_val = credentials.get("access_token", "")
            if not api_token_val and credentials.get("client_id") and credentials.get("client_secret"):
                api_token_val = f"{credentials['client_id']}:{credentials['client_secret']}"
            unified_credentials = APICredentials(api_key=api_token_val)
    else:
        api_token_val = str(credentials)
        unified_credentials = APICredentials(api_key=api_token_val)
        
    api = Unified3DAPI(credentials=unified_credentials)

    try:
        # Generate 3D model using API
        output_dir = str(get_output_dir())
        
        # Format quality
        quality_map = {
            "2048": "production",
            "1024": "high",
            "512": "standard",
            "256": "draft"
        }
        quality = quality_map.get(api_resolution, "standard")
        
        gen_result = await api.generate_from_image(
            image_path=image_path,
            output_dir=output_dir,
            model_name=name,
            quality=quality,
            format_type="glb",  # Request GLB initially for best mesh quality
            progress_callback=wrapped_callback,
            model_id=api_model,
            api_resolution=api_resolution
        )
        
        if not gen_result.success:
            raise Exception(gen_result.error_message)

        result = {"glb": gen_result.model_path}

        # Convert to multiple formats
        if wrapped_callback:
            wrapped_callback(96, "Converting to multiple formats...")

        glb_path = gen_result.model_path
        if glb_path and os.path.exists(glb_path):
            base_name = name

            try:
                # Load the mesh
                mesh = trimesh.load(glb_path, process=False)

                # Export to all formats
                formats_to_export = ["obj", "glb", "stl"]
                exported_count = 0
                for fmt in formats_to_export:
                    if fmt == "glb":
                        exported_count += 1
                        continue

                    output_path = os.path.join(output_dir, f"{base_name}.{fmt}")
                    try:
                        if isinstance(mesh, trimesh.Scene):
                            # For scenes, try to export the first mesh
                            for name_geo, geom in mesh.geometry.items():
                                geom.export(output_path, file_type=fmt)
                                result[fmt] = output_path
                                exported_count += 1
                                break
                        else:
                            mesh.export(output_path, file_type=fmt)
                            result[fmt] = output_path
                            exported_count += 1
                    except Exception as e:
                        print(f"[API Pipeline] Failed to export {fmt}: {e}")

                if wrapped_callback:
                    wrapped_callback(98, f"Exported {exported_count} formats")

            except Exception as e:
                print(f"[API Pipeline] Format conversion failed: {e}")
                # Continue with just the original file

        t1 = time.perf_counter()

        # Add processing method info and stats
        result["processing_method"] = "cloud_api"
        result["api_used"] = True
        result["api_model"] = api_model
        result["api_resolution"] = api_resolution
        result["api_format"] = api_format
        result["stats"] = {
            "total_seconds": round(t1 - t0, 3),
            "stages": {"api_processing": round(t1 - t0, 3)},
        }

        return result

    finally:
        pass # Unified3DAPI doesn't need to be closed explicitly in this context


def get_available_models(api_token: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    """
    Get available models for both local and API processing.
    Dynamically returns models based on detected platform (Tripo3D or Hitem3D).

    Args:
        api_token: Optional API token to detect platform type

    Returns:
        Dict with model information
    """
    from core.platform_features import get_available_models as get_platform_models

    # Detect platform type from token
    platform_type = "hitem3d"  # Default
    if api_token:
        if ":" in api_token:
            platform_type = "hitem3d"
        else:
            platform_type = "tripo3d"

    platform_models = get_platform_models(platform_type)

    return {
        "local": {
            "name": "Local Processing",
            "description": "Process using local GPU/CPU resources",
            "models": {
                "default": {
                    "name": "Default Local Model",
                    "description": "Standard local 3D generation model",
                }
            },
        },
        "api": platform_models.get(
            "api",
            {
                "name": "Cloud API",
                "description": "Cloud-based 3D generation service",
                "models": {},
            },
        ),
        "features": platform_models.get("features", {}),
        "generation_modes": platform_models.get("generation_modes", []),
    }


def detect_platform_type(api_token: Optional[str] = None) -> str:
    """
    Detect which platform type the API token belongs to.

    Args:
        api_token: API token or credentials string

    Returns:
        'tripo3d', 'hitem3d', or 'unknown'
    """
    if not api_token:
        return "unknown"

    # Tripo3D keys start with 'tsk_' and don't contain colons
    if api_token.startswith("tsk_") and ":" not in api_token:
        return "tripo3d"

    # Hitem3D uses client_id:secret format
    if ":" in api_token:
        return "hitem3d"

    # Default assumption for long keys without colons
    if len(api_token) > 30 and ":" not in api_token:
        return "tripo3d"

    return "hitem3d"


async def validate_api_token(token: str) -> bool:
    """
    Validate Cloud API token by making a test request.

    Args:
        token: API access token to validate

    Returns:
        True if token is valid, False otherwise
    """
    try:
        credentials = resolve_hitem3d_credentials(token)
        api = Hitem3DAPI(
            access_token=credentials["access_token"],
            client_id=credentials["client_id"],
            client_secret=credentials["client_secret"],
        )
        is_valid = await api.validate_access_token()
        await api.close()
        return is_valid
    except Exception:
        return False


async def get_hitem3d_balance(api_token: Optional[str]) -> Dict[str, Any]:
    credentials = resolve_hitem3d_credentials(api_token)
    if not (
        credentials["access_token"]
        or (credentials["client_id"] and credentials["client_secret"])
    ):
        return {"available": None, "error": "credentials_missing"}
    api = Hitem3DAPI(
        access_token=credentials["access_token"],
        client_id=credentials["client_id"],
        client_secret=credentials["client_secret"],
    )
    try:
        result = await api.get_balance()
    finally:
        await api.close()
    balance = result.get("balance")
    return {"available": balance}


def save_api_credentials(api_token: str) -> Dict[str, Optional[str]]:
    """
    Save API credentials for either Tripo3D or Hitem3D.

    Args:
        api_token: API token - can be:
            - Tripo3D: single API key (e.g., "tsk_...")
            - Hitem3D: "access_key:secret_key" format

    Returns:
        Dictionary with credential information
    """
    token_value = (api_token or "").strip()
    if not token_value:
        raise ValueError("API token is required")

    # Detect platform type
    platform_type = "tripo3d"
    access_token = token_value
    client_id = None
    client_secret = None

    if ":" in access_token:
        # Hitem3D format: access_key:secret_key
        parts = access_token.split(":", 1)
        if len(parts) == 2 and parts[0] and parts[1]:
            client_id, client_secret = parts[0].strip(), parts[1].strip()
            access_token = None
            platform_type = "hitem3d"
    elif access_token.startswith("tsk_"):
        # Tripo3D format
        platform_type = "tripo3d"

    # Save to unified credentials file
    data = {
        "platform": platform_type,
        "access_token": access_token or "",
        "client_id": client_id or "",
        "client_secret": client_secret or "",
        "saved_at": datetime.utcnow().isoformat(),
    }

    def get_user_data_dir() -> Path:
        import os
        from pathlib import Path

        if os.name == "nt":
            appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
            return Path(appdata) / "trivoxaimodels"
        return Path(os.path.expanduser("~")) / ".trivoxaimodels"

    config_dir = get_user_data_dir() / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    target = config_dir / "api_credentials.json"

    with open(target, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"[Credentials] Saved {platform_type} credentials to {target}")

    return {
        "platform": platform_type,
        "access_token": access_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }


# Keep old function name for backward compatibility
def save_hitem3d_credentials(api_token: str) -> Dict[str, Optional[str]]:
    """Backward compatibility - redirects to unified save function."""
    return save_api_credentials(api_token)


def resolve_hitem3d_credentials(api_token: Optional[str]) -> Dict[str, Optional[str]]:
    """Resolve API credentials from various sources."""
    token_value = (api_token or "").strip()
    if token_value:
        access_token = token_value
        client_id = None
        client_secret = None
        if ":" in access_token:
            parts = access_token.split(":", 1)
            if len(parts) == 2 and parts[0] and parts[1]:
                client_id, client_secret = parts[0].strip(), parts[1].strip()
                access_token = None
        return {
            "access_token": access_token,
            "client_id": client_id,
            "client_secret": client_secret,
        }

    from core.secret_manager import get_secret

    # 1. Check Env Vars (Local override)
    access_token = (
        os.getenv("HITEM3D_ACCESS_TOKEN")
        or os.getenv("HITEM3D_API_TOKEN")
        or os.getenv("TRIPO_API_KEY")
    )
    client_id = os.getenv("HITEM3D_CLIENT_ID")
    client_secret = os.getenv("HITEM3D_CLIENT_SECRET")

    # 2. Check Secret Manager (Supabase app_secrets table)
    if not (access_token or (client_id and client_secret)):
        # Try fetching from secure cloud config (requires license)
        access_token = get_secret("TRIPO_API_KEY") or get_secret("HITEM3D_API_TOKEN")

        # If stored as separate ID/Secret
        if not access_token:
            client_id = get_secret("HITEM3D_CLIENT_ID")
            client_secret = get_secret("HITEM3D_CLIENT_SECRET")

    # 3. Check model_api_keys Supabase table (admin-managed keys)
    if not (access_token or (client_id and client_secret)):
        try:
            from core.supabase_client import get_supabase_client
            sb = get_supabase_client()
            if sb:
                # Try Tripo3D key first
                result = sb.table("model_api_keys").select("key_value").eq(
                    "key_name", "TRIPO_API_KEY"
                ).eq("is_active", True).limit(1).execute()
                rows = result.data or []
                if rows and rows[0].get("key_value"):
                    access_token = rows[0]["key_value"]
                else:
                    # Try Hitem3D keys
                    result = sb.table("model_api_keys").select("key_name, key_value").eq(
                        "model_id", "hitem3d"
                    ).eq("is_active", True).execute()
                    rows = result.data or []
                    for r in rows:
                        if r.get("key_name") == "HITEM3D_CLIENT_ID" and r.get("key_value"):
                            client_id = r["key_value"]
                        elif r.get("key_name") == "HITEM3D_CLIENT_SECRET" and r.get("key_value"):
                            client_secret = r["key_value"]
        except Exception:
            pass

    def get_user_data_dir() -> Path:
        import os
        from pathlib import Path

        if os.name == "nt":
            appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
            return Path(appdata) / "trivoxaimodels"
        return Path(os.path.expanduser("~")) / ".trivoxaimodels"

    config_dir = get_user_data_dir() / "config"

    # First check new unified credentials file
    unified_file = config_dir / "api_credentials.json"
    if unified_file.exists():
        try:
            with open(unified_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            file_access_token = data.get("access_token") or data.get("token")
            file_client_id = data.get("client_id")
            file_client_secret = data.get("client_secret")

            access_token = access_token or file_access_token
            client_id = client_id or file_client_id
            client_secret = client_secret or file_client_secret
        except Exception:
            pass

    # Fallback to old credential files
    if not access_token and not client_id:
        base_dir = Path(__file__).resolve().parents[1]
        try_files = [
            config_dir / "hitem3d_credentials.json",
            base_dir / "hitem3d_credentials.json",
            Path("config") / "hitem3d_credentials.json",
            Path("hitem3d_credentials.json"),
        ]
        for p in try_files:
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    file_access_token = data.get("access_token") or data.get("token")
                    file_client_id = data.get("client_id")
                    file_client_secret = data.get("client_secret")
                    access_token = access_token or file_access_token
                    client_id = client_id or file_client_id
                    client_secret = client_secret or file_client_secret
                    break
                except Exception:
                    pass

    # Parse combined token if needed
    if access_token and not (client_id or client_secret):
        if ":" in access_token:
            parts = access_token.split(":", 1)
            if len(parts) == 2 and parts[0] and parts[1]:
                client_id, client_secret = parts[0].strip(), parts[1].strip()
                access_token = None

    return {
        "access_token": access_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }


def load_saved_api_credentials() -> Optional[Dict[str, Any]]:
    """
    Load saved API credentials for display in UI.

    Returns:
        Dictionary with token string and platform type, or None if no credentials saved
    """

    def get_user_data_dir() -> Path:
        import os
        from pathlib import Path

        if os.name == "nt":
            appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
            return Path(appdata) / "trivoxaimodels"
        return Path(os.path.expanduser("~")) / ".trivoxaimodels"

    config_dir = get_user_data_dir() / "config"
    creds_file = config_dir / "api_credentials.json"

    if not creds_file.exists():
        return None

    try:
        with open(creds_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        platform = data.get("platform", "unknown")

        # Reconstruct token string based on platform
        if platform == "hitem3d":
            client_id = data.get("client_id", "")
            client_secret = data.get("client_secret", "")
            if client_id and client_secret:
                return {
                    "token": f"{client_id}:{client_secret}",
                    "platform": platform,
                }
        else:
            access_token = data.get("access_token", "")
            if access_token:
                return {
                    "token": access_token,
                    "platform": platform,
                }

        return None
    except Exception as e:
        print(f"[Credentials] Failed to load saved credentials: {e}")
        return None
