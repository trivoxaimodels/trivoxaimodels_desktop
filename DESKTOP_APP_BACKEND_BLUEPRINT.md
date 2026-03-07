# TrivoxModels Desktop App — Complete Backend Blueprint

> **Purpose**: This document is a **self-contained specification** for another AI model to implement the full desktop app backend by mirroring the web app (`I:\TrivoxAIModels_BACKUP`). Follow every section in order; nothing is optional unless marked `[OPTIONAL]`.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Supabase Configuration](#2-supabase-configuration)
3. [Device Fingerprint & Anti-Tamper System](#3-device-fingerprint--anti-tamper-system)
4. [Authentication & Session Management](#4-authentication--session-management)
5. [Credit System](#5-credit-system)
6. [Payment Integration (Gumroad)](#6-payment-integration-gumroad)
7. [3D Generation Pipeline — Fixing the Local Processing Bug](#7-3d-generation-pipeline--fixing-the-local-processing-bug)
8. [Cloud API Integration (Tripo3D / Hitem3D / Meshy / Neural4D)](#8-cloud-api-integration)
9. [Admin Dashboard](#9-admin-dashboard)
10. [License Manager](#10-license-manager)
11. [Desktop-Specific Supabase Tables](#11-desktop-specific-supabase-tables)
12. [File-by-File Implementation Checklist](#12-file-by-file-implementation-checklist)
13. [Known Bugs & Fixes](#13-known-bugs--fixes)
14. [Environment Variables & .env Configuration](#14-environment-variables--env-configuration)
15. [Build & Distribution](#15-build--distribution)

---

## 1. Architecture Overview

### Web App Architecture (source of truth)

```
I:\TrivoxAIModels_BACKUP\
├── config/
│   ├── settings.py          # Centralized configs (ProcessingConfig, APIConfig, UIConfig)
│   ├── payment_config.py    # Payment provider configs (Gumroad, Razorpay, Stripe, etc.)
│   └── *.json               # Auth, device fingerprint, credentials caches
├── core/
│   ├── auth.py              # bcrypt password auth, session tokens
│   ├── server_auth.py       # Server-side device auth with TAMPER DETECTION
│   ├── credit_manager.py    # Full credit system (register, deduct, purchase, refund)
│   ├── device_fingerprint.py # Hardware fingerprint (CPU, mobo, disk, MAC, BIOS, GUID)
│   ├── license_manager.py   # License key validation, trial tracking, admin license
│   ├── payment_factory.py   # Unified payment processor interface
│   ├── admin_manager.py     # Admin model management, user tracking, sales tracker
│   ├── supabase_client.py   # Supabase connection (uses SERVICE ROLE key)
│   ├── secret_manager.py    # Reads API keys from Supabase app_secrets
│   ├── unified_api.py       # Multi-provider 3D API client (Tripo3D, Hitem3D, Meshy, Neural4D)
│   ├── unified_pipeline.py  # Pipeline orchestrator (local + cloud)
│   ├── pipeline.py          # Local TripoSR inference pipeline
│   ├── hitem3d_api.py       # Hitem3D specific client
│   ├── tripo3d_client.py    # Tripo3D specific client
│   ├── meshy_ai_client.py   # Meshy AI client
│   ├── neural4d_client.py   # Neural4D client
│   ├── user_db.py           # SQLite user DB (web-only, NOT needed for desktop)
│   ├── providers/
│   │   ├── base.py          # Abstract payment provider
│   │   ├── gumroad.py       # Gumroad payment provider
│   │   └── razorpay.py      # Razorpay payment provider
│   ├── inference/
│   │   ├── model_manager.py # ModelManager wrapper
│   │   ├── triposr.py       # TripoSR local inference engine
│   │   └── triposr_direct.py # Direct TripoSR (alternative)
│   └── postprocess/
│       ├── cleanup.py       # Mesh cleanup
│       └── advanced_mesh_processor.py  # Advanced mesh post-processing
└── ui/web/
    └── api.py               # FastAPI backend (4957 lines, 71+ endpoints)
```

### Desktop App Target Architecture

```
I:\trivoxmodels_desktop_app\
├── config/
│   ├── settings.py          # [MODIFY] Add local_min_ram_gb, TripoSR configs
│   ├── payment_config.py    # [KEEP] Already identical to web
│   └── __init__.py
├── core/
│   ├── supabase_client.py   # [MODIFY] Fix key handling (see Section 2)
│   ├── device_fingerprint.py # [MODIFY] Harden anti-tamper (see Section 3)
│   ├── session_manager.py    # [MODIFY] Add tamper detection (see Section 4)
│   ├── credit_manager.py     # [MODIFY] Add full purchase flow (see Section 5)
│   ├── server_auth.py        # [NEW] Copy from web app (see Section 4)
│   ├── auth.py               # [NEW] Copy from web app
│   ├── license_manager.py    # [NEW] Copy from web app (see Section 10)
│   ├── payment_factory.py    # [NEW] Copy from web app (see Section 6)
│   ├── admin_manager.py      # [NEW] Copy from web app (see Section 9)
│   ├── secret_manager.py     # [NEW] Copy from web app
│   ├── unified_api.py        # [KEEP] Already identical
│   ├── unified_pipeline.py   # [MODIFY] Fix local pipeline bug (see Section 7)
│   ├── pipeline.py           # [NEW] Copy from web app (see Section 7)
│   ├── hitem3d_api.py        # [KEEP] Already identical
│   ├── tripo3d_client.py     # [KEEP] Already identical
│   ├── meshy_ai_client.py    # [KEEP] Already identical
│   ├── neural4d_client.py    # [KEEP] Already identical
│   ├── platform_features.py  # [NEW] Copy from web app
│   ├── exporter.py           # [NEW] Copy from web app
│   ├── user_db.py            # [NOT NEEDED] Web-only SQLite (desktop uses Supabase)
│   ├── providers/
│   │   ├── __init__.py       # [NEW]
│   │   ├── base.py           # [NEW] Copy from web app
│   │   └── gumroad.py        # [NEW] Copy from web app
│   ├── inference/
│   │   ├── model_manager.py  # [NEW] Copy from web app
│   │   ├── triposr.py        # [NEW] Copy from web app
│   │   └── triposr_direct.py # [NEW] Copy from web app
│   └── postprocess/
│       ├── cleanup.py        # [NEW] Copy from web app
│       └── advanced_mesh_processor.py  # [NEW] Copy from web app
├── ui/
│   ├── auth_dialog.py        # [MODIFY] Add password registration login (see Section 4)
│   ├── main_window.py        # [MODIFY] Fix generation, add payment UI (see Sections 5,6,7)
│   └── styles/               # [KEEP]
└── main.py                   # [MODIFY] Initialize new modules
```

---

## 2. Supabase Configuration

### CRITICAL: Key Differences Between Web and Desktop

The web app uses the **service_role** key (`SUPABASE_KEY`), which bypasses Row Level Security (RLS).
The desktop app currently uses the **anon** key (`SUPABASE_ANON_KEY`), which is restricted by RLS.

**Problem**: The desktop app cannot write to many tables (e.g., `registered_devices`, `credit_ledger`, `user_generations`) because RLS is NOT enabled on these tables (as shown in the Supabase schema), but the anon key still has limited permissions compared to service_role.

**Solution**: The desktop app should use the **service_role key** (same as web) since it's a trusted app (compiled binary, not a browser). Update `core/supabase_client.py`:

```python
# FILE: core/supabase_client.py — MODIFIED

import os, sys
from pathlib import Path
from supabase import create_client, Client

# Auto-load .env (same logic as web app)
try:
    _candidates = []
    _candidates.append(Path(__file__).resolve().parent.parent / ".env")
    if getattr(sys, 'frozen', False):
        _exe_dir = Path(sys.executable).resolve().parent
        _candidates.append(_exe_dir / ".env")
        _meipass = getattr(sys, '_MEIPASS', None)
        if _meipass:
            _candidates.append(Path(_meipass) / ".env")
        _appdata = os.environ.get("APPDATA", "")
        if _appdata:
            _candidates.append(Path(_appdata) / "TrivoxModels" / ".env")
    for _env_path in _candidates:
        if _env_path.exists():
            for line in _env_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
            break
except Exception:
    pass


class SupabaseClient:
    _instance = None
    _client = None

    @classmethod
    def get_client(cls) -> Client:
        if cls._client is None:
            url = os.environ.get("SUPABASE_URL")
            # IMPORTANT: Use service_role key for desktop app (trusted binary)
            # This is the SAME key the web app uses
            key = (os.environ.get("SUPABASE_KEY")
                   or os.environ.get("SUPABASE_ANON_KEY"))
            if url and key:
                cls._client = create_client(url, key)
        return cls._client


def get_supabase() -> Client:
    return SupabaseClient.get_client()

get_supabase_client = get_supabase
```

### .env File for Desktop App

```env
# Required
SUPABASE_URL=https://hovggmmmmledvmnmeuff.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhvdmdnbW1tbWxlZHZtbm1ldWZmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTg2NjU0MiwiZXhwIjoyMDg3NDQyNTQyfQ.l9d7qyh6YRJ8zTaSiSb2YROERnHEkDM8ktMnR6_Q8UE

# For Gumroad payment (required for credit purchase)
GUMROAD_ACCESS_TOKEN=GRifd1Uz_c0TJDytcWE9zpqubTpMjIRCVbXeYTgvocM

# Optional: Override output dir
OUTPUT_DIR=
```

### Live Supabase Tables (14 tables, all confirmed present)

| # | Table | Rows | Purpose |
|---|-------|------|---------|
| 1 | `web_users` | 5 | User accounts (username, password_hash, trial) |
| 2 | `user_credits` | 5 | Credit balance per user |
| 3 | `credit_ledger` | 9 | Audit trail for credit changes |
| 4 | `app_secrets` | 3 | API keys stored securely |
| 5 | `payment_transactions` | 0 | Payment records from any provider |
| 6 | `gumroad_sales` | 0 | Gumroad-specific sale tracking |
| 7 | `model_api_keys` | 5 | Admin-managed API keys per model |
| 8 | `user_generations` | 6 | Generation history per user |
| 9 | `cloud_model_config` | 4 | Model enable/disable configs |
| 10 | `app_admins` | 0 | Admin role assignments |
| 11 | `user_profiles` | 0 | Device info, usage stats |
| 12 | `registered_devices` | 1 | Device fingerprint tracking |
| 13 | `usage_logs` | 0 | Detailed usage logging |
| 14 | `licenses` | 0 | License key tracking |

> **No new tables are needed.** The existing schema supports both web and desktop.

---

## 3. Device Fingerprint & Anti-Tamper System

### The Problem

Users can **reinstall the app to get another free trial credit**. The current desktop fingerprint caches to a local JSON file (`config/device_fp.json`). If deleted, the app just regenerates it — but the **same hardware fingerprint** is produced.

The web app already has the solution: `registered_devices` table on Supabase tracks fingerprints server-side, and `server_auth.py` detects tamper attempts.

### Implementation Steps

#### 3.1. Copy web app's `core/server_auth.py` to desktop

This file is the **key anti-tamper module**. It already works with the same Supabase tables. Copy it as-is from `I:\TrivoxAIModels_BACKUP\core\server_auth.py` → `I:\trivoxmodels_desktop_app\core\server_auth.py`.

Functions provided:
- `check_device_server(fingerprint)` — Checks if device exists in `registered_devices`
- `register_device_server(fingerprint, password_hash, ...)` — Registers new device
- `verify_device_login_server(fingerprint)` — Gets stored password for verification
- `use_trial_server(fingerprint)` — **Atomically** consumes 1 trial credit on server
- `report_tamper_attempt(fingerprint, reason)` — Logs tamper attempt, increments counter
- `get_trial_remaining_server(fingerprint)` — Gets server-side trial count

#### 3.2. Keep existing `core/device_fingerprint.py` (hardware collection)

The current desktop `device_fingerprint.py` collects hardware info but is simpler than the web version. **Replace it with the web version** (`I:\TrivoxAIModels_BACKUP\core\device_fingerprint.py`) which collects:
- CPU ID (via WMIC)
- Motherboard serial
- Disk serial
- MAC address
- BIOS serial
- Windows Machine GUID (from registry)

This produces a **SHA-256 fingerprint** that is identical on the same hardware regardless of app reinstallation.

#### 3.3. Anti-tamper flow (implemented in session_manager.py)

```
App Launch
    │
    ├─ Generate device fingerprint (SHA-256 of hardware IDs)
    │
    ├─ Call check_device_server(fingerprint)
    │   │
    │   ├─ If NOT found → New device → Allow registration
    │   │   └─ register_device_server() → Creates entry with trial_remaining=1
    │   │
    │   ├─ If found AND registered → Returning user
    │   │   ├─ Check if local auth files exist
    │   │   │   ├─ If YES → Normal login flow
    │   │   │   └─ If NO  → TAMPER DETECTED!
    │   │   │       ├─ report_tamper_attempt(fingerprint, "Local files deleted")
    │   │   │       ├─ Increment tamper_attempts in registered_devices
    │   │   │       └─ If tamper_attempts >= 3 → BAN device (is_banned=True)
    │   │   └─ Check trial_remaining from SERVER (not local cache)
    │   │
    │   └─ If found AND banned → Show "Device banned" error, exit
    │
    └─ Save server state to local cache (for offline fallback)
```

#### 3.4. Key rule: NEVER trust local trial counter

The `registered_devices` table has `trial_remaining` and `trial_used` columns. **Always read these from the server.** The local cache is **read-only fallback** for offline mode.

```python
# CORRECT: Server-authoritative trial check
from core.server_auth import get_trial_remaining_server, use_trial_server

remaining = get_trial_remaining_server(fingerprint)
if remaining > 0:
    result = use_trial_server(fingerprint)  # Atomic server-side decrement
    if result["success"]:
        # Allow generation
```

```python
# WRONG: Local-only trial check (can be tampered by deleting files)
trial_data = load_local_trial_file()
if trial_data["remaining"] > 0:  # DO NOT DO THIS
    ...
```

---

## 4. Authentication & Session Management

### 4.1. Auth Methods (same as web app)

The desktop app should support **3 auth methods** (web app supports all 3):

1. **Device fingerprint login** — Primary for desktop. Auto-registers on first launch.
2. **Username/password login** — Same `web_users` table. User creates account via registration.
3. **OAuth (Google/GitHub)** — Via Supabase Auth, opens system browser for callback.

### 4.2. Modify `session_manager.py` — Add Server Auth

The current `session_manager.py` already has the basic structure. Add tamper detection:

```python
# In SessionManager.login_with_device():

from core.server_auth import (
    check_device_server,
    register_device_server,
    verify_device_login_server,
    use_trial_server,
    report_tamper_attempt,
)
from core.device_fingerprint import get_device_fingerprint

def login_with_device(self) -> dict:
    fp = get_device_fingerprint()
    
    # 1. Check server for this device
    server_state = check_device_server(fp)
    
    if not server_state["online"]:
        # Offline fallback — use local cache
        return self._offline_login(fp)
    
    if server_state.get("is_banned"):
        return {
            "success": False,
            "error": f"Device banned: {server_state.get('ban_reason', 'Policy violation')}"
        }
    
    if not server_state["found"]:
        # New device — register with 1 trial credit
        reg_result = register_device_server(
            fingerprint=fp,
            password_hash="",  # No password for device login
            machine_name=platform.node(),
            platform_info=platform.platform(),
            app_version="1.0.0",
        )
        if reg_result["success"]:
            # Create session
            self._session = UserSession(
                user_id=fp,  # Use fingerprint as user_id for device auth
                device_fingerprint=fp,
                trial_remaining=1,
                is_authenticated=True,
                auth_method="device",
            )
            return {"success": True, "trial_remaining": 1}
    
    else:
        # Existing device — check for tampering
        local_cache = self._load_local_cache()
        if server_state["registered"] and not local_cache:
            # Local files deleted but server has record = TAMPER ATTEMPT
            report_tamper_attempt(fp, "Local auth files deleted after registration")
        
        # Use server-authoritative trial count
        self._session = UserSession(
            user_id=fp,
            device_fingerprint=fp,
            trial_remaining=server_state.get("trial_remaining", 0),
            is_authenticated=True,
            auth_method="device",
        )
        
        # Save server state to local cache
        self._save_local_cache(server_state)
        
        return {
            "success": True,
            "trial_remaining": server_state.get("trial_remaining", 0),
        }
```

### 4.3. Copy `core/auth.py` from web app

This provides:
- `hash_password(plain)` — bcrypt hashing
- `verify_password(plain)` — Verifies against stored hash
- `set_password(plain)` — Stores password hash
- `create_session_token()` — HMAC signed tokens
- `verify_session_token(token)` — Token validation

### 4.4. Modify `auth_dialog.py` — Add username/password registration

Current auth dialog has device login + OAuth buttons. Add:
- **Registration tab** with username, password, email fields
- Calls `credit_manager.register_user()` (same as web)
- On success, auto-logs in and shows credit balance

---

## 5. Credit System

### 5.1. How credits work (identical to web app)

```
Credit Costs per Operation:
┌─────────────────────────┬──────────┐
│ Operation               │ Credits  │
├─────────────────────────┼──────────┤
│ Local Processing        │ 1        │
│ Cloud API 512px         │ 15       │
│ Cloud API 1024px        │ 20       │
│ Cloud API 1536px        │ 50       │
│ Cloud API 1536pro       │ 70       │
└─────────────────────────┴──────────┘

Credit Packs (sold via Gumroad):
┌──────────────┬────────┬─────────┬──────────────┐
│ Pack         │ Price  │ Credits │ Gumroad ID   │
├──────────────┼────────┼─────────┼──────────────┤
│ Micro        │ ₹99    │ 40      │ sijpb        │
│ Small        │ ₹199   │ 100     │ ershej       │
│ Medium       │ ₹799   │ 500     │              │
│ Large        │ ₹2499  │ 2000    │              │
│ Starter/mo   │ ₹499   │ 100     │              │
│ Pro/mo       │ ₹999   │ 300     │              │
│ Enterprise/mo│ ₹4999  │ 2000    │              │
└──────────────┴────────┴─────────┴──────────────┘
```

### 5.2. Copy `core/credit_manager.py` from web app

The web app's credit_manager.py is the **single source of truth**. It provides:

- `register_user(username, password, email, ip_address)` → Creates `web_users` + `user_credits` entries
- `verify_user_login(username, password)` → Validates credentials against Supabase
- `get_user_balance(user_id)` → Returns trial info + credit balance + cost preview
- `can_generate(user_id, resolution)` → Checks if user can generate (trial or credits)
- `deduct_credits(user_id, resolution, model_id, ...)` → Atomically deducts credits
- `mark_generation_complete(generation_id, success, ...)` → Marks done or **refunds on failure**
- `add_credits_from_purchase(user_id, platform, ...)` → Adds credits after purchase
- `admin_grant_credits(user_id, credits, reason)` → Admin manual grant
- `process_refund(platform_transaction_id)` → Handles refund
- `get_master_api_key(provider)` → Gets admin's master API key from `model_api_keys`

### 5.3. Credit deduction flow in desktop app

In `ui/main_window.py`, the `GenerationWorker.run()` must be modified to:

```python
# BEFORE generation:
from core.credit_manager import can_generate, deduct_credits, mark_generation_complete

# 1. Check if user can generate
can, reason, cost = can_generate(user_id, resolution)
if not can:
    self.error.emit(f"Cannot generate: {reason}")
    return

# 2. Deduct credits (creates user_generations entry with status="processing")
deduction = deduct_credits(user_id, resolution, model_id, input_type, output_format)
if not deduction["success"]:
    self.error.emit(f"Credit deduction failed: {deduction.get('error')}")
    return

generation_id = deduction["generation_id"]

# 3. Run actual generation...
try:
    result = await run_pipeline_async(...)
    
    # 4. Mark success
    mark_generation_complete(generation_id, success=True, time_ms=elapsed_ms)
    
except Exception as e:
    # 5. Mark failure → credits are REFUNDED automatically
    mark_generation_complete(generation_id, success=False, error=str(e))
    self.error.emit(str(e))
```

### 5.4. Display credit balance in sidebar

In `MainWindow._create_credit_card()`, call `get_user_balance(user_id)` and display:
- Trial remaining (if any)
- Credits balance
- Cost per next generation (based on selected resolution)
- "Buy Credits" button → Opens Gumroad (Section 6)

---

## 6. Payment Integration (Gumroad)

### 6.1. How it works

The desktop app **does NOT process payments directly**. Instead:

1. User clicks "Buy Credits" in the desktop app
2. Desktop opens Gumroad checkout URL in the system browser
3. User pays on Gumroad
4. Gumroad sends a **webhook** to the web app's backend (Render server)
5. Web app's `/webhook/gumroad` endpoint processes the payment and adds credits to Supabase
6. Desktop app **polls** Supabase for updated credit balance

### 6.2. Implementation

```python
# In ui/main_window.py — "Buy Credits" button handler:

import webbrowser
from core.credit_manager import CREDIT_PACKS

def _on_buy_credits(self):
    """Open Gumroad purchase page for selected credit pack."""
    # Show a dialog with pack options
    packs = CREDIT_PACKS
    # User selects e.g., "credits_micro"
    selected_pack = packs["credits_micro"]
    gumroad_id = selected_pack.get("gumroad_id")
    
    if gumroad_id:
        # Include user_id in the Gumroad URL for webhook matching
        user_id = self.session_manager.user_id
        gumroad_url = f"https://trivoxmodels.gumroad.com/l/{gumroad_id}"
        
        # Open in system browser
        webbrowser.open(gumroad_url)
        
        # Start polling for credit update
        self._start_credit_polling()

def _start_credit_polling(self):
    """Poll Supabase every 5 seconds for credit balance update."""
    self._poll_timer = QTimer()
    self._poll_timer.timeout.connect(self._check_credit_update)
    self._poll_timer.start(5000)  # 5 seconds
    self._poll_count = 0
    self._initial_balance = self.session_manager.credits

def _check_credit_update(self):
    """Check if credits have been updated."""
    self._poll_count += 1
    self.session_manager.refresh_credits()
    
    if self.session_manager.credits > self._initial_balance:
        # Credits added! Purchase successful
        self._poll_timer.stop()
        self._refresh_credit_balance()
        QMessageBox.information(self, "Purchase Complete",
            f"Credits added: {self.session_manager.credits - self._initial_balance}\n"
            f"New balance: {self.session_manager.credits}")
    
    elif self._poll_count > 60:  # 5 minutes timeout
        self._poll_timer.stop()
```

### 6.3. Credit pack selection dialog

Create a new `CreditPurchaseDialog` (QDialog) that shows:
- All credit packs with prices
- Subscription plans
- "Buy" button per pack → Opens Gumroad URL
- Current balance display

### 6.4. Webhook (already handled by web app)

The web app's `/webhook/gumroad` endpoint at `https://trivoxaimodels-r5ip.onrender.com/webhook/gumroad` already:
1. Receives Gumroad sale notification
2. Finds/creates user by buyer email
3. Looks up plan_id from product
4. Calls `add_credits_from_purchase()` to add credits to `user_credits` table
5. Records in `payment_transactions` and `gumroad_sales` tables

**No changes needed on the webhook side.** The desktop app just needs to match user accounts (by email or user_id).

---

## 7. 3D Generation Pipeline — Fixing the Local Processing Bug

### 7.1. THE BUG: Fake Fast Completion

The user reported this log output:
```
[17:47:24] Image loaded: temple.jpg
[17:47:26] 🚀 Starting 3D generation: temple.jpg
[17:47:26] 📊 Initializing...
[17:47:27] 📊 Processing image...
[17:47:28] 📊 Generating 3D mesh...
[17:47:29] 📊 Exporting formats...
[17:47:30] ✅ 3D model generation complete!
[17:47:30] 📦 Outputs: OBJ, STL, GLB
```

**Total time: 4 seconds.** Real TripoSR takes **30-120 seconds** on a typical machine. This means the local pipeline is **NOT actually running TripoSR** — it's either:

1. **Silently catching an error** and returning an empty/dummy result
2. **Missing the TripoSR dependency** (`open3d`, TripoSR repo) and returning a fallback
3. **The `_run_local_pipeline` function in `unified_pipeline.py` is failing** at the import stage and returning the error dict, but the UI treats it as success

### 7.2. Root Cause Analysis

Looking at `unified_pipeline.py` → `_run_local_pipeline()`:

```python
try:
    from core.pipeline import run_pipeline as local_pipeline
except Exception as exc:
    return {
        "error": f"Local processing failed to initialize: {exc}",
        ...
        "obj": "", "stl": "", "glb": "",  # Empty paths
    }
```

**The desktop app is missing `core/pipeline.py`!** The import fails, the function returns the error dict with empty paths, but the `GenerationWorker.run()` in `main_window.py` doesn't check for `result.get("error")` — it just emits `finished(result)` with the error dict.

Then `_on_generation_finished()` in `main_window.py` likely just logs "Complete!" without validating the result.

### 7.3. Fix: Copy Local Pipeline Files

Copy these files from web app to desktop app:

1. `core/pipeline.py` — The actual local TripoSR pipeline
2. `core/inference/model_manager.py` — ModelManager wrapper
3. `core/inference/triposr.py` — TripoSR engine (shells out to TripoSR repo's `run.py`)
4. `core/inference/triposr_direct.py` — Alternative direct TripoSR
5. `core/postprocess/cleanup.py` — Mesh cleanup
6. `core/postprocess/advanced_mesh_processor.py` — Advanced mesh processing
7. `core/exporter.py` — Mesh export helper

### 7.4. Fix: Dependencies for Local Processing

Add to `requirements.txt`:
```
open3d>=0.17.0
trimesh>=4.0.0
numpy>=1.24.0
Pillow>=10.0.0
torch>=2.0.0
psutil>=5.9.0
```

And ensure the TripoSR git repository is available:
```
# TripoSR repo is cloned at runtime by triposr.py._ensure_repo()
# It clones: https://github.com/VAST-AI-Research/TripoSR.git
# To a local cache directory
```

### 7.5. Fix: `GenerationWorker.run()` — Check for Errors

```python
# In GenerationWorker.run() — AFTER getting result:

if result.get("error") or result.get("error_message"):
    error_msg = result.get("error") or result.get("error_message")
    self.error.emit(f"Generation failed: {error_msg}")
    return

# Only emit success if we actually have output files
if not any(result.get(fmt) for fmt in ["obj", "stl", "glb"]):
    self.error.emit("Generation produced no output files. Check system requirements.")
    return

self.progress.emit(100)
self.status.emit("Complete!")
self.finished.emit(result)
```

### 7.6. Fix: Progress Callback Connection

The current `GenerationWorker` doesn't pass a `progress_callback` to the pipeline. Fix:

```python
def run(self):
    try:
        from core.unified_pipeline import run_pipeline_async
        from config.settings import get_output_dir

        def progress_callback(stage, pct, msg):
            """Route pipeline progress to UI signals."""
            self.progress.emit(int(pct))
            self.status.emit(msg)

        self.status.emit("Initializing...")
        self.progress.emit(5)

        output_dir = str(get_output_dir())
        
        if self.model == "cloud":
            result = asyncio.run(
                run_pipeline_async(
                    self.image_path,
                    use_api=True,
                    api_model="hitem3dv1.5",
                    api_resolution=resolution,
                    api_format=",".join(self.output_formats),
                    output_dir=output_dir,
                    quality=self.quality,
                    progress_callback=progress_callback,  # ADD THIS
                )
            )
        else:
            result = asyncio.run(
                run_pipeline_async(
                    self.image_path,
                    use_api=False,
                    output_dir=output_dir,
                    quality=self.quality,
                    progress_callback=progress_callback,  # ADD THIS
                )
            )

        # CHECK FOR ERRORS
        if result.get("error") or result.get("error_message"):
            self.error.emit(result.get("error") or result.get("error_message"))
            return

        if not any(result.get(f) for f in ["obj", "stl", "glb"]):
            self.error.emit("No output files generated")
            return

        self.progress.emit(100)
        self.status.emit("Complete!")
        self.finished.emit(result)

    except Exception as e:
        self.error.emit(str(e))
```

### 7.7. Local processing time expectations

| Machine | RAM | Expected Time |
|---------|-----|--------------|
| Low-end (no GPU) | 8GB | 60-120 seconds |
| Mid-range | 16GB | 30-60 seconds |
| High-end (GPU) | 32GB+ | 15-30 seconds |

If processing completes in < 10 seconds, something is wrong.

---

## 8. Cloud API Integration

### 8.1. Providers (same as web app)

The desktop already has the cloud API client files. They work identically:

| Provider | File | Key Format | Features |
|----------|------|------------|----------|
| Tripo3D | `tripo3d_client.py` | `tsk_xxx` | Image→3D, Text→3D, Multiview |
| Hitem3D | `hitem3d_api.py` | `client_id:secret` | Image→3D, High quality |
| Meshy AI | `meshy_ai_client.py` | API key | Image→3D, Text→3D |
| Neural4D | `neural4d_client.py` | API key | Image→3D |

### 8.2. Credential Resolution Chain

The `unified_pipeline.py` → `resolve_hitem3d_credentials()` already searches:
1. Passed api_token parameter
2. Environment variables (`HITEM3D_ACCESS_TOKEN`, `TRIPO_API_KEY`, etc.)
3. Supabase `app_secrets` table (via `secret_manager.py`)
4. Supabase `model_api_keys` table (admin-managed)
5. Local `api_credentials.json` file
6. Legacy credential files

### 8.3. Master API Key (admin owns the keys)

The admin stores their bulk API keys in Supabase `model_api_keys` table. When a regular user generates, the system uses the admin's master key:

```python
from core.credit_manager import get_master_api_key

# Get the admin's API key for the selected provider
master_key = get_master_api_key(provider="hitem3d")
if master_key:
    result = await run_pipeline_async(
        image_path,
        use_api=True,
        api_token=master_key,  # Use admin's key, not user's
        ...
    )
```

### 8.4. Copy `core/secret_manager.py` from web app

This module reads from the `app_secrets` Supabase table:

```python
# core/secret_manager.py
from core.supabase_client import get_supabase_client

def get_secret(key: str) -> str:
    """Look up a secret value from the app_secrets table."""
    try:
        sb = get_supabase_client()
        if not sb:
            return ""
        result = sb.table("app_secrets").select("value").eq("key", key).limit(1).execute()
        rows = result.data or []
        return rows[0]["value"] if rows else ""
    except Exception:
        return ""
```

---

## 9. Admin Dashboard

### 9.1. What it provides (from web app)

The web app has a full admin dashboard at `/admin/` with:
- Model management (enable/disable cloud models)
- API key management (store/rotate keys per model)
- Credit balance sync (fetch real balance from provider APIs)
- User management (view all users, grant credits, ban devices)
- Sales analytics (Gumroad sales data)
- Usage logs

### 9.2. Desktop Admin Panel

For the desktop app, implement an admin panel as a **QDialog** (not a web page). Copy ```core/admin_manager.py``` from the web app, then create a new `ui/admin_dialog.py`:

```python
# ui/admin_dialog.py — Admin Dashboard Dialog

class AdminDashboard(QDialog):
    """Admin dashboard for desktop app management."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.admin_mgr = AdminModelManager()
        self.user_tracker = UserTracker()
        self._setup_ui()
    
    def _setup_ui(self):
        # Tabs:
        # 1. Models — Enable/disable, set API keys
        # 2. Users — List all users, grant credits, ban
        # 3. Analytics — Generation stats, revenue
        # 4. Settings — API keys, webhooks
        pass
```

### 9.3. Admin authentication

To access the admin panel, the user must:
1. Have a license key starting with `I3D-ADMIN-*`
2. OR be flagged `is_admin=True` in `web_users`

The desktop checks this via `LicenseManager.is_admin_license()` or `AdminModelManager.is_admin(user_id)`.

---

## 10. License Manager

### 10.1. Copy `core/license_manager.py` from web app

This provides the complete license lifecycle:

- `LicenseManager()`
  - `has_trial_available()` — Server-side trial check
  - `get_trial_remaining()` — Server-side remaining count
  - `use_trial_generation()` — Atomic server-side trial consumption
  - `has_valid_license()` — Checks license validity + hardware binding
  - `validate_license_online(license_key)` — Validates against Supabase `licenses` table
  - `activate_license(license_key, license_obj)` — Activates and hardware-binds
  - `can_use_app()` — Main check: has trial OR has license
  - `require_license_or_trial()` — Enforces the check
  - `is_admin_license()` — Checks if license starts with `I3D-ADMIN-`
  - `set_admin_password()` / `verify_admin_password()` — Desktop admin access

### 10.2. Integration with main_window.py

```python
# Before ANY generation:
from core.license_manager import LicenseManager

license_mgr = LicenseManager()

if not license_mgr.can_use_app():
    # Show "Buy License" or "No free trial remaining" dialog
    show_purchase_dialog()
    return

# If trial:
if license_mgr.has_trial_available():
    success = license_mgr.use_trial_generation()
    if not success:
        show_error("Trial expired")
        return
# Else: deduct from credits (Section 5)
```

---

## 11. Desktop-Specific Supabase Tables

### No new tables needed!

All 14 existing tables support the desktop app. Here's how desktop uses each:

| Table | Desktop Usage |
|-------|--------------|
| `registered_devices` | **PRIMARY** — Stores device fingerprint, trial tracking, tamper detection, ban status |
| `web_users` | User accounts (shared between web and desktop) |
| `user_credits` | Credit balance (shared) |
| `credit_ledger` | Audit trail (shared) |
| `user_generations` | Generation history (shared) |
| `usage_logs` | Per-generation detailed logs |
| `user_profiles` | Device info, usage stats |
| `model_api_keys` | Admin's API keys (read by desktop for generation) |
| `cloud_model_config` | Which models are enabled |
| `app_secrets` | Secure API key storage |
| `payment_transactions` | Payment records (written by webhook, read by desktop) |
| `gumroad_sales` | Gumroad sales data |
| `licenses` | License key tracking |
| `app_admins` | Admin role assignments |

### Linking desktop devices to user accounts

The `registered_devices` table has a `user_id` column (FK to `web_users`). When a device user purchases credits:

1. They register with username/password → creates `web_users` entry
2. Device is linked: `registered_devices.user_id = web_users.id`
3. Credits from Gumroad webhook go to `user_credits` for that `user_id`
4. Desktop reads credit balance via that `user_id`

---

## 12. File-by-File Implementation Checklist

### Files to COPY from web app (no modifications needed):
```
core/auth.py                        # Password hashing, session tokens
core/server_auth.py                 # Server-side device auth + tamper detection
core/secret_manager.py              # Reads API keys from Supabase
core/pipeline.py                    # Local TripoSR inference pipeline
core/exporter.py                    # Mesh export helper
core/platform_features.py          # Platform feature detection
core/admin_manager.py              # Admin model/user management
core/license_manager.py            # License lifecycle management
core/payment_factory.py            # Unified payment processor
core/providers/__init__.py          # Provider package init
core/providers/base.py              # Abstract payment provider
core/providers/gumroad.py          # Gumroad payment provider
core/inference/__init__.py          # (create empty __init__.py)
core/inference/model_manager.py    # ModelManager wrapper
core/inference/triposr.py          # TripoSR local engine
core/inference/triposr_direct.py   # Direct TripoSR alternative
core/postprocess/__init__.py        # (create empty __init__.py)
core/postprocess/cleanup.py        # Mesh cleanup
core/postprocess/advanced_mesh_processor.py  # Advanced mesh processing
```

### Files to MODIFY:
```
.env                                # Add SUPABASE_KEY (service role)
core/supabase_client.py            # Use SUPABASE_KEY instead of SUPABASE_ANON_KEY
core/device_fingerprint.py         # Replace with web version (more hardware IDs)
core/session_manager.py            # Add server_auth tamper detection
core/credit_manager.py             # Replace with web version (full credit system)
core/unified_pipeline.py           # Already correct, just verify import paths
config/settings.py                 # Add any missing configs
ui/auth_dialog.py                  # Add password registration tab
ui/main_window.py                  # Fix generation, add credits, add payment UI
main.py                            # Initialize new modules
requirements.txt                   # Add open3d, torch, trimesh, psutil, bcrypt
```

### Files to CREATE:
```
ui/admin_dialog.py                 # Admin dashboard (QDialog)
ui/credit_purchase_dialog.py       # Credit pack purchase dialog
core/inference/__init__.py          # Package init
core/postprocess/__init__.py        # Package init
core/providers/__init__.py          # Package init
```

### Files NOT needed (web-only):
```
core/user_db.py                    # SQLite DB (web-only, desktop uses Supabase)
core/multiangle_processor.py       # Web-only multi-angle processing
core/texture/                      # Web-only texture processing
ui/web/                            # Web UI (api.py, templates, static)
```

---

## 13. Known Bugs & Fixes

### Bug 1: Local Processing Completes Too Fast (4 seconds instead of 30-120s)

**Root Cause**: `core/pipeline.py` is missing from the desktop app. The import fails silently in `_run_local_pipeline()`, which returns an error dict with empty paths. The UI doesn't check for errors.

**Fix**: 
1. Copy `core/pipeline.py` and all inference/postprocess files from web app
2. Add error checking in `GenerationWorker.run()` (see Section 7.5)
3. Install dependencies: `open3d`, `torch`, `trimesh`, `psutil`

### Bug 2: Desktop App Uses ANON Key

**Root Cause**: Desktop `.env` has `SUPABASE_ANON_KEY` and `supabase_client.py` prefers it.

**Fix**: Update `.env` to include `SUPABASE_KEY` with the service role key. Update `supabase_client.py` to prefer `SUPABASE_KEY`.

### Bug 3: Trial Credits Can Be Reset

**Root Cause**: Trial tracking is local-only. Reinstalling app deletes local files.

**Fix**: Use `server_auth.py` functions to track trials server-side in `registered_devices` table. See Section 3.

### Bug 4: No Credit Deduction on Generation

**Root Cause**: Desktop's `GenerationWorker.run()` doesn't call `deduct_credits()` before generation.

**Fix**: Add credit check and deduction (see Section 5.3).

### Bug 5: OAuth Doesn't Complete

**Root Cause**: `auth_dialog.py` starts OAuth thread but the callback handling is incomplete. The thread tries to listen on a local HTTP port for the OAuth redirect.

**Fix**: Ensure the OAuth redirect URL is configured in Supabase Auth settings to redirect to `http://localhost:PORT/callback` and the callback thread properly handles the token exchange.

### Bug 6: Progress Not Shown During Generation

**Root Cause**: `GenerationWorker.run()` doesn't pass `progress_callback` to `run_pipeline_async()`.

**Fix**: Create a callback that emits Qt signals (see Section 7.6).

---

## 14. Environment Variables & .env Configuration

### Complete `.env` for desktop app:

```env
# ═══════════════════════════════════════════════════════════
# TrivoxModels Desktop App — Environment Configuration
# ═══════════════════════════════════════════════════════════

# Supabase (REQUIRED)
SUPABASE_URL=https://hovggmmmmledvmnmeuff.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhvdmdnbW1tbWxlZHZtbm1ldWZmIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc3MTg2NjU0MiwiZXhwIjoyMDg3NDQyNTQyfQ.l9d7qyh6YRJ8zTaSiSb2YROERnHEkDM8ktMnR6_Q8UE

# Gumroad (for payment links)
GUMROAD_ACCESS_TOKEN=GRifd1Uz_c0TJDytcWE9zpqubTpMjIRCVbXeYTgvocM

# Optional API Keys (if not using admin's master keys)
TRIPO3D_API_KEY=
HITEM3D_CLIENT_ID=
HITEM3D_CLIENT_SECRET=
MESHY_API_KEY=
NEURAL4D_API_KEY=

# Optional
OUTPUT_DIR=
UPDATE_URL=https://raw.githubusercontent.com/your-repo/TrivoxModels/main/updates.json
```

### Security Note

For the **distributed binary** (PyInstaller build), the `.env` file should be:
1. Bundled inside the PyInstaller MEIPASS directory (so it's part of the executable)
2. OR placed in `%APPDATA%/TrivoxModels/.env` at install time

**NEVER** expose the service_role key in a web browser context. It's safe in a desktop binary because the user cannot easily inspect bundled files.

---

## 15. Build & Distribution

### 15.1. Updated `requirements.txt`

```
# Core UI
PyQt6>=6.5.0

# Supabase
supabase>=2.0.0
python-dotenv>=1.0.0

# 3D Processing (local pipeline)
open3d>=0.17.0
trimesh>=4.0.0
numpy>=1.24.0
Pillow>=10.0.0
torch>=2.0.0
psutil>=5.9.0

# Auth
bcrypt>=4.0.0

# HTTP (for API clients)
aiohttp>=3.9.0
httpx>=0.25.0
requests>=2.31.0
```

### 15.2. PyInstaller spec updates

Add new data files to the spec:
```python
# In TrivoxModels.spec
datas=[
    ('.env', '.'),
    ('assets/', 'assets/'),
],
hiddenimports=[
    'core.server_auth',
    'core.auth',
    'core.license_manager',
    'core.payment_factory',
    'core.admin_manager',
    'core.secret_manager',
    'core.pipeline',
    'core.inference.model_manager',
    'core.inference.triposr',
    'core.postprocess.cleanup',
    'core.postprocess.advanced_mesh_processor',
    'core.providers.gumroad',
    'core.providers.base',
    'open3d',
    'trimesh',
    'bcrypt',
],
```

---

## Summary of Implementation Priority

### Phase 1 — Critical (do first)
1. ✅ Fix `supabase_client.py` to use service_role key
2. ✅ Copy `device_fingerprint.py` from web (full hardware fingerprint)
3. ✅ Copy `server_auth.py` from web (tamper detection)
4. ✅ Update `session_manager.py` with server auth
5. ✅ Copy `credit_manager.py` from web (full credit system)
6. ✅ Fix `GenerationWorker.run()` error handling

### Phase 2 — Local Processing Fix
7. ✅ Copy `pipeline.py` + inference + postprocess files
8. ✅ Install `open3d`, `torch`, `trimesh` dependencies
9. ✅ Test local generation (should take 30-120 seconds)

### Phase 3 — Payment & Licensing
10. ✅ Copy `license_manager.py`, `payment_factory.py`
11. ✅ Create "Buy Credits" dialog with Gumroad links
12. ✅ Copy `secret_manager.py` for API key retrieval
13. ✅ Add credit deduction before generation

### Phase 4 — Admin & Polish
14. ✅ Copy `admin_manager.py`
15. ✅ Create admin dashboard dialog
16. ✅ Add registration tab to auth dialog
17. ✅ Update PyInstaller spec and requirements.txt

---

> **Note for the implementing model**: Every file reference in this document uses absolute paths relative to `I:\trivoxmodels_desktop_app\` (desktop) and `I:\TrivoxAIModels_BACKUP\` (web source). When copying files, watch for import path differences — the web app uses `from core.X import Y` which should work identically in the desktop app since both have the same package structure.
