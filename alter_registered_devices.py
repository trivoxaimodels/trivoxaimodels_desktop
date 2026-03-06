import os
import requests
from dotenv import load_dotenv

load_dotenv()

access_token = os.getenv("SUPABASE_ACCESS_TOKEN")
project_id = "iiyewbxdgncosiqtllnm"

migration_sql = """
ALTER TABLE public.registered_devices
ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES public.web_users(id) ON DELETE CASCADE;

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
            'user_id', device_record.user_id,
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
"""

headers = {
    "Authorization": f"Bearer {access_token}",
    "Content-Type": "application/json"
}
url = f"https://api.supabase.com/v1/projects/{project_id}/database/query"

response = requests.post(url, headers=headers, json={"query": migration_sql})
print(response.status_code, response.text)
