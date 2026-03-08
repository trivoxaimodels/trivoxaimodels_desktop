# Razorpay Payment Gateway Integration

This document describes the secure Razorpay payment gateway integration for VoxelCraft Desktop Application.

## Overview

The Razorpay integration provides a secure, tamper-proof payment system for purchasing credits. It supports both order-based payments (secure) and Payment Links (simpler fallback).

## Features

- **Secure Key Management**: API keys are never hardcoded
- **Three-Tier Security**: Environment Variables → Local Cache → Remote Supabase RPC
- **Payment Verification**: HMAC-SHA256 signature verification
- **Webhook Support**: Automatic credit addition via webhooks
- **Polling Fallback**: Automatic credit detection for Payment Links
- **Comprehensive Logging**: Full audit trail

## Security Architecture

### Three-Tier Key Storage

1. **Environment Variables** (Development)
   - Set via `.env` file or system environment
   - Fast access for development

2. **Local Cache** (Runtime)
   - In-memory cache after first fetch
   - Reduces API calls

3. **Remote Supabase RPC** (Production)
   - Fetched via `get_app_config` RPC
   - Requires valid license
   - Keys encrypted in transit and at rest

### Key Security Features

- Keys fetched via `SecretManager` class
- No keys stored in source code
- Tamper detection via signature verification
- Secure comparison using `hmac.compare_digest`
- Webhook signatures verified with HMAC-SHA256

## Configuration

### 1. Environment Variables (Development)

Create a `.env` file in the project root:

```bash
# Razorpay Configuration
RAZORPAY_KEY_ID=rzp_test_YourTestKeyIdHere
RAZORPAY_KEY_SECRET=YourTestKeySecretHere
RAZORPAY_WEBHOOK_SECRET=YourWebhookSecretHere
```

See `.env.example` for complete template.

### 2. Supabase RPC (Production)

Store keys in Supabase and fetch via RPC:

```sql
-- Create get_app_config function in Supabase
CREATE OR REPLACE FUNCTION get_app_config(
    p_license_key TEXT,
    p_device_id TEXT
) RETURNS JSON AS $$
DECLARE
    v_config JSON;
BEGIN
    -- Validate license
    IF NOT EXISTS (
        SELECT 1 FROM licenses 
        WHERE key = p_license_key 
        AND device_fingerprint = p_device_id
        AND active = true
    ) THEN
        RETURN jsonb_build_object('error', 'Invalid license');
    END IF;
    
    -- Return secure config
    SELECT jsonb_build_object(
        'RAZORPAY_KEY_ID', (SELECT value FROM app_config WHERE key = 'RAZORPAY_KEY_ID'),
        'RAZORPAY_KEY_SECRET', (SELECT value FROM app_config WHERE key = 'RAZORPAY_KEY_SECRET'),
        'RAZORPAY_WEBHOOK_SECRET', (SELECT value FROM app_config WHERE key = 'RAZORPAY_WEBHOOK_SECRET')
    ) INTO v_config;
    
    RETURN v_config;
END;
$$ LANGUAGE plpgsql;
```

### 3. Payment Config

Update `config/payment_config.py`:

```python
PAYMENT_PROVIDER = PaymentProvider.RAZORPAY  # Switch to Razorpay
```

## Usage

### Basic Payment Flow

```python
from core.payment_handler import get_payment_handler
from ui.credit_purchase_dialog import CreditPurchaseDialog

# In your main window
dialog = CreditPurchaseDialog(
    parent=self,
    current_balance=current_credits,
    user_id=user_id,
    user_email=user_email
)
dialog.exec()
```

### Manual Payment Processing

```python
from core.payment_handler import get_payment_handler

# Get payment handler
handler = get_payment_handler()

# Check if available
if handler.is_available():
    # Create order
    order = handler.create_order_for_pack(
        pack_id="credits_small",
        user_id="user_123",
        email="user@example.com"
    )
    
    # Open payment page
    if order:
        handler.open_payment_page(order["id"])
        
        # Start polling
        handler.start_payment_polling(
            user_id="user_123",
            expected_credits=100
        )
```

### Webhook Handling

```python
from core.payment_handler import get_payment_handler

# In your webhook endpoint
handler = get_payment_handler()

# Verify webhook signature
if handler.verify_webhook(webhook_body, webhook_signature):
    # Process webhook
    success = handler.handle_webhook(webhook_data)
```

