import os
import requests
from dotenv import load_dotenv

load_dotenv()

access_token = os.getenv("SUPABASE_ACCESS_TOKEN")
project_id = "iiyewbxdgncosiqtllnm"

migration_sql = """
CREATE OR REPLACE FUNCTION public.register_device_server(p_fingerprint TEXT, p_password_hash TEXT, p_machine_name TEXT, p_platform TEXT, p_app_version TEXT)
RETURNS json
LANGUAGE plpgsql
AS $$
DECLARE
    device_record RECORD;
    new_user_id UUID;
    result json;
BEGIN
    SELECT * INTO device_record FROM public.registered_devices WHERE device_fingerprint = p_fingerprint;
    
    IF FOUND THEN
        -- If already registered but no user_id, let's create one
        IF device_record.user_id IS NULL THEN
            INSERT INTO public.web_users (username, password_hash, device_fingerprint, trial_remaining, trial_used)
            VALUES ('DeviceUser_' || substr(p_fingerprint, 1, 8), p_password_hash, p_fingerprint, 1, 0)
            RETURNING id INTO new_user_id;

            UPDATE public.registered_devices SET user_id = new_user_id WHERE device_fingerprint = p_fingerprint;
            device_record.user_id := new_user_id;
        END IF;

        result := json_build_object(
            'success', true,
            'user_id', device_record.user_id,
            'already_registered', true,
            'trial_remaining', device_record.trial_remaining,
            'message', 'Device is already registered, returning user.',
            'is_banned', device_record.is_banned
        );
    ELSE
        -- Create user
        INSERT INTO public.web_users (username, password_hash, device_fingerprint, trial_remaining, trial_used)
        VALUES ('DeviceUser_' || substr(p_fingerprint, 1, 8), p_password_hash, p_fingerprint, 1, 0)
        RETURNING id INTO new_user_id;

        -- Create device
        INSERT INTO public.registered_devices (device_fingerprint, user_id, password_hash, machine_name, platform, app_version, trial_remaining, trial_used, is_registered, registered_at, last_login_at)
        VALUES (p_fingerprint, new_user_id, p_password_hash, p_machine_name, p_platform, p_app_version, 1, 0, true, now(), now());

        -- Initial balance
        INSERT INTO public.user_credits (user_id, credits_balance, total_purchased, total_used)
        VALUES (new_user_id, 0, 0, 0);

        result := json_build_object(
            'success', true,
            'user_id', new_user_id,
            'already_registered', false,
            'trial_remaining', 1,
            'message', 'Device and user successfully registered.',
            'is_banned', false
        );
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

response = requests.post(url, headers=headers, json={"query": migration_sql})
print(response.status_code, response.text)
