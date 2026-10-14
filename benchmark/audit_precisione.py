# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Raccoglie i dati grezzi per l'audit di precisione sui documenti reali.

Sette degli otto documenti in ``benchmark/documenti_utente/`` non hanno
annotazione ``.veri.json``: ``benchmark.utente`` per quelli sa contare le
sostituzioni ma non sa dire se siano giuste.  Questo script produce le due
metà che mancano, così che il giudizio si dia leggendo, non stimando:

  falsi positivi  — ogni entità emessa, col suo contesto nel testo, per la
                    classificazione a mano;
  falsi negativi  — una scansione del **testo in uscita** (quello già
                    anonimizzato) con espressioni volutamente larghe, che
                    ritrova ciò che il motore ha lasciato in chiaro.

La scansione dei residui non riusa i recognizer dell'applicazione: se
usasse la stessa logica che sta valutando, non troverebbe mai nulla.  Usa
schemi indipendenti e tolleranti agli errori dell'OCR, che sbagliano per
eccesso di proposte — filtrarle è compito di chi legge.

Due configurazioni, due domande diverse.  Con ``--categorie consegna``
(difetto) si misura il prodotto come esce di fabbrica.  Con ``--categorie
tutte`` si misura di che cosa il motore è capace: serve per LUOGO, ORG,
DATA e le altre categorie spente per difetto, che altrimenti non si
vedrebbero mai.

Uso:
    venv/bin/python -m benchmark.audit_precisione
    venv/bin/python -m benchmark.audit_precisione --categorie tutte
    venv/bin/python -m benchmark.audit_precisione --solo Indagine
    venv/bin/python -m benchmark.audit_precisione --rileggi   # ignora la cache
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from benchmark import CATEGORIE_CONSEGNA, isola

isola("audit")

CARTELLA = ROOT / "benchmark" / "documenti_utente"
VAULT_DB = os.environ.get("PRIVACYBRIDGE_AUDIT_VAULT", "/tmp/pb_audit_vault.db")

ESTENSIONI = {".pdf", ".docx", ".txt", ".md", ".csv", ".eml", ".rtf", ".odt", ".html"}
CONTESTO = 65
MAX_OCC = 3

# Il segnaposto sostituito dal motore: le regioni che lo contengono sono
# già coperte e vanno escluse dalla scansione dei residui, altrimenti ogni
# «CF_3» verrebbe riproposto come dato trovato in chiaro.
RE_SEGNAPOSTO = re.compile(r"«[A-Z_]+_\d+»")


# ---------------------------------------------------------------------------
# Schemi larghi per i residui — pensati per trovare, non per decidere
# ---------------------------------------------------------------------------
#
# Ogni schema accetta più di quanto dovrebbe: spazi dentro i numeri, punti
# fuori posto, cifre al posto di lettere.  Sono gli errori che l'OCR
# introduce e che fanno fallire i controlli di validità del motore, cioè
# esattamente i casi che l'audit deve far emergere.

RESIDUI: dict[str, re.Pattern[str]] = {
    # Spazi attorno alla chiocciola e punto subito dopo: due difetti
    # ricorrenti dell'OCR che rompono il riconoscimento delle e-mail.
    "email": re.compile(
        r"[A-Za-z0-9._%+\-]{2,}\s{0,3}@\s{0,3}\.?[A-Za-z0-9.\-]{2,}\.[A-Za-z]{2,}"
    ),
    # Sedici caratteri con la forma del codice fiscale, ma tollerando le
    # confusioni O/0 e I/1 che l'OCR produce e che invalidano il carattere
    # di controllo.
    "codice_fiscale": re.compile(r"\b[A-Z]{6}[0-9O]{2}[A-Z][0-9O]{2}[A-Z][0-9O]{3}[A-Z]\b"),
    "iban": re.compile(r"\b[A-Z]{2}[\s]?\d{2}[\s]?[A-Z0-9][\s\dA-Z]{10,28}\b"),
    # Da 13 a 19 cifre, con o senza separatori: la forma di una carta di
    # credito a prescindere dall'esito di Luhn.
    "sequenza_carta": re.compile(r"(?<![\d.,])(?:\d[ \-]?){12,18}\d(?![\d.,])"),
    "telefono_mobile": re.compile(r"(?:\+\s?39\s?)?\b3\d{2}[\s.\-/]?\d{3}[\s.\-/]?\d{3,4}\b"),
    "telefono_fisso": re.compile(r"(?:\+\s?39\s?)?\b0\d{1,3}[\s.\-/]?\d{5,8}\b"),
    "partita_iva": re.compile(r"(?<!\d)\d{11}(?!\d)"),
    "targa": re.compile(r"\b[A-Z]{2}\s?\d{3}\s?[A-Z]{2}\b"),
    "data_nascita": re.compile(r"\b\d{1,2}[/.\-]\d{1,2}[/.\-](?:19|20)\d{2}\b"),
    # Titolo di cortesia seguito da parola con l'iniziale maiuscola: è il
    # segnale di persona più forte che esista senza dizionario, e non
    # dipende da nessuna lista di nomi.
    "persona_da_titolo": re.compile(
        r"\b(?:Sig\.ra|Sig\.|Sig|Dott\.ssa|Dott\.|Dr\.|Avv\.|Ing\.|Prof\.ssa|Prof\.|"
        r"Geom\.|Rag\.|Arch\.|On\.|Mar\.llo|Mar\.|Isp\.|Sovr\.|Ass\.|Comm\.|"
        r"Cav\.|Don|Padre|Suor)\s+[A-Z][A-Za-zà-ùÀ-Ù'’]{2,}(?:\s+[A-Z][A-Za-zà-ùÀ-Ù'’]{2,})?"
    ),
    # Forme societarie: serve alla parte 1.2 (a) del mandato, dove il
    # richiamo delle organizzazioni è il limite dichiarato.
    "organizzazione": re.compile(
        r"\b(?:[A-Z][A-Za-zà-ùÀ-Ù&'’.\-]{1,}\s+){1,4}"
        r"(?:S\.?r\.?l\.?s?|S\.?p\.?A|S\.?n\.?c|S\.?a\.?s|S\.?c\.?a\.?r\.?l|"
        r"Soc\.?\s?Coop|SRL|SPA|SNC|SAS|Ltd|GmbH|Inc)\b\.?"
    ),
}


