import json, time
from ringfence.awx import Awx, AwxError
k = Awx().for_tenant("kestrel")
try:
    ga = k.post("/global_accounts/create", {"request_id": "rf-probe-ga-us2-" + str(int(time.time())), "country_code": "US",
                "nick_name": "Kestrel USD", "required_features": [{"currency": "USD", "transfer_method": "LOCAL"}]})
    print("GA", json.dumps(ga, default=str)[:900])
except AwxError as e:
    print("GA ERR", e.status, e.code, e.message[:300], e.details)
print("existing GAs:", json.dumps(k.get("/global_accounts"), default=str)[:600])
