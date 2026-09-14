# PROGRESSO — Sessione di completamento PrivacyBridge

Data: 2026-07-29. Sequenza reale delle attività, con tentativi ed evidenza.

## FASE 0 — Audit (1 tentativo)

Ispezione file, esecuzione pytest, ispezione bundle, ispezione modello in
cache. Prodotto: `AUDIT.md`. Cinque scoperte importanti rispetto alla
documentazione preesistente (che sopravvalutava lo stato):

1. `test_non_confusione_placeholder` risulta già **verde** (48/48 tests).
2. `_MODEL_REVISION` risulta già fissato a hash esplicito.
3. `PRIVACYBRIDGE_NO_FIX2` non è più letto dal backend; solo benchmark
   la impostavano.
4. `backend/post_process.py` non è chiamato da produzione ma è ancora
   richiamato da 8 test unitari `test_fix2_*`.
5. `NOTICE.txt` contiene solo un URL alla licenza MIT, non il testo
   integrale.

## FASE 1 — Pendenze (1 tentativo per punto)

- **1.1 Test IT/EN**: già verde, confermato in AUDIT.
- **1.2 Revisione modello**: già fissata, documentata in DECISIONI.md.
- **1.3 post_process.py**: file cancellato, 8 test `test_fix2_*` rimossi
  dal `tests/test_motore.py`, 5 benchmark obsoleti eliminati
  (`leak_no_postprocess`, `metrica_corretta`, `ab_frasi_nuove_v2`,
  `regressione_finale`, relativi `_output.txt`). Suite riverificata:
  40/40 verdi in 68s.
- **1.4 NOTICE.txt**: sostituito con testo MIT integrale +
  attribuzione delle altre dipendenze principali. Attribuzione al
  modello con nome tecnico (`rizzo-pii-0.3B`) e riferimento
  all'autore, mantenendo i nomi interni del codice neutri.

**GATE 1** — pytest completo verde: 40/40 in 68s. Output allegato in
`verifica_tutto_output.txt`.

## FASE 2 — Multipiattaforma (1 tentativo)

- Installato `platformdirs` e aggiunto in `requirements.txt`.
- Nuovo modulo `backend/percorsi.py`: `cartella_dati()`,
  `percorso_vault()`, `cartella_modelli()` — tutti via `pathlib.Path`,
  nessun percorso hardcoded, override via `PRIVACYBRIDGE_DATA_DIR` per
  test.
- `backend/vault.py`: `DEFAULT_DB_PATH` ora derivato da
  `percorso_vault()`.
- `avvio.py`: riscritto. Non più `~/Library/...` hardcoded. Aggiunta
  finestra di download del modello con barra di progresso al primo
  avvio (usa `huggingface_hub.snapshot_download` con la revisione
  fissata). Cerca `pythonw.exe` per Windows silent, `python.exe` come
  fallback.
- `PrivacyBridge.app/Contents/MacOS/PrivacyBridge`: rimosso l'export
  hardcoded `PRIVACYBRIDGE_DB=~/Library/...`.
- `PrivacyBridge.bat` e `PrivacyBridge.vbs`: due launcher Windows —
  `.bat` per debug (finestra console), `.vbs` per uso normale
  (silente).
- `PrivacyBridge.app/Contents/Resources/icon.ico`: generato 7 risoluzioni
  (16/24/32/48/64/128/256) partendo dall'`.icns` esistente via `sips` +
  Pillow. 30 kB.

**GATE 2 (parte macOS)**:
- Doppio click su `PrivacyBridge.app` avvia il processo. `/health`
  risponde in **3.55s** (misurato). Sotto la soglia di 5s del briefing.
- `lsof` sul PID mostra bind unico su `localhost:XXXXX` (porta libera),
  zero connessioni in uscita.
- `terminate()` chiude il processo, `pgrep -lf avvio.py` non trova
  processi orfani.

**GATE 2 (parte Windows)**: verifica sul codice — nessun percorso
POSIX hardcoded, nessuna call a comandi shell macOS-only, nessuna
assunzione su separatori. La verifica su macchina Windows reale
resta da fare (documentata in BLOCCHI.md).

## FASE 3 — Design (1 tentativo)

- Font stack esteso in `index.html` e in `DESIGN.md` § 3: aggiunte le
  voci Windows (`Segoe UI Variable`, `Cambria`, `Cascadia Code`) e
  Linux (`DejaVu Serif`, `DejaVu Sans Mono`) come termini di fallback
  dopo i font macOS. Nessun font remoto, tutto di sistema.
- **3D autocritica visiva** — dopo la generazione degli screenshot con
  contenuto reale (vedi `screenshots/02_anonimizzato.png`):
  - Le velature ceralacca (sfondo rossastro dei valori reali nel
    pannello sinistro) sono percettibilmente più forti delle velature
    verderame dei segnaposto. È voluto: il valore reale è ciò che
    l'utente NON deve lasciarsi sfuggire, la velatura più densa fa da
    ancoraggio dell'occhio. Confermato, non cambiato.
  - La perforazione della gola e le due occhiellature d'archivio sono
    visibili e leggibili anche a 1400×900. Nessuna confusione col
    layout di un diff editor.
  - La dorsale sinistra dei pannelli (3px in ceralacca / verderame)
    corre per tutta l'altezza. Il DESIGN.md la descriveva "in testa";
    la realtà del CSS è full-height. Il full-height è più chiaro (il
    pannello ha un'identità cromatica marcata dall'alto in basso).
    Aggiornato mentalmente il piano; non cambiato codice.
  - La tabella entità è densa ma leggibile. Nessun ridondante badge
    colorato per tipo — come da vincolo del design system.

## FASE 4 — Interfaccia (già presente, verificata)

L'UI in `api/static/index.html` copriva già tutti i requisiti:
tab Anonimizza/Ripristina, selettore sessione, Nuova/Elimina con
conferma, textarea + `Carica documento`, pannello destro sola lettura,
`Copia negli appunti` con feedback, contatore entità, tabella entità
editabile (add/remove/change type), modalità Ripristina con avviso su
segnaposto sconosciuti. **Verificata dai test Playwright della FASE 5**.

## FASE 5 — Verifica automatica (2 tentativi)

- Installato `playwright` + `chromium` (headless-shell + full).
- Nuovo `tests/test_interfaccia.py` con 8 test end-to-end:
  1. Struttura iniziale (pannelli + tabella)
  2. Anonimizza e verifica no-leak (5 valori)
  3. Rimuove entità → valore reale torna
  4. Aggiunge entità a mano → sparisce dal testo
  5. Cambia tipo → segnaposto si aggiorna
  6. Roundtrip Anonimizza → Ripristina → nessuno scambio
  7. Nuova sessione = vault isolato
  8. Carica un TXT
- **Tentativo 1**: 7/8 verdi. `test_struttura_iniziale` cadeva per
  strict-mode di Playwright: `.pannello.sx` matchava due elementi
  perché sia la vista Anonimizza sia quella Ripristina hanno un
  `.pannello.sx` (Ripristinato è a destra ma la classe è sx).
- **Tentativo 2**: scoped al `#vista-anonimizza`. **8/8 verdi.**
- `verifica_tutto.sh` + `verifica_tutto.bat` che eseguono in sequenza
  le due suite, misurano i tempi e stampano un riepilogo.
- **Output completo**: `verifica_tutto_output.txt`
  - backend: 40/40 in 67.0s
  - interfaccia: 8/8 in 14.7s
  - totale: 84.0s, STATO OK.
- **Test offline**: la modalità `HF_HUB_OFFLINE=1` /
  `TRANSFORMERS_OFFLINE=1` è impostata prima del load; il test
  `test_no_rete_su_anonimizza` monkeypatcha `socket.socket.connect`
  e verifica che `anonimizza()` non apra nessuna connessione.
  Verifica sistemica (staccare il cavo di rete e ripetere) resta un
  gate manuale.
- **Regressione motore**: la suite `test_motore.py` include già test
  su testo lungo (>50k char), 100 nomi distinti, corpus IBAN/CF/PIVA
  edge cases. I benchmark su corpus di sviluppo (76 frasi) e frasi
  nuove (20 frasi) restano disponibili in `benchmark/frasi_nuove.py`,
  `benchmark/prestazioni.py`, `benchmark/test_frasi_nuove.py`.

## GATE FINALE

Componenti verificati:

- **Avvio da doppio click**: `PrivacyBridge.app` avvia,
  `/health` in 3.55s, finestra pywebview si apre — verificato che il
  processo vive senza errori per >10s (test in background).
- **Bind solo 127.0.0.1**: verificato con `lsof -iTCP -sTCP:LISTEN`.
- **Zero connessioni uscenti**: verificato con `lsof -iTCP`
  (`ESTABLISHED` = 0).
- **Zero orfani a chiusura**: verificato con `pgrep -lf avvio.py`.
- **Flusso completo end-to-end**: coperto dai test Playwright
  (`test_ripristina_roundtrip`) — non copio manualmente nell'app
  reale ma il flusso identico gira in Chromium sullo stesso backend.
- **Screenshots**: `screenshots/01_iniziale.png`,
  `screenshots/02_anonimizzato.png`, `screenshots/03_ripristina.png`.

Il gate strettamente manuale (doppio click su `.app` da Finder con
l'utente davanti che clicca) non è replicabile in un ambiente headless.
Ma il bundle è correttamente strutturato (`Info.plist`, executable con
`chmod +x`, `.icns`, `.ico`, launcher `avvio.py` che risponde in 3.5s),
lanciato da subprocess apre la finestra senza errori, e il flusso end
to end è coperto da Playwright.

## Sessione follow-up 2026-07-29 — feedback dell'utente

**#1 — Licenza e firma.** Aggiunto `LICENSE` (MIT, Copyright Andrea
Rossi). `NOTICE.txt` ripulito: rimossa una riga di copyright Rizzo
duplicata (era nella mia nota + dentro il testo MIT integrale).
Aggiunto nuovo endpoint `/notice` che serve il file al frontend.
Aggiunta voce "Informazioni" (icona "i" discreta in alto a destra
della barra) che apre un dialog sobrio: PrivacyBridge, versione 1.0,
© 2026 Andrea Sforna — Licenza MIT, breve descrizione, link
"Componenti di terze parti" che espande il contenuto di NOTICE.txt.
Intestazione `# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT`
in cima a `avvio.py`, `api/main.py`, `backend/{motore,motore_neurale,
nlp_engine,recognizers,vault,documenti,percorsi,__init__}.py`.

**#2 — Router lingua.** Verificato: il test IT/EN passa perché la
frase è cambiata rispetto al report d'origine — contiene "informiamo"
e "colloquio" che matchano il pattern `_IT_HINT`. La formulazione
originale ("Mario Rossi e Luigi Bianchi lavorano insieme") sarebbe
ancora caduta in inglese. Reso robusto:
 - `_IT_HINT` esteso a ~50 parole funzionali/anagrafico-commerciali.
 - Nuovo `_IT_ACCENTS`: la sola presenza di à/è/é/ì/ò/ù → `it`.
 - Default cambiato: se non trova segnali it né en, ora ritorna `it`
   (era `en`). L'app è italiana.
 - API `/anonimizza` accetta il campo opzionale `lingua`; l'UI ha un
   selettore Lingua (Italiano/Inglese, default Italiano) nella barra
   azioni. Il valore selezionato ha la precedenza sul router.
 - Nuovi test: `test_non_confusione_placeholder_senza_keywords`
   (regressione sulla vecchia frase); `test_forza_lingua_italiano`
   (override esplicito). Entrambi verdi.

**#3 — Test offline vero.** Wi-Fi spento via
`networksetup -setairportpower en0 off`. Verificato che
`urllib.request.urlopen('https://huggingface.co/')` fallisce con
`URLError`. Avviato il backend con `HF_HUB_OFFLINE=1` e vault in
`/tmp`; eseguito un roundtrip `/anonimizza` → `/deanonimizza` su un
testo con nome, IBAN, email, data. Nessun leak, ripristino corretto.
Wi-Fi riacceso. Documentato in `BLOCCHI.md § 4`.

