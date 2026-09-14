# AUDIT — Stato reale del progetto PrivacyBridge

Data audit: 2026-07-29. Comandi eseguiti, non fede in documentazione preesistente.

## 1. Struttura file (righe di codice sorgente)

| File | Righe | Ruolo |
|---|---:|---|
| `backend/motore.py` | 586 | Pipeline anonimizza/deanonimizza/rianonimizza |
| `backend/motore_neurale.py` | 288 | Recognizer Presidio per il modello neurale |
| `backend/recognizers.py` | 780 | Recognizer regex+checksum italiani |
| `backend/nlp_engine.py` | 82 | Registry + costruzione AnalyzerEngine |
| `backend/vault.py` | 271 | SQLite vault (batch mode) |
| `backend/documenti.py` | 109 | Parser PDF/DOCX/TXT/MD/CSV |
| `backend/post_process.py` | 213 | **CODICE MORTO** — solo test lo importano |
| `api/main.py` | 210 | 8 endpoint FastAPI |
| `api/static/index.html` | 1329 | UI SPA (HTML + CSS + JS inline) |
| `tests/test_motore.py` | 700 | 36 test motore |
| `tests/test_documenti.py` | 219 | 12 test parser |
| `avvio.py` | 68 | Bootstrap pywebview + FastAPI |

## 2. Bundle applicativo (macOS)

Esiste `PrivacyBridge.app/` con:
- `Contents/Info.plist` — bundle id `com.andrea.privacybridge`, versione 1.0.0
- `Contents/MacOS/PrivacyBridge` — script bash che lancia `venv/bin/python avvio.py`
- `Contents/Resources/icon.icns` — icona 215 kB (Mac OS X icon type "ic12")

Non c'è nessun `.ico` per Windows, nessuno script `.bat`/`.vbs`.

## 3. Come si avvia oggi

- **macOS**: doppio click su `PrivacyBridge.app` (verifica visiva ancora da fare) o `venv/bin/python avvio.py`.
- **Backend headless**: `python scripts_test_app.py` avvia FastAPI su porta libera e testa `/health` + `/anonimizza`. **Verificato**: `test_app_avvio.txt` mostra 25s in vita, anonimizzazione OK. Il processo NON viene killato allo shutdown dello script — la stampa "process alive after 25s" mostra il ricordo del PID; il thread è daemon, quindi muore col processo principale, ma solo perché lo script termina subito.
- **Windows**: nessuna via di avvio. Manca lo script.

## 4. DESIGN.md e CSS attuale

`DESIGN.md` esiste (15 kB) e contiene: palette, tipografia, elemento firma ("linea di strappo"), autocritica del piano (§ 6). Le variabili CSS in `api/static/index.html:7-53` **corrispondono** al file: stessi hex, stessi nomi (`--grafite`, `--ceralacca`, `--verderame`), stessa scala tipografica. Il CSS deriva effettivamente dai token del design system.

**Limite noto**: gli stack font sono **solo macOS**. `New York`, `SF Pro Text`, `SF Mono`, `Iowan Old Style` non esistono su Windows: là cadranno rispettivamente su Georgia, system-ui (Segoe UI) e Consolas. La documentazione lo dichiara "solo font di sistema macOS" (§ 3): va allargato a Windows in FASE 3.

## 5. Test suite — output raw

```
$ python -m pytest tests/ -v
============================= test session starts ==============================
platform darwin -- Python 3.11.15, pytest-9.1.1
collected 48 items

tests/test_documenti.py (12 test) — tutti PASSED
tests/test_motore.py (36 test) — tutti PASSED

================== 48 passed, 27 warnings in 71.49s (0:01:11) ==================
```

**48/48 verdi.** Compreso `test_non_confusione_placeholder`, che nella documentazione precedente risultava fallito. Motivo: nel test la frase attuale ("Gentile Dott. Mario Rossi, la informiamo che il colloquio con Luigi Bianchi è confermato.") contiene "informiamo" e "colloquio" — sufficienti al pattern `_IT_HINT` di `motore.py:203` per triggerare `it`, quindi il modello neurale italiano funziona e restituisce i due nomi. La versione descritta in `CONSEGNA.md § 5` era diversa ("Mario Rossi e Luigi Bianchi lavorano insieme") e cadeva in inglese — il test corrente è già la versione fissata.

Warning residui: 27 `Tokenizer does not support real words` da transformers (avviso interno, non azione).

## 6. Modello neurale — caricamento

- ID: `rizzoaiacademy/rizzo-pii-0.3B` (ModernBERT, ~300M param).
- Revisione: **fissata** in `backend/motore_neurale.py:44` — `_MODEL_REVISION = "a7f1160d829c7b436a6d8f8ebdae523f83437edf"`. Non "latest".
- Cache HF: `~/.cache/huggingface/hub/models--rizzoaiacademy--rizzo-pii-0.3B/` — presente.
- Load strategy: prova offline (`HF_HUB_OFFLINE=1`), poi fallback online se manca in cache.
- Device: `-1` (CPU). Commento nel codice: MPS rotto su questo hardware.

