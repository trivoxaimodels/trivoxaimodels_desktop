from core.session_manager import SessionManager
from core.supabase_client import get_supabase
import os

sm = SessionManager()
fp = sm.device_fingerprint
print(f"Device Fingerprint: {fp}")

sb = get_supabase()
res = sb.table("registered_devices").select("*").eq("device_fingerprint", fp).execute()
print(f"DB Record: {res.data}")

from core import server_auth
status = server_auth.check_device_server(fp)
print(f"Check Device Result: {status}")
