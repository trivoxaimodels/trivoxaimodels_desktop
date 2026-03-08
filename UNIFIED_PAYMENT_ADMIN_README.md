# Unified Payment Admin System

## Overview

This system allows **web admin panel** to control payment settings for **BOTH** web and desktop apps.

### Key Features

✅ **Single Admin Panel** - Web admin controls both web and desktop payment settings  
✅ **Real-time Sync** - Desktop app fetches config from web API  
✅ **No Desktop Admin UI** - Clean desktop app, all admin in web  
✅ **Secure Keys** - API keys fetched securely via authenticated API  
✅ **Tamper-proof** - Keys never hardcoded, fetched from secure storage  

---

## 📁 Files Created

### Web App Files (for `I:\TrivoxAIModels_BACKUP`)

1. **`supabase_migrations/008_payment_settings.sql`**
   - Creates `payment_settings` table
   - Stores payment provider config
   - Includes RPC functions for desktop app
   - RLS policies for security

2. **`api/admin/payment_config_api.py`**
   - REST API endpoints:
     - `GET /api/v1/payment-config/public` - Public config
     - `GET /api/v1/payment-config` - Full config (admin)
     - `PUT /api/v1/payment-config` - Update config (admin)
     - `GET /api/v1/payment-config/desktop` - Desktop app config
     - `GET /api/v1/payment-config/keys/{provider}` - Secure keys
     - `POST /api/v1/payment-config/switch-provider` - Switch provider
     - `POST /api/v1/payment-config/test-provider` - Test provider
     - `GET /api/v1/payment-config/providers` - Available providers

3. **`ui/admin/tabs/payment_settings.html`**
   - Admin UI tab for payment settings
   - Switch providers
   - Configure API keys
   - Manage credit packs
   - Test connections

4. **`static/js/admin/payment-settings.js`**
   - JavaScript functionality for admin panel
   - API integration
   - Form handling
   - Real-time updates

### Desktop App Files (for `I:\VoxelCraft_desktop_app`)

1. **`core/payment_config_sync.py`**
   - Syncs payment config from web to desktop
   - Caches config locally
   - Secure key retrieval
   - Handles offline mode

---

## 🚀 Implementation Steps

### Step 1: Setup Database (Web App)

Run the SQL migration in Supabase:

```bash
# Connect to Supabase and run:
supabase db execute < supabase_migrations/008_payment_settings.sql
```

Or run via Supabase Dashboard → SQL Editor

### Step 2: Install API Routes (Web App)

Add to your FastAPI app (in `api.py`):

```python
# At the top of api.py, add import
from api.admin.payment_config_api import router as payment_config_router

# In your app setup, add:
app.include_router(payment_config_router)
```

### Step 3: Add Admin Tab (Web App)

Add the Payment Settings tab to your admin dashboard:

1. Include the HTML file:
```html
<!-- In your admin dashboard HTML, add: -->
<div class="tab" onclick="switchTab('payment')">💰 Payment</div>

<!-- And the content: -->
{% include 'ui/admin/tabs/payment_settings.html' %}
```

2. Include the JavaScript:
```html
<script src="/static/js/admin/payment-settings.js"></script>
```

3. Initialize on tab switch:
```javascript
function switchTab(tabName) {
    if (tabName === 'payment') {
        PaymentSettings.init();
    }
}
```

### Step 4: Configure Environment (Desktop App)

Add to your desktop app's `.env` file:

```bash
# Web API URL for desktop app to fetch config
WEB_API_URL=https://your-domain.com/api/v1
```

### Step 5: Initialize on Desktop App Startup

Add to your desktop app's initialization:

```python
# In main.py or startup code
from core.payment_config_sync import initialize_payment_sync

# Initialize payment sync
initialize_payment_sync()
```

### Step 6: Update Desktop Payment Dialog

Modify `CreditPurchaseDialog` to use web config:

```python
from core.payment_config_sync import get_payment_config_sync

def __init__(self, parent=None):
    super().__init__(parent)
    
    # Sync config from web
    config_sync = get_payment_config_sync()
    config_sync.sync_config()
    
    # Get provider from web config
    self.active_provider = config_sync.get_active_provider()
    self.currency = config_sync.get_currency()
```

---

## 🔐 Security Features

### API Key Security

1. **Environment Variables** - Development
2. **Local Cache** - Runtime caching
3. **Supabase RPC** - Production secure storage

### Authentication

- Desktop app requires valid license to fetch config
- API endpoints require:
  - `license_key` - Valid license key
  - `device_fingerprint` - Device ID

### Key Flow

```
Desktop App → License Check → Web API → Supabase RPC → Secure Keys
     ↓
  Cache Locally
     ↓
Use for Payments
```

---

## 🎯 Usage Guide

### For Web Admin

1. **Login to Admin Panel** (`/admin`)
2. **Click "Payment Settings" Tab**
3. **Select Payment Provider**
   - Choose from: Gumroad, Razorpay, Stripe, PayPal, LemonSqueezy
4. **Configure API Keys**
   - Enter keys for selected provider
   - Click "Save API Keys"
5. **Switch Provider**
   - Select new provider
   - Click "Switch to This Provider"
   - Confirm the switch
6. **Configure Credit Packs**
   - Add/edit/delete credit packs
   - Set provider-specific IDs
