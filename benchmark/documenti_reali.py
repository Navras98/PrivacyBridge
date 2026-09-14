# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Corpus 'documenti reali': tre white paper simulati che ricalcano la
forma dei documenti tecnici che l'utente processa realmente.

L'utente ha segnalato che su un suo white paper l'app aveva prodotto
60+ sostituzioni di cui UNA sola era un dato personale. Motivo: i
corpora di frasi non contengono tabelle, titoli maiuscoli, nomi di
file, termini tecnici — che sono la maggior parte di un white paper.

Uso: ``python -m benchmark.documenti_reali``
Output: numero di sostituzioni totali VS sostituzioni di dati sensibili
veri (annotati). Obiettivo: quasi solo dati personali veri.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


# Ogni voce: (id, testo, dati_sensibili_veri)
# I "dati_sensibili_veri" sono un elenco di sottostringhe che SI
# aspetta vengano correttamente mascherate; qualsiasi altra
# sostituzione è un falso positivo.
DOCUMENTI: list[tuple[str, str, list[str]]] = [

    # -----------------------------------------------------------------
    # 1. White paper tecnico: gestione rischio portafoglio
    # -----------------------------------------------------------------
    (
        "wp_tech_var",
        """
GESTIONE DEL RISCHIO DI PORTAFOGLIO

Autore: Mario Rossi — andrem.rossi@example.it
Versione: 1.2 — data 19 giugno 2026

# ABSTRACT

Questo white paper descrive un'implementazione di calcolo VaR e
CVaR su un portafoglio multi-asset. Il codice sorgente è in
backend/rischio.py e usa NumPy, pandas e SciPy. I dati arrivano da
Yahoo Finance via API REST, con caching in SQLite (modalità WAL).

## 1. INTRODUZIONE

Il Value at Risk (VaR) è una metrica finanziaria standard. Il modello
implementato usa bootstrap non-parametrico su serie storiche di 10
anni scaricate da Yahoo Finance. Le posizioni sono calcolate con
riferimento a benchmark MSCI World e S&P500.

## 2. STACK TECNOLOGICO

- Linguaggio: Python 3.11
- Persistenza: SQLite con journal_mode=WAL
- API: FastAPI + Uvicorn
- Notifiche: Telegram Bot API
- Automazione: launchd (macOS) o cron

Il file di configurazione principale è config.json. I log vanno in
data/log.txt tramite il modulo standard logging. Le metriche
esportate includono NAV, beta, drawdown, Sharpe ratio.

## 3. ARCHITETTURA

La classe PortfolioManager (in portfolio.py) espone i metodi
get_positions(), calculate_var(), get_metrics(). Il calcolo VaR-99
viene eseguito con soglia MonteCarlo di 10000 simulazioni.

I dati vengono scaricati con timeout HTTP di 3s. In caso di errore
retry con backoff esponenziale (max 3 tentativi). Se Yahoo Finance
non risponde, si tenta Polygon come fallback.
""",
        # Unica info personale nel documento: nome + email dell'autore.
        ["Mario Rossi", "andrem.rossi@example.it"],
    ),

    # -----------------------------------------------------------------
    # 2. Guida operativa con tabelle e codici
    # -----------------------------------------------------------------
    (
        "guida_op",
        """
GUIDA OPERATIVA — CASE STUDY

Titolo: DEPLOY IN PRODUZIONE
Priorità: P0 (bloccante)
Ticket: T1-URG, A3-XY

# CHECKLIST

1. Backup del database (backend/data/vault.db)
2. Deploy dell'artefatto sul server
3. Verifica endpoint /health via curl
4. Notifica al team su Slack

## MATRICE DI RESPONSABILITÀ

| Ruolo       | Nome                | Contatto                |
| ----------- | ------------------- | ----------------------- |
| Referente   | Mario Rossi       | mario@example.com      |
| Backup      | Luigi Bianchi       | luigi.bianchi@corp.it   |
| Supervisore | Direttore Tecnico   | (da definire)           |

## PROCEDURA

Fase 1: shutdown container Docker (docker-compose down).
Fase 2: pull del nuovo tag (git pull origin main).
Fase 3: rebuild con docker-compose up --build.
Fase 4: verifica con test suite: pytest tests/ -q.

## NOTE FINALI

Contattare il Servizio IT (sistema.it@aziendaesempio.it) in caso
di anomalie. Il numero di reperibilità è +39 333 1234567.
""",
        # Personali: 2 persone, 3 email, 1 telefono.
        [
            "Mario Rossi", "mario@example.com",
            "Luigi Bianchi", "luigi.bianchi@corp.it",
            "sistema.it@aziendaesempio.it", "333 1234567",
        ],
    ),

    # -----------------------------------------------------------------
    # 3. Documento con moltissimi titoli maiuscoli e termini tecnici
    # -----------------------------------------------------------------
    (
        "specifica_prodotto",
        """
SPECIFICA PRODOTTO — RELEASE 2.0

REVISIONE: 3
AUTORE: Marco Ferrari (marco.ferrari@studio.it)
STATO: BOZZA — NON APPRESA

# SEZIONE 1 — ARCHITETTURA

Il modulo core (core.py) implementa la logica business. Le dipendenze
esterne sono:

- FastAPI 0.115 per l'API REST
- SQLAlchemy per l'ORM
- Redis come cache in-memory
- Amazon S3 per lo storage documentale
- Stripe per i pagamenti

## SEZIONE 2 — SICUREZZA

Il sistema autentica via OAuth2 (Google, Microsoft, Apple).
Le password sono hashate con bcrypt. I JWT hanno TTL di 1h.
La comunicazione avviene su HTTPS (TLS 1.3).

### DIRITTI E RUOLI

| Ruolo              | Permessi          |
| ------------------ | ----------------- |
| Amministratore     | Tutto             |
| Direttore Vendite  | Read + Report     |
| Consigliere        | Read only         |
| Ospite             | Nulla             |

## SEZIONE 3 — DEPLOYMENT

Deploy automatico via GitHub Actions su push su main. Il file
.github/workflows/deploy.yml contiene la pipeline. I secret sono in
GitHub Secrets.

I test unitari usano pytest; quelli E2E usano Playwright su Chromium.
La coverage minima richiesta è 85%.
""",
        # Personali: 1 persona, 1 email.
        ["Marco Ferrari", "marco.ferrari@studio.it"],
    ),
]


