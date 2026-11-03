"""Tiny Airwallex sandbox caller for recon. Usage: python scripts/awx.py METHOD PATH [json-body] [--as ACCT] [--obo ACCT]"""
import json
import os
import sys

import httpx

sys.stdout.reconfigure(encoding="utf-8")


def env(name):
    if os.environ.get(name):
        return os.environ[name]
    if sys.platform == "win32":  # setx values are not visible to shells started before setx ran
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            return winreg.QueryValueEx(k, name)[0]
    raise KeyError(name)


BASE = env("AWX_BASE_URL")


def token(login_as=None):
    h = {"x-client-id": env("AWX_CLIENT_ID"), "x-api-key": env("AWX_API_KEY")}
    if login_as:
        h["x-login-as"] = login_as
    r = httpx.post(f"{BASE}/api/v1/authentication/login", headers=h, content=b"", timeout=30)
    r.raise_for_status()
    return r.json()["token"]


def call(method, path, body=None, login_as=None, obo=None):
    h = {"Authorization": f"Bearer {token(login_as)}"}
    if obo:
        h["x-on-behalf-of"] = obo
    r = httpx.request(method, f"{BASE}/api/v1{path}", headers=h, json=body, timeout=60)
    return r.status_code, (r.json() if r.content and "json" in r.headers.get("content-type", "") else r.text)


if __name__ == "__main__":
    args = sys.argv[1:]
    kw = {}
    for flag, key in (("--as", "login_as"), ("--obo", "obo")):
        if flag in args:
            i = args.index(flag)
            kw[key] = args[i + 1]
            del args[i:i + 2]
    method, path = args[0], args[1]
    body = json.loads(args[2]) if len(args) > 2 else None
    code, data = call(method, path, body, **kw)
    print("HTTP", code)
    print(json.dumps(data, indent=1)[:4000] if not isinstance(data, str) else data[:2000])
