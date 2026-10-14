# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Richiamo e precisione per tipo sul corpus annotato a mano.

I documenti dell'utente dicono quanto il motore sbaglia, ma non quanto
manca: senza annotazione non si sa che cosa avrebbe dovuto trovare.  Il
corpus di ``tests/corpus_annotato.py`` ha 76 frasi con gli span segnati
uno per uno, ed è l'unico posto dove il richiamo si può calcolare invece
che stimare.

Confronta gli span emessi con quelli annotati e divide gli esiti nelle
tre classi che contano, distinguendo il tipo sbagliato dallo span
sbagliato — sono difetti diversi e si correggono in punti diversi:

  esatto        span e tipo coincidono
  tipo_errato   span giusto, categoria sbagliata
  parziale      span che si sovrappone ma non coincide (troncato o esteso)
  mancante      annotato e non trovato          → falso negativo
  spurio        trovato e non annotato          → falso positivo

Gira con tutte le categorie accese: misura ciò di cui il motore è
capace, non ciò che è acceso per difetto nella consegna.

Uso:
    venv/bin/python -m benchmark.misura_corpus
    venv/bin/python -m benchmark.misura_corpus --tipo ORG   # solo un tipo
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from benchmark import isola, vault_isolato

isola("corpus")

VAULT_DB = vault_isolato("corpus")
USCITA = ROOT / "benchmark" / "misura_corpus_dati.json"


def _span_emessi(ents: list[dict], testo: str) -> list[dict]:
    """Ritrova nel testo la posizione di ogni entità emessa.

    ``anonimizza`` restituisce il valore, non lo span: per confrontarlo con
    l'annotazione la posizione va ricalcolata. Le frasi del corpus sono
    corte e un valore vi compare quasi sempre una volta sola.
    """
    fuori = []
    for e in ents:
        val = e.get("valore_reale") or ""
        if not val:
            continue
        for m in re.finditer(re.escape(val), testo):
            fuori.append({
                "start": m.start(),
                "end": m.end(),
                "tipo": e.get("tipo"),
                "valore": val,
                "suggerito": bool(e.get("suggerito")),
            })
    return fuori


