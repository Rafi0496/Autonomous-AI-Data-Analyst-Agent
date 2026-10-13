import urllib.request
import urllib.error
import json
import uuid
import sys

BACKEND_URL = "https://autonomous-ai-data-analyst-backend.onrender.com"
FRONTEND_URL = "https://autonomous-ai-data-analyst-frontend.onrender.com"

print("--- DIAGNOSTIC SCRIPT RUNNING ---")

# 1. Test Backend Health
try:
    req = urllib.request.Request(f"{BACKEND_URL}/api/v1/health", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as res:
        print("[OK] Backend Health:", res.status, res.read().decode())
except Exception as e:
    print("[FAIL] Backend Health:", e)

# 2. Test Anonymous Upload to Backend
boundary = "----WebKitFormBoundary" + uuid.uuid4().hex
csv_content = b"id,name,amount\n1,Alpha,100\n2,Beta,250\n3,Gamma,350\n"

body = bytearray()
body.extend(f"--{boundary}\r\n".encode())
body.extend(f'Content-Disposition: form-data; name="file"; filename="test.csv"\r\n'.encode())
body.extend(b"Content-Type: text/csv\r\n\r\n")
body.extend(csv_content)
body.extend(b"\r\n")
body.extend(f"--{boundary}--\r\n".encode())

dataset_id = None
try:
    req = urllib.request.Request(
        f"{BACKEND_URL}/api/v1/upload",
        data=bytes(body),
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "Mozilla/5.0"
        }
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        data = json.loads(res.read().decode())
        dataset_id = data.get("dataset_id")
        print("[OK] Direct Backend Upload 201:", data)
except urllib.error.HTTPError as e:
    print(f"[FAIL] Direct Backend Upload HTTP {e.code}: {e.read().decode()}")
except Exception as e:
    print("[FAIL] Direct Backend Upload Error:", e)

# 3. Test Clean & Profile on Backend
if dataset_id:
    try:
        req = urllib.request.Request(f"{BACKEND_URL}/api/v1/datasets/{dataset_id}/clean", data=b"", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as res:
            print("[OK] Direct Clean 200:", res.status)
    except urllib.error.HTTPError as e:
        print(f"[FAIL] Direct Clean HTTP {e.code}: {e.read().decode()}")

    try:
        req = urllib.request.Request(f"{BACKEND_URL}/api/v1/datasets/{dataset_id}/profile", data=b"", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as res:
            print("[OK] Direct Profile 200:", res.status)
    except urllib.error.HTTPError as e:
        print(f"[FAIL] Direct Profile HTTP {e.code}: {e.read().decode()}")

# 4. Test Chat on Backend
try:
    chat_payload = json.dumps({"query": "Hello", "dataset_id": dataset_id}).encode()
    req = urllib.request.Request(
        f"{BACKEND_URL}/api/v1/chat",
        data=chat_payload,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        print("[OK] Direct Chat 200:", res.read().decode()[:200])
except urllib.error.HTTPError as e:
    print(f"[FAIL] Direct Chat HTTP {e.code}: {e.read().decode()}")
except Exception as e:
    print("[FAIL] Direct Chat Error:", e)

# 5. Test General Chat (no dataset)
try:
    chat_payload = json.dumps({"query": "Hi"}).encode()
    req = urllib.request.Request(
        f"{BACKEND_URL}/api/v1/chat",
        data=chat_payload,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req, timeout=15) as res:
        print("[OK] General Chat 200:", res.read().decode()[:200])
except urllib.error.HTTPError as e:
    print(f"[FAIL] General Chat HTTP {e.code}: {e.read().decode()}")
except Exception as e:
    print("[FAIL] General Chat Error:", e)
