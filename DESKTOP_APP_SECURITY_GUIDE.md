# Trivox AI Models Desktop App - Comprehensive Fix & Development Guide

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture Overview](#architecture-overview)
3. [Security Requirements](#security-requirements)
4. [Development Environment Setup](#development-environment-setup)
5. [Key Files and Their Functions](#key-files-and-their-functions)
6. [Fixing and Updating Steps](#fixing-and-updating-steps)
7. [Security Implementation Guide](#security-implementation-guide)
8. [API Integration Guide](#api-integration-guide)
9. [Payment System Integration](#payment-system-integration)
10. [Building and Deployment](#building-and-deployment)
11. [Troubleshooting Common Issues](#troubleshooting-common-issues)
12. [Git Workflow](#git-workflow)

---

## Project Overview

### Desktop Application

**Repository:** https://github.com/trivoxaimodels/Voxel-Craft-Desktop-app.git

The Trivox AI Models Desktop Application is a PySide6-based desktop application that enables users to generate 3D models from images using cloud APIs (Tripo3D, Meshy AI, Neural4D, Hitem3D) or local inference (TripoSR).

### Web Application

**Location:** `I:\TrivoxAIModels_Web`

The web application provides:
- User authentication (OAuth, email/password)
- Credit purchase system
- Admin panel for managing payments and users
- API endpoints that the desktop app connects to

---

## Architecture Overview

### Desktop App Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    VoxelCraft Desktop                     │
├─────────────────────────────────────────────────────────────┤
│  UI Layer (PySide6)                                         │
│  ├── main_window.py - Main application window               │
│  ├── auth_dialog.py - Authentication dialog                 │
│  └── credit_purchase_dialog.py - Credit purchase UI          │
├─────────────────────────────────────────────────────────────┤
│  Core Business Logic                                        │
│  ├── session_manager.py - User session management            │
│  ├── credit_manager.py - Credit balance & transactions       │
│  ├── license_manager.py - License validation & trial        │
│  └── server_auth.py - Device authentication with server      │
├─────────────────────────────────────────────────────────────┤
│  API Integration                                            │
│  ├── unified_api.py - Unified 3D generation API client       │
│  ├── tripo3d_client.py - Tripo3D API integration            │
│  ├── meshy_ai_client.py - Meshy AI integration              │
│  ├── neural4d_client.py - Neural4D integration              │
│  ├── hitem3d_api.py - Hitem3D integration                  │
│  └── secret_manager.py - Secure API key retrieval           │
├─────────────────────────────────────────────────────────────┤
│  Local Processing                                           │
│  ├── pipeline.py - Local image-to-3D pipeline               │
│  ├── unified_pipeline.py - Unified local/cloud pipeline     │
│  └── inference/ - Local model inference (TripoSR)           │
├─────────────────────────────────────────────────────────────┤
│  Infrastructure                                             │
│  ├── supabase_client.py - Supabase database connection      │
│  ├── device_fingerprint.py - Hardware fingerprinting        │
│  ├── payment_config_sync.py - Payment settings sync         │
│  └── payment_handler.py - Payment processing               │
└─────────────────────────────────────────────────────────────┘
```

### Database Schema (Supabase)

The desktop app uses the following Supabase tables:

| Table | Purpose |
|-------|---------|
| `web_users` | User accounts |
| `user_credits` | Credit balances |
| `registered_devices` | Device registrations |
| `device_trials` | Trial tracking |
| `credit_ledger` | Credit transaction history |
| `payment_transactions` | Payment records |
| `payment_settings` | Payment configuration |
| `model_api_keys` | API keys for cloud services |
| `app_secrets` | Application secrets |

---

## Security Requirements

### CRITICAL SECURITY REQUIREMENTS

1. **No API Keys in Source Code**
   - NEVER hardcode API keys in source files
   - Store all keys in environment variables or Supabase
   - Use `.env.example` for development (never commit `.env`)

2. **Supabase Connection Security**
   - Use ANON_KEY for client operations (read-only when possible)
   - Use SERVICE_ROLE_KEY only for admin operations
   - Implement Row Level Security (RLS) policies

3. **Model Protection**
   - Models should NEVER be exposed or directly accessible
   - All model access must go through authenticated API calls
   - No user should be able to browse/extract models from the app

4. **Authentication Flow**
   - Device fingerprint + server validation required
   - Session tokens with expiration
   - Hardware binding for license validation

5. **Payment Security**
   - Payment processing via secure providers only
   - Never store raw payment credentials
   - Webhook signature verification required

---

## Development Environment Setup

### Prerequisites

```bash
# Install Python 3.10+ (recommended: Python 3.11)
python --version  # Should be 3.10 or higher

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root (DO NOT COMMIT THIS FILE):

```env
# Supabase Configuration
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key

# Web API (for payment config sync)
WEB_API_URL=https://your-web-api.onrender.com/api/v1

# Optional: API Keys (should come from Supabase, not here)
# TRIPO_API_KEY=
# MESHY_API_KEY=
# NEURAL4D_API_TOKEN=
```

### Running the Application

```bash
# Development mode
python main.py

# Or use the batch file
start_app.bat
```

---

## Key Files and Their Functions

### Core Authentication Files

#### 1. [`core/supabase_client.py`](core/supabase_client.py)
**Purpose:** Supabase database connection management

**Key Functions:**
- `SupabaseClient.get_client()` - Get or create Supabase client instance
- Auto-loads `.env` from multiple locations

**Security Note:** Uses environment variables for connection. The ANON_KEY should be used for regular operations.

#### 2. [`core/server_auth.py`](core/server_auth.py)
**Purpose:** Device authentication against Supabase

**Key Functions:**
- `check_device_server(fingerprint)` - Check device registration status
- `register_device_server(...)` - Register new device
- `verify_device_login_server(fingerprint)` - Verify device login
- `use_trial_server(fingerprint)` - Consume trial credit (server-side atomic)
- `report_tamper_attempt(...)` - Report tampering attempts

#### 3. [`core/session_manager.py`](core/session_manager.py)
**Purpose:** User session management

**Key Functions:**
- `login_with_device()` - Login using device fingerprint
- `register_device()` - Register new device
- `is_authenticated` - Check authentication status
- `user_id`, `credits`, `trial_remaining` - Session properties

#### 4. [`core/secret_manager.py`](core/secret_manager.py)
**Purpose:** Secure API key retrieval

**Key Functions:**
- `get_secret(key_name)` - Get API key with caching
- Multi-tier fallback: env vars → cache → Supabase

**Security Note:** Keys are fetched from Supabase using license validation.

### Credit & Payment Files

#### 5. [`core/credit_manager.py`](core/credit_manager.py)
**Purpose:** Credit system management

**Key Functions:**
- `add_credits(user_id, amount, source, description)` - Add credits
- `deduct_credits(user_id, amount)` - Deduct credits
- `get_user_balance(user_id)` - Get credit balance
- `register_user(...)` - Register new user with trial
- `CREDIT_COSTS` - Cost per generation type

#### 6. [`core/license_manager.py`](core/license_manager.py)
**Purpose:** License validation and trial tracking

**Key Functions:**
- `has_valid_license()` - Check if license is valid
- `validate_license_online(license_key)` - Validate license with server
- `has_trial_available()` - Check trial availability
- `use_trial_generation()` - Use trial credit (server-validated)

#### 7. [`core/payment_config_sync.py`](core/payment_config_sync.py)
**Purpose:** Sync payment settings from web app

**Key Functions:**
- `sync_config(force)` - Sync payment config from Supabase
- `get_payment_config()` - Get current payment settings

### API Integration Files

#### 8. [`core/unified_api.py`](core/unified_api.py)
**Purpose:** Unified 3D generation API client

**Key Classes:**
- `APIPlatform` - Enum for API providers
- `APICredentials` - Credential container
- `Unified3DAPI` - Main API client

**Supported Platforms:**
- Tripo3D (priority)
- Hitem3D (fallback)
- Meshy AI
- Neural4D

#### 9. [`core/pipeline.py`](core/pipeline.py)
**Purpose:** Local image-to-3D processing

**Key Function:**
- `run_pipeline(image, name, quality, scale, ...)` - Full local pipeline

**Quality Levels:**
- `draft` - Fast cleanup only
- `standard` - Basic processing
- `high` - Advanced processing
- `production` - Maximum quality

#### 10. [`core/unified_pipeline.py`](core/unified_pipeline.py)
**Purpose:** Unified local + cloud pipeline

**Key Functions:**
- `run_pipeline(...)` - Run image-to-3D (local or cloud)
- `run_text_pipeline_async(...)` - Text-to-3D generation

### UI Files

#### 11. [`ui/main_window.py`](ui/main_window.py)
**Purpose:** Main application window

**Key Classes:**
- `MainWindow` - Main application window
- `CompletionDialog` - Generation completion modal

#### 12. [`ui/auth_dialog.py`](ui/auth_dialog.py)
**Purpose:** Authentication dialog

---

## Fixing and Updating Steps

### Step 1: Security Audit and Fixes

#### 1.1 Remove Hardcoded Secrets

Check these files for hardcoded keys:
- `core/supabase_client.py`
- `config/settings.py`
- `config/payment_config.py`

**FIX:** Move all secrets to environment variables or Supabase:

```python
# BEFORE (INSECURE)
key = "sk-1234567890abcdef"

# AFTER (SECURE)
key = os.environ.get("SUPABASE_KEY")
if not key:
    # Fetch from Supabase using license validation
    key = SecretManager.get_secret("SUPABASE_KEY")
```

#### 1.2 Implement API Key Protection

The API keys (Tripo3D, Meshy, Neural4D, Hitem3D) should NEVER be accessible to users:

**Current Issue:** Keys stored in Supabase `model_api_keys` table and fetched via `SecretManager`

**Solution:** 
1. Implement server-side API proxy
2. Desktop app calls your server, server calls external APIs
3. This prevents key exposure

```python
# Instead of direct API calls, use:
# Desktop -> Your Server -> External API

# In unified_api.py or a new proxy module:
async def generate_with_protected_key(prompt: str, api_key: str) -> str:
    # Call your server, not directly to Tripo3D/Meshy/etc
    response = await your_server_api.generate_3d(
        prompt=prompt,
        provider="tripo3d",  # or "meshy", "neural4d"
        # DON'T pass the actual API key
    )
    return response.model_url
```

#### 1.3 Prevent Model Leakage

**Issue:** Users can potentially access generated models stored locally

**Solution:**
1. Store models in user-inaccessible locations
2. Use encrypted storage
3. Implement model access through authenticated streams only

```python
# Secure model storage approach:
import os
from pathlib import Path

class SecureModelStorage:
    @staticmethod
    def get_secure_storage_path() -> Path:
        """Get path in AppData that user cannot easily access"""
        appdata = os.environ.get("APPDATA", str(Path.home()))
        secure_path = Path(appdata) / "VoxelCraft" / "models"
        secure_path.mkdir(parents=True, exist_ok=True)
        
        # Set restrictive permissions (Windows)
        import stat
        secure_path.chmod(stat.S_IRWXU)  # User only
        
        return secure_path
    
    @staticmethod
    def get_model_path(model_id: str) -> Path:
        """Get path for a specific model"""
        return SecureModelStorage.get_secure_storage_path() / f"{model_id}.glb"
```

### Step 2: Authentication Improvements

#### 2.1 Strengthen Device Fingerprint

**Current Implementation:** [`core/device_fingerprint.py`](core/device_fingerprint.py)

**Improvements:**
1. Add more hardware identifiers
2. Implement anti-tampering checks
3. Add server-side fingerprint validation

```python
# Enhanced fingerprinting:
def get_enhanced_fingerprint() -> str:
    """Combine multiple identifiers for robust fingerprint"""
    identifiers = []
    
    # Hardware IDs
    identifiers.append(get_machine_id())
    identifiers.append(get_disk_serial())
    identifiers.append(get_cpu_id())
    
    # Network IDs (may change)
    # Only use as secondary
    
    # Combine and hash
    combined = "|".join(sorted(identifiers))
    return hashlib.sha256(combined.encode()).hexdigest()
```

#### 2.2 Add Session Expiration

**Current:** Sessions may persist indefinitely

**Fix in** [`core/session_manager.py`](core/session_manager.py):

```python
class SessionManager:
    SESSION_MAX_AGE_SECONDS = 7 * 24 * 3600  # 7 days
    VALIDATION_INTERVAL = 300  # 5 minutes
    
    def is_session_expired(self) -> bool:
        """Check if session has expired"""
        if not self._session:
            return True
        session_age = time.time() - self._session.login_time
        return session_age > self.SESSION_MAX_AGE_SECONDS
```

### Step 3: Database Security

#### 3.1 Implement Row Level Security (RLS)

In Supabase SQL Editor:

```sql
-- Enable RLS on all tables
ALTER TABLE web_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_credits ENABLE ROW LEVEL SECURITY;
ALTER TABLE registered_devices ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own data
CREATE POLICY "Users can view own data" ON web_users
    FOR SELECT USING (auth.uid() = id);

-- Policy: Users can only update own credits
CREATE POLICY "Users can update own credits" ON user_credits
    FOR UPDATE USING (auth.uid() = user_id);

-- Policy: Devices can only register themselves
CREATE POLICY "Devices can register" ON registered_devices
    FOR INSERT WITH CHECK (true);  -- Device registration is open

-- Policy: Admin-only access to secrets
CREATE POLICY "Admin only secrets" ON model_api_keys
    FOR SELECT USING (
        EXISTS (SELECT 1 FROM app_admins WHERE user_id = auth.uid())
    );
```

#### 3.2 Create Secure RPC Functions

```sql
-- Secure device check (doesn't expose sensitive data)
CREATE OR REPLACE FUNCTION check_device(p_fingerprint TEXT)
RETURNS TABLE (
    found BOOLEAN,
    registered BOOLEAN,
    trial_remaining INTEGER,
    is_banned BOOLEAN,
    ban_reason TEXT
) 
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
    RETURN QUERY
    SELECT 
        CASE WHEN d.id IS NOT NULL THEN true ELSE false END,
        d.is_registered,
        COALESCE(d.trial_remaining, 1),
        COALESCE(d.is_banned, false),
        d.ban_reason
    FROM registered_devices d
    WHERE d.device_fingerprint = p_fingerprint;
END;
$$;
```

### Step 4: API Integration Fixes

#### 4.1 Implement API Proxy Server

Instead of desktop app calling external APIs directly, create a server-side proxy:

**File to create:** `api/proxy_api.py` (in web app)

```python
"""
API Proxy - Forwards requests to external 3D APIs
Keeps API keys hidden from desktop app
"""

from fastapi import APIRouter, HTTPException, Header
from typing import Optional
import os

router = APIRouter()

@router.post("/generate/image-to-3d")
async def generate_image_to_3d(
    image_url: str,
    provider: str,  # tripo3d, meshy, neural4d
    quality: str = "standard",
    authorization: Optional[str] = Header(None)
):
    # Verify user authorization
    user = await verify_desktop_token(authorization)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    # Check user has credits
    if not await check_credits(user.id, required_credits):
        raise HTTPException(status_code=402, detail="Insufficient credits")
    
    # Get API key from secure storage (Supabase)
    api_key = await get_secure_api_key(provider)
    
    # Call external API
    if provider == "tripo3d":
        result = await call_tripo3d_api(image_url, api_key, quality)
    elif provider == "meshy":
        result = await call_meshy_api(image_url, api_key, quality)
    # ... etc
    
    # Deduct credits
    await deduct_credits(user.id, required_credits)
    
    return result
```

#### 4.2 Update Desktop App to Use Proxy

**Modify:** [`core/unified_api.py`](core/unified_api.py)

```python
class Unified3DAPI:
    def __init__(self, credentials=None):
        self.credentials = credentials
        self._proxy_base_url = "https://your-server.com/api/v1"
    
    async def generate_from_image(self, image_path: str, ...):
        # Instead of calling external API directly:
        # 1. Upload image to your server (or use signed URL)
        # 2. Call your proxy endpoint
        # 3. Receive model URL
        
        response = await self._call_proxy(
            endpoint="/generate/image-to-3d",
            data={
                "image_url": image_url,  # or upload and get URL
                "provider": self._detect_provider(),
                "quality": quality,
            },
            headers={
                "Authorization": f"Bearer {self.session_token}"
            }
        )
        
        return response
```

### Step 5: Payment Integration

#### 5.1 Secure Payment Flow

**Current:** Desktop app may handle payment directly

**Fix:** All payment processing should go through web app

```python
# In desktop app - ui/credit_purchase_dialog.py

def initiate_purchase(self, pack_id: str):
    """Open web payment page instead of in-app"""
    # Get payment URL from server
    payment_url = self._get_payment_url(pack_id)
    
    # Open in embedded browser or external browser
    QDesktopServices.openUrl(QUrl(payment_url))
    
    # Poll for payment completion
    self._poll_payment_status()
```

#### 5.2 Webhook Security

**In web app:**

```python
# api/webhooks/razorpay.py
from fastapi import APIRouter, Request, Header
import hmac
import hashlib

router = APIRouter()

@router.post("/razorpay-webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None)
):
    # Verify webhook signature
    secret = os.environ["RAZORPAY_WEBHOOK_SECRET"]
    payload = await request.body()
    
    expected = hmac.new(
        secret.encode(), 
        payload, 
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(x_razorpay_signature, expected):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Process webhook
    event = request.json()
    await handle_razorpay_event(event)
    
    return {"status": "received"}
```

### Step 6: Build and Distribution Security

#### 6.1 Obfuscate Sensitive Data

**In** `build.bat` **or** `build_complete.bat`:

```batch
@echo off
REM ... existing build commands ...

REM Encrypt or obfuscate config files
REM Use PyArmor for code obfuscation (optional, costs money)
REM Or use custom encryption for config

echo Building secure installer...
```

#### 6.2 Secure .env Handling

**In** `build_complete.bat`:

```batch
REM Create encrypted config from environment variables
REM DO NOT include actual keys in the built app

echo Creating secure configuration...
python -c "
import os
import json
import base64

# Create config that references env vars (not values)
config = {
    'SUPABASE_URL': os.environ.get('SUPABASE_URL', ''),
    'USE_PROXY': 'true',  # Force using API proxy
    'API_PROXY_URL': os.environ.get('API_PROXY_URL', ''),
}

# Write to file (will be loaded at runtime)
with open('config/app_config.json', 'w') as f:
    json.dump(config, f)
"
```

---

## Security Implementation Guide

### Checklist for Security

- [ ] All API keys removed from source code
- [ ] API proxy implemented (keys never exposed to client)
- [ ] Supabase RLS policies enabled
- [ ] Device fingerprint validated server-side
- [ ] Session tokens have expiration
- [ ] Payment processing via web app only
- [ ] Webhook signatures verified
- [ ] No sensitive data in logs
- [ ] Models stored in secure location
- [ ] HTTPS enforced for all connections

### Environment Variable Best Practices

```env
# Development (.env - NOT COMMITTED)
SUPABASE_URL=https://project.supabase.co
SUPABASE_KEY=eyJ...
# DO NOT ADD SERVICE KEY OR API KEYS HERE

# Production - Keys injected at build/deploy time
# via secure secret management
```

### Supabase Security

1. **Use separate keys:**
   - `SUPABASE_ANON_KEY` - For client operations (read-only preferred)
   - `SUPABASE_SERVICE_KEY` - For server/admin operations only

2. **RLS is mandatory:**

```sql
-- Always enable and configure RLS
ALTER TABLE table_name ENABLE ROW LEVEL SECURITY;

-- Create restrictive policies
CREATE POLICY "policy_name" ON table_name
    FOR operation
    USING (condition);
```

---

## API Integration Guide

### Adding a New 3D API Provider

1. **Create client module:**

```python
# core/new_provider_client.py
class NewProviderClient:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.newprovider.com/v1"
    
    async def generate(self, image_url: str, **options) -> GenerationResult:
        # Implement API call
        pass
```

2. **Register in unified_api.py:**

```python
# Add to APIPlatform enum
class APIPlatform(Enum):
    # ... existing ...
    NEW_PROVIDER = "new_provider"

# Add to Unified3DAPI
async def _get_new_provider_client(self):
    if self._new_provider_client is None:
        from core.new_provider_client import NewProviderClient
        api_key = self.credentials.api_key
        if not api_key:
            api_key = SecretManager.get_secret("NEW_PROVIDER_API_KEY")
        self._new_provider_client = NewProviderClient(api_key)
    return self._new_provider_client
```

3. **Add to detection logic:**

```python
async def _detect_best_platform(self) -> APIPlatform:
    # Add detection for new provider
    if self.credentials.platform == APIPlatform.NEW_PROVIDER:
        return APIPlatform.NEW_PROVIDER
```

---

## Payment System Integration

### Credit Packs Configuration

**In** `core/credit_manager.py`:

```python
CREDIT_PACKS = {
    "credits_micro": {
        "credits": 40,
        "price": 99,
        "name": "Micro Pack (40 Credits)",
        "gumroad_id": "product_permalink",
        "razorpay_id": "plan_id",
    },
    # Add more packs...
}
```

### Payment Provider Setup

#### Razorpay

1. Create Razorpay account
2. Create payment links/plans in dashboard
3. Add webhook for payment verification
4. Update `CREDIT_PACKS` with plan IDs

#### Gumroad

1. Create Gumroad account
2. Create products for credit packs
3. Add permalinks to `CREDIT_PACKS`
4. Configure webhook for license generation

---

## Building and Deployment

### Development Build

```bash
# Activate venv
venv\Scripts\activate

# Test imports
python -c "from core import unified_api; print('OK')"

# Run application
python main.py
```

### Production Build

```bash
# Run build script
build_complete.bat
```

The build will create:
- `dist/VoxelCraft/` - Standalone application
- `installer/VoxelCraft.exe` - NSIS installer

### Creating Installer

```bash
# Requires NSIS installed
cd installer
iscc VoxelCraft.iss
```

---

## Troubleshooting Common Issues

### Issue: "SUPABASE_URL not found"

**Cause:** Environment variables not loaded

**Fix:**
1. Create `.env` file in project root
2. Or set environment variables before running:
```batch
set SUPABASE_URL=https://your-project.supabase.co
set SUPABASE_KEY=your-key
python main.py
```

### Issue: "Device not registered"

**Cause:** Device not in `registered_devices` table

**Fix:**
1. Register device via auth dialog
2. Or manually add to Supabase:
```sql
INSERT INTO registered_devices (device_fingerprint, is_registered, trial_remaining)
VALUES ('your-fingerprint-here', true, 1);
```

### Issue: "No credits available"

**Cause:** User has no credits or trial used

**Fix:**
1. Purchase credits via web app
2. Or add trial credits in Supabase:
```sql
UPDATE user_credits 
SET credits_balance = 10 
WHERE user_id = 'user-id-here';
```

### Issue: API keys not working

**Cause:** Keys not properly configured in Supabase

**Fix:**
1. Add keys to `model_api_keys` table:
```sql
INSERT INTO model_api_keys (provider, key_id, key_secret, is_active)
VALUES ('tripo3d', 'tsk_your_key', 'your_secret', true);
```

### Issue: Payment sync failing

**Cause:** Network issues or incorrect config

**Fix:**
1. Check `WEB_API_URL` in environment
2. Verify payment_settings table has data:
```sql
SELECT * FROM payment_settings WHERE is_active = true;
```

---

## Git Workflow

### Before Making Changes

```bash
# Pull latest changes
git pull origin main

# Create feature branch
git checkout -b fix/security-update
```

### Committing Changes

```bash
# Stage changes
git add .

# Commit with descriptive message
git commit -m "Fix: Implement API proxy to prevent key exposure

- Added API proxy endpoint in web app
- Updated desktop app to use proxy
- Added RLS policies to Supabase
- Improved session security"

# Push to remote
git push origin fix/security-update
```

### Merging to Main

```bash
# Create pull request on GitHub
# Or merge locally
git checkout main
git merge fix/security-update
git push origin main
```

### Important Git Rules

1. **NEVER commit `.env` files**
2. **NEVER commit actual API keys**
3. **Use `.env.example` for template**
4. **Add secrets to GitHub Secrets for CI/CD**

---

## Summary

This guide provides comprehensive instructions for:

1. **Security hardening** - Prevent API key leakage, protect models
2. **Authentication** - Device fingerprint, session management
3. **Database** - Supabase RLS, secure RPC
4. **API integration** - Proxy server, new providers
5. **Payments** - Secure flow via web app
6. **Building** - Production builds, installers

### Priority Fixes (Must Do)

1. ☐ Implement API proxy to hide keys
2. ☐ Enable Supabase RLS policies  
3. ☐ Move payment flow to web app
4. ☐ Add session expiration
5. ☐ Secure model storage

### Secondary Fixes (Should Do)

1. ☐ Enhance device fingerprint
2. ☐ Add webhook verification
3. ☐ Implement secure logging
4. ☐ Add rate limiting

---

**Last Updated:** 2026-03-07
**Version:** 1.0.0
