#!/usr/bin/env python3
# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Misura le prestazioni reali dell'applicazione.

Quattro misure, nell'ordine in cui l'utente le incontra:

  1. **Avvio a freddo** — processo nuovo, come dopo un doppio clic
     sull'icona: quanto passa prima che la finestra abbia qualcosa da
     mostrare. Misurato in un sottoprocesso, altrimenti il modello già
     caricato in questo interprete falserebbe il numero.
  2. **Documenti reali dell'utente** — estrazione, anonimizzazione,
     ripristino e memoria su ogni file di ``benchmark/documenti_utente/``.
     Sono la misura che conta: un testo scritto per il benchmark dice
     solo quanto è veloce il benchmark.
  3. **Curva di scala** su testo sintetico, solo per le taglie che i
     documenti reali non raggiungono (100k, 500k caratteri). Serve a
     sapere dove finisce il lineare, non a dichiarare prestazioni.
  4. **Interrompibilità** — su mezzo milione di caratteri l'analisi
     supera i due minuti e non c'è modo di evitarlo: metà del tempo è
     inferenza del modello. Il numero che conta diventa quanto ci mette
     a fermarsi quando l'utente preme Annulla.
  5. **Tetto di memoria** — picco RSS del processo contro il limite di
     4 GiB.

Ogni riga verifica anche che il ripristino torni **identico byte per
byte** all'originale: una misura di velocità su un risultato sbagliato
non vale niente.

Uso:
    venv/bin/python -m benchmark.prestazioni | tee benchmark/prestazioni_output.txt
"""

from __future__ import annotations

import os
import resource
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

DOCUMENTI = ROOT / "benchmark" / "documenti_utente"
VAULT = "/tmp/pb_prestazioni_vault.db"
TETTO_MEMORIA_MIB = 4096
SOGLIA_INTERROMPIBILE_S = 120.0


def _rss_mib() -> float:
    """Picco RSS del processo. macOS riporta byte, Linux KiB."""
    ru = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return ru / (1024 * 1024) if sys.platform == "darwin" else ru / 1024


# ---------------------------------------------------------------------------
# 1. Avvio a freddo
# ---------------------------------------------------------------------------

# Riproduce il bootstrap di avvio.py fino al punto in cui la finestra
# riceve la pagina: porta libera, API in un thread, attesa di /health,
# prima GET della pagina. Non apre pywebview — la finestra nativa non è
# misurabile senza una sessione grafica, e il tempo che l'utente vede è
# dominato da questo tratto.
#
# La radice del progetto arriva dal ``cwd`` del sottoprocesso, non
# interpolata qui dentro: un solo livello di formattazione da leggere.
_SORGENTE_AVVIO = """
import os, sys, threading, time, urllib.request
sys.path.insert(0, os.path.join(os.getcwd(), "src"))
t0 = time.perf_counter()
import socket
with socket.socket() as s:
    s.bind(("127.0.0.1", 0))
    porta = s.getsockname()[1]

def serve():
    import uvicorn
    from api.main import app
    uvicorn.run(app, host="127.0.0.1", port=porta, log_level="critical")

threading.Thread(target=serve, daemon=True).start()
base = f"http://127.0.0.1:{porta}"
while True:
    try:
        with urllib.request.urlopen(base + "/health", timeout=1) as r:
            if r.status == 200:
                break
    except OSError:
        time.sleep(0.02)
t_health = time.perf_counter() - t0
with urllib.request.urlopen(base + "/", timeout=10) as r:
    r.read()
