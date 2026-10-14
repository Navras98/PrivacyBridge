# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""FastAPI app per PrivacyBridge.

Endpoints:
    POST   /anonimizza     — anonimizza un testo
    POST   /rianonimizza   — riapplica la mappatura entità corretta dall'utente
    POST   /deanonimizza   — ripristina i valori reali dai placeholder
    POST   /carica         — estrae il testo da un documento caricato
    POST   /precarica      — scalda il motore in sottofondo
    GET    /analisi/stato  — caratteri analizzati finora
    POST   /analisi/annulla — interrompe l'analisi in corso
    GET    /sessioni       — elenco delle sessioni nel vault
    DELETE /sessioni/{id}  — elimina una sessione
    GET    /tipi           — tipi di entità selezionabili
    GET    /               — serve index.html
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
import threading
import uuid
from pathlib import Path

logger = logging.getLogger("privacybridge.api")

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.avanzamento import Annullato, annulla_analisi, stato_analisi
from backend.documenti import (
    ESTENSIONI_SUPPORTATE,
    DocumentoError,
    DocumentoScansionato,
)
from backend.documenti import (
    carica as carica_documento,
)
from backend.motore import (
    TIPI_ENTITA,
    anonimizza,
    deanonimizza,
    get_analyzer,
    rianonimizza,
)
from backend.vault import DEFAULT_DB_PATH, Vault

app = FastAPI(title="PrivacyBridge", version="1.0.0")

HERE = Path(__file__).resolve().parent
STATIC = HERE / "static"
STATIC.mkdir(exist_ok=True)

ESTENSIONI_AMMESSE = set(ESTENSIONI_SUPPORTATE)
MAX_UPLOAD = 20 * 1024 * 1024


class AnonimizzaRequest(BaseModel):
    testo: str
    sessione: str | None = None
    lingua: str | None = None


class AnonimizzaResponse(BaseModel):
    testo_anonimizzato: str
    entita: list[dict]
    sessione: str


class EntitaModificata(BaseModel):
    valore_reale: str
    tipo: str
    # Il segnaposto che la riga aveva già. Se arriva e il tipo non è
    # cambiato, il motore lo riusa invece di rinumerare da capo: senza,
    # ogni ripristino fatto dal testo sposterebbe i numeri di tutte le
    # righe dello stesso tipo e mezzo documento cambierebbe per un click.
    placeholder: str = ""


class RianonimizzaRequest(BaseModel):
    testo: str
    sessione: str
    entita: list[EntitaModificata]


# I tre endpoint di analisi sono deliberatamente sincroni (``def``, non
# ``async def``): FastAPI esegue in threadpool le funzioni sincrone, e
# l'analisi è lavoro CPU che dura decine di secondi. Dichiarati ``async``
# occuperebbero l'event loop e per tutto quel tempo il server non
# risponderebbe più a nulla — finestra bloccata e avanzamento che mente.
# Stessa ragione per cui ``/carica`` chiama ``run_in_threadpool``; lì
# serve la forma esplicita perché l'endpoint deve attendere l'upload.
# Presidiato da tests/test_interfaccia.py::test_server_risponde_durante_anonimizzazione.