7. **Test Configuration**
   - Click "Test Provider" to verify keys

### For Desktop Users

**No action required!**

- Desktop app automatically syncs config on startup
- Uses the same payment provider as web app
- Changes take effect immediately

---

## 📊 Database Schema

### payment_settings Table

```sql
CREATE TABLE public.payment_settings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider TEXT NOT NULL DEFAULT 'gumroad',
    currency TEXT NOT NULL DEFAULT 'USD',
    test_mode BOOLEAN DEFAULT TRUE,
    credit_packs JSONB DEFAULT '{}',
    provider_settings JSONB DEFAULT '{}',
    webhook_secrets JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_by UUID REFERENCES public.web_users(id)
);
```

### Example Credit Packs JSON

```json
{
  "credits_micro": {
    "credits": 40,
    "price": 99,
    "name": "Micro Pack (40 Credits)",
    "gumroad_id": "sijpb",
    "razorpay_id": "pl_xxx"
  },
  "credits_small": {
    "credits": 100,
    "price": 199,
    "name": "Small Pack (100 Credits)",
    "gumroad_id": "ershej",
    "razorpay_id": "pl_yyy"
  }
}
```

### Example Provider Settings JSON

```json
{
  "razorpay": {
    "key_id": "rzp_test_xxx",
    "key_secret": "xxx",
    "webhook_secret": "xxx",
    "test_mode": true
  },
  "stripe": {
    "key_id": "pk_test_xxx",
    "key_secret": "sk_test_xxx",
    "webhook_secret": "whsec_xxx",
    "test_mode": true
  }
}
```

---

## 🔧 Configuration

### Web App Config

```python
# In config/payment_config.py
# This is now controlled by web admin, not hardcoded
PAYMENT_PROVIDER = PaymentProvider.GUMROAD  # Will be overridden by DB config
```

### Desktop App Config

```python
# In config/payment_config.py
# Now fetches from web automatically
from core.payment_config_sync import get_payment_config_sync

sync = get_payment_config_sync()
PAYMENT_PROVIDER = sync.get_active_provider()
```

---

## 🧪 Testing

### Test Web Admin

1. Navigate to `/admin`
2. Switch to Razorpay
3. Enter test keys (rzp_test_*)
4. Save and test

### Test Desktop Sync

```python
from core.payment_config_sync import get_payment_config_sync

sync = get_payment_config_sync()
sync.sync_config(force=True)

config = sync.get_config()
print(f"Provider: {config.provider}")
print(f"Currency: {config.currency}")
```

### Test API Keys

```python
from core.payment_config_sync import get_secure_key_manager

key_mgr = get_secure_key_manager()
keys = key_mgr.get_razorpay_keys()

if keys:
    print(f"Key ID: {keys.get('key_id')}")
```

---

## 🐛 Troubleshooting

### Desktop Not Syncing

**Problem**: Desktop app not getting config from web  
**Solution**:
1. Check `WEB_API_URL` is set correctly
2. Verify license is valid
3. Check network connectivity
4. Review logs in `~/.VoxelCraft/payment_config_cache.json`

### API Keys Not Working

**Problem**: Keys not retrieved  
**Solution**:
1. Check keys are saved in web admin
2. Verify license is active
3. Check device fingerprint matches
4. Review Supabase RPC permissions

### Cache Issues

**Problem**: Old config being used  
**Solution**:
```python
from core.payment_config_sync import clear_payment_config_cache
clear_payment_config_cache()
```

---

## 📝 Notes

### Desktop App Cache

- Cache location: `~/.VoxelCraft/payment_config_cache.json`
- TTL: 5 minutes (configurable via `CACHE_TTL_MINUTES`)
- Clear cache on app restart or call `clear_payment_config_cache()`

### Web App Updates

- Changes take effect immediately
- Desktop app syncs on startup and every 5 minutes
- Force sync with `sync_config(force=True)`

### Security

- Keys never stored in desktop app code
- Keys fetched securely via HTTPS
- License validation required
- Device fingerprint binding

---

## 🎉 Benefits

1. **Single Source of Truth** - Web admin controls both apps
2. **No Code Changes** - Switch providers without deploying desktop app
3. **Secure Keys** - Keys not hardcoded, fetched securely
4. **Consistent UX** - Same payment experience across platforms
5. **Easy Management** - One place to manage all payment settings
6. **Tamper-proof** - Keys cannot be extracted from desktop app

---

## 📞 Support

For issues:
1. Check logs in desktop app directory
2. Verify web API is responding
3. Test Supabase RPC functions
4. Review browser console for web admin errors

---

## ✅ Checklist

**Web App:**
- [ ] Database migration executed
- [ ] API routes registered
- [ ] Admin tab added
- [ ] JavaScript included

**Desktop App:**
- [ ] `payment_config_sync.py` added
- [ ] `WEB_API_URL` configured
- [ ] Initialization code added
- [ ] `CreditPurchaseDialog` updated

**Testing:**
- [ ] Web admin accessible
- [ ] Can switch providers
- [ ] Desktop fetches config
- [ ] Payment flow works

---

## 📚 Additional Resources

- `RAZORPAY_INTEGRATION.md` - Razorpay specific setup
- `test_razorpay.py` - Test script for desktop app
- `.env.example` - Environment variables template

---

**System is ready for deployment! 🚀**
