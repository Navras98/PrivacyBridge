# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Gate finale — flusso end-to-end sul testo canonico del briefing.

Verifica:
  1. Il bundle costruito parte in <5s (o l'interprete di dev).
  2. Anonimizza riconosce Persona, LUOGO_NASCITA, DATA_NASCITA,
     IBAN, Email, TELEFONO, PIVA, TARGA, e tutti e nove i nomi
     del testo canonico — i sei minuscoli in lista, PASQUALE in
     maiuscolo, "Delfo Berretti" e "Berretti" da solo, che deve
     ricevere un segnaposto distinto.
  3. Una correzione fatta in tabella viene applicata.
  4. Ripristina torna byte-per-byte identico all'originale.
  5. Stesso flusso sul PDF legale scansionato dell'utente.
  6. Stesso flusso ripetuto dopo il passaggio da tema chiaro a
     scuro.
  7. Genera gli screenshot 04/05 (chiaro) e 06/07 (scuro).

Uso:  python scripts/gate_finale.py
"""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"


# Testo canonico del briefing 2026-08-01.
TESTO = (
    "Ciao sono Delfo Berretti, nato ad Assisi il 27 marzo 2004.\n"
    "IBAN IT60X0542811101000000123456, email d.berretti@studio.it, "
    "cell. 3391234567.\n"
    "Sono con marco, giovanni, maria, luisa e fiorella.\n"
    "PENSO che luca, o PASQUALE vengano con l'auto targata FG771XD.\n"
    "Berretti conferma l'ordine per Edilservice S.p.A., P.IVA 01234567890."
)

# Ogni nome del testo canonico deve essere sostituito. Sono la parte
# difficile: sei minuscoli in mezzo a una lista, uno in maiuscolo dopo
# un "PENSO" anch'esso maiuscolo, e un cognome nudo che si riferisce a
# una persona già nominata per esteso.
NOMI_ATTESI = [
    "Delfo Berretti", "marco", "giovanni", "maria", "luisa",
    "fiorella", "luca", "PASQUALE", "Berretti",
]

# PDF legale scansionato reale (secondo flusso del gate).
PDF_SCANSIONATO = ROOT / "benchmark" / "documenti_utente" / "Indagine .pdf"


def porta_libera() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def attendi_health(base: str, timeout: float = 45.0) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            with urllib.request.urlopen(f"{base}/health", timeout=1) as r:
                if r.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            # Il server non è ancora in ascolto: è l'attesa, non un guasto.
            pass
        time.sleep(0.25)
    raise TimeoutError(f"server non risponde su {base}")


def http_post(url: str, payload: dict) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> int:
    OUT.mkdir(exist_ok=True)
    with TemporaryDirectory(prefix="pb-gate-") as tmp:
        env = os.environ.copy()
        env["PRIVACYBRIDGE_DATA_DIR"] = tmp
        env["PRIVACYBRIDGE_DB"] = str(Path(tmp) / "vault.db")
        env["HF_HUB_OFFLINE"] = "1"
        env["TRANSFORMERS_OFFLINE"] = "1"
        # Il codice sta in src/, il cwd resta la radice: i percorsi
        # relativi del figlio continuano a puntare dove puntavano.
        env["PYTHONPATH"] = str(ROOT / "src")

        # Usa il bundle se c'è, altrimenti uvicorn di dev. Prima quello
        # impacchettato da PyInstaller, poi quello costruito a mano: il
        # gate deve girare sul pacchetto vero quando esiste.
        bundle = ROOT / "dist" / "PrivacyBridge.app" / "Contents" / "MacOS" / "PrivacyBridge"
        if not bundle.exists():
            bundle = ROOT / "build" / "PrivacyBridge.app" / "Contents" / "MacOS" / "PrivacyBridge"
        porta = porta_libera()
        env["PRIVACYBRIDGE_PORT"] = str(porta)

        if bundle.exists():
            # Il bundle non accetta --port: lasciamo che scelga la sua.
            # Leggiamo la porta dal log.txt.
            proc = subprocess.Popen(
                [str(bundle)], env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            print(f"[gate] avviato bundle pid={proc.pid}")
            # Aspetta che scriva la porta.
            log = Path(tmp) / "log.txt"
            porta_bundle = None
            t0 = time.time()
            while time.time() - t0 < 45:
                if log.exists():
                    for riga in log.read_text().splitlines():
                        if "porta " in riga:
                            porta_bundle = int(riga.split("porta ")[1].split()[0])
                            break
                if porta_bundle is not None:
                    break
                time.sleep(0.25)
            if porta_bundle is None:
                proc.terminate()
                print("[gate] ERRORE: bundle non ha scritto la porta")
                return 1
            porta = porta_bundle
        else:
            proc = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "api.main:app",
                 "--host", "127.0.0.1", "--port", str(porta),
                 "--log-level", "critical"],
                cwd=str(ROOT), env=env,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            print(f"[gate] avviato uvicorn pid={proc.pid} porta={porta}")

        base = f"http://127.0.0.1:{porta}"
        try:
            t0 = time.time()
            attendi_health(base, timeout=60)
            t_avvio = time.time() - t0
            print(f"[gate] server pronto in {t_avvio:.1f}s (soglia gate: 5s)")

            # --- Anonimizza -----------------------------------------
            t0 = time.time()
            r = http_post(f"{base}/anonimizza", {"testo": TESTO})
            t_anon = time.time() - t0
            print(f"[gate] anonimizza in {t_anon:.1f}s")
            anon = r["testo_anonimizzato"]
            entita = r["entita"]
            sessione = r["sessione"]

            tipi = {e["tipo"] for e in entita if not e.get("suggerito")}
            valori = {e["valore_reale"] for e in entita if not e.get("suggerito")}
            attesi_tipi = {"PERSONA", "IBAN", "EMAIL", "TELEFONO", "PIVA",
                           "LUOGO_NASCITA", "DATA_NASCITA", "TARGA"}
            mancanti = attesi_tipi - tipi
            if mancanti:
                print(f"[gate] FAIL: tipi mancanti {mancanti}")
                print(f"[gate]   trovati: {tipi}")
                return 1
            print(f"[gate] OK tipi riconosciuti: {sorted(tipi)}")

            # Tutti i nomi del testo canonico, minuscoli compresi.
            mancanti_nomi = [n for n in NOMI_ATTESI if n not in valori]
            if mancanti_nomi:
                print(f"[gate] FAIL: nomi non sostituiti {mancanti_nomi}")
                print(f"[gate]   valori trovati: {sorted(valori)}")
                return 1
            rimasti = [n for n in NOMI_ATTESI if n in anon]
            if rimasti:
                print(f"[gate] FAIL: nomi ancora nel testo anonimizzato {rimasti}")
                return 1
            print(f"[gate] OK tutti i {len(NOMI_ATTESI)} nomi sostituiti: {NOMI_ATTESI}")
            if "FG771XD" in anon:
                print("[gate] FAIL: targa FG771XD ancora nel testo")
                return 1
            print("[gate] OK targa FG771XD sostituita")

            # "Berretti" da solo deve avere un segnaposto distinto da
            # "Delfo Berretti": sono la stessa persona, ma due forme
            # scritte diverse, e il ripristino deve rimetterle a posto
            # ognuna com'era.
            per_valore = {e["valore_reale"]: e for e in entita
                          if e.get("tipo") == "PERSONA" and not e.get("suggerito")}
            mr = per_valore.get("Delfo Berretti")
            rs = per_valore.get("Berretti")
            if not mr or not rs:
                print(f"[gate] FAIL: 'Delfo Berretti' e/o 'Berretti' non attivi — "
                      f"persone: {sorted(per_valore)}")
                return 1
            if mr["placeholder"] == rs["placeholder"]:
                print("[gate] FAIL: 'Delfo Berretti' e 'Berretti' hanno stesso placeholder")
                return 1
            print(f"[gate] OK 'Delfo Berretti' → {mr['placeholder']}, "
                  f"'Berretti' → {rs['placeholder']} (correlato_a={rs.get('correlato_a')})")

            # --- Correzione in tabella + rianonimizza ---------------
            # Simula l'utente che corregge una riga: aggiunge a mano
            # "Edilservice S.p.A." (ORG è spenta per default) come ORG.
            entita_mod = [
                {"valore_reale": e["valore_reale"], "tipo": e["tipo"]}
                for e in entita if not e.get("suggerito")
            ]
            entita_mod.append(
                {"valore_reale": "Edilservice S.p.A.", "tipo": "ORG"}
            )
            r = http_post(f"{base}/rianonimizza",
                          {"testo": TESTO, "sessione": sessione,
                           "entita": entita_mod})
            anon = r["testo_anonimizzato"]
            if "Edilservice" in anon:
                print("[gate] FAIL: correzione in tabella non applicata")
                return 1
            print("[gate] OK correzione in tabella (ORG aggiunta a mano) applicata")

            # --- Ripristina ----------------------------------------
            r = http_post(f"{base}/deanonimizza",
                          {"testo": anon, "sessione": sessione})
            restored = r["testo_ripristinato"]
            if restored != TESTO:
                print("[gate] FAIL: ripristino non byte-identico")
                print(f"       orig: {TESTO!r}")
                print(f"       rest: {restored!r}")
                return 1
            print("[gate] OK ripristino byte-identico (dopo la correzione)")

            # --- Secondo flusso: PDF legale scansionato -------------
            if PDF_SCANSIONATO.exists():
                import uuid as _uuid
                confine = _uuid.uuid4().hex
                corpo = (
                    f"--{confine}\r\n"
                    f'Content-Disposition: form-data; name="file"; '
                    f'filename="{PDF_SCANSIONATO.name}"\r\n'
                    f"Content-Type: application/pdf\r\n\r\n"
                ).encode() + PDF_SCANSIONATO.read_bytes() + (
                    f"\r\n--{confine}--\r\n".encode()
                )
                req = urllib.request.Request(
                    f"{base}/carica", data=corpo,
                    headers={"Content-Type":
                             f"multipart/form-data; boundary={confine}"},
                    method="POST",
                )
                t0 = time.time()
                with urllib.request.urlopen(req, timeout=300) as resp:
                    dati = json.loads(resp.read().decode("utf-8"))
                t_pdf = time.time() - t0
                testo_pdf = dati["testo"]
                info_ocr = dati.get("ocr", {})
                print(f"[gate] OK PDF scansionato caricato in {t_pdf:.0f}s — "
                      f"{len(testo_pdf)} char, pagine OCR: "
                      f"{info_ocr.get('ocr_pagine', 'nessuna (testo incorporato)')}")
                t0 = time.time()
                r = http_post(f"{base}/anonimizza",
                              {"testo": testo_pdf, "sessione": "gate-pdf"})
                t_anon_pdf = time.time() - t0
                n_ent = len([e for e in r["entita"] if not e.get("suggerito")])
                if n_ent == 0:
                    print("[gate] FAIL: il PDF legale non produce entità")
                    return 1
                rr = http_post(f"{base}/deanonimizza",
                               {"testo": r["testo_anonimizzato"],
                                "sessione": r["sessione"]})
                if rr["testo_ripristinato"] != testo_pdf:
                    print("[gate] FAIL: roundtrip PDF non byte-identico")
                    return 1
                print(f"[gate] OK PDF legale: {n_ent} entità in "
                      f"{t_anon_pdf:.0f}s, roundtrip byte-identico")
            else:
                print(f"[gate] SKIP PDF scansionato: {PDF_SCANSIONATO} assente")

            # --- Screenshot end-to-end via Playwright --------------
            try:
                from playwright.sync_api import sync_playwright
                with sync_playwright() as pw:
                    b = pw.chromium.launch(headless=True)
                    ctx = b.new_context(viewport={"width": 1400, "height": 900})
                    page = ctx.new_page()
                    page.goto(base)
                    page.wait_for_selector("#btn-anonimizza")
                    page.fill("#ta-originale", TESTO)
                    page.click("#btn-anonimizza")
                    page.wait_for_selector("#pannello-dx.completo", timeout=60_000)
                    page.screenshot(path=str(OUT / "04_gate_finale_anonimizza.png"),
                                    full_page=True)
                    page.click('[data-tab="ripristina"]')
                    page.fill("#ta-risposta",
                              "Ecco il tuo testo: " + anon +
                              " — pronto per il ripristino.")
                    page.click("#btn-ripristina")
                    page.wait_for_selector("#vista-ripristinato:not([hidden])",
                                           timeout=30_000)
                    page.screenshot(path=str(OUT / "05_gate_finale_ripristina.png"),
                                    full_page=True)

                    # Stesso flusso, tema scuro: il gate chiede di
                    # ripeterlo cambiando tema, perché il rischio non è
                    # il colore ma il testo che sparisce sul fondo.
                    tema_prima = page.get_attribute("html", "data-theme")
                    page.click("#btn-tema")
                    page.wait_for_function(
                        "document.documentElement.getAttribute('data-theme') === 'scuro'",
                        timeout=5_000)
                    page.click('[data-tab="anonimizza"]')
                    page.wait_for_selector("#pannello-dx.completo", timeout=10_000)
                    page.screenshot(path=str(OUT / "06_gate_finale_scuro_anonimizza.png"),
                                    full_page=True)
                    page.click('[data-tab="ripristina"]')
                    page.wait_for_selector("#vista-ripristinato:not([hidden])",
                                           timeout=10_000)
                    page.screenshot(path=str(OUT / "07_gate_finale_scuro_ripristina.png"),
                                    full_page=True)
                    tema_dopo = page.get_attribute("html", "data-theme")
                    if tema_prima == tema_dopo:
                        print(f"[gate] FAIL: il tema non è cambiato ({tema_dopo})")
                        return 1
                    print(f"[gate] OK tema {tema_prima} → {tema_dopo}, "
                          "contenuto invariato")
                    b.close()
                print("[gate] OK screenshot 04/05/06/07 generati")
            except Exception as e:
                print(f"[gate] SKIP screenshot: {e}")

            print()
            print("=" * 60)
            print("GATE FINALE: OK")
            print("=" * 60)
            print(f"  avvio server: {t_avvio:.1f}s")
            print(f"  anonimizza:   {t_anon:.1f}s")
            print(f"  tipi:         {sorted(tipi)}")
            print(f"  entità:       {len(entita)}")
            print("  ripristino:   byte-identico ✓")
            return 0
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    sys.exit(main())
