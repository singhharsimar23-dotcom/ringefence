"""P9: error shape for a garbage / malformed bearer token."""
import json

import httpx

from ringfence.awx import Awx

a = Awx()
out = {}
for name, tok in (("garbage", "garbage"), ("jwt_like", "eyJhbGciOiJIUzI1NiJ9.e30.abc")):
    r = httpx.get(f"{a.base}/balances/current", headers={"Authorization": f"Bearer {tok}"})
    out[name] = {"status": r.status_code, "body": r.text[:200]}
r = httpx.get(f"{a.base}/balances/current")
out["no_auth"] = {"status": r.status_code, "body": r.text[:200]}
print(json.dumps(out))
