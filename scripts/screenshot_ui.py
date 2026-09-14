# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Screenshot di ogni schermata dell'interfaccia, in entrambi i temi.

Il testo usato è quello del gate finale: contiene dati veri per forma
(IBAN, partita IVA, targa, e-mail sintattiche) ma non riferiti ad alcuna
persona reale. Serve per vedere le tabelle piene, non vuote.

Uso:
    python scripts/screenshot_ui.py            # -> screenshots/<tema>_<n>_<nome>.png
    python scripts/screenshot_ui.py prefisso   # -> screenshots/prefisso_<tema>_...

Le schermate coperte, per tema:
    1 vuoto            avvio, nessun contenuto
    2 anonimizzato     due pannelli pieni, tabella entità, suggerimenti
    3 ripristina       scheda Ripristina con testo ripristinato
    4 categorie        dialogo "Cosa anonimizzare"
    5 rubrica          dialogo "Rubrica personale"
    6 informazioni     dialogo "Informazioni & aggiornamenti"
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"

VIEWPORT = {"width": 1400, "height": 900}
ATTESA_MOTORE_MS = 180_000

TESTO = (
    "Ciao sono Mario Rossi, nato a Roma il 15 maggio 1975.\n"
    "IBAN IT60X0542811101000000123456, email m.rossi@example.it, "
    "cell. 3201234567.\n"
    "Sono con marco, giovanni, maria, luisa e fiorella.\n"
    "PENSO che luca, o PASQUALE vengano con l'auto targata FG771XD.\n"
    "Rossi conferma l'ordine per Edilservice S.p.A., P.IVA 01234567890."
)


def porta_libera() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _scatta(pagina, nome: str, prefisso: str, tema: str) -> None:
    percorso = OUT / f"{prefisso}{tema}_{nome}.png"
    pagina.screenshot(path=str(percorso), full_page=True)
    print(f"  {percorso.relative_to(ROOT)}")


def schermate(pagina, prefisso: str, tema: str) -> None:
    """Percorre l'applicazione scattando ogni superficie."""
    pagina.wait_for_selector("#ta-originale", timeout=30_000)
    pagina.evaluate("(t) => applicaTema(t)", tema)
    _scatta(pagina, "1_vuoto", prefisso, tema)

    pagina.fill("#ta-originale", TESTO)
    pagina.click("#btn-anonimizza")
    pagina.wait_for_selector("#pannello-dx.completo", timeout=ATTESA_MOTORE_MS)
    _scatta(pagina, "2_anonimizzato", prefisso, tema)

    # Ripristina: si incolla l'anonimizzato e si torna all'originale.
    anonimizzato = pagina.inner_text("#vista-anonimizzato")
    pagina.click('.scheda[data-tab="ripristina"]')
    pagina.fill("#ta-risposta", anonimizzato)
    pagina.click("#btn-ripristina")
    pagina.wait_for_selector("#vista-ripristinato:not([hidden])", timeout=60_000)
    _scatta(pagina, "3_ripristina", prefisso, tema)
    pagina.click('.scheda[data-tab="anonimizza"]')

    # Il velo si apre subito, il contenuto arriva dopo la chiamata al
    # backend: senza attendere il contenuto si fotografa lo stato di
    # caricamento, e il gate chiede schermate con contenuto reale.
    for id_voce, velo, pronto, nome in (
        ("btn-categorie", "#velo-categorie",
         "#cat-lista input[type=checkbox]", "4_categorie"),
        ("btn-rubrica", "#velo-rubrica", "#rub-tipo option", "5_rubrica"),
        ("btn-info", "#velo-info", "#check-nota:not(:empty)", "6_informazioni"),
    ):
        pagina.click("#btn-menu")
        pagina.click(f"#{id_voce}")
        pagina.wait_for_selector(f"{velo}.aperto", timeout=15_000)
        pagina.wait_for_selector(pronto, state="attached", timeout=15_000)
        _scatta(pagina, nome, prefisso, tema)
        pagina.keyboard.press("Escape")
        pagina.wait_for_selector(velo, state="hidden", timeout=15_000)


def main() -> int:
    prefisso = f"{sys.argv[1]}_" if len(sys.argv) > 1 else ""
    OUT.mkdir(exist_ok=True)

    with TemporaryDirectory(prefix="pb-shot-") as tmp:
        env = os.environ.copy()
        env["PRIVACYBRIDGE_DATA_DIR"] = tmp
        env["PRIVACYBRIDGE_DB"] = str(Path(tmp) / "vault.db")
        env["HF_HUB_OFFLINE"] = "1"
        env["TRANSFORMERS_OFFLINE"] = "1"
        # Il codice sta in src/, il cwd resta la radice: i percorsi
        # relativi del figlio continuano a puntare dove puntavano.
        env["PYTHONPATH"] = str(ROOT / "src")

        porta = porta_libera()
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "api.main:app",
             "--host", "127.0.0.1", "--port", str(porta),
             "--log-level", "critical"],
            cwd=str(ROOT), env=env,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        try:
            time.sleep(8)
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                b = pw.chromium.launch(headless=True)
                for tema in ("chiaro", "scuro"):
                    print(f"[tema {tema}]")
                    ctx = b.new_context(viewport=VIEWPORT)
                    pagina = ctx.new_page()
                    pagina.goto(f"http://127.0.0.1:{porta}")
                    schermate(pagina, prefisso, tema)
                    ctx.close()
                b.close()
            return 0
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    sys.exit(main())