def _contesto(testo: str, a: int, b: int) -> str:
    i = max(0, a - CONTESTO)
    j = min(len(testo), b + CONTESTO)
    pre = testo[i:a].replace("\n", "⏎")
    dentro = testo[a:b].replace("\n", "⏎")
    post = testo[b:j].replace("\n", "⏎")
    return f"…{pre}⟦{dentro}⟧{post}…"


def _luhn(cifre: str) -> bool:
    n = [int(c) for c in cifre if c.isdigit()]
    if len(n) < 12:
        return False
    tot, doppio = 0, False
    for c in reversed(n):
        if doppio:
            c *= 2
            if c > 9:
                c -= 9
        tot += c
        doppio = not doppio
    return tot % 10 == 0


def _maschera_segnaposto(out: str) -> str:
    """Sostituisce ogni «TIPO_N» con altrettanti spazi.

    Gli indici restano allineati al testo originale — serve per stampare il
    contesto giusto — ma il contenuto sparisce, così la scansione dei
    residui non ripesca ciò che il motore ha già coperto.
    """
    return RE_SEGNAPOSTO.sub(lambda m: " " * len(m.group(0)), out)


def _estrai(path: Path, rileggi: bool) -> tuple[str, dict]:
    """Legge il documento, con cache su disco in ``estratti/``.

    L'estrazione di ``Indagine .pdf`` costa 21 secondi di OCR: senza cache
    ogni giro dell'audit ne pagherebbe il prezzo per intero.

    La cache sta in una sottocartella, non accanto agli originali, perché
    ``benchmark.utente`` elenca i file della cartella e non scende nelle
    sottocartelle: un dump ``.txt`` lasciato lì viene riletto come se
    fosse un documento dell'utente e raddoppia ogni conteggio.  È già
    accaduto — 349 sostituzioni invece di 141.  Restano comunque dentro
    ``documenti_utente/``, che git ignora: è il testo integrale di
    documenti privati e non va in una cartella temporanea condivisa.
    """
    cache_dir = CARTELLA / "estratti"
    cache_dir.mkdir(exist_ok=True)
    cache = cache_dir / (path.name + ".txt")
    meta_p = cache_dir / (path.name + ".json")
    if not rileggi and cache.exists() and cache.stat().st_mtime > path.stat().st_mtime:
        meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
        return cache.read_text(encoding="utf-8"), meta

    from backend.documenti import carica, info_ultimo_caricamento

    t0 = time.perf_counter()
    testo, _ = carica(str(path))
    meta = dict(info_ultimo_caricamento() or {})
    meta["secondi_estrazione"] = round(time.perf_counter() - t0, 2)
    cache.write_text(testo, encoding="utf-8")
    meta_p.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return testo, meta


def _entita_con_contesto(ents: list[dict], testo: str) -> list[dict]:
    fuori = []
    for e in ents:
        valore = e.get("valore_reale") or ""
        pos = [m.start() for m in re.finditer(re.escape(valore), testo)] if valore else []
        fuori.append({
            "tipo": e.get("tipo"),
            "valore": valore,
            "occorrenze": e.get("occorrenze"),
            "suggerito": bool(e.get("suggerito")),
            "correlato_a": e.get("correlato_a"),
            "ritrovata_nel_testo": bool(pos),
            "contesti": [_contesto(testo, p, p + len(valore)) for p in pos[:MAX_OCC]],
        })
    return fuori


