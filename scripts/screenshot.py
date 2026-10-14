# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Genera screenshot dell'interfaccia PrivacyBridge per la consegna.

Usa un server FastAPI locale isolato + Chromium headless di Playwright.
Produce tre PNG in ``screenshots/``:

  01_iniziale.png            — vista Anonimizza vuota (stato di partenza)
  02_anonimizzato.png        — dopo Anonimizza, testo di esempio
  03_ripristina.png          — vista Ripristina con roundtrip completo

Uso: ``python scripts/screenshot.py`` dalla root del progetto.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"


TESTO = (
    "Gentile Mario Rossi,\n\n"
    "il colloquio è confermato per il 12 marzo 2026 presso la nostra sede "
    "di via Garibaldi 12, Milano. La invitiamo a presentare copia della "
    "carta d'identità e del codice fiscale (RSSMRA80A01H501U).\n\n"
    "Per contatti: mario.rossi@example.com, telefono 333 1234567.\n"
    "Per il rimborso spese, IBAN IT60X0542811101000000123456.\n\n"
    "La conferma è stata data da Luigi Bianchi per Beta Impianti.\n"
    "Cordiali saluti."
)


def _porta() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def main() -> int:
    OUT.mkdir(exist_ok=True)
    from playwright.sync_api import sync_playwright

    with TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env["PRIVACYBRIDGE_DATA_DIR"] = tmp
        env["PRIVACYBRIDGE_DB"] = str(Path(tmp) / "vault.db")
        env["HF_HUB_OFFLINE"] = "1"
        env["TRANSFORMERS_OFFLINE"] = "1"
        # Il codice sta in src/, il cwd resta la radice: i percorsi
        # relativi del figlio continuano a puntare dove puntavano.
        env["PYTHONPATH"] = str(ROOT / "src")
        porta = _porta()
        proc = subprocess.Popen(
            [
                sys.executable, "-m", "uvicorn", "api.main:app",
                "--host", "127.0.0.1", "--port", str(porta),
                "--log-level", "critical",
            ],
            cwd=str(ROOT), env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        )
        base = f"http://127.0.0.1:{porta}"
        try:
            for _ in range(600):
                try:
                    with urllib.request.urlopen(f"{base}/health", timeout=1) as r:
                        if r.status == 200:
                            break
                except Exception:
                    time.sleep(0.1)
            else:
                print("server non pronto")
                return 1

            with sync_playwright() as pw:
                b = pw.chromium.launch(headless=True)
                ctx = b.new_context(viewport={"width": 1400, "height": 900},
                                    device_scale_factor=2)
                page = ctx.new_page()
                page.goto(base)
                page.wait_for_selector("#btn-anonimizza")

                page.screenshot(path=str(OUT / "01_iniziale.png"), full_page=False)
                print("01_iniziale.png")

                page.fill("#ta-originale", TESTO)
                page.click("#btn-anonimizza")
                page.wait_for_selector("#pannello-dx.completo", timeout=180_000)
                page.screenshot(path=str(OUT / "02_anonimizzato.png"), full_page=False)
                print("02_anonimizzato.png")

                anon = page.locator("#vista-anonimizzato").inner_text()
                page.click('[data-tab="ripristina"]')
                page.fill("#ta-risposta",
                          "Buongiorno,\n\n" + anon +
                          "\n\nGrazie per la conferma.\nDistinti saluti,\nSegreteria")
                page.click("#btn-ripristina")
                page.wait_for_selector("#vista-ripristinato:not([hidden])",
                                       timeout=60_000)
                page.screenshot(path=str(OUT / "03_ripristina.png"), full_page=False)
                print("03_ripristina.png")

                b.close()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