def _sovrappone(a: dict, b: dict) -> bool:
    return a["start"] < b["end"] and b["start"] < a["end"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tipo", help="mostra il dettaglio solo per questo tipo")
    ap.add_argument("--suggeriti", action="store_true",
                    help="conta anche i suggerimenti come entità trovate")
    args = ap.parse_args()

    from backend.motore import CATEGORIE_TUTTE, anonimizza, reset_analyzer
    from tests.corpus_annotato import CORPUS
    reset_analyzer()
    cat = set(CATEGORIE_TUTTE)

    esiti: list[dict] = []
    for entry in CORPUS:
        testo = str(entry["testo"])
        attesi = [dict(e) for e in entry["entita"]]  # type: ignore[arg-type]
        _, ents = anonimizza(testo, str(entry["id"]), db_path=VAULT_DB, categorie_attive=cat)
        if not args.suggeriti:
            ents = [e for e in ents if not e.get("suggerito")]
        emessi = _span_emessi(ents, testo)

        usati: set[int] = set()
        for att in attesi:
            att["testo"] = testo[att["start"]:att["end"]]
            candidati = [
                (j, em) for j, em in enumerate(emessi)
                if j not in usati and _sovrappone(att, em)
            ]
            if not candidati:
                att["esito"] = "mancante"
                continue
            # Fra più sovrapposizioni vince quella che coincide, poi quella
            # col tipo giusto: altrimenti un LUOGO che tocca una PERSONA
            # nasconderebbe il fatto che la PERSONA era stata presa bene.
            candidati.sort(key=lambda c: (
                not (c[1]["start"] == att["start"] and c[1]["end"] == att["end"]),
                c[1]["tipo"] != att["tipo"],
            ))
            j, em = candidati[0]
            usati.add(j)
            att["emesso"] = em["valore"]
            att["tipo_emesso"] = em["tipo"]
            uguale = em["start"] == att["start"] and em["end"] == att["end"]
            if uguale and em["tipo"] == att["tipo"]:
                att["esito"] = "esatto"
            elif uguale:
                att["esito"] = "tipo_errato"
            else:
                att["esito"] = "parziale"

        spuri = [em for j, em in enumerate(emessi) if j not in usati]
        esiti.append({
            "id": entry["id"],
            "categoria": entry["categoria"],
            "testo": testo,
            "attesi": attesi,
            "spuri": spuri,
        })

    USCITA.write_text(json.dumps(esiti, ensure_ascii=False, indent=1), encoding="utf-8")

    per_tipo: dict[str, dict[str, int]] = {}
    for r in esiti:
        for att in r["attesi"]:
            d = per_tipo.setdefault(att["tipo"], {})
            d[att["esito"]] = d.get(att["esito"], 0) + 1
    spuri_tipo: dict[str, int] = {}
    for r in esiti:
        for s in r["spuri"]:
            spuri_tipo[s["tipo"]] = spuri_tipo.get(s["tipo"], 0) + 1

    print("=" * 86)
    print(f"CORPUS ANNOTATO — {len(CORPUS)} frasi, tutte le categorie accese")
    print("=" * 86)
    intest = f"{'tipo':<14}{'att.':>6}{'esatto':>8}{'parz.':>7}{'t.err':>7}{'manc.':>7}"
    print(intest + f"{'richiamo':>10}{'spuri':>7}")
    print("-" * 86)
    tot = {"n": 0, "esatto": 0, "parziale": 0, "tipo_errato": 0, "mancante": 0}
    for tipo in sorted(per_tipo, key=lambda t: -sum(per_tipo[t].values())):
        d = per_tipo[tipo]
        n = sum(d.values())
        ok = d.get("esatto", 0)
        pa = d.get("parziale", 0)
        te = d.get("tipo_errato", 0)
        ma = d.get("mancante", 0)
        tot["n"] += n
        for k in ("esatto", "parziale", "tipo_errato", "mancante"):
            tot[k] += d.get(k, 0)
        # Richiamo largo: trovato in qualche forma, anche con span o tipo
        # imperfetti. È il numero che dice se il dato è finito coperto.
        largo = (ok + pa + te) / n * 100 if n else 0.0
        print(f"{tipo:<14}{n:>6}{ok:>8}{pa:>7}{te:>7}{ma:>7}{largo:>9.1f}%"
              f"{spuri_tipo.get(tipo, 0):>7}")
    print("-" * 86)
    n = tot["n"]
    largo = (tot["esatto"] + tot["parziale"] + tot["tipo_errato"]) / n * 100
    stretto = tot["esatto"] / n * 100
    print(f"{'TOTALE':<14}{n:>6}{tot['esatto']:>8}{tot['parziale']:>7}"
          f"{tot['tipo_errato']:>7}{tot['mancante']:>7}{largo:>9.1f}%"
          f"{sum(spuri_tipo.values()):>7}")
    print(f"\nrichiamo largo (span anche imperfetto):  {largo:.1f}%")
    print(f"richiamo stretto (span e tipo esatti):   {stretto:.1f}%")
    print(f"span spuri (non annotati):               {sum(spuri_tipo.values())}")

    if args.tipo:
        t = args.tipo.upper()
        print(f"\n{'=' * 86}\nDETTAGLIO {t}\n{'=' * 86}")
        for r in esiti:
            for att in r["attesi"]:
                if att["tipo"] != t or att["esito"] == "esatto":
                    continue
                print(f"[{r['id']}] {att['esito']:<12} atteso {att['testo']!r}")
                if "emesso" in att:
                    print(f"{'':<19}emesso {att['emesso']!r} come {att['tipo_emesso']}")
            for s in r["spuri"]:
                if s["tipo"] == t:
                    print(f"[{r['id']}] spurio       {s['valore']!r}")
    print(f"\ndati grezzi in {USCITA.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