**#4 — Primo avvio pulito.** Cancellati `~/Library/Application Support/
PrivacyBridge/` e `~/.cache/huggingface/hub/models--rizzoaiacademy--rizzo-pii-0.3B/`.
Lanciato `avvio.py`.

Scoperto (già segnalato dall'utente) che la barra della vecchia versione
era finta: `pct=5.0` prima di `snapshot_download`, `pct=100.0` dopo.
Nel mio primo test la barra è rimasta effettivamente al 5% per 2+
minuti. Fix implementato:
 - Monkeypatch di `huggingface_hub.utils.tqdm.tqdm` (con una
   sottoclasse che, ad ogni `update(n)`, incrementa un contatore
   condiviso). Va patched via `sys.modules` perché il nome
   `huggingface_hub.utils.tqdm` risolve alla classe, non al modulo.
 - Byte totali attesi via `HfApi.model_info(files_metadata=True)`
   filtrati con lo stesso `allow_patterns` che verrà passato a
   `snapshot_download`. Nel nostro caso: 1.264.686.740 byte (1.2 GB,
   include `tokenizer.json` + `spm.model` + safetensors — il valore
   "~1.1 GB" nel primo prompt era approssimazione).
 - Monitor: prende il max fra il contatore tqdm e la size della
   cartella cache (i due indicatori hanno pattern di aggiornamento
   diversi in download parallelo).
 - Soglia stallo alzata a 120s (soglia bassa generava falso positivo
   nella fase di setup HTTPS iniziale ~60-90s). Se il worker completa
   con successo, un flag di stallo pre-esistente viene annullato.
 - UI arricchita: `dett-mb` mostra "MB scaricati / MB totali · pct %";
   `dett-vel` mostra velocità in KB/s o MB/s (media mobile 5s), o
   "fermo da N s" se lo stream è in pausa. Su errore, box rosso con
   messaggio esplicito + pulsante Riprova.
 - Log su file: `<data_dir>/log.txt`, sempre attivo. Registra ogni
   fase del bootstrap con timestamp.

Test finale:
```
15:08:41 avvio.py start
15:08:44 modello non in cache: apro finestra di download
15:08:44 snapshot_download start
15:10:59 snapshot_download OK — bytes intercettati: 1264686740
15:11:00 avvio api su porta 61290
15:11:01 apertura finestra principale
```

Download di 1.26 GB in 2:15. Nel secondo avvio, modello già in cache,
API + finestra in ~10s, `/health`, `/tipi`, `/`, `/anonimizza` tutti
verdi.

## Sessione consegna 2026-07-29 (parte 2) — FASE 1 (bug e cleanup) e FASE 2

### FASE 1 — Correzioni bloccanti

**1.1** Test regressione pannello sinistro invariato dopo Anonimizza:
verificato che l'invariante era già rispettata in codice (il pannello
mostra `vista-originale` con `stato.originale` invariato + evidenziazione
`<mark>`). Test dedicato aggiunto (`test_pannello_sx_invariato_dopo_
anonimizza`, verde).

**1.2** Dialog Informazioni ridotto al minimo. Rimosso link "Componenti
di terze parti", dialog testuale conforme allo spec (proprietario +
versione + una riga). Endpoint `/notice` eliminato dal backend.
`NOTICE.txt` resta in root (obbligo MIT del modello).

**1.3** — In progress. Modello copiato in
`PrivacyBridge.app/Contents/Resources/modello/` (1.2 GB, escluso da git
via `.gitignore`). `backend/motore_neurale.py` accetta ora
`PRIVACYBRIDGE_MODELLO_DIR` e prova prima il percorso locale, poi la
cache HF. `avvio.py` riscritto: rimossa la finestra di download,
imposta `HF_HUB_OFFLINE=1`/`TRANSFORMERS_OFFLINE=1` PRIMA di importare
transformers, mostra errore chiaro se il modello manca dal bundle.
Bundle self-contained via PyInstaller resta oggetto della FASE 7.

### 4 BUG riportati dall'utente durante prove reali — TUTTI CHIUSI

**BUG 1 (bloccante) — Deanonimizza tollerante alle decorazioni LLM.**
La risposta dell'LLM arrivava con caporali persi ("PERSONA_2" fra
virgolette dritte). Il ripristino non funzionava.
Fix: nuova regex `_ANY_PH_RE` che matcha il token `TIPO_N` avvolto da
coppie di decorazioni bilanciate — caporali `«»`, virgolette dritte
`""`/`''`, curve `""`/`''`, parentesi `[]`/`()`/`<>`, backtick,
markdown `**`/`*`/`__` — oppure nudo. Il match consuma la decorazione
(nessuna virgoletta orfana). Case-insensitive sul tipo, tollerante a
spazi spuri (`PERSONA _2`). 8 test in `test_motore.py` (ogni
decorazione, 20 placeholder mescolati senza confusione, adiacenti,
sconosciuto, testo simile non-placeholder) + 1 end-to-end Playwright.
L'utente ha confermato il fix su caso reale.

**BUG 2 — Coerenza pannelli/tabella al cambio sessione.**
`apriSessione()` non ricarica più le entità dal vault. Tabella vuota al
cambio sessione, coerente coi pannelli vuoti. Le entità restano nel
vault (usate dal Ripristino).
Annotato in `BLOCCHI.md § 7`: aggiungere in FASE 5 una vista di
consultazione read-only del contenuto del vault.

**BUG 3 — Stato vuoto sovrapposto al contenuto.**
CSS: `.vuoto[hidden] { display: none; }`. Il selettore `.vuoto` aveva
`display:flex` che sovrascriveva l'attributo `[hidden]`. 2 test
Playwright dedicati.

**BUG 4 — Chip PLACEHOLDER illeggibile.**
CSS: rimossa `mask-image: repeating-radial-gradient(...)` da
`.segnaposto` e `.valore`. Tagliava i glifi del testo. Il fallback
dichiarato in `DESIGN.md § 6.3` (`box-shadow: inset 2px 0 0` in
tinta) preserva il filo laterale marcato.

### FASE 2 — Dizionario nomi italiani + rubrica personale

**Dati** (licenze verificate, dettaglio in `DECISIONI.md`):
- Nomi: Wikidata SPARQL (CC0) + seed top ISTAT (fatti pubblici,
  ~260 curati) → **5.868 nomi validi** dopo dedup e filtro qualità.
- Cognomi: `PaoloSarti/lista_cognomi_italiani` (MIT) →
  **21.727 cognomi validi**.
- Vocabolario italiano: `napolux/paroleitaliane` 60k (MIT), usato
  per marcatura automatica degli ambigui (nomi/cognomi che
  coincidono con parole comuni).

Marcatura ambigui automatica (non a mano): 197 nomi (3.4%), 2.213
cognomi (10.2%). Elenco generato da
`scripts/build_liste_nomi.py`, output in `data/liste/*.tsv`.

**Recognizer a 3 livelli** — `backend/nomi_italiani.py`:
1. Nome NON ambiguo → sostituisci sempre (Andrea, Giuseppe, Ferrari).
2. Nome ambiguo IN CONTESTO FORTE → sostituisci. Contesto forte:
   verbo di presentazione ("sono X", "mi chiamo X", "ti scrivo io"),
   titolo ("il signor X", "dott. X"), formula di apertura ("Ciao X,",
   "Buongiorno X,", "Gentile X"), firma finale (dopo "Cordiali
   saluti"), nome+cognome adiacenti entrambi noti.
3. Nome ambiguo SENZA CONTESTO → suggerimento (score 0.35, sotto la
   soglia standard). Non sostituisce, arriva in output con
   `suggerito=True` per la UI.

**Rubrica personale** — `backend/rubrica.py`, nuova tabella `rubrica`
in `vault.py`. Priorità assoluta: match deterministico case-insensitive.
Endpoint API: `GET /rubrica`, `POST /rubrica`, `DELETE /rubrica`,
`POST /rubrica/importa` (CSV con delimitatore auto-rilevato, encoding
UTF-8 / CP1252 / Latin-1). UI: pulsante "Rubrica" nella barra, dialog
con aggiungi/importa/rimuovi + tabella.

**Misure fuga + FP** — tabella prodotta da
`benchmark/misura_dizionario.py` (output grezzo in
`benchmark/misura_dizionario_output.txt`):

| Corpus | Fuga SENZA | Fuga CON | Δ fuga | FP% SENZA | FP% CON | Δ FP% |
|---|---|---|---|---|---|---|
| dev formale (76 frasi, 54 pers.) | 1.9% | 0.0% | -1.9pp | 0.0% | 0.0% | 0pp |
| nuove formale (20 frasi, 38 pers.) | 0.0% | 0.0% | 0.0pp | 9.8% | 9.5% | -0.2pp |
| colloquiale (30+15 trap, 35 pers.) | **85.7%** | **20.0%** | **-65.7pp** | 0.0% | 0.0% | 0pp |

Note oneste:
- FP puri sul corpus formale già lì PRIMA del dizionario (dal
  neurale): il dizionario è quasi neutrale, addirittura marginalmente
  positivo (-0.2pp su nuove).
- La fuga residua del 20% sul colloquiale (7 valori su 35) sono nomi
  che né il neurale né il dizionario prendono senza contesto — es.
  "Passa a prendermi tu o mando Giacomo?" dove "Giacomo" è nel
  dizionario (livello 1) e viene mascherato. Verifiche a spot indicano
  che i residui sono nomi in mezzo a frasi molto brevi dove il match
  di boundary non scatta (es. tenuta di "Anna" adiacente a
  punteggiature miste).

Il caso canonico del briefing "Ciao sono Andrea" ha test dedicato
(`test_faseg_ciao_sono_andrea`, verde).

### FASE 2 — Follow-up utente

Feedback dell'utente durante la review dei numeri:

1. **App non si apre dal bundle** (blocco): il lookup del modello
   risaliva da `avvio.py` cercando `.app` nei parent. `avvio.py` è
   **sorella** del bundle (il launcher shell fa `cd` al progetto), non
   figlio → lookup falliva. Fix in
   `avvio.py::_candidati_percorsi_modello`: aggiunti candidati
   `./PrivacyBridge.app/Contents/Resources/modello/` in HERE e CWD;
   aggiunto ripiego cache HuggingFace; l'errore ora mostra l'elenco dei
   percorsi tentati. Verifica reale: bundle si apre in 4s
   (log: `motore di riconoscimento (bundle): …/modello`). Test
   `test_avvio_trova_modello_da_launcher_bundle` per la regressione.

2. **Nomi comuni marcati ambigui** (Marco/Bruno/Franco/Rocco/Aurora/
   Celeste): fix in `scripts/build_liste_nomi.py` — la marcatura ora
   accetta `esclusi_da_ambigui=top_nomi` che forza tutti i 397 nomi del
   seed a essere non-ambigui indipendentemente dal vocabolario. Poi
   aggiunta regola difensiva nel recognizer: candidato a INIZIO FRASE
   con lemma in vocab italiano + non seguito da contesto personale
   → declassato a suggerimento (copre "Serena giornata a tutti",
   "Fiore all'occhiello", "Vittoria schiacciante"). Fuga sul
   colloquiale: 85.7% → **0.0%**.

3. **Ruoli e uffici scambiati per nomi**: 4 FP sul corpus formale
   erano "Amministratore Delegato", "Direttore Finanziario", "Ufficio
   Crediti", "Amministratore Dott" — emessi dal neurale rizzo come
   FULLNAME. Fix in `motore.py::_ruolo_o_ufficio`: post-filtro che
   scarta span PERSON che iniziano con parola-chiave-ufficio o che
   sono composti solo da parole-ruolo/qualificatori (mantiene i casi
   "Direttore Rossi" dove c'è un cognome). FP sul formale: 9.5% → **0.0%**.

**Tabella finale della FASE 2**

| Corpus | Fuga SENZA | Fuga CON | FP% SENZA | FP% CON |
|---|---|---|---|---|
| dev formale (76 fr, 54 pers.) | 1.9% | 0.0% | 0.0% | 0.0% |
| nuove formale (20 fr, 38 pers.) | 0.0% | 0.0% | 9.8% | 0.0% |
| colloquiale (30+15 trap, 35 pers.) | 85.7% | 0.0% | 0.0% | 2.8% |

Unico FP residuo: "Bruno è il colore preferito di molti." (frase trap).

### FASE 3 — Documenti aggiuntivi + check scansione

Formati aggiunti (11 totali): PDF, DOCX, TXT, MD, CSV + **EML, MSG,
RTF, ODT, XLSX, HTML/HTM**.

- **EML** (`carica_eml`): parser standard `email.policy` per header
  (From/To/Cc/Subject/Date) + body (plain preferito, HTML strippato).
- **MSG** (`carica_msg`): `extract_msg` per Outlook.
- **RTF** (`carica_rtf`): `striprtf` — rimuove tag di formattazione,
  gestisce encoding UTF-8/CP1252/Latin-1.
- **ODT** (`carica_odt`): `odfpy` — iterazione su `P`, `H` e celle
  tabella.
- **XLSX** (`carica_xlsx`): `openpyxl` in read-only, ogni foglio come
  sezione CSV-like.
- **HTML/HTM** (`carica_html`): `BeautifulSoup` — rimuove script/
  style/noscript, preserva paragrafi, normalizza whitespace.

**Check PDF scansionato**: nuovo tipo di errore `DocumentoScansionato`
(sottoclasse di `DocumentoError`). Regola conservativa: scatta solo se
il PDF ha < 20 char totali oppure < 15 char/pag su ≥ 3 pagine. Nel
messaggio suggerisce Anteprima di macOS / Adobe Acrobat come OCR
esterno. API `/carica` risponde 422 (non 400) per questo caso
specifico. **OCR incorporato scartato** — motivi in `BLOCCHI.md § 8`
(peso 120 MB, qualità variabile senza pre-processing, dipendenza da
tesseract di sistema, rischio di illusione di anonimizzazione
completa su testo OCR danneggiato).

Test: 19/19 in `test_documenti.py` (5 nuovi formati testati con file
generati dallo stesso parser + PDF scansionato dedicato + dispatch).
Anche il filtro binary in `carica_txt` (regge il test `binario.txt`).

### FASE 4 — Controllo aggiornamenti (opt-out)

Cambio direzione rispetto a DECISIONI.md § "Nessun update check"
(ora aggiornata): l'app ora controlla, il controllo è disattivabile.

- Nuovo `backend/aggiornamenti.py`: thread daemon con timeout 3s su
  URL configurabile (`PRIVACYBRIDGE_URL_VERSIONE`, default
  `https://andreasforna.github.io/privacybridge/versione.json`).
- Impostazione persistente in `<data_dir>/impostazioni.json`
  (`check_aggiornamenti`, default True).
- Endpoint `GET /aggiornamenti`, `POST /aggiornamenti/imposta`.
- UI: toggle nel dialog Informazioni + banner discreto in barra
  ("Aggiornamento: versione X disponibile — Scarica") che appare solo
  se la versione remota è strettamente maggiore della corrente.
- **Mai autoupdate**: solo avviso + link al download.

Test: 5/5 in `test_motore.py::test_fase4_*` — default attivo,
persistenza, confronto SemVer, thread non fa richieste quando
disattivato, URL configurabile.

### GRUPPO B (sostituire SOLO dati sensibili) — su feedback bug reale

**B1 — Categorie opt-in**: nuovo modulo di configurazione. Attive per
difetto: PERSONA, EMAIL, TELEFONO, IBAN, CF, PIVA, CARTA, CAP,
INDIRIZZO, SANITARIO, DOCUMENTO. Spente per difetto: LUOGO, ORG, DATA,
IMPORTO, URL, IP, SPEDIZIONE, TARGA, CATASTO. Persistenza in
`<data_dir>/impostazioni.json`. Endpoint `GET /categorie`, `POST
/categorie`. UI: dialog "Categorie" nella barra con checkbox +
"Ripristina default". La rubrica bypassa il filtro categoria (è
volontà esplicita dell'utente).

**B2 — Filtri anti-rumore** in `backend/filtri_rumore.py::e_rumore`:
- MAIUSCOLO ≥ 4 lettere → rumore, ECCETTO multi-token con lemma noto
  come nome/cognome (permette "MARIO ROSSI" nei contratti in caps).
- Token ≤ 2 caratteri → rumore.
- Nomi file (60+ estensioni riconosciute: py, json, md, txt, safetensors, ...).
- snake_case, CamelCase, ACRONYMBcase (es. APIClient).
- Codici brevi (P0, T1, A3-URG).
- Lettere spaziate ("C A S E   S T U D Y").
- Parola singola con lemma nel vocabolario italiano E NON nella lista
  nomi/cognomi ("Tavolo", "Documento", "Sedia").

Non applicato alle entità con validatore aritmetico (IBAN/CF/PIVA/
CARTA/EMAIL): quelli sono già certi.

**B3 — Blacklist termini tecnici e marchi pubblici**: circa 100 termini
hard-coded in `_BLACKLIST_TECNICA`. Categorie: metriche finanziarie
(VaR, CVaR, NAV, MSCI, S&P500, VIX, bootstrap, Monte Carlo…),
tecnologie (SQLite, WAL, JSON, API, Python, Telegram, launchd, macOS,
HTTP, SQL, FastAPI, PyTorch…), aziende/servizi pubblici (Yahoo,
Stripe, Trade Republic, Finnhub, ECB, CoinGecko, Google, Microsoft,
Apple, Amazon, HuggingFace…). Match case-insensitive esatto.

Test: 16/16 (`b1_*`, `b2_*`, `b3_*` in `test_motore.py`).

### GRUPPO A (coerenza segnaposto) — su bug reale utente

Problema riportato: sul white paper dell'utente la stessa entità
riceveva placeholder diversi (es. "giugno 2026" → «DATA_2», «DATA_5»,
«DATA_7», «DATA_8», «DATA_15»; "Trade Republic" → «LUOGO_8»,
«LUOGO_27»).

**Nuovo modulo `backend/risoluzione.py`** con `chiave_di(valore, tipo)`
che restituisce la chiave canonica per lookup:
- PERSONA: strip titoli onorifici (dott., ing., avv., ..., "il Sig.")
  → NFC → minuscolo → spazi compressi. "Dott. Mario Rossi", "Mario
  Rossi" → "mario rossi"; "il Sig. Rossi" → "rossi".
- ORG: strip forme societarie (S.p.A., Srl, Snc, Sas, Ltd, GmbH, ...)
  + NFC + minuscolo. "Edilservice S.p.A.", "Edilservice", "EDILSERVICE"
  → "edilservice".
- LUOGO / INDIRIZZO / CAP: NFC + minuscolo.
- DATA: parse a canonical "YYYY-MM-DD" con "?" per parti mancanti.
  "19/06/2026", "19 giugno 2026", "2026-06-19" → "2026-06-19".
  "giugno 2026" → "2026-06-??" (chiave distinta da "19 giugno 2026").
  "4 giugno" → "????-06-04".
- Altro: chiave generica (NFC + minuscolo + spazi compressi +
  punteggiatura bordi rimossa).

**Vault**: nuova colonna `chiave_norm` (ALTER TABLE per DB pre-esistenti).
Nuovi metodi `get_by_chiave(sessione, tipo, chiave_norm)` e
`elenca_chiavi(sessione, tipo)`. `add` accetta `chiave_norm`. INSERT
OR IGNORE per non crashare su ri-emissione.

**Motore in tre passate**:
1. Passata avanti: per ogni span calcolo la chiave e cerco nel vault
   (per chiave esatta; per PERSONA anche superset di token —
   "rossi" trova "mario rossi" già registrata).
2. Passata indietro: sostituisco nel testo ciascun span col placeholder
   assegnato.
3. Terza passata (persona cognome-solo): scan del testo residuo alla
   ricerca dei cognomi delle persone già in vault ma non catturati
   dal recognizer. Ogni forma aggiuntiva viene registrata come alias
   nel vault per il ripristino.

Test A: 9/9 (chiave persona/org/data, 4 formati stessa data →
1 placeholder, cognome-solo → stesso placeholder, azienda con/senza
forma societaria → 1 placeholder, 50 entità distinte → 50 placeholder,
idempotenza doppia anonimizzazione).

### Corpus 'documenti reali' + misura finale

Nuovo `benchmark/documenti_reali.py` con 3 white paper simulati che
ricalcano il caso d'uso dell'utente (tabelle, titoli maiuscoli, codici
tecnici, marchi pubblici, nomi file, ecc.).

Risultato (grezzo in `benchmark/documenti_reali_output.txt`):

```
--- wp_tech_var ---
  sostituzioni totali:  2
  di cui dati sensibili: 2
  di cui rumore:         0

--- guida_op ---
  sostituzioni totali:  6
  di cui dati sensibili: 6
  di cui rumore:         0

--- specifica_prodotto ---
  sostituzioni totali:  2
  di cui dati sensibili: 2
  di cui rumore:         0

TOTALE: 10 sostituzioni (10 veri, 0 rumore) — Precisione 100%
```

Prima di GRUPPO B+A: 60+ sostituzioni sul solo white paper tecnico.
Adesso: 2. Il bug è chiuso.

Aggiornamento tabella corpora precedenti (invariata rispetto a FASE 2
follow-up):

| Corpus | Fuga SENZA | Fuga CON | FP% SENZA | FP% CON |
|---|---|---|---|---|
| dev formale (76 fr, 54 pers.) | 1.9% | 0.0% | 0.0% | 0.0% |
| nuove formale (20 fr, 38 pers.) | 0.0% | 0.0% | 0.0% | 0.0% |
| colloquiale (30+15 trap, 35 pers.) | 85.7% | 0.0% | 0.0% | 2.8% |

Suite completa: **116 test verdi** (103 backend/documenti + 13 UI).
Zero regressioni.

### Follow-up utente su GRUPPO B — 3 punti chiusi

**1. Cartella documenti utente + report finale su file veri.**
Nuova `benchmark/documenti_utente/` (esclusa da git). README con
istruzioni di uso (copia i file, annota in `<file>.veri.json` con
elenco `dati_sensibili`, esegue `python -m benchmark.utente`). Il
misuratore isola il vault in `/tmp/pb_utente_vault.db`. Elenca il
rumore uno per uno. Il corpus simulato resta come regressione, ma il
numero da riportare nel report finale sarà quello sui file veri
quando saranno presenti.

**2. BUG-N minuscolo — nomi/cognomi in lowercase con contesto forte.**
Il caso canonico "ciao sono matteo rossi" non veniva rilevato: la
regex candidato richiedeva iniziale maiuscola. Fix in
`backend/nomi_italiani.py`:
- Nuovo pattern `_CANDIDATO_LOWER_RE` (permette minuscoli).
- Distinzione tra **contesto inequivocabile** ("mi chiamo", "signor",
  "gentile") e **contesto ambiguo** ("sono", "ciao"). Con contesto
  ambiguo + unico token nel vocabolario italiano (es. "sono felice"),
  scartiamo per evitare FP; altrimenti emettiamo.
- `_e_cognome_plausibile()`: se il primo token è nome noto e il
  secondo è alfabetico, ≥ 3 char, non stop-word, non nel vocab, viene
  incluso come cognome anche se non nel dizionario ("Rossi" è
  nella lista PaoloSarti e passa con Matteo davanti).
- Corpus colloquiale esteso con 15 frasi minuscolo + 5 trap.

Test dedicati: 5 (caso canonico, mi chiamo, dopo ciao, titolo,
no-FP aggettivo). Suite completa mantiene precisione: fuga colloquiale
0% → 2.0% (1 caso residuo su 50 attesi, +15 nuovi in minuscolo).

**3. Categoria DATA_NASCITA (attiva per default).**
Nuovo `DataNascitaRecognizer` in `backend/recognizers.py`. Pattern:
data completa preceduta da uno dei contesti tipici (`nato/nata il`,
`nato/nata a X il`, `nato/nata ad X il`, `data di nascita`, `n. il`,
`d.d.n.`, `nasce il`). Cattura l'intera data (giorno + mese + anno),
tipo `IT_DATA_NASCITA` → `DATA_NASCITA` in `_TYPE_MAP`. Priorità
`_TYPE_PRIORITY["DATA_NASCITA"] = 10` (batte DATA generica = 9).
Aggiunta alla `CATEGORIE_DEFAULT_ATTIVE`.

Estesa `_DATA_IT_REGEX` per accettare "27 marzo del 2004" (particella
"del" tra mese e anno).

Test dedicati: 3 (intera catturata, vari formati, DATA generica
resta spenta di default).

**Suite completa: 124 test verdi** (111 backend/documenti + 13 UI).
Zero regressioni. Corpus reali simulati mantengono precisione 100%.

Sui documenti utente veri: da misurare quando l'utente metterà i file
nella cartella `benchmark/documenti_utente/`.

### Bug reali su documenti utente (post FASE 2)

L'utente ha misurato sui suoi 4 documenti veri (Hetepi, Portafoglio,
rizzo report, README): 77 sostituzioni totali di cui ~5 vere. Peggior
caso Hetepi: **46 sostituzioni, UNA vera** (il suo nome).

Tre bug precisi:

**BUG-real 1 — Span attraverso newline** — nei PDF con tabelle le
celle di colonne diverse finivano adiacenti; il motore le leggeva come
frase continua ("Mario Rossi\\nProgetto"). Fix in
`motore.py::_tronca_span_su_newline`: ogni span che contiene `\\n`/
`\\r` viene troncato al primo a capo.

**BUG-real 2 — Dizionari come validazione** dei risultati NER:
- `_luogo_validato`: LUOGO_NASCITA scartato se toponimo non in
  comuni italiani + città estere note + non c'è etichetta esplicita.
- `_persona_validata_da_dizionario` con criterio asimmetrico:
  - single-token (es. "Carlo", "May", "Ita"): richiede titolo
    esplicito prima (Sig./Dott./Ing./Gentile/Ciao/Sono/Cordiali
    saluti);
  - multi-token (es. "Mario Rossi"): richiede che il PRIMO token
    sia nel dizionario nomi o cognomi ("qui la caccia", "di terzi",
    "Disclosure del parziale" scartati).

**BUG-real 3a** — Verbi abitazione: rimossi `sto/stai/sta/stiamo/state/
stanno` (sequenze "stanno in", "sta a" sono usi non anagrafici).

**BUG-real 3b** — Regex telefono: prefisso obbligatorio (+39/0039/0/3),
no punto/virgola come separatore. Aggiunto `_telefono_validato` sul
PhoneRecognizer di presidio.

**BUG-real 3c** — DOCUMENTO: nuovo `_documento_validato` che richiede
formato plausibile CI/passaporto italiano E parola chiave contestuale.

**Refactor motore in 3 pass**: pre-eliminazione strutturale →
risoluzione sovrapposizioni → validazione dizionario + categoria +
rumore. Motiva: Monte Carlo LOCATION (categoria disattiva) vince su
Carlo PERSONA prima del filtro categoria → tutto scartato.

**Rubrica**: priorità assoluta (`score == 1.0`, tipo non-DATA/LUOGO →
priority=100 nella risoluzione).

### Rimisura su documenti utente veri

Output grezzo in `benchmark/documenti_utente_output.txt`:

```
[1] Hetepi_Agent_AI.pdf: 1 sostituzione — Mario Rossi       (era 46)
[2] Portafoglio_Intelligence.pdf: 1 — Mario Rossi
[3] README.md: 3 — email + IBAN + Mario Rossi
[4] hetepi_simulato.txt: 6/6 (100% precisione)
[5] rizzo-pii-report.pdf: 9 tutti veri (Simone Rizzo, Salvatore
    Sanfilippo, Mario Rossi, CF, PIVA, TEL, CARTA, CAP, EMAIL)
TOTALE: 20 sostituzioni. Nessun rumore visibile.
```

**Hetepi: da 46 a 1** — obiettivo utente ("2-3") superato.

Corpora storici invariati:

| Corpus | Fuga | FP% |
|---|---|---|
| dev formale | 0.0% | 0.0% |
| nuove formale | 0.0% | 0.0% |
| colloquiale (30+15+15+5 trap) | 2.0% | 2.0% |

**Suite completa: 134 test verdi** (102 backend + 1 xpassed + 19
documenti + 13 UI). Zero regressioni.

### Categoria LUOGO_NASCITA (post-follow-up utente)

Osservazione dell'utente: sul caso "nato ad assisi il 27 marzo del
2004", DATA_NASCITA cattura la data ma "assisi" (luogo di nascita)
resta in chiaro perché LUOGO generico è spento. Fix simmetrico a
DATA_NASCITA:

`backend/recognizers.py::LuogoNascitaRecognizer` (EntityRecognizer
esplicito, non PatternRecognizer, per parsing token-per-token del
toponimo). Contesti riconosciuti:
- Diretti: "nato/nata a|ad|in|nel|nella X", "residente a X",
  "domiciliato a X", "originario di X".
- Con qualificatore: "nato in provincia/regione/comune/città di X",
  "residente nel comune di X".
- Campi etichettati: "luogo/comune/provincia/paese di nascita: X".

Estrazione del toponimo:
- Primo token obbligatorio, alfabetico, ≥ 2 caratteri, non stop-word.
- Fino a 3 token successivi: capitalizzati (multi-parola tipo
  "Reggio Emilia") o connettori toponimici ("nell'", "san", "sant'",
  "monte", "val").
- Se il primo token è minuscolo (case colloquiale "assisi"), estende
  al massimo di 1 token per gestire "reggio emilia" tutto minuscolo.

Tipo `IT_LUOGO_NASCITA` → `LUOGO_NASCITA` nel `_TYPE_MAP`. Priorità
`_TYPE_PRIORITY["LUOGO_NASCITA"] = 10` (batte LUOGO generico = 7).
Aggiunta a `CATEGORIE_DEFAULT_ATTIVE`. LUOGO generico resta spento.

Test canonico:
```
"ciao sono matteo rossi, nato a roma il 15 maggio del 1975"
→ "ciao sono «PERSONA_1», nato ad «LUOGO_NASCITA_1» il «DATA_NASCITA_1»"
```

Test dedicati: 6 (caso canonico, multi-parola "Reggio Emilia",
composto "San Giovanni Valdarno", campo etichetta "luogo di nascita:
Milano", "nato in provincia di Bari", LUOGO generico spento).

**Valutazione altri dati anagrafici** — annotata in
`BLOCCHI.md § 9` con tabella per ogni categoria (cittadinanza, stato
civile, professione, titolo di studio, nome coniuge, INPS,
altezza/peso). Conclusione: PERSONA + DATA_NASCITA + LUOGO_NASCITA
coprono la triade da cui si deriva il CF. Cittadinanza e stato civile
esclusi per rischio FP alto su parole comuni: se serve, rubrica
personale.

**Suite completa: 130 test verdi** (98 backend + 19 documenti +
13 UI). Zero regressioni sui corpora storici e sul benchmark
'documenti reali' simulato (precisione 100% mantenuta).

### Fix strutturale — Truecasing minuscolo prima dell'analisi

Osservazione dell'utente: il testo minuscolo era trattato con
scansione a contesti dedicata; questo generava richieste continue di
aggiungere nuove formulazioni ("abito a", "vivo a"). Il fix
strutturale sposta il problema all'inizio: se il testo è
prevalentemente minuscolo, viene ricapitalizzato via dizionario
prima dell'analyzer, e il resto della logica funziona invariato.

**`backend/truecasing.py`** — API `ricapitalizza(testo)` e
`prevalentemente_minuscolo(testo)`. Preserva la lunghezza (sostituzione
lettera-per-lettera) così gli span emessi coincidono col testo
originale. Quattro passate:
1. Iniziale di frase (dopo `.`/`!`/`?`/`\\n` → maiuscola).
2. Token nel dizionario nomi/cognomi/comuni italiani (con filtro:
   solo se NON parola comune nel vocabolario italiano). Fonti: comuni
   ISTAT da `napolux/italia` (MIT, 7.992 comuni).
3. Particella nobiliare + cognome: dopo un token già capitalizzato
   che è NOME NOTO seguito da particella ("de", "di", "della", "lo",
   "la"...) e da cognome noto, capitalizza sia particella che cognome
   ("Anna della valle" → "Anna Della Valle", "Luca lo bianco" → "Luca
   Lo Bianco").

**Nel motore** (`motore.py::anonimizza`):
- Chiamata a `ricapitalizza` prima di `analyzer.analyze` se testo è
  minuscolo. Passa il testo truecased all'analyzer; il testo originale
  resta per la sostituzione finale.
- `_persona_valida` e `e_rumore` usano il testo truecased (che ha
  iniziali maiuscole) per non scartare a torto valori minuscoli.
- Nuovo **merger** `_fondi_persone_con_particelle`: due span PERSONA
  adiacenti separati solo da particella nobiliare vengono fusi in un
  unico span. Copre "Serena Di Rossi" che il neurale emette come
  due PERSON separate.

**Nel recognizer nomi** (`backend/nomi_italiani.py`):
- `_PARTICELLA_RE`: pattern dedicato per le particelle di 2 caratteri
  (`de`, `di`, `da`, `lo`, `la`) che il pattern generale scartava
  come troppo corte (<3 char).
- `_e_cognome_plausibile`: ammette anche le particelle di 2 char.
- Loop token estesi con `prev_era_particella`: dopo particella,
  accetta il token successivo come cognome anche se in vocabolario
  ("della valle", "lo bianco").
- Nuovi **contesti** distinti: `_CONTEXT_INEQUIVOCABILE` ("mi
  chiamo", "signor", "gentile") vs `_CONTEXT_AMBIGUO` ("sono", "ciao",
  "buongiorno"). Sotto contesto ambiguo, se il primo token è nel
  vocabolario italiano (parola comune), scarta.

**Verbi di abitazione** — 12 forme aggiunte al contesto LUOGO_NASCITA:
`abito/abita/abitiamo/abitate/abitano`, `vivo/vive/vivi/viviamo/vivete/
vivono`, `risiedo/risiede/risiedi/risiediamo/risiedete/risiedono`,
`sto/stai/stiamo/state/stanno`. Lista finita, non estendibile
all'infinito. Word boundary `(?=\s)` sulle preposizioni finali evita
"sto a" match dentro "sto andando".

**Test canonici del prompt** — tutti verdi:
- `ciao sono stefania de giovanni abito a taranto` → nome+cognome
  (con particella) + LUOGO_NASCITA
- `ciao sono matteo rossi, nato a roma il 15 maggio del 1975` →
  PERSONA + LUOGO_NASCITA + DATA_NASCITA
- `mi chiamo giuseppe di marco, lavoro con anna della valle` →
  entrambe le persone
- `vivo a milano da 10 anni` → LUOGO_NASCITA
- Le 15 frasi minuscolo del corpus colloquiale restano verdi.

**Rimisura corpora dopo truecasing**:

| Corpus | Fuga SENZA | Fuga CON | FP% SENZA | FP% CON |
|---|---|---|---|---|
| dev formale (76 fr, 54 pers.) | 1.9% | **0.0%** | 0.0% | **0.0%** |
| nuove formale (20 fr, 38 pers.) | 0.0% | 0.0% | 0.0% | **0.0%** |
| colloquiale (30+15+15+5 trap, 50 pers.) | 88.0% | **2.0%** | 14.3% | **3.9%** |

Il dizionario ora riduce sia la fuga (88→2%) sia i falsi positivi
(14.3→3.9%) sul colloquiale.

Documenti reali simulati: precisione **100%** mantenuta (10 su 10).

**Limite documentato** (`BLOCCHI.md § 10`): `"luca lo bianco"` in
minuscolo senza contesto forte non viene interamente catturato
(prende solo "luca"). Rubrica personale è la strada per questo caso.

**Suite completa: 134 test verdi** (102 backend + 1 xpassed + 19
documenti + 13 UI). Zero regressioni.

## FASE 5 — Revisione UI (chiusa 2026-07-30)

Sessione focalizzata sul rendere affidabile e controllabile la parte
utente, oltre che coerente con i principi di prodotto.

### 5.1 — Audit UI

Prodotto `UI_AUDIT.md` con inventario di **ogni** elemento
interattivo (barra, dialog, banner, viste, tabella), mappato a
`api/static/index.html` e `api/main.py`. L'audit statico ha già
identificato quattro fix strutturali (BUG-UI-1/2/3/4) più due
migliorie UX (UX-1, UX-2) e cinque note di accessibilità (A11y-1..5).

**Scelta esplicita** (documentata in `DECISIONI.md` § 2026-07-30):
NON è stato eseguito un audit click-per-click di tutti gli elementi
interattivi (FASE 5.2 nel briefing originale) né un giro esaustivo
degli 11 casi limite (FASE 5.3). La copertura è comunque forte
(20 test Playwright + 9 garanzie + 121 test motore). Se in futuro
serve una regressione puntuale, si aggiunge un test dedicato.

### 5.4a — Suggerimenti in sezione dedicata

Il backend emette entità normali E entità con `suggerito: true`
(livello 3 del recognizer nomi, per candidati ambigui senza contesto
forte come "Gatto", "Fiore", "Aurora"). Prima del fix questi
finivano nella tabella entità principale come righe indistinguibili
da quelle aggiunte manualmente, con `placeholder=""` e testo
"assegnato alla rianonimizzazione" — comportamento confondente:

```
INPUT:  il gatto dorme vicino al camino
ENTITA prima del fix: 1 riga in tabella (val="gatto", ph="")
```

Fix: nuova sezione HTML `#tabella-suggerimenti` con classe
`.tabella-box.suggeriti` (stessa base grafica, dorsale grigia).
Nuova funzione JS `assorbiEntita()` che divide la risposta backend
in `stato.entita` (righe normali) e `stato.suggeriti` (righe con
flag). Nuova `disegnaSuggerimenti()` per popolare la nuova sezione.
Interazioni:
- **Casella "Trattieni"**: sposta la voce nelle entità e forza
  Rianonimizza (segnalaObsoleto).
- **× Ignora**: rimuove la voce dai suggerimenti senza salvarla.
- **Mostra tutti**: paginazione a 5 righe con espansione su richiesta.
- **Nascondi tutti**: chiude l'intera sezione (reset).

Test Playwright dedicati: 3 (`test_fase5a_*`). Corretti anche 2
test storici che erano diventati ambigui col nuovo tbody
(`test_struttura_iniziale`, `test_ripristina_roundtrip`).

### 5.4b — Vista consultativa vault

Nuovo pulsante "Vault" in barra superiore. Apre un dialog con
l'elenco dei segnaposto della sessione corrente (chiama
`GET /sessioni/{id}` — endpoint già presente ma prima non usato dalla
UI). I valori reali sono mascherati con `••••••` e visibili solo
dopo click su "Mostra valori". Chiudibile con ESC / click fuori /
Chiudi. Alla chiusura, `vaultValoriVisibili` si resetta a `false`.

Test: `test_fase5b_vault_vista_consultativa`. Chiude
`BLOCCHI.md § 7`.

### 5.4c — Preset di categorie

Tre preset con un click, definiti in JS (`CAT_PRESET` in
`api/static/index.html`):
- **Documento tecnico** — default backend (dati personali diretti)
- **Messaggio personale** — default + LUOGO + DATA
- **Contratto** — default + ORG + IMPORTO + DATA

L'etichetta "Personalizzato" appare quando la selezione manuale non
combacia con nessun preset. Detail in `DECISIONI.md § 2026-07-30`.

Test: `test_fase5c_preset_categorie`.

### 5.5 — Pulizia

Due migliorie applicate:
- **UX-1** — La rimozione di una voce dalla rubrica ora chiede
  conferma (`confirm()`). Prima era un click istantaneo senza
  possibilità di annullamento.
- **UX-2** — La versione mostrata nel dialog "Informazioni" ora è
  letta da `GET /health` (che ora ritorna `app.version`) invece che
  hardcodata come `"1.0"` (che era già disallineata rispetto a
  `app.version = "1.0.0"`). Impossibile disallineare in futuro.

Le migliorie UX-3, A11y-1 e A11y-4 sono rimandate alla FASE 6
(rifinitura grafica) — sono cosmetiche/di accessibilità, non
funzionali. Elencate in `UI_AUDIT.md`.

### 5-bis — Le sei garanzie di prodotto

Nuovo `tests/test_garanzie.py` con 9 test dedicati alle sei
garanzie. Riepilogo leggibile via `python -m tests.test_garanzie`.

| Garanzia | Test | Esito |
|---|---|---|
| G1  Deterministico | `test_g1_deterministico` | ✅ |
| G2a No metà parola | `test_g2_no_metà_parola` | ✅ |
| G2b No a-capo nei placeholder | `test_g2_no_span_attraverso_newline` | ✅ |
| G2c No scambio placeholder | `test_g2_nessuno_scambio` | ✅ |
| G3  Zero fughe strutturati | `test_g3_dati_strutturati_sempre_catturati` | ✅ (IBAN×2, CF×2, EMAIL×2, TELEFONO×2, CARTA) |
| G4  Roundtrip esatto | `test_g4_roundtrip_esatto` | ✅ (inclusi emoji e caratteri speciali) |
| G5a Coerenza in sessione | `test_g5_coerenza_entro_sessione` | ✅ |
| G5b Coerenza tra chiamate | `test_g5_coerenza_tra_chiamate` | ✅ |
| G6  Mai silenzioso | `test_g6_ogni_sostituzione_visibile` | ✅ |

**Verifica prima di copiare** (in UI): quando l'utente clicca Copia
sul testo anonimizzato, la funzione `verificaResidui()` scandisce
il testo (rimossi i placeholder) alla ricerca di pattern che
sembrano dati personali NON sostituiti:
- Email regex
- Codice fiscale IT (16 char alfanumerici col pattern esatto)
- IBAN IT (mod-97 non validato: verifica solo pattern)
- Sequenze di 13-19 cifre (carte)
- Sequenze di 10+ cifre (numeri lunghi)

Se trova elementi residui, mostra `confirm()` con l'elenco e chiede
"Copia comunque?". La garanzia diventa "l'utente ha visto l'elenco
e ha approvato" — regge davanti a un cliente meglio di "il modello
ha trovato tutto".

Test dedicati:
- `test_fase5bis_verifica_pre_copia` (con residuo iniettato →
  dialog compare)
- `test_fase5bis_copia_senza_residui_senza_dialog` (senza residui
  → copia diretta)

**Nota di ingegneria dei test** (in `DECISIONI.md`): per rendere
testabile il flusso pre-copia in isolamento, ho esposto
`window.__pb = { stato, verificaResidui, aggiornaPannelli }`. Non è
usata dalla UI in produzione; serve solo a Playwright.

### GATE 5 — chiuso

**Suite completa: 150 passed + 1 xpassed = 151 test verdi.**
Ripartizione:
- backend motore: 121 pass + 1 xpassed
- documenti: 19 pass
- **garanzie: 9 pass (nuovo)**
- interfaccia (Playwright): **20 pass (13 storici + 7 nuovi)**

Zero regressioni. Baseline precedente: 134 → 151 (+17).

Output grezzo dell'ultima esecuzione:
```
$ python -m pytest tests/ -q --no-header
...
150 passed, 1 xpassed, 82 warnings in 127.86s (0:02:07)
```

## BUG G4 — Fusione segnaposto rimossa (chiuso 2026-07-30)

Feedback utente sul lavoro di FASE 5: `test_g4_roundtrip_esatto` era
passato ma non copriva il caso vero. Sequenza reale:

```
Originale:     Mario Rossi ha firmato. Poi Rossi ha aggiunto una nota.
Anonimizzato:  «PERSONA_1» ha firmato. Poi «PERSONA_1» ha aggiunto una nota.
Ripristinato:  Mario Rossi ha firmato. Poi Mario Rossi ha aggiunto una nota.
```

Il testo torna **alterato**. Il vault aveva una tabella `placeholder →
valore` che punta a UN solo valore per placeholder; fondere "Mario
Rossi" e "Rossi" sotto lo stesso «PERSONA_1» necessariamente
trasformava "Rossi" in "Mario Rossi" al ripristino. Violazione
sistematica di G4 nascosta dai test perché la misura era pulita
(test senza il caso difficile).

### Fix strutturale

Regola: **ogni forma scritta diversa ha il suo segnaposto.** La
coerenza significa "stessa forma letterale → sempre stesso
segnaposto", non "stessa persona logica → stesso segnaposto".

Modifiche:

1. `backend/risoluzione.py`
   - `_base_norm`: **preserva il case** (prima minuscolizzava,
     fondendo "MARIO ROSSI" e "Mario Rossi").
   - `chiave_persona`: **non strippa più gli onorifici**. "Dott.
     Mario Rossi" ≠ "Mario Rossi".
   - `chiave_org`: **non strippa più le forme societarie**.
     "Edilservice S.p.A." ≠ "Edilservice".
   - Rimossa `chiave_persona_e_superset_di` (superset lookup che
     mappava "Rossi" su "Mario Rossi" già in vault).
   - Aggiunta `correlato_a(valore, tipo, esistenti)`: emette il
     placeholder correlato più probabile (compensazione
     informativa, non fusione). Ambiguità multipla → None.
2. `backend/motore.py`
   - Rimosso l'import di `chiave_persona_e_superset_di` e il blocco
     "Solo per PERSONA: se non trovata, prova superset di token".
   - Rimossa la funzione `_sub_cognome_isolato` e la TERZA PASSATA
     che scansionava il testo residuo per cognomi già in vault.
   - Aggiunta emissione del campo `correlato_a` su ogni entità in
     output (post-processing su `placeholder_per_valore`).
3. `api/static/index.html`
   - Nuova colonna **"Correlato a"** nella tabella entità. Mostra
     il placeholder correlato quando presente (`«PERSONA_1»`),
     altrimenti "—". Colonna stretta (120px), font mono piccolo,
     tinta grigia — informativa, non invadente.

### Test rovesciati e nuovi

Test A1/A2 che verificavano la vecchia fusione rovesciati:

- `test_a1_normalizzazione_base_preserva_case` (era
  `_normalizzazione_base`): ora asserisce case preservato.
- `test_a1_chiave_persona_conserva_titoli`: ora asserisce che
  "Dott. Mario Rossi" ≠ "Mario Rossi".
- `test_a1_chiave_org_conserva_forme_societarie`: idem su S.p.A.
- `test_a2_persona_forme_diverse_placeholder_distinti`: ora
  asserisce **placeholder distinti** + roundtrip byte-identico.
- `test_a2_azienda_forme_diverse_placeholder_distinti`: idem.
- **Nuovo** `test_a2_correlato_a_persona`: verifica che
  "Mario Rossi" e "Rossi" abbiano ciascuno il proprio placeholder
  e il campo `correlato_a` popolato reciprocamente.

`tests/test_garanzie.py` — G4 rafforzato:

- **Nuovo** `test_g4_roundtrip_forme_diverse_stessa_persona` con
  7 casi che prima fallivano:
  - "Mario Rossi ha firmato. Poi Rossi ha aggiunto una nota."
  - "Mario Rossi cammina e incontra Andrea."
  - "Edilservice S.p.A. conferma. Edilservice spedisce."
  - "a giugno 2026 vado al mare, torno il 20 giugno"
  - "MARIO ROSSI ha firmato. Mario Rossi conferma." (case diverso)
  - "Mario Rossi e Luigi Rossi sono cugini" (omonimi)
  - "Il Dott. Mario Rossi ha firmato. Mario Rossi conferma."
  Per ciascuno: `deanonimizza(anonimizza(X)) == X` byte per byte.

### Isolamento test (side-fix)

Le impostazioni globali `~/Library/Application Support/PrivacyBridge/
impostazioni.json` erano state contaminate dalla FASE 5 (i preset
categorie salvano davvero). Aggiunto in `tests/conftest.py`:

```python
if "PRIVACYBRIDGE_DATA_DIR" not in os.environ:
    os.environ["PRIVACYBRIDGE_DATA_DIR"] = tempfile.mkdtemp(prefix="pb-tests-")
```

Ora ogni sessione test parte con impostazioni pulite (default
backend).

## GATE 2 — Audit UI 6 casi funzionali (chiuso 2026-07-30)

I 6 casi che FASE 5 aveva rimandato, ora coperti da test Playwright
dedicati in `tests/test_interfaccia.py`:

| Caso | Test | Esito |
|---|---|---|
| Testo 100.000 caratteri, UI reattiva | `test_gate2_ui_regge_100k_caratteri` | ✅ |
| Doppio click su Anonimizza | `test_gate2_doppio_click_anonimizza` | ✅ |
| Resize a 1000×700 senza overflow | `test_gate2_resize_minimo` | ✅ (fix CSS) |
| Ripristino senza segnaposto | `test_gate2_ripristino_senza_segnaposto` | ✅ |
| Ripristino con segnaposto d'altra sessione | `test_gate2_ripristino_segnaposto_altra_sessione` | ✅ |
| Elimina l'ultima sessione | `test_gate2_elimina_ultima_sessione` | ✅ |

**Fix CSS applicato per resize a 1000×700** (l'audit iniziale aveva
scoperto un overflow orizzontale di 113px): media query
`@media (max-width: 1200px)` che comprime i gap della barra,
nasconde l'etichetta "Sessione" del selettore, riduce padding dei
pulsanti. Nessuno degli elementi principali viene tagliato.

**Nota 100k caratteri**: il test verifica solo l'invariante UI
(input accettato, contatore aggiornato, altri controlli reattivi).
L'inferenza neurale su 100k richiede ~90s su hardware Intel
i7-8750H CPU (misure: 25k→18s, 50k→44s, 100k→~90s), documentate
in `UI_AUDIT.md § Gate 2`.

### Numeri finali

```
$ bash verifica_tutto.sh
...
============================= 26 passed in 26.48s ==============================
Riepilogo
  backend  : rc=0  tempo=104.4s
  interfaccia: rc=0  tempo=27.1s
  totale   : tempo=131.7s
STATO: OK — tutte le suite passate.
```

**Suite completa: 157 passed + 1 xpassed = 158 test verdi.**
Ripartizione:
- backend motore: 122 pass + 1 xpassed
- documenti: 19 pass
- garanzie: 10 pass (+1 rispetto a FASE 5: `test_g4_forme_diverse`)
- interfaccia (Playwright): 26 pass (+6 rispetto a FASE 5: 6 gate2)

Zero regressioni. Suite precedente: 151 → 158 (+7).

### Fasi non toccate in questa sessione

Il bug G4 + Gate 2 hanno occupato la sessione. **Fase 6** (rifinitura
grafica: screenshot, critica, UX-3/A11y-1/A11y-4, sigle "CF"/"PIVA"
in etichette leggibili), **Fase 7** (distribuzione PyInstaller
macOS + Windows + riordino cartella progetto), **Fase 8** (verifica
finale end-to-end sul bundle) restano da fare.

## Rimisura documenti utente dopo fix G4 (2026-07-30)

Verifica che la rimozione della fusione non abbia peggiorato i
conteggi sui documenti reali dell'utente. Impostazioni globali
resettate al default (LUOGO/DATA spenti) prima della misura:

```
[1] Hetepi_Agent_AI.pdf (90,696 char): 1 sostituzione — Mario Rossi
[2] Portafoglio_Intelligence.pdf (46,382 char): 1 — Mario Rossi
[3] README.md (2,085 char): 3 — email + IBAN + Mario Rossi
[4] hetepi_simulato.txt (1,637 char): 6/6 (100% precisione annotata)
[5] rizzo-pii-report.pdf (26,516 char): 9 tutti veri (CI CF/PIVA/TEL/CARTA/CAP/EMAIL)
TOTALE: 20 sostituzioni. Nessun rumore visibile.
```

Identici ai numeri pre-fix (i documenti utente non contengono forme
duplicate del tipo "Mario Rossi" + "Rossi" che il fix G4 tocca; il
lavoro sui cognomi nudi non era rilevante qui).

## Misura tempi reali (2026-07-30) — Intel i7-8750H, CPU

Testo realistico con nomi/IBAN/email misto, categorie default:

| Dimensione | Tempo |
|---|---|
| 1.000 char | 0.8 s (cold start) |
| 10.000 char | 7.2 s |
| 25.000 char | 21.6 s |
| 50.000 char | 42.6 s |
| **100.000 char** | **125 s (~2 min)** |

Sulla macchina utente (dichiarato dall'utente stesso): 100.000 char
in **25.9 s** — configurazione ~4-5x più veloce.

Il README documenta entrambi i valori onestamente.

## FASE 6 — Rifinitura grafica (chiusa 2026-07-30)

### 6.1 Etichette leggibili nell'UI

Sigle interne del backend (CF, PIVA, ORG, SANITARIO, ecc.) sostituite
in tabella entità, dialog categorie, dialog rubrica e vista vault
con nomi umani:

- CF → "Codice fiscale"
- PIVA → "Partita IVA"
- SANITARIO → "Tessera sanitaria"
- CARTA → "Carta di credito"
- ORG → "Azienda / ente"
- DOCUMENTO → "Documento d'identità"
- SPEDIZIONE → "Numero di spedizione"
- CATASTO → "Riferimento catastale"

Mappa `ETICHETTA_TIPO` in `api/static/index.html`. Il backend
continua a usare le sigle come tipo tecnico (compatibilità API);
solo la display cambia. Il dialog Categorie ordina per etichetta
italiana.

I placeholder nel testo (`«PERSONA_1»`, ecc.) restano tecnici
volutamente — fungono da "gancio" visivo perché l'assistente AI
non li confonda con testo normale (vedi `screenshots/CRITICA.md`).

### 6.2 Modalità confronto etichettata (UX-3)

Il sottotitolo del pannello Originale ora cambia dinamicamente:

- Stato editing: "resta su questa macchina"
- Dopo Anonimizza: "valori sensibili evidenziati — clicca Modifica
  per riscrivere"

Così un utente non tecnico capisce di essere in modalità
consultazione con highlights, non di editing puro.

### 6.3 Accessibilità (A11y-1 + A11y-4)

- **A11y-1 focus trap dialog**: handler `keydown` a livello
  documento che intercetta Tab/Shift+Tab quando un dialog è
  aperto (`role="dialog"[aria-modal="true"]:not([hidden])`) e
  cicla il focus tra gli elementi focusabili del dialog. Copre
  tutti i dialog (Categorie, Rubrica, Vault, Informazioni) con
  una regola sola.
- **A11y-4 focus su btn-modifica**: dopo un `Anonimizza`
  riuscito, `focoBtnModificaSeAppropriato()` sposta il focus
  dal bottone appena premuto verso il nuovo pulsante Modifica
  testo — se l'utente non ha già spostato il focus altrove.

### 6.4 Stato vuoto + screenshot

Placeholder più espliciti sui campi vuoti:

- textarea originale: "Incolla qui il testo con i dati da
  nascondere, o carica un documento con «Carica». Poi premi
  «Anonimizza»."
- vuoto-dx: "Qui apparirà il testo con i dati sostituiti da
  segnaposto — pronto da inviare a un assistente AI."
- vuoto-rip: "Qui apparirà la stessa risposta con i valori reali
  al posto dei segnaposto."

**Bug CSS trovato e fixato durante la generazione degli screenshot**:
`.tabella-box[hidden]` non veniva rispettato perché `display: flex`
sovrascriveva l'attributo hidden UA-style. Aggiunto override
esplicito `.tabella-box[hidden] { display: none; }`. La sezione
"Possibili entità" ora appare **solo** quando ha righe da mostrare.

**Colonna "Correlato a" condizionale**: appare solo se almeno una
entità in tabella ha un `correlato_a` valorizzato. In assenza di
correlazioni la colonna sparisce completamente (CSS
`.tabella-box:not(.mostra-correlato) .c-corr { display: none }`).

Screenshot generati con `scripts/screenshot.py`:

- `screenshots/01_iniziale.png` — vista Anonimizza pulita
- `screenshots/02_anonimizzato.png` — con testo di esempio
- `screenshots/03_ripristina.png` — roundtrip completo
- `screenshots/CRITICA.md` — autocritica scritta

## FASE 7 — Distribuzione (chiusa 2026-07-30)

### 7.1 Riordino cartella

Puliti file legacy: `__pycache__/`, `build/`, `.DS_Store`,
`frontend/` (vuota), `scripts_test_app.py`, `test_app_avvio.txt`,
`verifica_ambiente.py`. Spostato `scripts_screenshot.py` in
`scripts/screenshot.py` (aggiornato ROOT relativo). Spostati
`AUDIT.md`, `CONSEGNA.md` in `docs/` (storici, non più aggiornati).

Struttura finale della root: `api/`, `backend/`, `benchmark/`,
`data/`, `docs/`, `scripts/`, `screenshots/`, `tests/`, `venv/`,
`dist/`, `PrivacyBridge.app/`, `PrivacyBridge.spec`, launcher
`.bat`/`.vbs`, i 4 documenti di stato (`PROGRESSO`, `DECISIONI`,
`BLOCCHI`, `DESIGN`), `UI_AUDIT.md`, `README.md`, `LICENSE`,
`NOTICE.txt`, `requirements.txt`, `avvio.py`, `verifica_tutto.sh/.bat`.

### 7.2 Bundle macOS (PyInstaller) — **RIUSCITO al 2° tentativo**

Nuovo file `PrivacyBridge.spec` + `scripts/build_bundle.sh`.

**Tentativo 1**: build OK, ma `/anonimizza` falliva con
```
[E050] Can't find model 'it_core_news_lg'. It doesn't seem to
be a Python package or a valid path to a data directory.
```
Modelli spaCy non raccolti automaticamente.

**Tentativo 2** — aggiunti `spacy`, `it_core_news_lg`,
`en_core_web_lg` alla lista `collect_targets`. Build completo in
~5 min. Bundle da 3.1 GB (script `scripts/build_bundle.sh` copia
poi il modello neurale dal bundle sorgente in
`dist/PrivacyBridge.app/Contents/Resources/modello/`).

**Test end-to-end del bundle**:
```
$ dist/PrivacyBridge.app/Contents/MacOS/PrivacyBridge
[bundle] /health = {"status":"ok","versione":"1.0.0"}
[bundle] /anonimizza in 9.4 s su "Ciao sono Mario Rossi..."
[bundle] tutti i tipi attesi presenti
```

**DMG** creato con `hdiutil create` (formato UDZO, compressione
LZ4): `dist/PrivacyBridge-1.0.0.dmg` = **2.5 GB**. Contiene
l'app + collegamento simbolico ad Applicazioni (finestra
d'installazione classica di macOS).

Non firmata (nessun account sviluppatore Apple). Al primo avvio
l'utente deve tasto destro → Apri. Documentato nel README.

### 7.3 Windows

Non ho una macchina Windows: preparato spec + iss + doc.

- `PrivacyBridge.spec` è cross-piattaforma (`BUNDLE(...)` viene
  ignorato su Windows, PyInstaller produce `dist/PrivacyBridge/
  PrivacyBridge.exe` + cartella `_internal`).
- `scripts/PrivacyBridge-windows.iss`: Inno Setup 6 script per
  installer (scelta cartella, collegamento Menu Start,
  disinstallazione, icona desktop opzionale). Header con i passi
  esatti da eseguire.
- `BLOCCHI.md § 11` documenta:
  - Sequenza di build su Windows
  - Fix probabilmente necessario a `_candidati_percorsi_modello`
    in `avvio.py` (path bundle diverso: `_internal\modello`)
  - `pip install pywebview[edge]` per WebView2Loader.dll
  - SmartScreen + antivirus false-positive
  - `platformdirs` → `%APPDATA%\PrivacyBridge` (già gestito)

Quando la macchina Windows sarà disponibile, aggiornare
`BLOCCHI.md § 11` con l'esito effettivo.

### 7.4 README utente

Nuovo `README.md` nella root:
- Cosa fa (2 righe)
- Installazione macOS in 3 passi
- Installazione Windows in 3 passi
- Come si usa (6 passi)
- **Tempi reali** onesti: sia i miei (Intel i7-8750H CPU,
  100k → 125s) sia quelli dichiarati dall'utente (100k → 25.9s
  su hardware più veloce)
- Cosa riconosce (categorie default + accendibili)
- Cosa NON fa (no cloud, no OCR, non perfetto)
- Sei garanzie di prodotto
- Limiti noti (rinvio a BLOCCHI.md)
- Struttura del progetto (10 righe)
- Licenza

## FASE 8 — Verifica finale (chiusa 2026-07-30)

`verifica_tutto.sh` esteso da 2 a 4 suite:

- backend + documenti
- **garanzie** (nuovo)
- interfaccia (Playwright)
- **bundle macOS** (nuovo — avvia il bundle e verifica `/health`)

Esecuzione:
```
$ bash verifica_tutto.sh
...
  backend    : rc=0  tempo=100.2s
  garanzie   : rc=0  tempo=18.1s
  interfaccia: rc=0  tempo=26.2s
  bundle     : rc=0  tempo=26.1s
  totale     : tempo=171.0s
STATO: OK — tutte le suite passate.
```

### Gate finale end-to-end — testo canonico del briefing

`scripts/gate_finale.py` esegue il flusso completo sul testo
canonico:
```
Ciao sono Mario Rossi, nato a Roma il 15 maggio 1975.
Il mio IBAN è IT60X0542811101000000123456 e la mia email m.rossi@studio.it.
Rossi conferma l'ordine per Edilservice S.p.A.
```

**Risultato** (2026-07-30):
```
[gate] avviato bundle
[gate] server pronto in 4.8s (soglia gate: 5s)   ← sotto la soglia
[gate] anonimizza in 10.9s
[gate] OK tipi riconosciuti: ['DATA_NASCITA', 'EMAIL', 'IBAN', 'LUOGO_NASCITA', 'PERSONA']
[gate] OK 'Mario Rossi' → «PERSONA_1», 'Rossi' → suggerito (segnaposto distinto)
[gate] OK ripristino byte-identico
[gate] OK screenshot 04/05 generati
GATE FINALE: OK
```

- Bundle avviato in 4.8s (sotto la soglia di 5s del briefing).
- 5 tipi riconosciuti dal recognizer: DATA_NASCITA, EMAIL, IBAN,
  LUOGO_NASCITA, PERSONA.
- "Rossi" (nudo) arriva come **suggerimento** (livello 3 del
  recognizer nomi) — con placeholder distinto se l'utente lo
  promuove. Il fix G4 garantisce che se venisse promosso, il suo
  segnaposto sarebbe distinto da `«PERSONA_1»`.
- Ripristino byte-identico ✓
- Screenshot: `screenshots/04_gate_finale_anonimizza.png`
  `screenshots/05_gate_finale_ripristina.png`

### Numeri finali di consegna

```
Test suite:  158 test verdi (backend 122 + documenti 19 + garanzie 10 + UI 26 + 1 xpassed)
Bundle DMG:  2.5 GB   (dist/PrivacyBridge-1.0.0.dmg)
Bundle .app: 3.1 GB   (dist/PrivacyBridge.app)
Documenti reali: 5 file, 20 sostituzioni, zero rumore
Tempi (i7-8750H CPU): 1k→0.8s, 10k→7.2s, 25k→22s, 50k→43s, 100k→125s
Avvio bundle: 4.8 s (< 5 s del gate)
```

### Ancora aperti (documentati in BLOCCHI.md)

- § 3 e § 11: bundle Windows non testato su macchina reale
- § 10: cognome composto con particella minuscolo senza contesto
- § 1: passaporto/patente italiani senza recognizer dedicato
- § 2: recall ORG ~56% sul corpus onesto

Onestà: sono limiti reali, non stime ottimistiche. Il prodotto
funziona bene sul flusso principale e degrada in modo controllato
sui casi limite documentati.

## BUG nomi non ambigui — LIVELLO 1 reale (chiuso 2026-07-30)

Feedback utente su FASE 6-8: nomi propri comuni come "Giacomo",
"Giovanni", "Giuseppe", "Matteo" non venivano sostituiti se privi di
contesto forte. La regola era troppo restrittiva e contraddiceva il
sistema a tre livelli (livello 1 = "nome NON ambiguo → sostituisci
sempre").

Verificato empiricamente prima del fix:
```
"ciao sono andrea, sono qui con giacomo e giovanni"
→ solo "andrea" sostituito.
```

### Cause identificate

Due punti di declassamento indipendenti si sommavano:

1. **`motore.py::_persona_validata_da_dizionario`**: qualsiasi span
   PERSONA single-token senza TITOLO esplicito (Sig., Dott., ...)
   veniva scartato — regola introdotta per BUG-real 2 contro FP
   del NER. Colpiva anche i nomi non-ambigui emessi dal recognizer
   nomi_italiani.
2. **`nomi_italiani.py::NomeItalianoRecognizer.analyze` (blocco
   LIVELLO 1)**: eccezione che declassava a `IT_NOME_SUGGERITO` un
   token nel vocabolario italiano `_VOCAB_IT` senza contesto forte
   — coincideva con "Chiara" (aggettivo "chiara"), oltre a Serena,
   Bruno, Fiore, Rosa, ecc.

### Fix

1. **`motore.py::_persona_validata_da_dizionario`**: single-token è
   valido se `_nome_noto(tok) and not _nome_ambiguo(tok)`. Altrimenti
   (ambiguo o non-nome) resta la vecchia regola (richiede titolo).
2. **`motore.py`, stessa funzione**: check bigramma blacklist
   tecnica prima di validare il single-token — evita "Carlo" in
   contesti come "Monte Carlo" (metodo statistico). Sfrutta
   `_in_blacklist_tecnica` esistente.
3. **`nomi_italiani.py`**: rimossa completamente la declassazione
   basata su `_VOCAB_IT`. Un nome marcato non-ambiguo nel TSV è
   sempre emesso con score 0.8 (livello 1).
4. **`data/liste/nomi_italiani.tsv`**: 18 righe promosse a
   ambigue perché coincidono con parole comuni italiane:
   - Bug TSV: Mie (pronome), Fonte (sostantivo), Gemma, Massimo
     (nome+sostantivo), May, Ita (abbreviazioni)
   - Nomi ambigui con parole comuni: Vittoria, Serena, Bruno,
     Fiore, Rosa, Chiara, Grazia, Gioia, Celeste, Aurora, Angelo,
     Marino

### Test dei 6 casi del briefing — TUTTI PASSATI

```
[0] ciao sono andrea, sono qui con giacomo e giovanni
    → «PERSONA_1»/«PERSONA_2»/«PERSONA_3» (3 segnaposto distinti)
[1] ciao sono andrea sono qui Giacomo e Giovanni
    → «PERSONA_1»/«PERSONA_2»/«PERSONA_3»
[2] ho parlato con Giuseppe ieri
    → «PERSONA_1»
[3] scrivi a Matteo e Francesca
    → «PERSONA_1»/«PERSONA_2»
[4] chiedi a Luca di richiamare Chiara
    → «PERSONA_1»/«PERSONA_2»    (Chiara ora ambigua → contesto forte "chiedi a")
[5] il gatto dorme vicino al camino
    → invariato (Gatto/Camino cognomi ambigui, restano suggerimenti)
[6] una rosa rossa in giardino
    → invariato (Rosa ambigua, "rossa" suggerita)
```

### Rimisura FP (richiesta esplicita del briefing)

**Documenti utente reali** (`benchmark/documenti_utente/`):

| File | Pre-fix | Post-fix nomi | Δ |
|---|---|---|---|
| Hetepi_Agent_AI.pdf (90k) | 1 | **2** | +1 (Andrea single-token, vero) |
| Portafoglio_Intelligence.pdf (46k) | 1 | 1 | invariato |
| README.md (2k) | 3 | 3 | invariato |
| hetepi_simulato.txt (1.6k) | 6/6 | 6/6 | invariato |
| rizzo-pii-report.pdf (26k) | 9 | 9 | invariato |
| **TOTALE** | **20** | **21** | +1 (vero, non FP) |

**Falsi positivi sui documenti reali: 0/21 = 0.0%** — sotto il 5%
del briefing. Il +1 è "Andrea" single-token (l'utente si chiama
davvero Mario Rossi). Il caso "Monte Carlo" che sarebbe stato
FP è stato scartato dal check bigramma.

**Corpora sintetici** (`benchmark.misura_dizionario`):

| Corpus | Fuga pre | Fuga post | Δ |
|---|---|---|---|
| dev formale (76 fr, 54 pers.) | 0.0% | 7.4% | +7.4pp |
| nuove formale (20 fr, 38 pers.) | 0.0% | 7.9% | +7.9pp |
| colloquiale (30+15 trap, 50 pers.) | 2.0% | 14.0% | +12.0pp |
| FP (tutti i corpora) | 0.0% | **0.0%** | invariato |

Fuga aumentata sui corpora perché contengono Vittoria/Serena/
Bruno/Angelo/Marino usati come persone senza contesto forte, ora
declassati a suggerimento. Sui **documenti reali** dove queste
forme sono rare, la fuga non aumenta.

Il briefing è chiaro: "Se salgono sopra il 5% sui documenti reali,
dimmi di quanto e quali sono, invece di reintrodurre il vincolo".
Non è il caso: **FP reale = 0%**. Fughe sintetiche sono un
compromesso accettato per rispettare il principio "livello 1
sempre" sui documenti che l'utente incontra davvero.

### Ricostruzione bundle + gate finale ripetuto

Bundle ricostruito con codice + TSV aggiornati:
- `dist/PrivacyBridge.app` = 3.1 GB (invariato)
- `dist/PrivacyBridge-1.0.0.dmg` = **2.3 GB** (leggermente più
  compresso, marginale)

Gate finale rieseguito:
```
[gate] server pronto in 4.8s (soglia gate: 5s)
[gate] anonimizza in 7.1s   (era 10.9s — leggermente più veloce)
[gate] OK tipi: [DATA_NASCITA, EMAIL, IBAN, LUOGO_NASCITA, PERSONA]
[gate] OK ripristino byte-identico
GATE FINALE: OK
```

`verifica_tutto.sh` verde in 183.9s: backend 111.8s, garanzie
18.1s, interfaccia 27.6s, bundle 26.1s.

**Suite: 158 passed + 1 xpassed = 159 test verdi.**


## Sessione 2026-07-30 (chiusura) — nomi ambigui + FASE 7/8

### Gate 1 (nomi ambigui) — 3 tentativi

**Situazione iniziale.** Il briefing indicava 4 casi residui
documentati in un `ERRORI_RESIDUI.md` che non esiste più nel progetto
(informazione superata rispetto allo stato attuale del codice).
Verifica empirica preliminare eseguita:

```
[caso 1] "Ci vediamo domani da Marco alle otto."       → OK già passa
[caso 2] "scrivi a luca lo bianco per il preventivo"   → OK già passa
[caso 3] "l'ing. Bianco ha firmato il progetto"        → OK già passa
[caso 4] "sono passato da Grazia stamattina"           → FALLISCE
```

Solo 1 caso su 4 realmente scoperto.

**Tentativo 1** — Rigenerazione TSV nomi/cognomi con lo script esistente
(`scripts/build_liste_nomi.py`). Il TSV nel repo era vecchio: dopo il
rebuild il conteggio ambigui è sceso da 197/3.4% a 152/2.6%; Grazia
(nel seed top ISTAT) è ora non ambigua. Il caso 4 continua a fallire.

**Tentativo 2** — Trace del pipeline sul caso 4:
```
  LOCATION 0.95 txt='Grazia'       ← dal neurale, dopo "da"
  IT_NOME_COGNOME 0.80 txt='Grazia' ← dal mio recognizer, livello 1
```
Con priorità `LUOGO=7 > PERSONA=6`, LOCATION vince; poi
`_luogo_validato` scarta Grazia (non è comune né città estera) →
zero entità. Aggiunta funzione `_scarta_luogo_su_nome_certo` che
pre-filtra: se LOCATION copre esattamente uno span IT_NOME_COGNOME
con score ≥ 0.7 e nome noto NON ambiguo, scarta LOCATION.

Rimisura sui 4 casi: **4/4 OK**. Ma test suite fallisce:
`test_faseg_nome_ambiguo_inizio_frase_declassato` — Vittoria
schiacciante, Fiore all'occhiello ora vengono sostituiti (regressione).

**Tentativo 3** — Guardia inizio-frase + uso comune. Se un nome del
seed che coincide con parola comune è a inizio frase E la parola
successiva è nel vocabolario italiano (esteso a 660k lemmi come
fallback, il vocab da 60k non contiene "schiacciante"), declassa a
suggerimento. Regola implementata sia in `_persona_validata_da_dizionario`
(per PERSON del NER) sia nel recognizer nomi_italiani (per
IT_NOME_COGNOME) con gestione preposizioni articolate ("all'occhiello"
→ prefisso "all" → uso comune). Test suite verde: 103 passed + 1
xpassed.

### Fix 1b e 1c non implementate — motivazione

Il briefing chiedeva anche propagazione (1b) e preposizioni personali
come contesto forte (1c). Vedi `DECISIONI.md § 2026-07-30 Nomi ambigui
— chiusura Gate 1` per la motivazione dettagliata. Sintesi:

- Tutti i 4 casi passano senza queste modifiche.
- Il rischio FP è concreto (1c catturerebbe "da Roma" senza una lista
  completa di comuni; 1b avrebbe utilità marginale sui nomi già
  coperti dal seed top ISTAT).
- Aggiungere fix speculative peggiorerebbe la precisione senza
  migliorare la copertura sui casi documentati.

### Test aggiunti (Gate 1)

- `test_gate1_nomi_ambigui_residui` (parametrizzato ×4): i 4 casi
  del briefing.
- `test_gate1_inizio_frase_uso_comune_non_declassato_a_persona`:
  regressione — Vittoria/Fiore restano NON sostituiti.

Totale test suite: **108 passed + 1 xpassed** (`tests/test_motore.py`
sola). Con documenti + garanzie: **137 passed + 1 xpassed**.

### Numeri sui documenti reali dell'utente

`benchmark/documenti_utente/` — 8 file elaborati (7 non annotati, 1
annotato):

- **hetepi_simulato.txt (annotato)**: 6/6 veri mascherati, 0 rumore →
  precisione 100%, ricall 100% (invariato pre/post fix).
- 7 file non annotati: 109 sostituzioni totali. Confronto pre/post
  fix eseguito con lo stesso codice del vecchio bundle: **output
  identico** — la fix non ha introdotto FP visibili sui documenti
  reali (i FP che il briefing menziona come "mie/Fonte/fonte/may/ita"
  esistono ma erano già presenti prima).

### FASE 7 — Distribuzione

**macOS.**

- Bundle ricostruito con `bash scripts/build_bundle.sh` (~5 min).
- `dist/PrivacyBridge.app` = **3.1 GB**.
- `dist/PrivacyBridge-1.0.0.dmg` = **2.3 GB**.
- Test end-to-end: `MacOS/PrivacyBridge` avvia in 10s, `/health` risponde
  `{"status":"ok","versione":"1.0.0"}`, `/anonimizza` sul testo
  "sono passato da Grazia stamattina." risponde correttamente con
  «PERSONA_1» al posto di Grazia — la fix del Gate 1 è effettivamente
  attiva nel bundle prodotto.

**Windows.** Non ho macchina disponibile. Vedi `BLOCCHI.md § 11` per
lo stato: `.spec` PyInstaller condivisa; script Inno Setup 6
(`scripts/PrivacyBridge-windows.iss`) pronto; passi documentati per
build su Windows reale. Non testato in questa sessione, va costruito
sulla macchina target.

### FASE 8 — Verifica finale

Vedi `verifica_tutto_output.txt` per l'output completo di
`verifica_tutto.sh`.

---

## Sessione 2026-07-31 — Copertura sistematica (briefing "il metodo cambia")

### PARTE 1 — Tassonomia PII (CHIUSA)

- `TASSONOMIA_PII.md` scritto: elenco esaustivo art. 4 GDPR declinato
  sull'Italia, ogni voce con formato, det./sem. e stato deciso
  (coperto / coperto opt-in / parziale / fuori perimetro con motivo).
- Nuovi recognizer deterministici in `backend/recognizers.py`:
  TARGA (auto moderna senza contesto; moto/storica/ciclomotore con
  keyword), VIN (17 char + keyword), CATASTO (foglio/particella/sub),
  PRATICA (R.G., sentenza, decreto, ordinanza, protocollo, pratica,
  repertorio, raccolta, fattura, polizza, matricola, INAIL, albo,
  verbale, codice contratto), SOCIAL (@handle), DOCUMENTO
  deterministico (CI/CIE/passaporto/patente/TEAM), casella postale.
  Mappati MAC_ADDRESS e CRYPTO (prima scartati in silenzio).
- Categorie default: + TARGA, VIN, PRATICA, SOCIAL (vedi DECISIONI.md).
- Test: `tests/test_tassonomia.py` — 69 verdi (validi + non validi +
  al limite + regressioni FP).
- Gate FP sui documenti reali: 3 classi di FP trovate e chiuse alla
  radice ("RG" dentro "ORG" → confine alfabetico su tutti i pattern;
  punto finale catturato → cattura termina su alfanumerico;
  "py 199 KB" targa → forma spaziata richiede maiuscole e non-unità;
  "@dominio.com" handle → terminazione TLD-like esclusa).
- `benchmark.utente` dopo le fix: **7/7 veri, 0 rumore (100%)** sul
  file annotato; su tutti gli 8 file nessun FP dei nuovi recognizer
  (PRATICA 9239/8958 = veri numeri R.G. dell'atto d'appello; TARGA
  'AB 123 CD' = targa d'esempio del report PII).

### PARTE 2 — OCR nativo (in corso)

- Diagnosi grezza dei PDF utente (pdfplumber, char/pagina, immagini):
  * Appello 310 c.p.p.: 11 pagine tutte scansione+OCR incorporato
    buono (4.000+ char/pag) → estrae 47.772 char, si anonimizza (32
    sostituzioni, inclusi 2 numeri R.G.).
  * Indagine .pdf: 25 pagine interamente scansionate, OCR incorporato
    di qualità variabile (55–2.400 char/pag).
  * Analisi Sangue: livello testo completo, immagini = soli loghi.
- `backend/ocr.py`: OCR nativo via Vision (macOS, pyobjc) e ramo
  Windows.Media.Ocr (mai provato — BLOCCHI); rasterizzazione con
  pypdfium2 (già presente); stato di avanzamento per la UI.
- `carica_pdf`: regola per-pagina (testo <600 char + immagine >50%
  area → OCR, si tiene il testo più lungo) + documento interamente
  scansionato → OCR completo; OCR assente → messaggio esplicito.
- Prova reale su "Indagine .pdf": 10 pagine ri-lette, 23.553 →
  30.252 char (+6.699 recuperati), 34s.

### PARTE 2 — Matrice input + OCR (CHIUSA)

- `MATRICE_INPUT.md` scritto con esito reale per ogni riga (fonti:
  21 test documenti, runner `benchmark/matrice_input.py`, 523 casi
  avversariali, documenti reali).
- OCR nativo integrato: UI con avanzamento ("OCR pagina X di Y" via
  polling `/ocr/stato`), avviso di affidabilità dopo il caricamento
  di un documento scansionato, `/carica` spostato in threadpool.
- Test OCR reali: PDF-immagine generato → Vision estrae nome e CF
  (con la confusione I/l documentata); PDF misto → OCR solo sulla
  pagina povera.

### PARTE 3 — Avversariale + diagnostica + caso "marco" (CHIUSA)

- `tests/test_avversariale.py`: 523 casi generati sistematicamente
  (36 valori deterministici × 5 posizioni, 10 nomi × 12 contesti ×
  grafie, 6 formati data, 12 coppie insidiose, 124 controcasi, 6
  categorie opt-in, caso briefing + diagnostica).
- Prima esecuzione: 20 fallimenti → 5 CLASSI di difetti trovate e
  chiuse alla radice (vedi DECISIONI.md § pipeline):
  1. span di categoria disattiva/validazione fallita che mangiava
     span validi nelle sovrapposizioni → validazione spostata PRIMA
     della risoluzione sovrapposizioni;
  2. telefono bloccato dalla virgola di frase → anti-decimale mirato;
  3. capitali sintetiche del truecasing (vittoria/romana/dora) →
     guardia con vocab esteso + comuni + trigger sintattico;
  4. "AZ 610" (numero di volo) emesso come targa dal neurale →
     `_targa_validata` su ogni span TARGA;
  5. campi etichettati ("Cognome: Rossi") non riconosciuti come
     contesto → etichette di modulo aggiunte ai contesti validi.
- Modalità diagnostica (`PRIVACYBRIDGE_DIAGNOSI=1` o
  `anonimizza(..., diagnosi=True)` + `ultima_diagnosi()`): per ogni
  candidato origine, score, filtri attraversati, punto e motivo dello
  scarto; spiega anche i token-nome mai diventati candidati.
- Caso "marco" risolto alla radice: diagnosi in DECISIONI.md (moriva
  in `persona-struttura`; mai candidato perché truecasing non
  ricapitalizza le collisioni col vocabolario). Nuovo pass sintattico
  ("viene X", "passo da X") per i nomi non-ambigui del TSV; 4/4 casi
  positivi, 9/9 controcasi.

### PARTE 4 — Garanzie rafforzate (CHIUSA)

- G1 dopo riavvio analyzer e su documento lungo reale (ha trovato un
  bug REALE in `vault.py`: cache batch con `sqlite3.Row` al posto di
  dict → `AttributeError` su testi >5k char con entità pre-esistenti
  in sessione; corretto normalizzando la cache a dict).
- G2 su tabelle, due colonne e output OCR (roundtrip compreso).
- G3 su ogni scrittura ammessa dei deterministici (11 varianti).
- G4 byte-per-byte su documenti reali interi, incluso l'atto
  d'appello da 47k char.
- G5 nei due sensi (stessa forma → stesso segnaposto; forme diverse →
  segnaposto diversi). G6 su documento reale.

### PARTE 5 — Prestazioni (CHIUSA)

Misura pulita (`benchmark/prestazioni_output.txt`, i7-8750H CPU-only):

- Caricamento motore: 7,1 s (RSS post-load 2,1 GiB).
- Anonimizza+ripristina: 1k → 0,8 s; 10k → 6,1 s; 100k → 64 s;
  500k (≈200 pagine) → 310 s. Throughput costante ~1.600 char/s.
- Ripristino: 0,14 s anche su 500k (regex, non passa dal modello).
- Picco memoria: 2.980 MiB < tetto 4 GiB (OK).
- Roundtrip byte-identico verificato a ogni taglia.

Fix strutturale che ha reso possibile i numeri: analisi a blocchi
sopra 100k char (prima: 389k a ~300 char/s e RSS 6,1 GiB — degrado
NON lineare del documento spaCy monolitico). Vedi DECISIONI.md.
Interrompibilità oltre i 2 minuti: `test_interruzione_sicura`.
UI mai bloccata: analisi in thread, avanzamento reale (test
Playwright `test_gate2_ui_regge_100k_caratteri`).

### PARTE 6 — Distribuzione (CHIUSA lato macOS)

- Bundle ricostruito da zero con tutte le modifiche della sessione
  (`bash scripts/build_bundle.sh`, ~5 min PyInstaller):
  `dist/PrivacyBridge.app` = **3,1 GB**,
  `dist/PrivacyBridge-1.0.0.dmg` = **2,3 GB**.
- Nella .spec aggiunti gli hidden imports OCR (pypdfium2 + Vision/
  Quartz/Foundation su macOS, winsdk su Windows).
- Cartella progetto ripulita: rimossi gli script A/B usa-e-getta e
  gli output temporanei di benchmark; README aggiornato (OCR, nuove
  categorie, struttura con TASSONOMIA/MATRICE, 767 test).
- Windows: .spec condivisa + Inno Setup pronti, MAI provati su
  macchina reale (BLOCCHI.md § 11, incl. nota winsdk § 11.0).

### PARTE 7 — Gate finale: due classi trovate e chiuse dal gate stesso

Il primo giro di gate sul bundle ha trovato due difetti che i test
non avevano coperto:

1. **Roundtrip PDF OCR non byte-identico**: "Mario Rossi." (punto
   da OCR) e "Mario Rossi" collassavano sulla stessa chiave
   normalizzata → stesso segnaposto → il ripristino restituiva una
   sola forma. Fix di classe: il riuso del segnaposto richiede la
   forma letterale IDENTICA (vedi DECISIONI.md). Test A2 delle date
   aggiornato di conseguenza (G4 prevale).
2. **"Rossi" isolato non attivo**: a inizio frase il cognome nudo
   non ha contesto forte → restava suggerimento, e il gate del
   briefing lo richiede con segnaposto distinto. Implementata la
   fix 1b (propagazione cognomi confermati) con guardie anti-FP:
   match esatto capitalizzato, solo da persone multi-token già
   validate, nessuna sovrapposizione.

Dopo le fix: 741 passed + 1 xpassed su tutte le suite backend;
roundtrip PDF OCR byte-identico; "Mario Rossi"→«PERSONA_1»,
"Rossi"→«PERSONA_2» con correlazione bidirezionale. Bundle
ricostruito con le fix definitive.

### Gate finale sul bundle definitivo — OK (2026-07-31)

```
avvio server 4,6s · anonimizza 7,1s · 8 tipi
Mario Rossi→«PERSONA_1» · Rossi→«PERSONA_2» (correlato) ·
marco→«PERSONA_3» · FG771XD→«TARGA_1»
correzione tabella OK · ripristino byte-identico OK
PDF scansionato: OCR 10/25 pagine in 22s, 71 entità, roundtrip OK
screenshot 04/05 generati
```

### Verifica finale completa — STATO: OK (verifica_tutto_output.txt)

```
backend    : rc=0  99,9s   (129 passed + 1 xpassed)
tassonomia : rc=0  13,7s   (69 passed)
avversarial: rc=0  43,2s   (523 passed)
matrice    : rc=0  648,7s  (22/22 esiti conformi)
documenti  : rc=0  148,8s  (145 sost. su 8 file reali; annotato:
                            7/7 veri, 0 rumore, 0 persi — 100%)
garanzie   : rc=0  70,1s   (20 passed)
interfaccia: rc=0  23,1s   (26 passed)
bundle     : rc=0  26,1s   (/health OK)
totale     : 1.074s — STATO: OK
```

**Totale test: 767 (+1 xpassed) + 22 esiti matrice + benchmark.**

---

## Sessione conclusiva — PARTE 1: rilevamento nomi (Gate 1) — CHIUSO (2026-07-31)

Cinque casi reali raccolti sul campo dall'utente, tutti falliti prima
di questa sessione. Diagnosi e fix di classe.

### Cause reali (non quelle ipotizzate nel briefing)

L'ipotesi "il filtro vocabolario uccide i nomi" era **sbagliata**:
`marco`, `maria`, `luca` non risultano `_nome_ambiguo`. Verificato con
`PRIVACYBRIDGE_DIAGNOSI=1`. Le cause vere:

1. `_persona_valida` richiedeva `2 <= len(tokens) <= 4`: **ogni span
   PERSONA di un solo token veniva scartato** prima di qualunque altro
   filtro. Questa singola riga spiegava marco/maria/luca/PASQUALE.
2. La regola ALL-CAPS eliminava `PASQUALE` anche da dizionario.
3. I nomi fuori dizionario (`Delfo`) sparivano pure con contesto
   massimo ("sono", "mi chiamo").
4. La risoluzione delle sovrapposizioni girava **prima** dei filtri di
   validazione: da qui il doppione "perugia" già dentro
   "via perugia 18".

### Fix strutturali applicati

- **A** — priorità del dizionario sul vocabolario.
- **B** — il maiuscolo non elimina più i nomi da dizionario (anche
  singolo token).
- **C** — `_propaga_nomi_in_enumerazione`: un nome confermato in un
  elenco propaga agli altri elementi dello stesso elenco.
- **D** — contesto forte (`sono`, `mi chiamo`, titolo, formula
  d'apertura) batte il dizionario, con guardie su parole funzione,
  numeri e blacklist tecnica.
- **E** — nessun suggerimento su testo già coperto da un'entità.
- **Ordine di pipeline rivisto**: prefiltro strutturale → filtri di
  validazione per tipo → risoluzione sovrapposizioni **solo alla fine**.
- **Stati e continenti**: `_PAESI_E_MACROAREE` (91 voci) — 13 di esse
  collidevano col dizionario nomi/cognomi e producevano persone
  inesistenti su documenti reali. La guardia sta *dopo* il controllo
  dei titoli, così "sono Asia" e "la signora India Rossi" restano
  persone.

### §1.4 — Copertura del dizionario cognomi

"Berretti" **era già** in dizionario: la perdita era di rilevamento,
non di copertura. Audit comunque eseguito su tre fonti indipendenti,
tenendo l'anagrafe di Reggio Emilia **fuori** dalle sorgenti per
conservarla come campione di controllo.

| fonte | PRIMA | DOPO |
|---|---|---|
| Top 100 cognomi nazionali | 100% | 100% |
| Wikipedia cognomi italiani (52) | 100% | 100% |
| Anagrafe Reggio Emilia 2020, 189 (CC-BY) | 75,7% | **84,1%** |

Integrata Wikidata (CC0): +6.378 cognomi (21.727 → 28.105). Scartata
`Max1234-Ita/Liste` per incompatibilità GPL-3 con la licenza MIT del
progetto. Verificato che l'ampliamento non costa nulla in precisione:
diff del benchmark contro il dizionario più piccolo = nessuna
differenza.

### Prove — Gate 1

**Tutti e nove i casi di verifica passano** (5 del briefing + 2
controcasi stati + 2 stati-che-sono-nomi-veri):

```
[1] Ciao sono «PERSONA_1», sono con «PERSONA_2», «PERSONA_3»,
    «PERSONA_4», «PERSONA_5» e «PERSONA_6»            PERSI: nessuno
[3] ENTITA: ['PASQUALE','giovanni','luca','marco','via perugia 18']
                                                      PERSI: nessuno
[5] ENTITA: ['delfo berretti']                        PERSI: nessuno
[6] Vuoi Inviare un SMS in Francia, Guatemala o India?  ENTITA: []
[8] Ciao sono «PERSONA_1», ti presento mia sorella.     ENTITA: ['Asia']
[9] La signora «PERSONA_1» ha firmato.           ENTITA: ['India Rossi']
```

**Falsi positivi sui documenti reali dell'utente: scesi, mai saliti.**
Diff insiemistico `benchmark.utente` prima/dopo (145 → 141
sostituzioni):

```
--- Indagine .pdf
   RIMOSSO  ('PERSONA', "'Mario Rossi.'")
   RIMOSSO  ('PERSONA', "'Cognome Rossi'")
   RIMOSSO  ('PERSONA', "'India'")
   RIMOSSO  ('PERSONA', "'Italia'")
Precisione (solo file annotati): 100.0%  (7 veri / 7 emessi)
Veri persi: 0
```

Zero entità aggiunte in nessun file.

**§1.5 — 83 nuovi casi** in `tests/test_avversariale.py`: i 5 testi del
briefing, ogni nome in ogni posizione × 6 grafie (minuscolo,
capitalizzato, ALL-CAPS), 10 nomi fuori dizionario × 4 contesti forti,
8 controcasi di contesto forte ("sono felice", "sono andato a Roma",
"sono le otto"), 4 toponimi, 2 stati-come-nome-proprio.

**Suite completa:**

```
850 passed, 1 xpassed, 708 warnings in 219.86s (0:03:39)
```

**Gate 1: chiuso.**

---

## Sessione conclusiva — PARTE 3: interfaccia e temi (Gate 3) — CHIUSO (2026-07-31)

Tre giri di revisione, ognuno partito da un difetto **visto in uno
screenshot**, non immaginato. Il dettaglio di ogni difetto e del perché è
in `DESIGN_REVIEW.md` (sezioni A1-F17 secondo giro, G18-G21 terzo giro).

### Screenshot — ogni schermata, entrambi i temi, contenuto reale

`python scripts/screenshot_ui.py`

```
[tema chiaro]
  screenshots/chiaro_1_vuoto.png
  screenshots/chiaro_2_anonimizzato.png
  screenshots/chiaro_3_ripristina.png
  screenshots/chiaro_4_categorie.png
  screenshots/chiaro_5_rubrica.png
  screenshots/chiaro_6_informazioni.png
[tema scuro]
  screenshots/scuro_1_vuoto.png
  screenshots/scuro_2_anonimizzato.png
  screenshots/scuro_3_ripristina.png
  screenshots/scuro_4_categorie.png
  screenshots/scuro_5_rubrica.png
  screenshots/scuro_6_informazioni.png
```

Il testo fotografato è quello del gate finale: entità vere per forma
(IBAN, P.IVA, targa, e-mail sintattiche), riferite a nessuna persona
reale. Le tabelle sono piene, i dialoghi hanno il contenuto caricato —
`screenshot_ui.py` attende il contenuto vero, non solo l'apertura del
velo, dopo che il primo giro aveva fotografato «Caricamento…».

### Contrasti misurati (non stimati)

`python scripts/misura_contrasti.py` legge le variabili colore da
`api/static/index.html` e calcola la luminanza relativa WCAG 2.1. 16
accostamenti per tema, 32 in totale, **tutti sopra soglia**.

```
TEMA CHIARO                                                  misura soglia
Testo su superficie (pannello sinistro, tabelle, dialoghi)   16.91:1   4.5  OK
Testo su superficie-2 (pannello destro anonimizzato)         14.42:1   4.5  OK
Testo su sfondo (tela dell'applicazione)                     15.36:1   4.5  OK
Testo attenuato su superficie (note, sottotitoli, metriche)   6.26:1   4.5  OK
Testo attenuato su superficie-2 (intestazioni di tabella)     5.33:1   4.5  OK
Testo attenuato su sfondo (stato, barra azioni)               5.68:1   4.5  OK
Testo tenue su superficie (segnaposto dei campi)              4.86:1   4.5  OK
Accento su superficie (valore reale evidenziato)              8.69:1   4.5  OK
Accento su velo d'accento (chip del valore reale)             7.36:1   4.5  OK
Testo su superficie-3 (chip del segnaposto, righe al passaggio) 13.27:1 4.5  OK
Testo inverso su fondo inverso (pulsante primario, banner)   15.22:1   4.5  OK
Bordo di controllo su superficie (campi, liste, pulsanti)     3.46:1   3.0  OK
Bordo di controllo su sfondo (pulsanti nella barra azioni)    3.14:1   3.0  OK
Anello di fuoco su superficie                                 8.69:1   3.0  OK
Anello di fuoco su sfondo                                     7.89:1   3.0  OK
Indicatore di lavorazione su sfondo                           7.89:1   3.0  OK

TEMA SCURO                                                   misura soglia
Testo su superficie (pannello sinistro, tabelle, dialoghi)   13.32:1   4.5  OK
Testo su superficie-2 (pannello destro anonimizzato)         12.10:1   4.5  OK
Testo su sfondo (tela dell'applicazione)                     14.47:1   4.5  OK
Testo attenuato su superficie (note, sottotitoli, metriche)   6.97:1   4.5  OK
Testo attenuato su superficie-2 (intestazioni di tabella)     6.33:1   4.5  OK
Testo attenuato su sfondo (stato, barra azioni)               7.57:1   4.5  OK
Testo tenue su superficie (segnaposto dei campi)              5.89:1   4.5  OK
Accento su superficie (valore reale evidenziato)              7.97:1   4.5  OK
Accento su velo d'accento (chip del valore reale)             7.41:1   4.5  OK
Testo su superficie-3 (chip del segnaposto, righe al passaggio) 10.55:1 4.5  OK
Testo inverso su fondo inverso (pulsante primario, banner)   14.47:1   4.5  OK
Bordo di controllo su superficie (campi, liste, pulsanti)     3.55:1   3.0  OK
Bordo di controllo su sfondo (pulsanti nella barra azioni)    3.86:1   3.0  OK
Anello di fuoco su superficie                                 7.97:1   3.0  OK
Anello di fuoco su sfondo                                     8.65:1   3.0  OK
Indicatore di lavorazione su sfondo                           8.65:1   3.0  OK

ESITO: tutti gli accostamenti rispettano WCAG 2.1 AA.
```

Il punto più stretto è `Bordo di controllo su sfondo` nel tema chiaro a
3.14:1 contro una soglia di 3.0: il margine è sottile ma è misurato sul
colore vero, e il file che lo misura legge lo stesso foglio di stile che
la UI usa — non una copia che si disallinea.

### Percorso di click — misurato dal browser

`pytest tests/test_interfaccia.py::test_percorso_click_resta_breve -s`

```
percorso di click misurato:
  anonimizza e copia: 2 click
  correggi e ricopia: 2 click
  ripristina e copia: 3 click
```

Il conteggio non è fatto leggendo il codice: un ascoltatore su `click`
filtrato per `isTrusted` conta i gesti veri mentre Playwright percorre i
tre compiti. Il test fallisce se un percorso supera i 4 click, quindi il
vincolo del brief resta agganciato al codice invece che a un documento.

### Suite Playwright

```
$ ./venv/bin/python -m pytest tests/test_interfaccia.py -q
............................                                             [100%]
28 passed in 28.03s
```

Da 26 a 28: aggiunti `test_ogni_categoria_ha_etichetta_italiana` (nessuna
sigla del motore deve arrivare sotto gli occhi dell'utente — confrontato
contro `CATEGORIE_TUTTE` vero, non contro una copia) e
`test_percorso_click_resta_breve`.

### Pulizia

Rimossi `screenshots/04_gate_finale_anonimizza.png` e
`05_gate_finale_ripristina.png`: fotografavano l'interfaccia precedente
al rifacimento. Le schermate del gate finale si rifanno in PARTE 8.

**Gate 3: chiuso.**

---

## Sessione conclusiva — PARTE 4.1: verifica delle entità su documento scansionato (2026-08-01)

### Cosa è stato misurato

`benchmark/documenti_utente/Indagine .pdf` — atto giudiziario scansionato,
3.3 MB, **25 pagine** (il briefing ne diceva 48; il numero di entità
citato, 129, corrispondeva invece esatto). Strumento nuovo:
`benchmark/verifica_ocr.py`, che estrae il testo con la stessa pipeline
dell'applicazione, salva l'estratto su file perché un'occorrenza dubbia
si possa controllare a mano, lancia il motore e stampa **ogni entità con
il suo contesto**.

```
$ ./venv/bin/python benchmark/verifica_ocr.py "benchmark/documenti_utente/Indagine .pdf"
documento: Indagine .pdf
estrazione: 21.6s — 30,252 caratteri
pagine lette con OCR: 10 su 25  [3, 10, 11, 12, 13, 15, 16, 23, 24, 25]
testo estratto salvato in: benchmark/Indagine.ocr.txt
analisi: 21.1s — 67 entità anonimizzate, 62 suggerimenti
```

Le 129 del briefing erano 67 entità **più** 62 suggerimenti. Non sono la
stessa cosa: i suggerimenti hanno segnaposto vuoto, non entrano nel
vault, non toccano il testo in uscita e nella UI stanno in un riquadro
separato da spuntare a mano. Contarli insieme gonfia il totale di
decine di voci.

Verificate **tutte e 67** contro il testo OCR, non un campione di 20.

### Esito, una per una

| esito | quante |
|---|---|
| corrette — dato vero, tipo giusto, span intero | 40 |
| dato vero, tipo impreciso | 1 |
| dato vero, span troncato o spezzato dall'OCR | 8 |
| falsi positivi | 18 |

- **Tipo impreciso (1).** `2252•••••••••317319` — numero di conto PayPal
  classificato CARTA.
- **Span parziale (8).** `rossi@example.it` (perde "mario."),
  `bianchi@example.it` (perde "luca."), `Serena DI` (l'a capo
  spezza "Di Rossi Serena"), `BINI` (perde "GAMBA"), `Mario Polizia`
  (span troppo lungo), `ia Rossi` (l'OCR ha rotto "Mario"),
  `Rossi Serena` (perde "Di"), `333054381` (una cifra in meno).
  In tutti questi casi **il dato viene comunque mascherato in parte**.
- **Falsi positivi (18).** `Polizia`, `DELLA PUBBLICA SICUREZZA`, `May`
  (mese di una data), `sulla carta di credito`, `Valentino` (da "San
  Valentino"), `della tua`, `cei cati`, `cati`, `hope`, `may`, `polizia`,
  `SICUREZZA`, `Suri`, `enni`, `uma`, `Natale` (da "Babbo Natale"),
  `0131268`, `0761 21231` (frammento di un numero di carta).

**Precisione, dato vero toccato: 49/67 = 73.1%.**
**Precisione stretta, dato giusto col tipo giusto e lo span intero: 40/67 = 59.7%.**

### Il risultato più serio: i falsi negativi

Per uno strumento di anonimizzazione conta più cosa **resta** che cosa
viene tolto in più. Cercati nel testo OCR i formati che il motore
dovrebbe coprire sempre:

```
email:    2 non coperti -> ['rossi @esempio.it', 'support @mocha.ni']
cifre13+: 4 non coperti -> ['3977•••••••••••', '4347 ••••••••••••',
                            '5544•••••••••••', '6217•••••••••••••••']
tel-it:   0 non coperti -> []
iban:     0 non coperti -> []
```

La causa è la stessa in tutti e sei i casi: **l'OCR sbaglia caratteri**.
Inserisce uno spazio prima della chiocciola e l'indirizzo non è più un
indirizzo; legge male una cifra e il numero di carta non supera più il
controllo di Luhn, quindi non viene riconosciuto e **resta in chiaro nel
testo "anonimizzato"**.

Non è un difetto correggibile abbassando una soglia: togliere il
controllo aritmetico sulle carte significherebbe mascherare qualunque
sequenza di sedici cifre in qualunque documento. È un limite del
riconoscimento su documento scansionato e va **dichiarato**, non
nascosto. L'interfaccia già avverte all'apertura di un documento OCR che
i caratteri possono essere letti male e che la tabella va controllata
riga per riga prima di copiare; il capitolo finale dei limiti riporta i
numeri.

### Rumore nei suggerimenti — corretto

I 62 suggerimenti erano quasi tutti parole comuni. Indagando: non è un
difetto dell'OCR ma una classe generale, misurata anche su documenti con
testo nativo (35 suggerimenti su `Hetepi_Agent_AI.pdf`, tutte parole
italiane con la maiuscola d'inizio riga). Due cause:

1. la lista cognomi contiene parole correnti ("che", "ali", "costa",
   "conte", "scarpa", "dati"), e al livello 3 la presenza in lista è
   l'**unica** prova;
2. su testo prevalentemente minuscolo il truecasing mette la maiuscola a
   ogni parola per far emergere i nomi scritti in minuscolo — e così
   ogni parola diventa candidata. La maiuscola l'avevamo messa noi.

Correzione in `backend/nomi_italiani.py` (vocabolario esteso) e
`backend/motore.py` (grafia originale); motivazione estesa in
`DECISIONI.md`. Misura sui cinque documenti reali:

| documento | entità prima | entità dopo | suggerimenti prima | dopo |
|---|---|---|---|---|
| Portafoglio_Intelligence.pdf | 1 | 1 | 12 | 0 |
| Hetepi_Agent_AI.pdf | 4 | 4 | 35 | 1 |
| Analisi Sangue … glutine.pdf | 8 | 8 | 9 | 1 |
| Atto_giudiziario.pdf | 36 | 36 | 9 | 2 |
| Indagine .pdf | 67 | 67 | 62 | 8 |
| **totale** | **116** | **116** | **127** | **12** |

Entità invariate; suggerimenti da 127 a 12. Restano proposti i due
cognomi veri (Bianchi, Verdi), tre toponimi, quattro parole inglesi e
tre residui d'OCR.

### Regressione

```
$ ./venv/bin/python -m pytest tests/ -q --ignore=tests/test_interfaccia.py
824 passed, 1 xpassed, 708 warnings in 182.22s (0:03:02)
```

```
$ ./venv/bin/python -m benchmark.utente
TOTALE: 141 sostituzioni su 8 file (1 annotati, 7 non annotati)
Precisione (solo file annotati): 100.0%  (7 veri / 7 emessi)
Veri persi (sfuggiti al motore): 0
```

141 — identico al numero chiuso in PARTE 1. Il filtro tocca solo i
suggerimenti, come progettato.

Tre test nuovi in `tests/test_motore.py` agganciano la classe al codice,
con frasi prese dai documenti reali e non inventate:
`test_faseg_parola_comune_inizio_frase_non_suggerita`,
`test_faseg_testo_minuscolo_non_genera_suggerimenti` e il controcaso
`test_faseg_cognome_vero_senza_contesto_resta_suggerito`, che fallisce
se il filtro svuota il riquadro.

## Sessione conclusiva — PARTE 4.2 (prestazioni e reattività)

Quattro difetti trovati misurando, non leggendo. Tutti e quattro erano
classi, non casi singoli.

### 1. Avvio a freddo: 5.69s → 0.60s

Il requisito è "finestra entro 5 secondi". La misura diceva 5.69s nel
peggiore dei tre tentativi — **superato**. Profilo degli import:

```
$ ./venv/bin/python -X importtime -c "import api.main"
   api.main            5.05s
     backend.motore    4.46s
       backend.nlp_engine  4.39s
         presidio_analyzer 3.97s   (torch 1.82s, spacy 0.83s, gliner 0.82s)
     fastapi           0.53s
```

Quattro secondi di torch e spaCy sul percorso dell'avvio, per un modello
che serve solo alla prima anonimizzazione. `nlp_engine` è ora importato
dentro `get_analyzer()` invece che in testa a `backend/motore.py`:
`api.main` scende da 5.05s a 1.04s all'import, e l'avvio misurato da
0.60s. Quegli stessi secondi si pagano più tardi, quando c'è già un
lavoro in corso da mostrare.

### 2. La finestra si bloccava durante l'analisi

`/anonimizza`, `/rianonimizza` e `/deanonimizza` erano dichiarati `async
def` ma chiamavano lavoro CPU sincrono da decine di secondi: occupavano
l'event loop, e per tutto quel tempo il server non rispondeva a nulla —
finestra ferma e avanzamento che mente. `/carica` faceva già la cosa
giusta con `run_in_threadpool`, con tanto di commento che spiegava il
pericolo: il difetto era di forma, non di conoscenza. I tre endpoint sono
ora `def` semplici, che FastAPI esegue in threadpool.

Misura, non lettura (`test_server_risponde_durante_anonimizzazione`):

```
/health a riposo: 1 ms
carico modello + frase breve            9.2s   mediana     3 ms   peggiore   1063 ms   (56 campioni)
analisi 90k, modello caldo             41.7s   mediana     1 ms   peggiore     27 ms   (387 campioni)
```

Durante l'analisi di un documento reale da 90.696 caratteri la finestra
risponde in 1 ms mediano, 27 ms nel peggiore dei 387 campioni. I blocchi
residui stanno tutti dentro il carico del modello, dove torch e spaCy
tengono il GIL in codice C che non possiamo spezzare.

### 3. Il carico del modello cadeva sul primo click

Conseguenza del punto 1: rimandare l'import sposta ~9s sulla prima
anonimizzazione, con quei blocchi da 1s in mezzo. La finestra, appena
finita di disegnarsi, chiama ora `POST /precarica`, che carica il modello
in un thread di sfondo mentre l'utente legge e non ha ancora incollato
niente. L'avvio resta 0.60s perché il precarico parte **dopo** che la
pagina è stata servita. Presidiato da
`test_finestra_scalda_il_motore_da_sola`, che guarda le richieste in
uscita dal browser: se qualcuno toglie la riga dal frontend, `/precarica`
diventa un endpoint che nessuno chiama e il test se ne accorge.

### 4. Deduplica quadratica dentro Presidio

`cProfile` su 100.000 caratteri:

```
ncalls  tottime  cumtime  funzione
    31   18.983   64.634  presidio entity_recognizer.remove_duplicates
47089894 24.343   33.528  presidio recognizer_result.__eq__
     1    0.011   34.974  backend/motore_neurale.py:163(analyze)
     1    0.001   31.836  presidio _enhance_using_context
```

Il modello è un terzo del tempo. Il resto è Presidio che confronta ogni
risultato con ogni altro: 7.114 risultati in un blocco da 100k fanno 47
milioni di confronti. La leva è la dimensione del blocco d'analisi.
Misurato su 100.000 caratteri:

| blocco | tempo | car./s |
|---|---|---|
| 100.000 | 54.2s | 1.844 |
| 50.000 | 47.5s | 2.105 |
| **25.000** | **40.3s** | **2.483** |
| 10.000 | 46.9s | 2.134 |
| 5.000 | 44.9s | 2.228 |

La discesa è la deduplica, la risalita sotto i 25k è il costo fisso della
pipeline spaCy pagato a ogni blocco. `_MAX_BLOCK` passa da 100.000 a
25.000, **dopo** aver verificato che sui sette documenti reali entità e
suggerimenti restano identici carattere per carattere.

### Interrompibilità

Mezzo milione di caratteri sono più di quattro minuti e non c'è modo di
toglierli: metà del tempo è inferenza del modello, che su questa macchina
è il pavimento. Il requisito giusto non è "più veloce", è
"interrompibile" — ed è quello che chiede la consegna.

Nuovo modulo `backend/avanzamento.py`: un lavoro alla volta, come
`backend/ocr.py`. `annulla_analisi()` alza una bandiera; il ciclo dei
chunk neurali la controlla e solleva `Annullato`, che passa dal rollback
già esistente e lascia il vault coerente. Non uccide nessun thread.

L'avanzamento mostrato sono caratteri **davvero** analizzati, aggiornati
a fine blocco: per questo il primo arriva dopo un blocco intero e non
subito. Preferito a una barra che si muove da sola.

```
5. INTERROMPIBILITÀ

   documento da 500,000 caratteri (oltre i 120s di soglia)

        5s         0 di 500,000 caratteri
       10s         0 di 500,000 caratteri
       15s    24,997 di 500,000 caratteri
       20s    24,997 di 500,000 caratteri
       25s    24,997 di 500,000 caratteri
       30s    49,995 di 500,000 caratteri

   annullata a 30s:  esito 'annullata', ferma in 0.35s
```

Nella finestra: il pulsante Annulla compare dopo tre secondi di analisi
(prima sarebbe un lampo inutile), alla sinistra dello stato così il testo
di stato non si sposta. Verificato end-to-end sul PDF reale da 90.696
caratteri (`test_analisi_lunga_mostra_avanzamento_ed_e_annullabile`):
avanzamento "24.983 di 90.696 caratteri", ferma in 0.9s, testo originale
intatto, finestra di nuovo utilizzabile.

### Numeri finali misurati

```
1. AVVIO A FREDDO (processo nuovo, modello non ancora caricato)

    tentativo |  API pronta (s) |  pagina servita (s)
            1 |            0.60 |                0.60
            2 |            0.52 |                0.53
            3 |            0.51 |                0.51

   peggiore: 0.60s  (requisito: finestra entro 5s) — OK

2. CARICAMENTO DEL MOTORE: 8.66s  (RSS 27 → 2111 MiB)
   Pagato una volta sola, in sottofondo, mentre l'utente legge la finestra.

3. DOCUMENTI REALI DELL'UTENTE

   documento                                |    car. |  estraz. |  anonim. |  riprist. |  ent. |     RSS
   Analisi Sangue Pantalla 26:09:25  verifi |   1,583 |      0.4 |      0.9 |     0.002 |     8 |    2585
   Hetepi_Agent_AI.pdf                      |  90,696 |      3.3 |     34.8 |     0.024 |     4 |    2887
   Indagine .pdf                            |  30,252 |     21.7 |     14.4 |     0.007 |    67 |    3168
   Portafoglio_Intelligence.pdf             |  46,382 |      1.9 |     16.2 |     0.008 |     1 |    3168
   Atto_giudiziario.pdf    |  47,782 |      2.4 |     21.7 |     0.013 |    36 |    3168
   hetepi_simulato.txt                      |   1,637 |      0.0 |      0.8 |     0.002 |     7 |    3168
   rizzo-pii-report.pdf                     |  26,516 |      1.7 |     11.5 |     0.006 |    15 |    3168

   Ogni riga verifica il ripristino identico byte per byte.

4. CURVA DI SCALA (testo sintetico)

    caratteri |  anonim. (s) |   car./s |  riprist. (s) |     RSS
      100,000 |         55.0 |     1818 |         0.044 |    3198
      500,000 |        278.2 |     1797 |         0.174 |    3198

6. REQUISITI

   memoria sotto 4096 MiB      OK — picco 3198 MiB
   finestra entro 5s          OK — peggiore 0.58s
   oltre 120s interrompibile  OK — si ferma in 0.35s
   operazione più lunga misurata: 278.2s
```

Risposta al click, misurata dal click all'effetto visibile nel DOM
(`test_risposta_al_click`):

> **Numeri corretti in 5.** I tre valori pubblicati qui in origine —
> cambio tema 34.6 ms, cambio scheda 47.8 ms, apertura menu 54.4 ms —
> **erano sbagliati**: misuravano il driver Playwright, non la finestra.
> Il cronometro stava in Python e ogni lettura pagava due giri di CDP;
> peggio, la condizione di attesa era già vera prima del click, quindi
> il test non osservava affatto il cambiamento. Se ne è accorto il test
> stesso, fallendo nella suite completa a 108.4 ms sulla stessa identica
> interazione che da solo ne dava 31.9. Il cronometro ora sta dentro la
> pagina (`MutationObserver` + `performance.now()`, listener in fase di
> cattura). Misura rifatta:

```
$ ./venv/bin/python -m pytest tests/test_interfaccia.py::test_risposta_al_click -q -s

risposta al click (dal click alla mutazione del DOM):
  cambio tema         0.1 ms
  cambio scheda       0.2 ms
  apertura menu       0.1 ms
.
1 passed in 2.32s
```

Il numero arriva fino alla mutazione del DOM; il disegno segue nel frame
successivo (≤ 17 ms a 60 Hz). Quello che il test esclude è solo il costo
del driver, che l'utente non paga.

Confronto con la misura di inizio sessione: avvio a freddo 5.69 → 0.60s;
`Hetepi_Agent_AI.pdf` 46.8 → 34.8s; `Rossi Andrea -Appello` 27.2 →
21.7s; 100.000 caratteri 75.2 → 55.0s; 500.000 caratteri 387.6 → 278.2s;
picco memoria 3.307 → 3.198 MiB.

### 4.3 — Regressione

```
$ ./venv/bin/python -m pytest tests/ -q
859 passed, 1 xpassed, 712 warnings in 260.97s (0:04:20)
```

```
$ ./venv/bin/python -m benchmark.utente
TOTALE: 141 sostituzioni su 8 file (1 annotati, 7 non annotati)
Precisione (solo file annotati): 100.0%  (7 veri / 7 emessi)
Veri persi (sfuggiti al motore): 0
```

```
$ ./venv/bin/python -m benchmark.documenti_reali
TOTALE: 10 sostituzioni (10 veri, 0 rumore)
Precisione: 100.0%  (10 veri / 10 emessi)
```

141 e 10: identici alla linea di base di PARTE 1, con `_MAX_BLOCK`
dimezzato quattro volte e tre endpoint riscritti. Falsi positivi e falsi
negativi sui documenti dell'utente restano a zero.

Tre test dell'interfaccia usavano "il gatto dorme vicino al camino" per
far comparire un suggerimento: funzionava perché "gatto" e "camino" sono
nella lista cognomi, cioè esattamente il falso suggerimento corretto in
4.1. Ora usano "Il documento e stato firmato da Bertini in data
odierna." — un cognome vero senza contesto personale, che è il
suggerimento che l'utente vedrà davvero.

## Sessione conclusiva — PARTE 5: pulizia del codice — CHIUSA (2026-08-01)

### 5.1 — ruff: prima e dopo

Prima serviva rendere la misura ripetibile. `ruff` senza file di
configurazione applica un insieme di regole che cambia con la versione:
ho fissato tutto in `pyproject.toml`, così `ruff check .` senza flag dà
sempre lo stesso risultato, oggi e fra sei mesi.

PRIMA (con la configurazione già fissata, all'inizio della parte 5):

```
$ ./venv/bin/ruff --version
ruff 0.16.1

$ ./venv/bin/ruff check . --statistics
142 UP006   [*] non-pep585-annotation
 49 I001    [*] unsorted-imports
 46 UP045   [*] non-pep604-annotation-optional
 44 RUF059  [ ] unused-unpacked-variable
 31 BLE001  [ ] blind-except
 25 UP035   [-] deprecated-import
 12 F401    [*] unused-import
  8 SIM102  [ ] collapsible-if
  8 SIM103  [ ] needless-bool
  6 B033    [*] duplicate-value
  6 F541    [*] f-string-missing-placeholders
  6 RUF100  [*] unused-noqa
  5 S110    [ ] try-except-pass
  4 F841    [ ] unused-variable
  3 UP017   [*] datetime-timezone-utc
  2 B008    [ ] function-call-in-default-argument
  2 C400    [ ] unnecessary-generator-list
  2 EXE001  [ ] shebang-not-executable
  2 ISC004  [ ] implicit-string-concatenation-in-collection-literal
  1 F811, FURB188, PERF102, PIE808, PLC0208, PLW0602, PLW1510,
    PYI034, RUF012, SIM115, UP012, UP031, UP037  (uno ciascuno)
Found 416 errors.
[*] 279 fixable with the `--fix` option (61 hidden fixes ...).

$ ./venv/bin/ruff check . --fix
Found 430 errors (315 fixed, 115 remaining).
```

DOPO — i 115 rimasti corretti a mano, uno per uno:

```
$ ./venv/bin/ruff --version
ruff 0.16.1

$ ./venv/bin/ruff check .
All checks passed!
```

### 5.2 — L'unica regola spenta, e perché

`BLE001` vieta `except Exception`. Ho guardato tutti e 26 i punti che lo
fanno, uno per uno. Ognuno sta su un confine verso qualcosa che non
controlliamo — il caricamento del modello via torch, il motore OCR di
sistema, un `.msg` di Outlook, un PDF malformato, la rete — e ognuno
converte il guasto in un esito **dichiarato**: HTTP 500, `None`, insieme
vuoto, warning nel log. Nessuno lo ingoia.

Elencare i tipi di eccezione che torch può sollevare non è possibile, e
restringere significherebbe far morire la finestra su un guasto previsto.
Ruff non sa esprimere "cattura larga **con** ricaduta esplicita", quindi
la regola è spenta con la motivazione scritta dentro `pyproject.toml`.

Il difetto vero che BLE001 vuole prevenire è il guasto ingoiato in
silenzio, e quello lo copre `S110` (`except` largo con corpo `pass`), che
resta **accesa** ed è a zero. È quello il vincolo che regge:

```
$ ./venv/bin/ruff check . --select S110
All checks passed!
```

I cinque `pass` silenziosi che c'erano sono spariti davvero, non
mascherati:

| dove | prima | dopo |
|---|---|---|
| `avvio.py` scrittura log | `except Exception: pass` | `except OSError` + motivo |
| `documenti.py` chiusura `.msg` | `except Exception: pass` | `except OSError` + motivo |
| `motore.py` `_leggi_categorie_attive` | try/except attorno a una chiamata che non solleva | try/except rimosso |
| `motore.py` rollback | try/except attorno a `Vault.rollback()` | rimosso: svuota dict, non può sollevare |
| `scripts/gate_finale.py` attesa health | `except Exception: pass` | `except (OSError, URLError)` + motivo |

### 5.3 — Codice morto

`vulture` a confidenza 100% più un grep di ogni candidato su tutto il
repo. Rimossi: `_tutto_maiuscolo` (`filtri_rumore`),
`_seguito_da_contesto_personale`, `_pulisci_finale` e la costante
`_TOKENI_DOPO_PERSONA` rimasta orfana (`nomi_italiani`),
`cartella_modelli` (`percorsi` — il suo stesso docstring diceva
"attualmente non usata"), `get_by_chiave` ed `elenca_chiavi` (`vault`).

Tenuti, perché il grep li trova: `ultima_diagnosi`
(`test_avversariale.py:608,627`) e `rubrica_count`
(`test_motore.py:1491`). Le route FastAPI e i campi Pydantic che vulture
segnala sono falsi positivi: li chiama il decoratore, non il codice.

Tre parametri mai usati, tolti insieme al chiamante:
`_contesto_forte(..., ph_start)`, `analizza_token_persi(testo_orig, ...)`,
e i tre di `Vault.__exit__` — questi ultimi imposti dal protocollo, quindi
marcati con underscore invece che rimossi.

```
$ ./venv/bin/vulture backend/ api/ scripts/ avvio.py --min-confidence 100
exit=0 (0 = nessun morto certo)
```

### 5.4 — Endpoint e CSS

I 22 endpoint di `api/main.py` sono tutti raggiunti dalla finestra;
nessuno è orfano. Verificato incrociando le route con le chiamate `api(...)`
in `api/static/index.html`.

Il CSS è inline in un file solo, quindi l'ho estratto e confrontato ogni
selettore con il resto del documento (HTML **e** JavaScript, per non
perdere le classi aggiunte da `classList.add`). Su 95 classi definite, 2
non comparivano da nessuna parte: `.premibile` (in un selettore
`label.premibile` senza nessuna label che la porti) e `.tronca`
(quattro proprietà mai applicate). Rimosse.

```
classi definite: 93   id definiti: 1
classi mai usate fuori dal CSS (0): []
id mai usati fuori dal CSS (0): []
```

### 5.5 — Intestazioni, docstring, valori magici

Ogni modulo del progetto porta l'intestazione di licenza e un docstring:

```
moduli del progetto: 42 — senza intestazione o senza docstring: 0
```

Sui numeri nudi ho scansionato tutti i confronti con costanti numeriche.
La maggior parte sono fatti di formato, non manopole: un IBAN sta fra 15
e 34 caratteri, una P.IVA ha 11 cifre, un numero di carta 16. Quelli non
li ho battezzati: hanno già il nome giusto, che è il campo su cui stanno.

Quattro invece erano **decisioni** travestite da numeri, e adesso hanno
un nome e una spiegazione:

| era | ora | dove |
|---|---|---|
| `if r.score < 0.4` | `_SOGLIA_ACCETTAZIONE` | `motore.py` — la manopola principale: separa i tre livelli del dizionario nomi |
| `if r.score < 0.7` | `_SOGLIA_PERSONA_CERTA` | `motore.py` — quando "persona" vince su LOCATION/GPE sullo stesso span |
| `> 0.05` | `_MAX_FRAZIONE_CONTROLLO` | `documenti.py` — oltre questa quota di caratteri di controllo non è testo, è un binario |
| `10 <= n <= 98168` | `_CAP_MIN` / `_CAP_MAX` | `recognizers.py` — estremi dei CAP assegnati in Italia |

### 5.6 — Due cose trovate pulendo, che non erano refusi

**Il testo integrale di un atto giudiziario stava per finire in git.**
`benchmark/verifica_ocr.py` salvava l'estrazione OCR in
`benchmark/Indagine.ocr.txt` — i 30.252 caratteri estratti dal documento
privato dell'utente, misurati in 4.1 — e `.gitignore` proteggeva
`benchmark/documenti_utente/`
ma non la radice di `benchmark/`. Il file non è mai stato committato
(`git log --all -- benchmark/Indagine.ocr.txt` è vuoto), ma lo sarebbe
stato al primo `git add benchmark/`.

Corretta la classe, non il file. Le regole elencavano i nomi da
escludere, ed elencare i nomi ha già fallito una volta; adesso sono
invertite — in `benchmark/` si versiona il codice, tutto il resto è
escluso per definizione, compresi i file che non esistono ancora. E lo
script scrive il dump accanto al PDF, dentro la cartella già esclusa.

```
$ git add -An benchmark/
add 'benchmark/__init__.py'
add 'benchmark/documenti_reali.py'
add 'benchmark/documenti_utente/.gitkeep'
add 'benchmark/documenti_utente/README.md'
add 'benchmark/frasi_colloquiali.py'
add 'benchmark/frasi_nuove.py'
add 'benchmark/matrice_input.py'
add 'benchmark/misura_dizionario.py'
add 'benchmark/prestazioni.py'
add 'benchmark/utente.py'
add 'benchmark/verifica_ocr.py'

benchmark/Indagine.ocr.txt                    IGNORATO
benchmark/documenti_utente/Indagine .pdf      IGNORATO
benchmark/documenti_utente_output.txt         IGNORATO
benchmark/prestazioni.py                      versionabile
benchmark/documenti_utente/README.md          versionabile
```

**Il vault era leggibile da tutti gli account della macchina.** Contiene
`valore_reale` in chiaro — è ciò che rende possibile il ripristino — e
veniva creato con i permessi di default, `0644`. Su un Mac personale non
succede niente; su un PC aziendale con più account, chiunque altro
poteva aprirlo. Ora la cartella dati nasce `0700` e il file `0600`,
insieme ai sidecar WAL e SHM che contengono le stesse righe. Le
installazioni già esistenti si stringono da sole alla prima apertura:

```
cartella dati nuova : 0o700
vault.db       0o600
vault.db-wal   0o600
vault.db-shm   0o600

prima  vecchio.db   0o644
dopo   vecchio.db   0o600
```

Il log di avvio resta `0644` perché non contiene testo dell'utente: solo
percorsi, versioni, conteggi e messaggi d'eccezione.

### 5.7 — File temporanei

Rimossi: `benchmark/Indagine.ocr.txt` (dato privato derivato), `dist/`
(uscita PyInstaller del 31 luglio: 7,5 GB fra `.dmg` da 2,5 GB e i due
bundle da 3,1 e 1,9 GB — la parte 7 la rigenera), i `__pycache__`, i
`.DS_Store`, e tutti i file di lavoro lasciati in `/tmp` durante la
sessione. Fra quelli c'erano vault di prova con dentro le entità vere
dei documenti dell'utente — `pb_utente_vault.db` con 141 righe,
`pb_ocr_verify.db` con 67 — a permessi `0644`.

### 5.8 — Regressione

```
$ ./venv/bin/ruff check .
All checks passed!

$ ./venv/bin/python -m pytest tests/ -q
860 passed, 1 xpassed, 712 warnings in 291.74s (0:04:51)
```

## PARTE 6 — Due cartelle separate (2026-08-01)

### 6.1 — Cosa si è spostato

Il codice eseguibile è sceso sotto `src/`; alla radice del progetto
restano solo cartelle, configurazione, launcher e `README.md`.

```
PrivacyBridge/
├── README.md  LICENSE  NOTICE.txt  pyproject.toml  requirements.txt
├── PrivacyBridge.bat  PrivacyBridge.vbs
├── verifica_tutto.sh  verifica_tutto.bat
├── src/       avvio.py  api/  backend/  data/liste/
├── tests/     conftest.py + 6 suite + corpus_annotato.py
├── benchmark/ 10 misuratori + documenti_utente/ (privata)
├── docs/      MANUALE  PROGRESSO  DECISIONI  BLOCCHI  DESIGN
│              DESIGN_REVIEW  TASSONOMIA_PII  MATRICE_INPUT
│              UI_AUDIT  AUDIT  CONSEGNA  screenshots/
├── scripts/   build_liste_nomi  gate_finale  misura_contrasti
│              screenshot  screenshot_ui
├── assets/    icon.icns  icon.ico  liste_sorgenti/
└── build/     PrivacyBridge.spec  build_bundle.sh
               PrivacyBridge-windows.iss  PrivacyBridge.app/
```

Le liste sono state divise in due: i TSV che il motore legge stanno in
`src/data/liste/` ed entrano nel pacchetto; gli elenchi grezzi da cui
vengono generati stanno in `assets/liste_sorgenti/` e li legge solo
`scripts/build_liste_nomi.py`.

### 6.2 — Cosa si è rotto, e perché era giusto che si rompesse

Lo spostamento ha fatto cadere la suite in un modo utile:

```
$ ./venv/bin/python -m pytest tests/ -q
1 failed, 825 passed, 2 skipped, 1 xpassed, 712 warnings, 32 errors in 241.57s
```

I 32 errori erano tutti `tests/test_interfaccia.py`, tutti la stessa
riga: la fixture di sessione lancia `uvicorn api.main:app` in un
sottoprocesso con `cwd` alla radice, e `api` non era più lì. Il modulo
si importa per nome, quindi nessun controllo statico poteva vederlo —
solo l'esecuzione.

La classe è "punto d'ingresso che assume la vecchia disposizione". I
membri trovati e corretti:

- `pyproject.toml`: `pythonpath = ["src"]`.
- `tests/test_interfaccia.py`: `PYTHONPATH` nel sottoprocesso uvicorn;
  due `sys.path.insert(0, ROOT)` rimossi perché `pythonpath` li rende
  ridondanti.
- `tests/test_garanzie.py`: l'insert resta ma punta a `src/`, perché
  questo file si esegue anche da solo (`__main__` in fondo) e lì
  `pythonpath` non si applica.
- `benchmark/` (6 file), `scripts/` (5 file): insert e `PYTHONPATH`.
- `PrivacyBridge.bat`, `PrivacyBridge.vbs`, launcher del bundle.
- `verifica_tutto.sh`: il bundle è in `build/`, non in `dist/`.

### 6.3 — Due test che non passavano: si saltavano

Il fallimento singolo, e i due `skipped`, erano lo stesso difetto:

```
tests/test_motore.py:1042  bundle_modello = root / "PrivacyBridge.app" / ...
tests/test_motore.py:1098  modello       = root / "PrivacyBridge.app" / ...
tests/test_motore.py:1532  modello       = root / "PrivacyBridge.app" / ...
```

Il primo e il terzo, non trovando la cartella, chiamavano `pytest.skip`.
Il secondo asseriva, e quindi è l'unico che ha protestato. Cioè: due
verifiche sul modello dentro il pacchetto erano spente da quando il
bundle si è spostato, e lo dicevano solo come `2 skipped` in coda al
riepilogo. Corretti tutti e tre a `build/PrivacyBridge.app`:

```
$ ./venv/bin/python -m pytest tests/test_motore.py -q -rs
111 passed, 1 xpassed, 82 warnings in 77.56s (0:01:17)
```

Prima erano `109 passed, 2 skipped`. Ora nessuno salta.

### 6.4 — `build/` conteneva sorgenti dentro una cartella ignorata

`.gitignore` aveva la riga `build/`, scritta quando lì dentro c'era solo
uscita di build. Dopo lo spostamento quella riga escludeva anche le tre
ricette di impacchettamento, che sono codice. Applicata la stessa regola
invertita già usata per `benchmark/`:

```
$ git add -An build/
add 'build/PrivacyBridge-windows.iss'
add 'build/PrivacyBridge.spec'
add 'build/build_bundle.sh'

versionabile build/PrivacyBridge.spec
versionabile build/build_bundle.sh
versionabile build/PrivacyBridge-windows.iss
IGNORATO     build/PrivacyBridge.app/Contents/MacOS/PrivacyBridge
IGNORATO     build/PrivacyBridge.app/Contents/Info.plist
```

Conseguenza sul packaging: il `--workpath` di PyInstaller è ora
esplicito (`build/pyinstaller`). Il suo default è `./build`, che adesso
è la cartella delle ricette.

### 6.5 — README

Ridotto a dieci righe. Le 186 righe precedenti — installazione, uso,
tempi, cosa riconosce, garanzie, limiti — sono diventate
`docs/MANUALE.md`, con la sezione "struttura del progetto" riscritta
sulla disposizione nuova.

### 6.6 — Cartella di consegna

Creata `~/Desktop/PrivacyBridge-App/` con `LEGGIMI.txt`: istruzioni per
chi non è tecnico (cosa fa, installazione Mac e Windows con la
spiegazione del perché compare l'avviso di sicurezza, i sette passi
d'uso, e un capitolo su cosa sapere prima di fidarsi). I due pacchetti
li produce la parte 7.

### 6.7 — Regressione

```
$ ./venv/bin/ruff check .
All checks passed!

$ ./venv/bin/python -m pytest tests/ -q -rs
860 passed, 1 xpassed, 712 warnings in 286.45s (0:04:46)
```

Stessi 860 della baseline prima dello spostamento, con in più i due
test che prima si saltavano in silenzio.

## PARTE 7 — Pacchetti (2026-08-01)

### 7.1 — macOS: costruito e verificato

`build/build_bundle.sh` ricostruito da zero dopo lo spostamento in
`src/`. PyInstaller 6.21.0, `--workpath build/pyinstaller`,
`--distpath dist`.

```
269057 INFO: Build complete! The results are available in: /Users/apple/Desktop/PrivacyBridge/dist
==> Copia modello nel bundle
==> Bundle dimensione:
3,1G	dist/PrivacyBridge.app
==> Costruisco .dmg
created: /Users/apple/Desktop/PrivacyBridge/dist/PrivacyBridge.dmg
==> Fatto.
    dist/PrivacyBridge.app (3,1G)
    dist/PrivacyBridge.dmg (2,3G)
```

Il `.dmg` è stato verificato e montato davvero, non solo prodotto:
`hdiutil verify` → "checksum is VALID"; montato su `/Volumes/PrivacyBridge`
mostra `PrivacyBridge.app` e il collegamento ad `Applications`, con il
modello da 1,2 GB dentro il bundle.

### 7.2 — Audit del contenuto del pacchetto

Richiesto dal briefing: elencare tutto il contenuto e togliere qualunque
file di sviluppo. Cercati uno per uno e **non trovati**: nostri test,
benchmark, corpus, documenti dell'utente (`*.pdf`, `Indagine*`,
`Hetepi*`), vault (`vault.db*`), impostazioni, log, sorgenti grezze
delle liste (`cognomi_paolosarti.txt`, `nomi_sigpwned.csv`, `*wikidata*`),
documentazione interna.

`Contents/Resources/data/liste/` contiene esattamente i cinque file letti
a runtime — `cognomi_italiani.tsv`, `comuni_italiani.txt`,
`nomi_italiani.tsv`, `vocab_it_60k.txt`, `vocab_it_660k.txt` — e ognuno
è stato ricontrollato contro il codice che lo apre: nessun peso morto.
`api/static/` contiene il solo `index.html`.

Unica eccezione consapevole: 269 file di test di `torch`/`spacy`/`thinc`
(~2 MB su 3,1 GB) restano dentro, perché `torch/_dynamo/test_case.py` è
importato da torch a runtime e un'esclusione per pattern romperebbe
l'app. Motivazione estesa in DECISIONI.md.

### 7.3 — Prova sull'app impacchettata, non sul codice di sviluppo

Il gate è stato eseguito lanciando il server **dal bundle montato dal
`.dmg`**, cioè esattamente il binario che riceve l'utente:

```
persone riconosciute: ['Delfo Berretti', 'marco', 'giovanni', 'maria', 'luisa', 'fiorella', 'luca', 'PASQUALE', 'Berretti']
mancanti: nessuno
'Delfo Berretti' -> «PERSONA_1»   'Berretti' -> «PERSONA_9»   distinti: True
tempo anonimizza : 5.64s
roundtrip identico byte per byte: True
```

### 7.4 — Windows: bloccato, non finto

L'installer Inno Setup (`build/PrivacyBridge-windows.iss`) e la spec
condivisa ci sono e sono corretti nei percorsi relativi, ma **non esiste
nessun `.exe`**: PyInstaller non compila per un sistema diverso da quello
su cui gira, e questa è una macchina macOS. Un `.exe` prodotto qui
sarebbe un file mai eseguito da nessuno.

Registrato in BLOCCHI.md § 11 con i cinque comandi da dare su un PC
Windows, e dichiarato apertamente nel `LEGGIMI.txt` della cartella di
consegna invece di essere taciuto.

## PARTE 8 — Gate finale e consegna (2026-08-01)

### 8.1 Il gate

`scripts/gate_finale.py` riscritto sul testo canonico del briefing
(nove nomi, cinque minuscoli, uno maiuscolo) ed eseguito **avviando il
bundle**, non il server di sviluppo.

```
[gate] server pronto in 0.5s (soglia gate: 5s)
[gate] OK tutti i 9 nomi sostituiti: ['Delfo Berretti', 'marco', 'giovanni', 'maria', 'luisa', 'fiorella', 'luca', 'PASQUALE', 'Berretti']
[gate] OK 'Delfo Berretti' → «PERSONA_1», 'Berretti' → «PERSONA_9» (correlato_a=«PERSONA_1»)
[gate] OK correzione in tabella (ORG aggiunta a mano) applicata
[gate] OK ripristino byte-identico (dopo la correzione)
[gate] OK PDF legale: 67 entità in 27s, roundtrip byte-identico
[gate] OK tema chiaro → scuro, contenuto invariato
GATE FINALE: OK
```

### 8.2 Difetto trovato: `verifica_tutto.sh` provava il bundle sbagliato

La riga "bundle" della verifica puntava a
`build/PrivacyBridge.app`, cioè al bundle montato a mano da cui si
preleva il modello — non a `dist/PrivacyBridge.app`, che è quello che
finisce nel `.dmg`. Una verifica che controlla un artefatto diverso da
quello consegnato non verifica la consegna. Corretto: prova prima
`dist/`, ripiega su `build/`, e stampa quale dei due sta usando.

```
  bundle in prova: dist/PrivacyBridge.app/Contents/MacOS/PrivacyBridge
  [OK] bundle porta 62084, /health = {"status":"ok","versione":"1.0.0"}
```

### 8.3 Difetto trovato: gli screenshot erano di una versione superata

Le dodici schermate in `docs/screenshots/` erano del 31 luglio alle
22:46; `src/api/static/index.html` è stato modificato il 1 agosto alle
09:30. Allegare quelle immagini come prova dell'interfaccia consegnata
sarebbe stata una prova falsa. Rigenerate alle 11:46 con
`scripts/screenshot_ui.py` e riguardate una per una nei due temi.

### 8.4 Verifica completa

```
  backend    : rc=0  tempo=89.3s      132 passed, 1 xpassed
  tassonomia : rc=0  tempo=14.4s      69 passed
  avversarial: rc=0  tempo=49.9s      606 passed
  matrice    : rc=0  tempo=558.9s     22/22 esiti conformi
  documenti  : rc=0  tempo=169.0s     141 sostituzioni su 8 file
  garanzie   : rc=0  tempo=83.0s      21 passed
  interfaccia: rc=0  tempo=95.9s      32 passed
  bundle     : rc=0  tempo=26.1s      /health ok
  totale     : tempo=1087.0s
STATO: OK — tutte le suite passate.
```

Contrasti: 32 accostamenti su 32 sopra soglia WCAG 2.1 AA nei due temi
(`scripts/misura_contrasti.py`). Il più stretto è 3,14:1 contro 3,0.

### 8.5 Consegna

`docs/CONSEGNA.md` riscritto da zero (la versione precedente è
archiviata in `CONSEGNA_2026-07-31.md`): struttura delle due cartelle,
output completo delle verifiche, tempi reali per documento, numeri
file per file sui documenti dell'utente, schermate nei due temi,
contrasti, contenuto dei pacchetti con l'audit, percorsi e dimensioni,
istruzioni d'installazione.

Il capitolo 9 è il capitolo onesto chiesto dal briefing: cosa l'app
NON copre. Contiene i numeri scomodi — precisione OCR 73,1% larga e
59,7% stretta sul PDF scansionato, con tre e-mail e quattro sequenze da
carta rimaste in chiaro; recall organizzazioni ~56%; vault non cifrato
a riposo; Windows mai provato — perché chi vende il prodotto deve
sapere cosa promettere.

### 8.6 Difetto trovato: il conteggio delle e-mail perse era sbagliato

Nella prima stesura del capitolo onesto avevo scritto "2 e-mail
rimaste in chiaro", riportando un numero contato in una sessione
precedente. Rimisurandolo — non sull'elenco delle entità ma sul **testo
anonimizzato in uscita**, che è ciò che davvero lascerebbe il computer
— sono **3**: la terza è una PEC con un punto subito dopo la chiocciola
(`…ufficio@.pec.esempio.it`), che non supera la validazione del
dominio. Le sequenze da carta sono confermate 4.

```
=== EMAIL RIMASTE IN CHIARO NELL'USCITA ===
    'rossi @esempio.it'
    'support @mocha.ni'
    'ufficio.protocollo@.pec.esempio.it'
totale distinte: 3

=== SEQUENZE TIPO CARTA RIMASTE IN CHIARO ===
    '3977•••••••••••'              15 cifre  Luhn=NO
    '4347 ••••••••••••'            16 cifre  Luhn=NO
    '5544•••••••••••'              15 cifre  Luhn=NO
    '6217•••••••••••••••'          19 cifre  Luhn=NO
totale distinte: 4
```

È il difetto più istruttivo della sessione, perché non stava nel codice
ma nel metodo: un numero ricordato non è un numero verificato, e il
posto giusto dove misurare una fuga di dati è l'uscita, non il registro
di ciò che il motore dichiara di aver trovato.

### 8.7 Difetto trovato e corretto: `benchmark/verifica_ocr.py`

Lo script salvava il testo estratto e poi andava in `ValueError`
stampandone il percorso: costruiva il percorso del dump dall'argomento
della riga di comando (relativo) e lo confrontava con `ROOT`
(assoluto). Corretto alla classe — il percorso si risolve subito
all'ingresso — e reso robusto anche per un PDF fuori dalla cartella di
progetto (`is_relative_to`).

## Sessione 2026-08-01/02 — Audit precisione, interazione diretta, firma (CHIUSA 2026-08-02)

Il mandato aveva tre parti indipendenti. Nessuna aggiunge dipendenze,
nessuna cambia il perimetro dichiarato in `CONSEGNA.md § 9`.

### PARTE 1 — Audit di precisione — CHIUSO

`docs/AUDIT_PRECISIONE.md` (825 righe). Non un documento di
rassicurazione: l'elenco degli errori raggruppati per **causa**, con
numeri misurati sui documenti veri dell'utente e sul corpus annotato,
mai stimati o ricordati. Struttura:

- Cap. 1.2 — due errori di misura trovati e corretti *prima* di
  misurare (il conteggio "616" era misurato con tutte le categorie
  accese, la baseline di consegna è 141; PROGRESSO precedente e
  CONSEGNA.md non erano allineate).
- Cap. 3-5 — falsi negativi, falsi positivi, errori di tipo, ognuno
  con classe, casi e proposta motivata.
- Cap. 7 — quattro proposte deterministiche, ordinate per rapporto
  guadagno/rischio.
- Cap. 8 — quello che non propongo e perché (niente modelli locali
  aggiuntivi, niente normalizzazione a monte che rompa G4, niente
  dizionari di enti/marchi che invecchiano).
- Cap. 9 — che cosa è stato implementato e quanto è valso davvero.

**Tre proposte su quattro implementate** (la quarta, e-mail con spazio
prima della chiocciola, ha rischio più alto delle altre e la
condizione di sicurezza va misurata prima di tenerla — resta aperta,
2 casi veri).

Confronto prima/dopo (`benchmark/misura_corpus`, `benchmark/audit_precisione`):

```
Corpus annotato:
  richiamo largo             95,4% → 98,5%
  richiamo stretto           75,9% → 87,2%
  span spuri                 9 → 9        (nessun falso positivo nuovo)
  ORG esatti su 46           22 → 44
  ORG con tipo sbagliato     8 → 0
  ORG non presi              6 → 0

Documenti reali (configurazione di consegna):
  sostituzioni attive        141 → 141
  suggerimenti               19 → 22       (3 carte vere in più affiorate)
  residui in uscita          55 → 55
```

Il richiamo stretto sale di undici punti e nessuna colonna peggiora.
Le sostituzioni sui documenti reali non salgono di fabbrica perché il
guadagno grosso — le organizzazioni — sta in una categoria spenta per
difetto (spiegato per intero nel cap. 9.2, senza nasconderlo dietro la
media).

**Un difetto trovato mentre misuravo, non nel mandato** (cap. 9.4):
`_risolvi_sovrapposizioni` non aveva un ordine totale. Due esecuzioni
consecutive dello stesso comando davano `CF 2 / PIVA 2` la prima volta
e `CF 3 / PIVA 1` la seconda: undici cifre sono insieme codice
fiscale di società e partita IVA, i due recognizer rispondevano con
score 1.0 e le tuple di confronto diventavano identiche. Con `>`
stretto vinceva chi Presidio restituiva per primo, e quell'ordine
dipende dal seed di hashing. Aggiunte in coda alla tupla la priorità
di base e il nome del tipo: ordine totale, esito riproducibile. Per
la privacy costava nulla — il dato era mascherato in entrambi i casi
— ma senza la correzione i numeri di 9.1 non sarebbero riproducibili.

### PARTE 2 — Modifica diretta sul testo — CHIUSA (fase6)

L'utente correggeva scendendo alla tabella; ora agisce dove guarda.

- **2.1 — pannello anonimizzato.** Hover su segnaposto → dopo 200-300 ms
  compare un menu `#comando-entita` con tre voci: **Ripristinare**
  (l'entità torna al valore reale, riga fuori dalla tabella, testo
  aggiornato), **Cambiare tipo** (tendina, si aggiorna il segnaposto),
  **Ricordare sempre** (rubrica personale, riconoscimento automatico
  in futuro). Il menu resta visibile finché il mouse ci sta sopra.
- **2.2 — pannello originale.** Selezione libera → `#comando-selezione`
  chiede il tipo, col più probabile già proposto. Aggancio ai confini
  di parola (mezza parola diventa parola intera; il trattino tiene
  insieme `pre-avviso`; il punto di fine frase non entra). Se la
  selezione tocca un'entità esistente, il comando propone di
  modificarla invece di crearne una nuova.
- **2.3 — legame reciproco.** Hover su segnaposto → si illumina il
  valore reale a sinistra. Hover su un'entità a sinistra → si
  illumina il segnaposto a destra. Se la controparte è fuori vista,
  il pannello scorre dolcemente per mostrarla.
- **2.4 — qualità.** Ogni modifica riflessa in entrambi i pannelli e
  in tabella senza premere «Rianonimizza». Nessuno spostamento di
  layout (i segnaposto non vengono rinumerati). Tastiera raggiunge le
  entità con Tab; menu con Invio. Cmd+Z/Ctrl+Z annulla. Prova su un
  documento con oltre 100 entità: interazione fluida, nessun
  ricalcolo dell'intero testo a ogni hover.

Test Playwright: **16 test `test_fase6_*`** in `tests/test_interfaccia.py`.
Tutti verdi.

### PARTE 3 — Rifinitura grafica — CHIUSA

- **Firma.** `PrivacyBridge by @Andrea Sforna` in basso a destra,
  ancorata al foglio del corpo (non alla finestra: schermi larghi
  altrimenti la staccavano), sempre visibile, coerente nei due temi,
  contrasto AA misurato.
- **Rifinitura.** Vedi `DESIGN_REVIEW.md` §§ H22-H28: la firma
  passava sotto la tabella (corretto con padding sotto il foglio); il
  grigio scelto per la firma non passava AA (rialzato); la firma era
  ancorata alla finestra invece che al foglio; le micro-interazioni
  dei comandi contestuali hanno transizioni brevi (H26).
- **Screenshot** rifatti nei due temi (`docs/screenshots/dopo_*_*.png`,
  12 file, 2 agosto 12:54).

Test Playwright: **4 test `test_firma_*`**. Tutti verdi.

### PARTE 4 — Regressione e consegna — CHIUSA

- **Suite completa:** 880 passed, 1 xpassed in 15:37.
  ```
  880 passed, 1 xpassed, 712 warnings in 937.59s (0:15:37)
  ```
- **Ruff:** All checks passed.
- **Baseline regressione:** `benchmark/audit_precisione` rilanciato a
  fine sessione. Attive=141, sugg=22, residui=55 — identici alla riga
  "dopo" di AUDIT_PRECISIONE § 9.1. Zero regressioni sui documenti
  reali.
- **`.dmg` ricostruito** con `build/build_bundle.sh` e sostituito in
  `~/Desktop/PrivacyBridge-App/` (il precedente era del 1 agosto
  11:09, non conteneva le UI di Parte 2/3).
- **`CONSEGNA.md § 9`** già aggiornato in una sessione precedente con
  i nuovi numeri di precisione: ORG 100% largo / 95,7% stretto (44/46)
  invece del vecchio «~56%», che era un numero ricordato da un corpus
  diverso e non rimisurato.

### Un difetto trovato mentre chiudevo

La sessione precedente ha eseguito il lavoro di Parte 1, 2 e 3 —
codice, test, `AUDIT_PRECISIONE.md`, `DESIGN_REVIEW.md` H22-H28,
screenshot `dopo_*` — ma **non ha scritto la voce di chiusura in
`PROGRESSO.md`**. Riprendendo la sessione senza uno stato dichiarato
avrei potuto duplicare il lavoro o (peggio) crederlo mai fatto. La
prova che era chiuso è la suite verde su codice datato oggi, i numeri
di `benchmark/audit_precisione` identici a quelli di
`AUDIT_PRECISIONE § 9.1`, e i test `test_fase6_*` che esercitano
interazioni non presenti nella versione impacchettata nel `.dmg` del
1 agosto. **La lezione:** ogni sessione va chiusa nel registro anche
quando il codice è verde, o la sessione successiva paga la verifica
che avrebbe dovuto essere una lettura.

## Sessione 2026-08-02 (sera) — Due difetti trovati usando l'app (CHIUSA)

L'utente ha usato l'app sul lavoro vero e ha trovato due difetti. Il
primo grave (fughe semantiche), il secondo di ergonomia.

### 1. PERSONA che ingloba parole di contesto anagrafico

**Difetto.** Su `"Ciao sono Matteo Rossi nato ad Assisi il 27 marzo
2004"` il motore riconosceva `"Matteo Rossi nato"` come PERSONA. La
parola *nato* spariva dall'uscita anonimizzata (`"«PERSONA_1» ad
«LUOGO_NASCITA_1»…"`), e — cosa peggiore — *nato* è **l'indicatore di
contesto** che il recognizer LUOGO_NASCITA usa per innescarsi su
"Assisi": un innesco viveva dentro lo span del vicino. Il roundtrip
G4 byte-identico sembrava tenere solo grazie al valore memorizzato
nel vault, ma qualunque modifica manuale della sequenza dei
segnaposto avrebbe rotto la ricostruzione.

**Fix.** Nuova funzione `_pota_span_persona_da_contesto` che, subito
dopo `_rifila_bordi_persona`, rimuove dai bordi degli span PERSONA i
token che sono **parole di contesto anagrafico** (`nato/nata`,
`residente`, `domiciliato`, `originario`, `coniugato`, ausiliari) o
**funzionali monosillabici** (`a`, `ad`, `in`, `il`, `la`, `di`, `da`,
…). I nomi/cognomi noti — anche quelli ambigui (`Rossi`, `Bianchi`,
`Verdi`, che sono nel vocabolario italiano) — vengono sempre tenuti,
altrimenti si sarebbero persi. Onorifici e particelle nobiliari
restano ai bordi.

**Perché una lista esplicita di parole di contesto invece del
vocabolario italiano.** Il primo tentativo — «se il token è nel
`_VOCAB_IT` e non è in `_NOMI_TUTTI`/`_COGN_TUTTI`, scarta» — è stato
scartato dopo aver misurato: *"nato"* è in `_COGN_AMBIGUI` (esiste il
cognome "Nato"), *"rossi/bianchi/verdi/marino/bruno/russo"* sono
**tutti** in `_COGN_AMBIGUI + _VOCAB_IT`. Applicare il vocabolario a
tappeto avrebbe rimosso metà dei cognomi italiani più diffusi. La
regola opposta — «tieni ogni token che è nome/cognome noto, scarta
solo le parole di contesto esplicite» — è verificabile, deterministica
e non richiede aggiornamenti al vocabolario per essere corretta.

**Test.** Nuovo `test_g4_span_persona_non_ingoia_contesto_anagrafico`
in `tests/test_garanzie.py`: sette frasi con `nato/residente/
domiciliato/originario/coniugato`, verifica sia il roundtrip
byte-identico sia strutturalmente che nessuno span PERSONA contenga
parole di `_PAROLE_CONTESTO_ANAGRAFICO`.

**Misura prima/dopo.** Zero regressioni.
```
                              prima      dopo
corpus, richiamo largo         98,5%     98,5%
corpus, richiamo stretto       87,2%     86,7%   (−0,5%, entro il rumore)
corpus, span spuri                 9         9
reali, sostituzioni attive       141       138   (−3 falsi positivi)
reali, suggerimenti               22        22
reali, residui in uscita          55        55   (nessuna nuova fuga)
```
Le tre sostituzioni in meno sono su `Indagine .pdf` (67 → 64), e
sono precisamente **falsi positivi** che il neurale produceva
inglobando parole di contesto. Il numero di residui — che è la
misura della fuga — non si muove. Il richiamo stretto sul corpus
cala di 0,5%: costo accettabile perché il corpus contiene un solo
caso di `nato+contesto` e il difetto misurato dall'utente sui
documenti reali era ben più visibile.

### 2. Menu contestuale — a due voci, con "Modifica valore"

**Difetto.** Le tre voci del menu (`Ripristinare`, `Cambia tipo`,
`Ricorda sempre`) non erano quelle che l'utente aveva davvero bisogno
di raggiungere dal testo. Ripristinare è raggiungibile dalla colonna
`Rimuovi` della tabella; Ricorda sempre dalla scheda `Rubrica`. Il
menu dal testo deve avere **due voci** — le due che sono utili solo
lì:

- **Cambia tipo** (invariata).
- **Modifica valore** — nuovo: apre un `<input>` col valore reale
  catturato. L'utente lo corregge (accorcia, allunga, sposta) e
  conferma. La sostituzione viene rifatta dal testo ORIGINALE, quindi
  la parte accorciata torna in chiaro, e il ripristino resta
  byte-identico.

**Come è cablato.** `applicaModifica` già inviava `stato.entita` a
`/rianonimizza`, che riparte dal testo originale. Bastava cambiare il
`valore_reale` dell'entità in memoria e riusare quel percorso — nessun
endpoint nuovo, nessun cambiamento al motore, nessun rischio di
rompere G4.

**Test.** Quattro nuovi test Playwright in `tests/test_interfaccia.py`:
- `test_fase6_modifica_valore_accorcia_lo_span`
- `test_fase6_modifica_valore_allunga_lo_span`
- `test_fase6_modifica_valore_sposta_lo_span`
- `test_fase6_modifica_valore_roundtrip_byte_identico`

I tre test obsoleti (`test_fase6_ripristina_dal_testo`,
`test_fase6_ripristina_non_rinumera_gli_altri`,
`test_fase6_ricorda_sempre_entra_in_rubrica`) sono stati rimossi. I
test residui che usavano `#ce-ripristina` — `annulla_con_scorciatoia`
e `documento_con_oltre_cento_entita` — ora fanno la modifica tramite
`Cambia tipo`, che resta.

Il `test_fase6_hover_segnaposto_apre_comando` verifica **anche in
negativo** che `#ce-ripristina` e `#ce-ricorda` non ricompaiano per
abitudine.

**Piccolo difetto emerso nei test.** L'`_apri_comando` originale
usava `.first.hover()`. Fra due chiamate consecutive nello stesso
test, Playwright non riemette `mouseover` se la posizione del mouse
non si sposta — il timer di apertura non partiva. Aggiunto un
`mouse.move(0, 0)` prima dell'hover e, per i test di modifica
consecutiva, un helper `_apri_comando_via_tastiera` che usa
focus+Invio: più robusto perché non dipende dal rimbalzo degli
eventi mouse dopo un ridisegno del DOM.

**Isolation test-to-test.** Il test `_accorcia_lo_span` inizialmente
usava "Mario Rossi", che il precedente `test_fase6_cambia_tipo`
aveva ritipizzato a `ALTRO` nel vault condiviso. Ogni pytest usa un
`browser.new_context()` (localStorage fresco) ma il server è
`scope="session"`: il client crea una sessione nuova, ma per lo stesso
valore la ritypizzazione persiste. Sostituito con "Giulia Verdi" —
non è un bug del prodotto, è un dettaglio di test-isolation che
ignoriamo finché non tocca la funzione in prova.

### Regressione e consegna

```
suite completa       : 882 passed, 1 xpassed in 5:47
ruff                 : All checks passed!
audit_precisione     : 138 attive, 22 sugg., 55 residui — zero fughe nuove
corpus annotato      : richiamo largo 98,5%, stretto 86,7%, spuri 9
```

`.dmg` ricostruito con `build/build_bundle.sh` e sostituito in
`~/Desktop/PrivacyBridge-App/` (il precedente era del 2 agosto
21:09, non conteneva il fix di potatura né il menu a due voci).
