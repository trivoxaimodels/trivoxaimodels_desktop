import os
import requests
from dotenv import load_dotenv

load_dotenv()

access_token = os.getenv("SUPABASE_ACCESS_TOKEN")
project_id = "iiyewbxdgncosiqtllnm"

if not access_token:
    print("Error: SUPABASE_ACCESS_TOKEN not found in .env file")
    exit(1)

migration_sql = """
CREATE OR REPLACE FUNCTION public.check_device(p_fingerprint TEXT)
RETURNS json
LANGUAGE plpgsql
AS $$
DECLARE
    device_record RECORD;
    result json;
BEGIN
    SELECT * INTO device_record FROM public.registered_devices WHERE device_fingerprint = p_fingerprint;
    
    IF FOUND THEN
        UPDATE public.registered_devices SET last_login_at = now() WHERE device_fingerprint = p_fingerprint;
        result := json_build_object(
            'found', true,
            'registered', true,
            'trial_remaining', device_record.trial_remaining,
            'is_banned', device_record.is_banned,
            'ban_reason', device_record.ban_reason,
            'tamper_attempts', device_record.tamper_attempts
        );
    ELSE
        result := json_build_object(
            'found', false,
            'registered', false,
            'trial_remaining', 1,
            'is_banned', false,
            'tamper_attempts', 0
        );
    END IF;
    
    RETURN result;
END;
$$;

CREATE OR REPLACE FUNCTION public.register_device_server(p_fingerprint TEXT, p_password_hash TEXT, p_machine_name TEXT, p_platform TEXT, p_app_version TEXT)
RETURNS json
LANGUAGE plpgsql
AS $$
DECLARE
    device_record RECORD;
    result json;
BEGIN
    SELECT * INTO device_record FROM public.registered_devices WHERE device_fingerprint = p_fingerprint;
    
    IF FOUND THEN
        result := json_build_object(
            'success', false,
            'already_registered', true,
            'trial_remaining', device_record.trial_remaining,
            'message', 'Device is already registered.',
            'is_banned', device_record.is_banned
        );
    ELSE
        INSERT INTO public.registered_devices (device_fingerprint, password_hash, machine_name, platform, app_version, trial_remaining, trial_used, is_registered, registered_at, last_login_at)
        VALUES (p_fingerprint, p_password_hash, p_machine_name, p_platform, p_app_version, 1, 0, true, now(), now());
        
        result := json_build_object(
            'success', true,
            'already_registered', false,
            'trial_remaining', 1,
            'message', 'Device successfully registered.',
            'is_banned', false
        );
    END IF;
    
    RETURN result;
END;
$$;

CREATE OR REPLACE FUNCTION public.verify_device_login(p_fingerprint TEXT)
RETURNS json
LANGUAGE plpgsql
AS $$
DECLARE
    device_record RECORD;
    result json;
BEGIN
    SELECT * INTO device_record FROM public.registered_devices WHERE device_fingerprint = p_fingerprint;
    
    IF FOUND THEN
        UPDATE public.registered_devices SET last_login_at = now() WHERE device_fingerprint = p_fingerprint;
        result := json_build_object(
            'found', true,
            'password_hash', device_record.password_hash,
            'is_banned', device_record.is_banned,
            'ban_reason', device_record.ban_reason
        );
    ELSE
        result := json_build_object(
            'found', false,
            'password_hash', '',
            'is_banned', false,
            'ban_reason', ''
        );
    END IF;
    
    RETURN result;
END;
$$;

CREATE OR REPLACE FUNCTION public.use_device_trial(p_fingerprint TEXT)
RETURNS json
LANGUAGE plpgsql
AS $$
DECLARE
    device_record RECORD;
    result json;
BEGIN
    SELECT * INTO device_record FROM public.registered_devices WHERE device_fingerprint = p_fingerprint FOR UPDATE;
    
    IF NOT FOUND THEN
        result := json_build_object('success', false, 'remaining', 0, 'message', 'Device not found.');
    ELSIF device_record.trial_remaining > 0 THEN
        UPDATE public.registered_devices 
        SET trial_remaining = trial_remaining - 1, trial_used = trial_used + 1 
        WHERE device_fingerprint = p_fingerprint RETURNING trial_remaining INTO device_record.trial_remaining;
        
        result := json_build_object('success', true, 'remaining', device_record.trial_remaining, 'message', 'Trial used.');
    ELSE
        result := json_build_object('success', false, 'remaining', 0, 'message', 'No trial credits remaining.');
    END IF;
    
    RETURN result;
END;
$$;

CREATE OR REPLACE FUNCTION public.report_tamper_attempt(p_fingerprint TEXT, p_reason TEXT)
RETURNS json
LANGUAGE plpgsql
AS $$
DECLARE
    device_record RECORD;
    result json;
BEGIN
    SELECT * INTO device_record FROM public.registered_devices WHERE device_fingerprint = p_fingerprint FOR UPDATE;
    
    IF FOUND THEN
        UPDATE public.registered_devices 
        SET tamper_attempts = tamper_attempts + 1,
            is_banned = CASE WHEN tamper_attempts + 1 >= 3 THEN true ELSE is_banned END,
            ban_reason = CASE WHEN tamper_attempts + 1 >= 3 THEN 'Too many tamper attempts' ELSE ban_reason END,
            last_tamper_at = now()
        WHERE device_fingerprint = p_fingerprint;
        
        result := json_build_object('logged', true);
    ELSE
        result := json_build_object('logged', false);
    END IF;
    
    RETURN result;
END;
$$;
"""

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}

url = f"https://api.supabase.com/v1/projects/{project_id}/database/query"

print("Running corrected desktop SQL migration...")
try:
    response = requests.post(url, headers=headers, json={"query": migration_sql})
    if response.status_code in (200, 201):
        print("SQL executed successfully!")
    else:
        print(f"Error {response.status_code}: {response.text}")
except Exception as e:
    print(f"Failed: {e}")