## API Reference

### RazorpayClient

Core client for Razorpay API operations:

```python
from core.razorpay_client import get_razorpay_client

client = get_razorpay_client()

# Check configuration
if client.is_configured():
    info = client.get_active_keys_info()
    print(info)  # Shows key status without exposing values

# Create order
order = client.create_order(
    amount=19900,  # Amount in paise (₹199)
    currency="INR",
    receipt="receipt_123",
    notes={"user_id": "user_123"}
)

# Verify payment
is_valid = client.verify_payment_signature(
    order_id="order_xxx",
    payment_id="pay_xxx",
    signature="signature_xxx"
)

# Create payment link
link = client.create_payment_link(
    amount=19900,
    description="100 Credits",
    callback_url="https://yourapp.com/callback"
)
```

### PaymentHandler

High-level handler for payment operations:

```python
from core.payment_handler import get_payment_handler, PaymentStatus

handler = get_payment_handler()

# Create order and open payment
order_id = handler.create_and_open_payment(
    pack_id="credits_small",
    user_id="user_123",
    email="user@example.com"
)

# Check payment status
status = handler.get_payment_status()

# Signals
handler.payment_completed.connect(on_payment_success)
handler.payment_failed.connect(on_payment_failure)
```

## File Structure

```
config/
├── payment_config.py       # Payment configuration
├── .env.example            # Environment variables template
├── RAZORPAY_INTEGRATION.md # This file

core/
├── razorpay_client.py      # Secure Razorpay client
├── payment_handler.py      # Payment operations handler
├── secret_manager.py       # Secure key management
├── credit_manager.py       # Credit operations

ui/
├── credit_purchase_dialog.py  # Updated purchase dialog
```

## Testing

### Test Mode

Use Razorpay test keys (starting with `rzp_test_`):

```bash
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
```

### Test Cards

Use these test card details:

- **Card Number**: 5267 3181 8797 5449
- **Expiry**: Any future date
- **CVV**: Any 3 digits
- **OTP**: 123456

### Testing Checklist

- [ ] Create order successfully
- [ ] Verify payment signature
- [ ] Credits added after payment
- [ ] Webhook received and processed
- [ ] Error handling works correctly
- [ ] Keys fetched from SecretManager
- [ ] Fallback to Payment Links works

## Troubleshooting

### Common Issues

**1. "Razorpay credentials not found"**
- Check environment variables are set
- Verify Supabase RPC is accessible
- Ensure valid license for remote secrets

**2. "Payment verification failed"**
- Check webhook secret is correct
- Verify signature calculation
- Ensure body is not modified before verification

**3. "Credits not added"**
- Check webhook is configured correctly
- Verify Supabase function permissions
- Review logs in `core/logger.py`

### Debug Mode

Enable debug logging:

```python
import logging
logging.getLogger("core.razorpay_client").setLevel(logging.DEBUG)
logging.getLogger("core.payment_handler").setLevel(logging.DEBUG)
```

## Production Deployment

### Checklist

1. [ ] Switch to live Razorpay keys
2. [ ] Configure webhook URL in Razorpay Dashboard
3. [ ] Test webhook signature verification
4. [ ] Set up Supabase RPC for secure key storage
5. [ ] Remove test keys from environment
6. [ ] Enable HTTPS for webhook endpoints
7. [ ] Set up monitoring and alerts

### Webhook Configuration

In Razorpay Dashboard:
1. Go to Settings → Webhooks
2. Add webhook URL: `https://your-api.com/webhook/razorpay`
3. Select events: `payment.captured`, `order.paid`
4. Set secret key (same as `RAZORPAY_WEBHOOK_SECRET`)

## Security Best Practices

1. **Never commit keys** to version control
2. **Use environment variables** for development only
3. **Fetch from Supabase** in production
4. **Verify all signatures** before processing
5. **Log security events** for audit trail
6. **Rotate keys regularly**
7. **Use HTTPS only** in production
8. **Validate user permissions** before adding credits

## Support

For issues or questions:
- Check logs in application directory
- Review Razorpay documentation: https://razorpay.com/docs
- Contact support with order IDs and error messages

## Changelog

### v1.0.0
- Initial Razorpay integration
- Secure key management via SecretManager
- Order-based and Payment Link support
- Webhook signature verification
- Automatic credit addition