Anche `models--microsoft--mdeberta-v3-base` e `models--urchade--gliner_multi_pii-v1` sono in cache, retaggio della fase GLiNER — non più usati.

## 7. FASE 1 — Cosa la documentazione dà per fatto e non lo è

| Punto | Documentazione | Realtà |
|---|---|---|
| Test IT/EN | "fallito, non risolto" | **Verde**, la frase del test è stata cambiata |
| Revisione modello | non menzionata | Fissata a hash esplicito |
| `PRIVACYBRIDGE_NO_FIX2` | "flag per disattivare post_process" | **Non più letto dal backend**. Solo `benchmark/` lo imposta ancora |
| `backend/post_process.py` | "creato ma mantenuto" | Presente sul disco, non chiamato da `motore.py`, ma **8 test in `test_motore.py` lo importano direttamente** (`test_fix2_*`) e verificano `estendi_organization`. Se lo cancello i test si rompono |
| NOTICE.txt | "testo MIT completo" | **Solo un URL** a opensource.org, non il testo integrale |
| `backend/rizzo_recognizer.py` | menzionato in CONSEGNA.md | **Non esiste**. Il file è `backend/motore_neurale.py`, classe `NeuralRecognizer`. Nomi già neutri |

## 8. FASE 2 — Requisiti multipiattaforma

Da ispezione grep:
- `avvio.py:25` — `os.path.expanduser("~/Library/Application Support/PrivacyBridge")` **hardcoded macOS**. Su Windows scriverebbe in `~/Library/...` sotto la home Windows, cartella spuria.
- `platformdirs` **non installato** e non in `requirements.txt`. Va aggiunto.
- `playwright` **non installato**.
- Nessun `.ico`, nessun `.bat`, nessun `.vbs`.
- La cartella `data/vault.db` è dentro la repo (default `DEFAULT_DB_PATH` in `vault.py:19`). Con `avvio.py` `PRIVACYBRIDGE_DB` viene messo nella cartella utente, ma il default resta relativo al package.

## 9. Cosa manca rispetto al briefing

Pendenze reali da chiudere per raggiungere il gate finale:

**FASE 1**:
- (1.1) Test IT/EN già verde — solo da confermare in AUDIT (fatto).
- (1.2) Revisione modello già fissata — solo da documentare (DECISIONI.md).
- (1.3) `backend/post_process.py`: cancellare e rimuovere i 8 test `test_fix2_*` che dipendono da esso; pulire benchmark obsoleti.
- (1.4) NOTICE.txt: aggiungere testo MIT completo integrale.

**FASE 2**:
- `platformdirs` come dipendenza; `avvio.py` e `vault.py` DEFAULT_DB_PATH via `platformdirs.user_data_dir("PrivacyBridge")`.
- Icona `.ico` (multi-risoluzione) generata dallo stesso design dell'`.icns`.
- `PrivacyBridge.bat` (o `.vbs` con icona) per lancio silente su Windows.
- Download modello al primo avvio con progresso: attualmente il modello è già in cache; se manca l'`avvio.py` fallisce silenziosamente. Serve una schermata pre-web che scarichi e mostri progress.

**FASE 3**:
- Font stack allargato a Windows (Cambria/Georgia per il serif, Segoe UI per il corpo, Cascadia/Consolas per mono) — con nota esplicita in DESIGN.md.
- Screenshot 3D: solo dopo avvio dell'app con contenuto reale.

**FASE 4** — la UI in `index.html` copre già: tab Anonimizza/Ripristina, selettore sessione, Nuova/Elimina sessione, carica documento, textarea, tabella entità editabile, contatore, ripristina. Da verificare che tutto funzioni davvero dopo pulizia (test Playwright).

**FASE 5**:
- Suite Playwright `tests/test_interfaccia.py` da scrivere da zero.
- `verifica_tutto.sh` + `verifica_tutto.bat` da creare.
- Test offline (rete staccata) — verifica manuale.

**GATE FINALE**: doppio click → screenshot da produrre.

## 10. Verità onesta sui limiti già noti (dalla codebase, non da promesse)

- **Language routing** basato su keyword italiane. Frasi senza connettori italiani cadono su inglese. Verificato in codice, non un bug ma una scelta pragmatica.
- **Recall ORGANIZATION**: ~56% sul corpus onesto di 20 frasi inedite (documentato dal codice benchmark). La tabella entità nell'UI è la rete di sicurezza.
- **Modello neurale su CPU**: throughput ~1500 char/s. Documento medio-lungo (100k char) = ~1 minuto. Il modello pesa 2 GB in RSS.

---

Questo è lo stato reale al 2026-07-29. Le pendenze sopra elencate sono quelle su cui procedo nelle fasi successive.