@app.post("/anonimizza", response_model=AnonimizzaResponse)
def post_anonimizza(req: AnonimizzaRequest):
    if not req.testo or not req.testo.strip():
        raise HTTPException(status_code=400, detail="Il testo è vuoto.")
    sessione = req.sessione or uuid.uuid4().hex[:12]
    lingua = req.lingua if req.lingua in {"it", "en"} else None
    try:
        anon, entita = anonimizza(req.testo, sessione, lingua=lingua)
        return AnonimizzaResponse(
            testo_anonimizzato=anon,
            entita=entita,
            sessione=sessione,
        )
    except Annullato as e:
        # 409: non è un guasto, è l'esito che l'utente ha chiesto. La
        # finestra lo distingue dall'errore e non mostra il banner rosso.
        raise HTTPException(status_code=409, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/rianonimizza", response_model=AnonimizzaResponse)
def post_rianonimizza(req: RianonimizzaRequest):
    if not req.testo or not req.testo.strip():
        raise HTTPException(status_code=400, detail="Il testo originale è vuoto.")
    try:
        anon, entita = rianonimizza(
            req.testo,
            req.sessione,
            [e.model_dump() for e in req.entita],
        )
        return AnonimizzaResponse(
            testo_anonimizzato=anon,
            entita=entita,
            sessione=req.sessione,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/deanonimizza")
def post_deanonimizza(req: AnonimizzaRequest):
    if not req.testo or not req.testo.strip():
        raise HTTPException(status_code=400, detail="Il testo è vuoto.")
    if not req.sessione:
        raise HTTPException(status_code=400, detail="Sessione richiesta.")
    try:
        restored, report = deanonimizza(req.testo, req.sessione)
        return {
            "testo_ripristinato": restored,
            "report": report,
            "sessione": req.sessione,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/carica")
async def post_carica(file: UploadFile = File(...)):
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ESTENSIONI_AMMESSE:
        raise HTTPException(
            status_code=400,
            detail=f"Formato non supportato: {ext or 'sconosciuto'}. "
            f"Sono ammessi {', '.join(sorted(ESTENSIONI_AMMESSE))}.",
        )
    contenuto = await file.read()
    if len(contenuto) > MAX_UPLOAD:
        raise HTTPException(status_code=400, detail="File troppo grande (max 20 MB).")

    fd, percorso_tmp = tempfile.mkstemp(suffix=ext)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(contenuto)
        # In threadpool: l'estrazione (e l'eventuale OCR) è sincrona e
        # può durare decine di secondi — non deve bloccare l'event loop,
        # altrimenti il polling di /ocr/stato non risponderebbe.
        from fastapi.concurrency import run_in_threadpool
        testo, _ = await run_in_threadpool(carica_documento, percorso_tmp)
    except DocumentoScansionato as e:
        # Errore specifico: comunicalo con codice dedicato così la UI
        # può mostrare un messaggio dedicato al caso scansione.
        raise HTTPException(status_code=422, detail=str(e))
    except DocumentoError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lettura del file fallita: {e}")
    finally:
        os.unlink(percorso_tmp)

    risposta = {"testo": testo, "nome": file.filename, "caratteri": len(testo)}
    # Se alcune pagine sono passate dall'OCR, la UI deve avvisare che
    # il rilevamento è meno affidabile (l'OCR può sbagliare caratteri:
    # un CF letto male non supera più il controllo di validità).
    from backend.documenti import info_ultimo_caricamento
    info = info_ultimo_caricamento()
    if info.get("ocr_pagine"):
        risposta["ocr"] = info
    return risposta


@app.get("/ocr/stato")
async def get_ocr_stato():
    """Avanzamento OCR corrente — la UI lo interroga in polling durante
    il caricamento ("Documento scansionato: pagina 3 di 12")."""
    from backend.ocr import stato_ocr
    return stato_ocr()


@app.get("/analisi/stato")
async def get_analisi_stato():
    """Caratteri analizzati finora — la finestra lo interroga in polling.

    Sono caratteri davvero passati sotto il motore, non una stima: chi
    aspetta tre minuti ha diritto di sapere a che punto è, e una barra
    che si muove da sola dice solo che il programma non è morto.
    """
    return stato_analisi()


@app.post("/analisi/annulla")
async def post_analisi_annulla():
    """Interrompe l'analisi in corso.

    Alza solo una bandiera e torna subito: è il thread che sta
    analizzando ad accorgersene e a fermarsi da sé al chunk successivo,
    lasciando il vault coerente. Uccidere il thread lo lascerebbe a metà.
    """
    annulla_analisi()
    return {"annullata": True}


@app.get("/sessioni")
async def get_sessioni():
    vault = Vault(DEFAULT_DB_PATH)
    try:
        return {
            "sessioni": [
                {
                    "id": r["sessione_id"],
                    "entita": r["entita"],
                    "ultimo": r["ultimo"],
                }
                for r in vault.all_sessions()
            ]
        }
    finally:
        vault.close()


@app.get("/sessioni/{sessione}")
async def get_sessione(sessione: str):
    vault = Vault(DEFAULT_DB_PATH)
    try:
        return {
            "sessione": sessione,
            "entita": [
                {
                    "placeholder": r["placeholder"],
                    "valore_reale": r["valore_reale"],
                    "tipo": r["tipo"],
                    "occorrenze": None,
                }
                for r in vault.all_for_session(sessione)
            ],
        }
    finally:
        vault.close()


@app.delete("/sessioni/{sessione}")
async def delete_sessione(sessione: str):
    vault = Vault(DEFAULT_DB_PATH)
    try:
        vault.clear_session(sessione)
        return {"eliminata": sessione}
    finally:
        vault.close()


@app.get("/tipi")
async def get_tipi():
    return {"tipi": TIPI_ENTITA}


# ---------------------------------------------------------------------------
# Categorie attive (FASE 2 follow-up — GRUPPO B1)
# ---------------------------------------------------------------------------

@app.get("/categorie")
async def get_categorie():
    from backend.motore import (
        CATEGORIE_DEFAULT_ATTIVE,
        CATEGORIE_TUTTE,
        _leggi_categorie_attive,
    )
    attive = _leggi_categorie_attive()
    return {
        "tutte": sorted(CATEGORIE_TUTTE),
        "attive": sorted(attive),
        "default_attive": sorted(CATEGORIE_DEFAULT_ATTIVE),
    }


class CategorieRequest(BaseModel):
    attive: list[str]


@app.post("/categorie")
async def post_categorie(req: CategorieRequest):
    from backend.motore import (
        CATEGORIE_TUTTE,
        _leggi_categorie_attive,
        scrivi_categorie_attive,
    )
    # Filtro whitelisting: accetto solo categorie note.
    valide = {c.upper() for c in req.attive if c.upper() in CATEGORIE_TUTTE}
    scrivi_categorie_attive(valide)
    return {"attive": sorted(_leggi_categorie_attive())}


# ---------------------------------------------------------------------------
# Controllo aggiornamenti (FASE 4)
# ---------------------------------------------------------------------------

@app.get("/aggiornamenti")
async def get_aggiornamenti():
    from backend.aggiornamenti import stato_aggiornamento
    return stato_aggiornamento()


class CheckAggiornamentiRequest(BaseModel):
    attivo: bool


@app.post("/aggiornamenti/imposta")
async def post_impostazione_aggiornamenti(req: CheckAggiornamentiRequest):
    from backend.aggiornamenti import (
        controlla_in_background,
        imposta_check_aggiornamenti,
        stato_aggiornamento,
    )
    imposta_check_aggiornamenti(req.attivo)
    if req.attivo:
        # Se l'utente riattiva, esegue subito un check.
        controlla_in_background()
    return stato_aggiornamento()


# ---------------------------------------------------------------------------
# Rubrica personale (FASE 2.3)
# ---------------------------------------------------------------------------

class VoceRubrica(BaseModel):
    testo: str
    tipo: str = "ALTRO"


class ImportRubricaRequest(BaseModel):
    voci: list[VoceRubrica]


@app.get("/rubrica")
async def get_rubrica():
    vault = Vault(DEFAULT_DB_PATH)
    try:
        righe = list(vault.rubrica_all())
        return {
            "voci": [
                {"id": r["id"], "testo": r["testo"], "tipo": r["tipo"]}
                for r in righe
            ],
            "totale": len(righe),
        }
    finally:
        vault.close()


@app.post("/rubrica")
async def post_rubrica(voce: VoceRubrica):
    if not voce.testo.strip():
        raise HTTPException(status_code=400, detail="Il testo è vuoto.")
    vault = Vault(DEFAULT_DB_PATH)
    try:
        vault.rubrica_add(voce.testo.strip(), voce.tipo)
    finally:
        vault.close()
    # Ricostruisci l'analyzer perché la rubrica è cambiata.
    from backend.motore import reset_analyzer
    reset_analyzer()
    return {"ok": True, "testo": voce.testo.strip(), "tipo": voce.tipo}


@app.delete("/rubrica")
async def delete_rubrica_voce(testo: str):
    if not testo.strip():
        raise HTTPException(status_code=400, detail="Testo vuoto.")
    vault = Vault(DEFAULT_DB_PATH)
    try:
        vault.rubrica_remove(testo.strip())
    finally:
        vault.close()
    from backend.motore import reset_analyzer
    reset_analyzer()
    return {"ok": True, "eliminato": testo.strip()}


@app.post("/rubrica/importa")
async def post_rubrica_importa(file: UploadFile = File(...)):
    """Importa voci di rubrica da un CSV con colonne testo,tipo.

    Il tipo è opzionale (default ALTRO). Righe malformate scartate.
    """
    import csv
    import io

    contenuto = await file.read()
    if len(contenuto) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File troppo grande (max 5 MB).")

    # Prova UTF-8 poi CP1252 (Excel italiano).
    text: str | None = None
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            text = contenuto.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        raise HTTPException(status_code=400, detail="Codifica del file non riconosciuta.")

    # Rileva delimitatore.
    dialect = None
    try:
        dialect = csv.Sniffer().sniff(text[:2048], delimiters=",;\t|")
    except csv.Error:
        pass
    reader = csv.reader(io.StringIO(text), dialect=dialect) if dialect else csv.reader(io.StringIO(text))

    vault = Vault(DEFAULT_DB_PATH)
    aggiunte = 0
    scartate = 0
    try:
        for i, row in enumerate(reader):
            if not row:
                continue
            testo = row[0].strip()
            tipo = row[1].strip() if len(row) > 1 else "ALTRO"
            # Salta riga di header ("testo","tipo") o simili.
            if i == 0 and testo.lower() in {"testo", "nome", "valore", "termine"}:
                continue
            if not testo:
                scartate += 1
                continue
            vault.rubrica_add(testo, tipo)
            aggiunte += 1
    finally:
        vault.close()
    from backend.motore import reset_analyzer
    reset_analyzer()
    return {"aggiunte": aggiunte, "scartate": scartate}


@app.get("/", response_class=HTMLResponse)
async def get_index():
    index = STATIC / "index.html"
    if index.exists():
        return HTMLResponse(
            index.read_text(encoding="utf-8"),
            headers={"Cache-Control": "no-store"},
        )
    return HTMLResponse("<h1>PrivacyBridge</h1><p>index.html non trovato</p>")


@app.get("/health")
async def health():
    info: dict = {"status": "ok", "versione": app.version}
    try:
        from backend.motore_neurale import stato_modello

        info["modello"] = stato_modello()
    except Exception as e:
        logger.debug("stato_modello fallito: %s", e)
    try:
        from backend.vault_crypto import vault_is_encrypted

        info["vault_cifrato"] = vault_is_encrypted()
    except Exception as e:
        logger.debug("vault_is_encrypted fallito: %s", e)
    return info


@app.post("/precarica")
async def post_precarica():
    """Carica il modello in sottofondo, a finestra già disegnata.

    Il modello non si carica all'avvio, perché sono ~10s in cui l'utente
    guarderebbe una finestra vuota. Ma caricarlo alla prima
    anonimizzazione non è gratis: durante il caricamento torch e spaCy
    tengono il GIL dentro codice C, e le richieste HTTP restano ferme
    fino a 1.2s misurati. Quel blocco cade sul primo click dell'utente.

    Chiamato dalla pagina appena finita di disegnarsi, sposta il
    caricamento nei secondi in cui l'utente sta leggendo la finestra e
    non ha ancora incollato niente, e rende la prima anonimizzazione
    veloce quanto le successive.

    Il thread è di sfondo perché la risposta deve tornare subito:
    l'``async def`` qui sopra dura il tempo di avviare il thread.
    ``get_analyzer`` è idempotente, quindi una seconda chiamata (ricarico
    della pagina) non carica due volte.
    """
    threading.Thread(target=get_analyzer, name="precarico-motore",
                     daemon=True).start()
    return {"precarico": "avviato"}