t_pagina = time.perf_counter() - t0
print(f"{t_health:.3f} {t_pagina:.3f}")
"""


def misura_avvio_a_freddo(ripetizioni: int = 3) -> list[tuple[float, float]]:
    misure = []
    for _ in range(ripetizioni):
        out = subprocess.run(
            [sys.executable, "-c", _SORGENTE_AVVIO],
            capture_output=True, text=True, cwd=str(ROOT), timeout=180,
            check=False,
        )
        if out.returncode != 0:
            raise RuntimeError(f"avvio fallito: {out.stderr[-2000:]}")
        health, pagina = out.stdout.strip().split()
        misure.append((float(health), float(pagina)))
    return misure


# ---------------------------------------------------------------------------
# 2. Documenti reali
# ---------------------------------------------------------------------------

def _documenti_utente() -> list[Path]:
    if not DOCUMENTI.is_dir():
        return []
    esclusi = {".gitkeep", ".json", ".md"}
    return sorted(
        p for p in DOCUMENTI.iterdir()
        if p.is_file() and p.suffix not in esclusi and p.name not in esclusi
    )


def _testo_sintetico(caratteri: int) -> str:
    from tests.corpus_annotato import CORPUS
    frasi = [f["testo"] for f in CORPUS]
    pezzi, n, i = [], 0, 0
    while n < caratteri:
        f = frasi[i % len(frasi)]
        pezzi.append(f)
        n += len(f) + 1
        i += 1
    return " ".join(pezzi)[:caratteri]


def main() -> int:
    print("=" * 78)
    print("PrivacyBridge — prestazioni misurate")
    print("=" * 78)
    print(f"Python   {sys.version.split()[0]}")
    print(f"Sistema  {sys.platform}")
    print()

    # ---- 1. Avvio a freddo -------------------------------------------
    print("1. AVVIO A FREDDO (processo nuovo, modello non ancora caricato)")
    print()
    misure = misura_avvio_a_freddo()
    print(f"   {'tentativo':>10} | {'API pronta (s)':>15} | {'pagina servita (s)':>19}")
    print("   " + "-" * 50)
    for i, (h, p) in enumerate(misure, 1):
        print(f"   {i:>10} | {h:>15.2f} | {p:>19.2f}")
    peggiore = max(p for _h, p in misure)
    print(f"\n   peggiore: {peggiore:.2f}s  (requisito: finestra entro 5s) "
          f"— {'OK' if peggiore < 5 else 'SUPERATO'}")
    print()

    if os.path.exists(VAULT):
        os.unlink(VAULT)

    from backend import avanzamento
    from backend.documenti import carica
    from backend.motore import anonimizza, deanonimizza, get_analyzer

    # ---- Caricamento del motore --------------------------------------
    rss_prima = _rss_mib()
    t0 = time.perf_counter()
    analyzer = get_analyzer()
    t_modello = time.perf_counter() - t0
    rss_dopo = _rss_mib()
    print(f"2. CARICAMENTO DEL MOTORE: {t_modello:.2f}s  "
          f"(RSS {rss_prima:.0f} → {rss_dopo:.0f} MiB)")
    print("   Pagato una volta sola, alla prima anonimizzazione, non all'avvio.")
    print()
    analyzer.analyze(text="Mario Rossi vive a Roma.", language="it")  # warm-up

    # ---- 3. Documenti reali ------------------------------------------
    print("3. DOCUMENTI REALI DELL'UTENTE")
    print()
    intest = (f"   {'documento':<40} | {'car.':>7} | {'estraz.':>8} | "
              f"{'anonim.':>8} | {'riprist.':>9} | {'ent.':>5} | {'RSS':>7}")
    print(intest)
    print("   " + "-" * (len(intest) - 3))

    picco = rss_dopo
    piu_lento = 0.0
    for doc in _documenti_utente():
        t0 = time.perf_counter()
        testo, _ = carica(str(doc))
        t_estr = time.perf_counter() - t0

        sid = f"prest-{uuid.uuid4().hex[:8]}"
        t0 = time.perf_counter()
        anon, ents = anonimizza(testo, sid, db_path=VAULT)
        t_anon = time.perf_counter() - t0

        t0 = time.perf_counter()
        rip, _ = deanonimizza(anon, sid, db_path=VAULT)
        t_rip = time.perf_counter() - t0

        if rip != testo:
            raise AssertionError(f"ripristino NON identico su {doc.name}")

        attivi = [e for e in ents if not e.get("suggerito")]
        rss = _rss_mib()
        picco = max(picco, rss)
        piu_lento = max(piu_lento, t_estr + t_anon)
        print(f"   {doc.name[:40]:<40} | {len(testo):>7,} | {t_estr:>8.1f} | "
              f"{t_anon:>8.1f} | {t_rip:>9.3f} | {len(attivi):>5} | {rss:>7.0f}")
    print()
    print("   Ogni riga verifica il ripristino identico byte per byte.")
    print()

    # ---- 4. Curva di scala -------------------------------------------
    print("4. CURVA DI SCALA (testo sintetico — solo per le taglie che i")
    print("   documenti reali non raggiungono)")
    print()
    intest = (f"   {'caratteri':>10} | {'anonim. (s)':>12} | {'car./s':>8} | "
              f"{'riprist. (s)':>13} | {'RSS':>7}")
    print(intest)
    print("   " + "-" * (len(intest) - 3))
    for taglia in (100_000, 500_000):
        testo = _testo_sintetico(taglia)
        sid = f"scala-{uuid.uuid4().hex[:8]}"
        t0 = time.perf_counter()
        anon, _ents = anonimizza(testo, sid, db_path=VAULT)
        t_anon = time.perf_counter() - t0
        t0 = time.perf_counter()
        rip, _ = deanonimizza(anon, sid, db_path=VAULT)
        t_rip = time.perf_counter() - t0
        if rip != testo:
            raise AssertionError(f"ripristino NON identico a {taglia} caratteri")
        rss = _rss_mib()
        picco = max(picco, rss)
        piu_lento = max(piu_lento, t_anon)
        print(f"   {len(testo):>10,} | {t_anon:>12.1f} | {len(testo)/t_anon:>8.0f} | "
              f"{t_rip:>13.3f} | {rss:>7.0f}")
    print()

    # ---- 5. Interrompibilità ------------------------------------------
    # Mezzo milione di caratteri sono più di due minuti e non c'è modo di
    # toglierli: metà del tempo è inferenza del modello. Quindi il numero
    # che conta non è quanto dura, ma quanto ci mette a fermarsi.
    print("5. INTERROMPIBILITÀ")
    print()
    testo = _testo_sintetico(500_000)
    esito: dict = {}

    def _lavora() -> None:
        t0 = time.perf_counter()
        try:
            anonimizza(testo, f"annulla-{uuid.uuid4().hex[:8]}", db_path=VAULT)
            esito["fine"] = "completata"
        except avanzamento.Annullato:
            esito["fine"] = "annullata"
        esito["durata"] = time.perf_counter() - t0

    lavoro = threading.Thread(target=_lavora)
    lavoro.start()
    print(f"   documento da {len(testo):,} caratteri "
          f"(oltre i {SOGLIA_INTERROMPIBILE_S:.0f}s di soglia)")
    print()
    print("   L'avanzamento sale di un blocco per volta: sono caratteri")
    print("   analizzati davvero, per questo il primo arriva dopo un blocco")
    print("   intero e non subito.")
    print()
    for _ in range(6):
        time.sleep(5.0)
        stato = avanzamento.stato_analisi()
        print(f"      {_ * 5 + 5:>3}s   {stato['fatti']:>7,} di "
              f"{stato['totali']:,} caratteri")
    t0 = time.perf_counter()
    avanzamento.annulla_analisi()
    lavoro.join(timeout=300)
    fermata = time.perf_counter() - t0
    print()
    print(f"   annullata a 30s:  esito '{esito['fine']}', "
          f"ferma in {fermata:.2f}s")
    ok_interrompibile = esito["fine"] == "annullata" and fermata < 5.0
    print()

    # ---- 6. Requisiti ------------------------------------------------
    print("6. REQUISITI")
    print()
    ok_mem = picco < TETTO_MEMORIA_MIB
    print(f"   memoria sotto {TETTO_MEMORIA_MIB} MiB      "
          f"{'OK' if ok_mem else 'SUPERATO'} — picco {picco:.0f} MiB")
    ok_avvio = peggiore < 5
    print(f"   finestra entro 5s          "
          f"{'OK' if ok_avvio else 'SUPERATO'} — peggiore {peggiore:.2f}s")
    print(f"   oltre {SOGLIA_INTERROMPIBILE_S:.0f}s interrompibile  "
          f"{'OK' if ok_interrompibile else 'SUPERATO'} — "
          f"si ferma in {fermata:.2f}s")
    print(f"   operazione più lunga misurata: {piu_lento:.1f}s")
    return 0 if (ok_mem and ok_avvio and ok_interrompibile) else 1


if __name__ == "__main__":
    sys.exit(main())
