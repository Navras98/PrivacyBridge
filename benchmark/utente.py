# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Misuratore sui documenti reali dell'utente.

Cerca file in ``benchmark/documenti_utente/`` (esclusi da git), li apre
col dispatch dei documenti supportati, li anonimizza con le categorie
di default, e riporta:

  - sostituzioni totali
  - dati sensibili veri riconosciuti (leggendo l'annotazione da
    ``<file>.veri.json``, se presente)
  - rumore, ELENCATO uno per uno

Il vault è isolato in ``/tmp/pb_utente_vault.db`` (o
``PRIVACYBRIDGE_UTENTE_VAULT`` se settato).  Il modello resta caricato
una volta per tutti i file.

Le categorie sono fissate a ``CATEGORIE_CONSEGNA``, cioè quelle accese
per difetto nella versione consegnata: è il numero che descrive il
prodotto, non la configurazione con cui l'utente sta lavorando oggi.

Uso:
    venv/bin/python -m benchmark.utente
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from benchmark import CATEGORIE_CONSEGNA, isola

isola("utente")

_CARTELLA = ROOT / "benchmark" / "documenti_utente"
_VAULT_DB = os.environ.get("PRIVACYBRIDGE_UTENTE_VAULT", "/tmp/pb_utente_vault.db")


def _leggi_annotazione(path: Path) -> list[str] | None:
    """Ritorna la lista ``dati_sensibili`` da ``<file>.veri.json`` se
    presente, altrimenti None (documento non annotato)."""
    ann = path.with_suffix(path.suffix + ".veri.json")
    # Anche senza raddoppio dell'estensione: prova "<stem>.veri.json".
    if not ann.exists():
        ann = path.parent / (path.stem + ".veri.json")
    if not ann.exists():
        return None
    try:
        dati = json.loads(ann.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"  [!] {ann.name}: JSON non valido: {exc}", file=sys.stderr)
        return None
    val = dati.get("dati_sensibili")
    if not isinstance(val, list):
        return None
    return [str(v) for v in val if v]


def _elenca_file() -> list[Path]:
    if not _CARTELLA.is_dir():
        return []
    ESTENSIONI = {
        ".pdf", ".docx", ".txt", ".md", ".markdown", ".csv",
        ".eml", ".msg", ".rtf", ".odt", ".xlsx", ".html", ".htm",
    }
    file: list[Path] = []
    for p in sorted(_CARTELLA.iterdir()):
        if p.is_file() and p.suffix.lower() in ESTENSIONI:
            file.append(p)
    return file


def _e_vero(valore: str, veri: list[str]) -> bool:
    v = valore.strip().lower()
    for a in veri:
        aa = a.strip().lower()
        if v == aa or v in aa or aa in v:
            return True
    return False


def main() -> int:
    print("=" * 90)
    print(f"BENCHMARK UTENTE — documenti in {_CARTELLA}")
    print("=" * 90)

    file = _elenca_file()
    if not file:
        print(
            f"\nNessun file in {_CARTELLA}\n"
            "Vedi il README della cartella per istruzioni."
        )
        return 0

    # Cancella il vault temporaneo per iniziare pulito.
    try:
        os.unlink(_VAULT_DB)
    except FileNotFoundError:
        pass

    from backend.documenti import (
        DocumentoError,
        DocumentoScansionato,
    )
    from backend.documenti import (
        carica as carica_doc,
    )
    from backend.motore import anonimizza, reset_analyzer
    reset_analyzer()

    tot_sost = 0
    tot_veri = 0
    tot_rumore = 0
    tot_veri_persi = 0
    file_annotati = 0
    file_non_annotati = 0

    for i, path in enumerate(file, start=1):
        print(f"\n[{i}] {path.name} ({path.stat().st_size / 1024:.1f} KB)")
        try:
            testo, _ = carica_doc(str(path))
        except DocumentoScansionato as e:
            print(f"    [!] PDF scansionato: {e}")
            continue
        except DocumentoError as e:
            print(f"    [!] Errore lettura: {e}")
            continue

        print(f"    caratteri: {len(testo):,}")
        try:
            out, ents = anonimizza(
                testo, f"utente-{i}", db_path=_VAULT_DB,
                categorie_attive=set(CATEGORIE_CONSEGNA),
            )
        except Exception as e:
            print(f"    [!] Errore anonimizzazione: {e}")
            continue

        attivi = [e for e in ents if not e.get("suggerito") and e.get("placeholder")]
        sost = len(attivi)

        veri = _leggi_annotazione(path)
        if veri is None:
            file_non_annotati += 1
            print(f"    sostituzioni: {sost}")
            print("    [!] nessuna annotazione .veri.json — impossibile valutare veri/rumore")
            if attivi:
                print("    entità emesse:")
                for e in attivi:
                    print(f"      - {e['tipo']:16s} {e['valore_reale']!r}")
            tot_sost += sost
            continue

        file_annotati += 1
        veri_riconosciuti = sum(1 for v in veri if v not in out)
        veri_persi = len(veri) - veri_riconosciuti
        emessi_veri = sum(1 for e in attivi if _e_vero(e["valore_reale"], veri))
        rumore = sost - emessi_veri

        tot_sost += sost
        tot_veri += emessi_veri
        tot_rumore += rumore
        tot_veri_persi += veri_persi

        print(f"    sostituzioni totali:      {sost}")
        print(f"    di cui dati sensibili:    {emessi_veri}")
        print(f"    di cui rumore:            {rumore}")
        print(f"    veri annotati mascherati: {veri_riconosciuti}/{len(veri)}")
        if rumore:
            print("    RUMORE (elenco):")
            for e in attivi:
                if not _e_vero(e["valore_reale"], veri):
                    print(f"      - {e['tipo']:16s} {e['valore_reale']!r}")
        if veri_persi:
            print("    VERI PERSI (non mascherati):")
            for v in veri:
                if v in out:
                    print(f"      - {v!r}")

    print("\n" + "=" * 90)
    print(
        f"TOTALE: {tot_sost} sostituzioni su {len(file)} file "
        f"({file_annotati} annotati, {file_non_annotati} non annotati)"
    )
    if file_annotati and (tot_veri + tot_rumore) > 0:
        precisione = tot_veri / (tot_veri + tot_rumore) * 100
        print(
            f"Precisione (solo file annotati): {precisione:.1f}%  "
            f"({tot_veri} veri / {tot_veri + tot_rumore} emessi)"
        )
        print(f"Veri persi (sfuggiti al motore): {tot_veri_persi}")
    print("=" * 90)
    return 0


if __name__ == "__main__":
    sys.exit(main())
