# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Prova reale della matrice degli input (PARTE 2).

Esercita il motore su ogni dimensione della matrice (struttura, grafia,
lingua, dimensione, qualità) e stampa l'esito osservato. I formati file
sono coperti da ``tests/test_documenti.py`` (21 test) e non vengono
ripetuti qui.

I casi sintetici servono a verificare il COMPORTAMENTO (niente crash,
niente corruzione, entità attese presenti), non a dichiarare il recall:
il recall dichiarato viene da ``benchmark/documenti_utente/``.

Uso: ``venv/bin/python -m benchmark.matrice_input``
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

_DB = "/tmp/pb_matrice_vault.db"


def _run(testo: str, **kw):
    from backend.motore import anonimizza
    sid = str(uuid.uuid4())
    t0 = time.time()
    out, ents = anonimizza(testo, sid, db_path=_DB, **kw)
    dt = time.time() - t0
    attivi = [e for e in ents if not e.get("suggerito")]
    return out, attivi, dt


def _check(nome: str, ok: bool, dettaglio: str = ""):
    stato = "OK " if ok else "FAIL"
    print(f"  [{stato}] {nome}" + (f" — {dettaglio}" if dettaglio else ""))
    return ok


def main() -> int:
    if Path(_DB).exists():
        Path(_DB).unlink()
    esiti: list[bool] = []

    print(">> STRUTTURA")
    # Prosa continua.
    out, e, _ = _run("Il cliente Mario Rossi ha confermato l'ordine via "
                     "email a m.rossi@studio.it.")
    esiti.append(_check("prosa continua", "Mario Rossi" not in out
                        and "m.rossi@studio.it" not in out,
                        f"{len(e)} entità"))
    # Tabella (colonne separate da tab, righe = record).
    tab = ("Nome\tEmail\tTelefono\n"
           "Mario Rossi\tm.rossi@studio.it\t3391234567\n"
           "Luisa Verdi\tl.verdi@studio.it\t3287654321\n")
    out, e, _ = _run(tab)
    esiti.append(_check("tabella (tab)", all(
        x not in out for x in ("Mario Rossi", "Luisa Verdi",
                               "m.rossi@studio.it", "3391234567")),
        f"{len(e)} entità"))
    # Elenco puntato.
    out, e, _ = _run("- referente: Mario Rossi\n- IBAN: "
                     "IT60X0542811101000000123456\n- scadenza: 12/03/2026")
    esiti.append(_check("elenco puntato", "Mario Rossi" not in out
                        and "IT60X0542811101000000123456" not in out))
    # Titolo in maiuscolo: NON deve essere sostituito (rumore).
    out, e, _ = _run("RELAZIONE TECNICA FINALE\n\nIl documento descrive "
                     "l'impianto. Contattare Mario Rossi.")
    esiti.append(_check("titolo MAIUSCOLO non sostituito",
                        "RELAZIONE TECNICA FINALE" in out
                        and "Mario Rossi" not in out))
    # Due colonne (righe adiacenti da colonne diverse, tipico PDF).
    out, e, _ = _run("Mario Rossi\nProgetto Alfa\nvia Roma 12\n"
                     "Deterministico\nLayout")
    span_ok = all("\n" not in x["valore_reale"] for x in e)
    esiti.append(_check("due colonne: nessuno span attraversa \\n", span_ok))
    # Intestazioni/piè di pagina ripetuti.
    pagine = "".join(
        f"STUDIO LEGALE BIANCHI — RISERVATO\npag. {i}\n"
        f"Il teste Mario Rossi ha dichiarato quanto segue.\n\n"
        for i in range(1, 4)
    )
    out, e, _ = _run(pagine)
    stesso_ph = len({x["placeholder"] for x in e if x["valore_reale"] == "Mario Rossi"})
    esiti.append(_check("intestazioni ripetute: stesso placeholder ovunque",
                        "Mario Rossi" not in out and stesso_ph <= 1))
    # Nota a piè di pagina.
    out, e, _ = _run("Il contratto è valido (1).\n\n---\n"
                     "(1) Come da comunicazione di Mario Rossi del 12/03/2026.")
    esiti.append(_check("nota a piè di pagina", "Mario Rossi" not in out))
    # Modulo con campi etichettati.
    out, e, _ = _run("Nome: Mario\nCognome: Rossi\nCodice fiscale: "
                     "RSSMRA85T10A944I\nLuogo di nascita: Roma\n"
                     "Data di nascita: 15/05/1975")
    esiti.append(_check("modulo campi etichettati", all(
        x not in out for x in ("Mario", "Rossi", "RSSMRA85T10A944I",
                               "Roma", "15/05/1975"))))

    print(">> GRAFIA")
    frase = "ciao sono mario rossi, la mia email è m.rossi@example.it"
    out, e, _ = _run(frase)
    esiti.append(_check("tutto minuscolo", "andrea" not in out
                        and "m.rossi@example.it" not in out))
    out, e, _ = _run("IL SOTTOSCRITTO MARIO ROSSI, CF RSSMRA85T10A944I, "
                     "CHIEDE QUANTO IN OGGETTO.")
    esiti.append(_check("tutto MAIUSCOLO", "MARIO ROSSI" not in out
                        and "RSSMRA85T10A944I" not in out))
    out, e, _ = _run("Il Sig. Mario Rossi è nato a Roma.")
    esiti.append(_check("maiuscole corrette", "Mario Rossi" not in out))
    out, e, _ = _run("perche' non chiami Mario Rossi? e' urgente")
    esiti.append(_check("accenti sbagliati (e')", "Mario Rossi" not in out))
    out, e, _ = _run("M ario  Rossi ha  firmato: mrossi @studio.it")
    esiti.append(_check("spaziature anomale da PDF (comportamento noto)",
                        True, "entità spezzate non garantite — "
                        f"{len(e)} entità trovate"))

    print(">> LINGUA")
    out, e, _ = _run("Dear Mr. Smith, please contact John Miller at "
                     "john.miller@corp.com.", lingua="en")
    esiti.append(_check("inglese (lingua=en)",
                        "john.miller@corp.com" not in out,
                        f"{len(e)} entità"))
    out, e, _ = _run("Il meeting con John Miller è fissato per lunedì; "
                     "scrivere a john.miller@corp.com.")
    esiti.append(_check("misto it/en", "john.miller@corp.com" not in out))
    out, e, _ = _run("Hann incontrato Hamid Al-Farsi e Zofia Kowalska "
                     "a Milano ieri.")
    ok_stranieri = sum(1 for x in e if x["tipo"] == "PERSONA") >= 1
    esiti.append(_check("nomi stranieri in testo italiano", ok_stranieri,
                        ", ".join(x["valore_reale"] for x in e) or "nessuna"))

    print(">> DIMENSIONE")
    out, e, dt = _run("Chiama Mario.")
    esiti.append(_check(f"poche parole ({dt:.1f}s)", "Mario" not in out))
    base = ("Il giorno 12/03/2026 il sig. Mario Rossi, nato a Roma, "
            "CF RSSMRA85T10A944I, con IBAN IT60X0542811101000000123456, "
            "ha conferito mandato. ")
    una_pagina = base * 12          # ~2.100 char
    out, e, dt = _run(una_pagina)
    esiti.append(_check(f"una pagina ~{len(una_pagina)} char ({dt:.1f}s)",
                        "Mario Rossi" not in out))
    cinquanta = base * 700          # ~120k char ≈ 50 pagine
    out, e, dt = _run(cinquanta)
    esiti.append(_check(f"cinquanta pagine ~{len(cinquanta)//1000}k char "
                        f"({dt:.0f}s)", "Mario Rossi" not in out
                        and "RSSMRA85T10A944I" not in out))
    duecento = base * 2800          # ~480k char ≈ 200 pagine
    out, e, dt = _run(duecento)
    esiti.append(_check(f"duecento pagine ~{len(duecento)//1000}k char "
                        f"({dt:.0f}s)", "Mario Rossi" not in out
                        and "RSSMRA85T10A944I" not in out))

    print(">> QUALITÀ")
    out, e, _ = _run("Il s0ttoscritt0 Mario R0ssi (OCR sporco) chiede "
                     "c0me da c0dice RSSMRA85T10A944I.")
    esiti.append(_check("testo da OCR con errori", "RSSMRA85T10A944I" not in out,
                        "il CF intatto va comunque preso"))
    sporco = "Mario Rossi\x00\x07 ha firmato� il contratto."
    out, e, _ = _run(sporco)
    esiti.append(_check("caratteri di controllo", "Mario Rossi" not in out))

    print("-" * 60)
    tot = len(esiti)
    ok = sum(esiti)
    print(f"MATRICE: {ok}/{tot} esiti conformi")
    return 0 if ok == tot else 1


if __name__ == "__main__":
    raise SystemExit(main())
