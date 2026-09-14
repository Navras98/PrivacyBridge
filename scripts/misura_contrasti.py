# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Misura i rapporti di contrasto dell'interfaccia secondo WCAG 2.1.

Legge le variabili colore direttamente da ``api/static/index.html`` — non
da una copia a mano, che si disallineerebbe — e verifica ogni accostamento
che l'utente vede davvero, in entrambi i temi.

Soglie applicate (WCAG 2.1 AA):
 - 4.5:1  testo normale
 - 3.0:1  testo grande (>= 18.66px grassetto o >= 24px) e componenti
          d'interfaccia (bordi di controlli, indicatori di stato)

Uso:
    python scripts/misura_contrasti.py
Esce con codice 1 se anche un solo accostamento è sotto soglia.
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SORGENTE = ROOT / "src" / "api" / "static" / "index.html"

# Soglie WCAG 2.1 AA.
SOGLIA_TESTO = 4.5
SOGLIA_UI = 3.0


def _canali(colore: str) -> tuple[float, float, float]:
    c = colore.strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        raise ValueError(f"colore non esadecimale: {colore!r}")
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


def luminanza(colore: str) -> float:
    """Luminanza relativa secondo WCAG 2.1, formula
    ``L = 0.2126 R + 0.7152 G + 0.0722 B``."""
    def lineare(v: float) -> float:
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (lineare(v) for v in _canali(colore))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrasto(a: str, b: str) -> float:
    la, lb = luminanza(a), luminanza(b)
    chiaro, scuro = max(la, lb), min(la, lb)
    return (chiaro + 0.05) / (scuro + 0.05)


def leggi_palette(testo: str, selettore: str) -> dict[str, str]:
    """Estrae le variabili ``--nome: #rrggbb`` dal blocco del selettore."""
    inizio = testo.index(selettore)
    apertura = testo.index("{", inizio)
    chiusura = testo.index("}", apertura)
    blocco = testo[apertura:chiusura]
    return {
        m.group(1): m.group(2)
        for m in re.finditer(r"--([a-z0-9-]+):\s*(#[0-9A-Fa-f]{3,6})\s*;", blocco)
    }


# Accostamenti reali dell'interfaccia: (descrizione, primo piano, fondo, soglia).
ACCOSTAMENTI: tuple[tuple[str, str, str, float], ...] = (
    ("Testo su superficie (pannello sinistro, tabelle, dialoghi)",
     "testo", "superficie", SOGLIA_TESTO),
    ("Testo su superficie-2 (pannello destro anonimizzato)",
     "testo", "superficie-2", SOGLIA_TESTO),
    ("Testo su sfondo (tela dell'applicazione)",
     "testo", "sfondo", SOGLIA_TESTO),
    ("Testo attenuato su superficie (note, sottotitoli, metriche)",
     "testo-fioco", "superficie", SOGLIA_TESTO),
    ("Testo attenuato su superficie-2 (intestazioni di tabella)",
     "testo-fioco", "superficie-2", SOGLIA_TESTO),
    ("Testo attenuato su sfondo (stato, barra azioni)",
     "testo-fioco", "sfondo", SOGLIA_TESTO),
    ("Testo tenue su superficie (segnaposto dei campi)",
     "testo-tenue", "superficie", SOGLIA_TESTO),
    ("Testo attenuato su sfondo (firma del prodotto)",
     "testo-fioco", "sfondo", SOGLIA_TESTO),
    ("Accento su superficie (valore reale evidenziato)",
     "accento", "superficie", SOGLIA_TESTO),
    ("Accento su velo d'accento (chip del valore reale)",
     "accento", "accento-velo", SOGLIA_TESTO),
    ("Testo su superficie-3 (chip del segnaposto, righe al passaggio)",
     "testo", "superficie-3", SOGLIA_TESTO),
    ("Testo inverso su fondo inverso (pulsante primario, banner)",
     "inverso-testo", "inverso-fondo", SOGLIA_TESTO),
    # Componenti d'interfaccia: soglia 3:1.
    ("Bordo di controllo su superficie (campi, liste, pulsanti)",
     "bordo-controllo", "superficie", SOGLIA_UI),
    ("Bordo di controllo su sfondo (pulsanti nella barra azioni)",
     "bordo-controllo", "sfondo", SOGLIA_UI),
    ("Anello di fuoco su superficie",
     "accento", "superficie", SOGLIA_UI),
    ("Anello di fuoco su sfondo",
     "accento", "sfondo", SOGLIA_UI),
    ("Indicatore di lavorazione su sfondo",
     "accento", "sfondo", SOGLIA_UI),
)


def verifica(nome_tema: str, palette: dict[str, str]) -> list[tuple[str, float, float, bool]]:
    esiti = []
    for descrizione, davanti, dietro, soglia in ACCOSTAMENTI:
        rapporto = contrasto(palette[davanti], palette[dietro])
        esiti.append((descrizione, rapporto, soglia, rapporto >= soglia))
    return esiti


def stampa(nome_tema: str, palette: dict[str, str],
           esiti: Iterable[tuple[str, float, float, bool]]) -> int:
    print(f"\n{'=' * 78}\nTEMA {nome_tema.upper()}\n{'=' * 78}")
    print(f"{'accostamento':<58}{'misura':>9}{'soglia':>7}  esito")
    print("-" * 78)
    falliti = 0
    for descrizione, rapporto, soglia, ok in esiti:
        if not ok:
            falliti += 1
        print(f"{descrizione:<58}{rapporto:>8.2f}:1{soglia:>6.1f}  "
              f"{'OK' if ok else 'SOTTO SOGLIA'}")
    return falliti


def main() -> int:
    testo = SORGENTE.read_text(encoding="utf-8")
    temi = {
        "chiaro": leggi_palette(testo, '[data-theme="chiaro"]'),
        "scuro": leggi_palette(testo, '[data-theme="scuro"]'),
    }

    falliti = 0
    for nome, palette in temi.items():
        mancanti = {v for _, a, b, _ in ACCOSTAMENTI for v in (a, b)} - palette.keys()
        if mancanti:
            print(f"tema {nome}: variabili mancanti {sorted(mancanti)}")
            return 2
        falliti += stampa(nome, palette, verifica(nome, palette))

    print()
    if falliti:
        print(f"ESITO: {falliti} accostamenti sotto soglia WCAG AA.")
        return 1
    print("ESITO: tutti gli accostamenti rispettano WCAG 2.1 AA.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