# ---------------------------------------------------------------------------

def _valuta():
    from backend.motore import anonimizza, reset_analyzer
    reset_analyzer()

    print("=" * 90)
    print("BENCHMARK 'DOCUMENTI REALI' — sostituzioni vs dati sensibili veri")
    print("=" * 90)

    tot_sost = 0
    tot_veri = 0
    tot_rumore = 0

    for doc_id, testo, veri in DOCUMENTI:
        # Uso categorie default (solo dati personali).
        out, ents = anonimizza(testo, f"real-{doc_id}")
        # Conteggi solo sulle sostituzioni ATTIVE (esclusi i suggeriti
        # livello 3, che non modificano il testo).
        attivi = [e for e in ents if not e.get("suggerito") and e.get("placeholder")]
        sost = len(attivi)
        veri_mascherati = sum(1 for v in veri if v not in out)
        veri_totali = len(veri)
        emessi_veri = 0
        for e in attivi:
            valore = e["valore_reale"]
            if any(v in valore or valore in v for v in veri):
                emessi_veri += 1
        emessi_rumore = sost - emessi_veri

        tot_sost += sost
        tot_veri += emessi_veri
        tot_rumore += emessi_rumore

        print(f"\n--- {doc_id} ---")
        print(f"  sostituzioni totali:  {sost}")
        print(f"  di cui dati sensibili: {emessi_veri}")
        print(f"  di cui rumore:         {emessi_rumore}")
        print(f"  veri mascherati:       {veri_mascherati}/{veri_totali}")
        if emessi_rumore:
            print("  RUMORE:")
            for e in attivi:
                valore = e["valore_reale"]
                if not any(v in valore or valore in v for v in veri):
                    print(f"    - {e['tipo']}: {valore!r}")

    print("\n" + "=" * 90)
    print(f"TOTALE: {tot_sost} sostituzioni "
          f"({tot_veri} veri, {tot_rumore} rumore)")
    if tot_sost:
        print(f"Precisione: {tot_veri/tot_sost*100:.1f}%  "
              f"({tot_veri} veri / {tot_sost} emessi)")
    print("=" * 90)


if __name__ == "__main__":
    _valuta()