def _residui(out: str) -> list[dict]:
    pulito = _maschera_segnaposto(out)
    trovati: list[dict] = []
    visti: set[tuple[str, str]] = set()
    for nome, rx in RESIDUI.items():
        for m in rx.finditer(pulito):
            grezzo = m.group(0).strip()
            if not grezzo:
                continue
            chiave = (nome, grezzo)
            if chiave in visti:
                continue
            visti.add(chiave)
            voce = {
                "schema": nome,
                "valore": grezzo,
                "contesto": _contesto(out, m.start(), m.end()),
            }
            if nome == "sequenza_carta":
                cifre = re.sub(r"\D", "", grezzo)
                voce["cifre"] = len(cifre)
                voce["luhn"] = _luhn(cifre)
            trovati.append(voce)
    return trovati


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--solo", help="analizza solo i file il cui nome contiene questo testo")
    ap.add_argument("--rileggi", action="store_true", help="ignora la cache di estrazione")
    ap.add_argument("--categorie", choices=("consegna", "tutte"), default="consegna",
                    help="quali categorie tenere accese (default: consegna)")
    args = ap.parse_args()

    file = sorted(
        p for p in CARTELLA.iterdir()
        if p.is_file() and p.suffix.lower() in ESTENSIONI
    )
    if args.solo:
        file = [p for p in file if args.solo.lower() in p.name.lower()]
    if not file:
        print(f"nessun documento in {CARTELLA}")
        return 1

    try:
        os.unlink(VAULT_DB)
    except FileNotFoundError:
        pass

    from backend.motore import CATEGORIE_TUTTE, anonimizza, reset_analyzer
    reset_analyzer()

    cat = set(CATEGORIE_TUTTE) if args.categorie == "tutte" else set(CATEGORIE_CONSEGNA)
    print(f"categorie: {args.categorie} ({len(cat)} accese)\n", flush=True)

    dati: list[dict] = []
    for i, path in enumerate(file, 1):
        print(f"[{i}/{len(file)}] {path.name}", flush=True)
        testo, meta = _estrai(path, args.rileggi)
        t0 = time.perf_counter()
        out, ents = anonimizza(testo, f"audit-{i}", db_path=VAULT_DB, categorie_attive=cat)
        secondi = round(time.perf_counter() - t0, 2)

        attive = [e for e in ents if not e.get("suggerito") and e.get("placeholder")]
        sugg = [e for e in ents if e.get("suggerito")]
        residui = _residui(out)
        print(
            f"    {len(testo):,} car — {len(attive)} attive, {len(sugg)} suggerite, "
            f"{len(residui)} residui — {secondi}s",
            flush=True,
        )

        dati.append({
            "file": path.name,
            "kb": round(path.stat().st_size / 1024, 1),
            "caratteri": len(testo),
            "estrazione": meta,
            "secondi_analisi": secondi,
            "attive": _entita_con_contesto(attive, testo),
            "suggerite": _entita_con_contesto(sugg, testo),
            "residui": residui,
        })

    uscita = ROOT / "benchmark" / f"audit_precisione_{args.categorie}.json"
    uscita.write_text(json.dumps(dati, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\ndati grezzi in {uscita.relative_to(ROOT)}")

    print("\n" + "=" * 78)
    print(f"{'documento':<42}{'attive':>8}{'sugg.':>8}{'residui':>9}")
    print("=" * 78)
    for d in dati:
        print(f"{d['file'][:41]:<42}{len(d['attive']):>8}{len(d['suggerite']):>8}"
              f"{len(d['residui']):>9}")
    print("=" * 78)
    print(f"{'TOTALE':<42}{sum(len(d['attive']) for d in dati):>8}"
          f"{sum(len(d['suggerite']) for d in dati):>8}"
          f"{sum(len(d['residui']) for d in dati):>9}")

    conta: dict[str, int] = {}
    for d in dati:
        for r in d["residui"]:
            conta[r["schema"]] = conta.get(r["schema"], 0) + 1
    print("\nresidui per schema (candidati falsi negativi, da classificare):")
    for nome, n in sorted(conta.items(), key=lambda x: -x[1]):
        print(f"  {nome:<20}{n:>5}")

    tipi: dict[str, int] = {}
    for d in dati:
        for e in d["attive"]:
            tipi[e["tipo"]] = tipi.get(e["tipo"], 0) + 1
    print("\nentità emesse per tipo:")
    for nome, n in sorted(tipi.items(), key=lambda x: -x[1]):
        print(f"  {nome:<20}{n:>5}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
