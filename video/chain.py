"""Screenshot the public Metal testnet explorer for the run's real txs (pull, over-pull refusal, lookalike refusal).
Reads video/src/facts.json (run video/facts.py first). Writes video/public/chain/{pull,over,poison}.png.
Usage: uv run --with playwright python video/chain.py"""
import asyncio
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


async def main() -> None:
    from playwright.async_api import async_playwright
    f = json.loads((ROOT / "src/facts.json").read_text(encoding="utf-8"))
    refused = {r["code"]: r for r in f["metal_refused"]}
    shots = {"pull": f["metal_pull"][0]["tx"], "over": refused["mandate_cap_exceeded"]["tx"], "poison": refused["mandate_payee_not_listed"]["tx"]}
    out = ROOT / "public/chain"
    out.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="msedge", headless=True)
        page = await b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2, color_scheme="dark")
        for name, tx in shots.items():
            await page.goto(f"https://testnet.metalntwx.com/tx/{tx}", wait_until="networkidle", timeout=90_000)
            await page.wait_for_timeout(2500)
            await page.screenshot(path=str(out / f"{name}.png"))
            print(name, tx)
        await b.close()


asyncio.run(main())
