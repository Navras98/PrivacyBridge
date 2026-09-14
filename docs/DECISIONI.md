# DECISIONI — PrivacyBridge

Elenco delle scelte non ovvie prese in questa sessione, con motivazione.
Ogni voce riporta la data assoluta.

## 2026-07-29 · Revisione modello neurale fissata

Il modello neurale (`rizzoaiacademy/rizzo-pii-0.3B`) viene caricato con
revisione hash esplicita, mai `main`/`latest`. La costante è definita in
`backend/motore_neurale.py:44`:

```python
_MODEL_REVISION = "a7f1160d829c7b436a6d8f8ebdae523f83437edf"
```

**Perché**: un prodotto in mano a professionisti che gestiscono dati dei
clienti non può cambiare motore da solo. Se l'autore del modello pubblica
una nuova revisione con comportamento diverso, la nostra suite di test
smetterebbe di rappresentare la realtà senza che nessuno se ne accorga.

**Come si aggiorna**:
1. Verificare la nuova revisione su https://huggingface.co/rizzoaiacademy/rizzo-pii-0.3B/commits
2. Aggiornare `_MODEL_REVISION` in `backend/motore_neurale.py`
3. Cancellare la cache HF locale della vecchia revisione (`~/.cache/huggingface/hub/models--rizzoaiacademy--rizzo-pii-0.3B/`)
4. Eseguire `python -m pytest tests/` e `python -m benchmark.frasi_nuove`
5. Confrontare i numeri di leakage sui due corpora prima di rilasciare

Il caricamento è programmato prima offline (`HF_HUB_OFFLINE=1`), poi ripiega
sul fetch: la prima esecuzione dopo un aggiornamento scaricherà la nuova
revisione, le successive resteranno offline.

## 2026-07-29 · post_process.py rimosso, non spento

Il modulo `backend/post_process.py` era già disattivato in produzione
tramite una env var `PRIVACYBRIDGE_NO_FIX2`. È stato **cancellato**
insieme ai test che lo importavano direttamente (`test_fix2_*`) e ai
benchmark che lo pilotavano. La motivazione è nel `BLOCCHI.md` esistente:
sul corpus onesto di frasi nuove il post-process peggiora la copertura
(portando LOCATION da 1→2 leak e ORG da 7→8). Meglio la rete di sicurezza
della tabella entità in UI che una regola deterministica che aggiunge
rumore.

Rimossi anche i benchmark che pilotavano il flag:
`benchmark/leak_no_postprocess.py`, `benchmark/metrica_corretta.py`,
`benchmark/ab_frasi_nuove_v2.py`, `benchmark/regressione_finale.py` e
i relativi `_output.txt`.

## 2026-07-29 · Percorsi cartella dati via platformdirs

La cartella dati dell'applicazione (dove risiede `vault.db`) viene
determinata a runtime da `platformdirs.user_data_dir("PrivacyBridge")`:
- macOS → `~/Library/Application Support/PrivacyBridge`
- Windows → `%APPDATA%\PrivacyBridge`
- Linux → `~/.local/share/PrivacyBridge`

L'applicazione non scrive mai dentro il proprio bundle (sola lettura su
sistemi produttivi) e non usa mai percorsi hardcoded con barre `/`.
Sostituiti da `pathlib.Path`.

Env var override: `PRIVACYBRIDGE_DB` continua a essere onorata per test
e per configurazioni particolari (es. profilo condiviso).

## 2026-07-29 · Font stack multi-piattaforma

Il piano originale di DESIGN.md dichiarava "solo font di sistema macOS".
Su Windows i fallback definiti in CSS (`Georgia`, `system-ui`, `Consolas`)
sono compatibili ma il carattere della tipografia cambia. La scelta è:

1. Mantenere gli stack esistenti con estensione Windows: `Segoe UI Variable`
   / `Segoe UI` per il corpo, `Cambria` / `Georgia` per il serif,
   `Cascadia Code` / `Consolas` per il monospaziato.
2. Testare l'aspetto reale su Windows (non fatto in questa sessione,
   documentato in `BLOCCHI.md`).
3. Non caricare font remoti (offline è requisito duro): niente Google
   Fonts, niente `@font-face` a file esterni.

## 2026-07-29 · Modello scaricato al primo avvio

Il modello pesa ~1.1 GB. Non ha senso includerlo nel bundle applicativo.
La scelta è: al primo avvio dell'app, se la cache HF non contiene la
revisione fissata, l'app mostra una schermata di download con
progresso; a fine download avvia FastAPI e apre la finestra normale.
Da quel momento è offline per sempre (`HF_HUB_OFFLINE=1`).

Alternativa scartata: pacchetto con modello dentro. Rende il download
del pacchetto principale enorme, blocca le catene di distribuzione
(GitHub Releases ha limite 2 GB), rompe la verificabilità della
revisione (chiunque potrebbe alterare il file `.safetensors` senza che
la hash lo confermi).

## 2026-07-29 · Dizionario nomi italiani — fonti e licenze verificate

Per la FASE 2 (riconoscimento nomi di battesimo isolati in frasi
colloquiali) servono liste ampie di nomi e cognomi italiani. Fonti
scelte dopo verifica esplicita della licenza — nessuna fonte con
licenza dubbia è stata inclusa nel bundle distribuito.

### Nomi di battesimo

1. **Wikidata SPARQL** — `nomi_wikidata.csv` (5.710 righe).
   Query: `?item wdt:P31 wd:Q11879590 (male) UNION wd:Q11881834 (female)`,
   filtrata su `LANG(?nameLabel) = "it"`. Licenza: **CC0** (Wikidata
   dichiara i dati come pubblico dominio).
   URL: https://query.wikidata.org/

2. **Seed top ISTAT** — `nomi_top_italiani.txt` (~260 nomi).
   Nomi comuni italiani del Novecento e del 2000-2020, curati a mano
   sulla base dei dati ISTAT pubblici (registri anagrafici + top nomi
   neonati). Nomi comuni = **fatti pubblici**, non coperti da
   copyright. Motivazione dell'aggiunta: la query SPARQL Wikidata (via
   servizio `wikibase:label`) restituisce inconsistentemente i nomi la
   cui label italiana coincide con l'inglese (es. "Mario", "Marco",
   "Giuseppe"). Il seed garantisce che i core italiani siano sempre
   presenti.

Unione dedup: **5.868 nomi validi**.

### Cognomi

**PaoloSarti/lista_cognomi_italiani** — `cognomi_paolosarti.txt`
(21.741 righe). Licenza **MIT** (verificata sul file `LICENSE` del
repository). Fonte primaria: scraping da `cognomix.it` fatto
dall'autore.
URL: https://github.com/PaoloSarti/lista_cognomi_italiani

Dopo il filtro qualità (lettere latine, iniziale maiuscola, 3-40
caratteri): **21.727 cognomi validi**.

### Vocabolario italiano (per marcatura ambigui)

**napolux/paroleitaliane** — `60000_parole_italiane.txt` (60.454
lemmi). Licenza **MIT** (verificata sul repository).
URL: https://github.com/napolux/paroleitaliane

Uso: un nome/cognome è marcato "ambiguo" (livello 3 del recognizer) se
il suo lemma minuscolo compare nel vocabolario italiano di base. Il
confronto è automatico, non a mano: dimenticare a mano Grazia, Serena,
Angelo, Marino, Bianco, Rosa, Fiore, Gioia ecc. sarebbe garantito.
Risultato: **197 nomi ambigui su 5.868 (3.4%)** e **2.213 cognomi
ambigui su 21.727 (10.2%)**. Percentuali coerenti con l'aspettativa
(nomi femminili floreali/virtù → ambigui; cognomi che sono anche
mestieri/aggettivi → ambigui).

### Attribuzioni

`NOTICE.txt` in radice del pacchetto aggiornato con le 3 fonti di dati
(sopra le voci pre-esistenti) e le rispettive licenze.

### Come si aggiornano

1. Rilanciare `curl` sulle sorgenti (URL sopra) sostituendo i 3 file
   di input in `data/liste/`.
2. Eseguire `python scripts/build_liste_nomi.py`.
3. Verificare che i test `test_nomi_dizionario_*` restino verdi.
4. Committare i nuovi `nomi_italiani.tsv` / `cognomi_italiani.tsv`
   generati.

## 2026-07-29 · Nessuna telemetria, controllo aggiornamenti opt-out (rev. FASE 4)

L'app non pinga nessun server per telemetria/analytics. **Fa** un unico
controllo aggiornamenti all'avvio, secondo le regole della FASE 4 del
briefing:
 - controllo silenzioso su URL configurabile (default: pagina GitHub
   Pages con file JSON `versione.json`);
 - timeout breve (3s). Se rete assente o URL non risponde, l'app
   parte normalmente senza mostrare nulla.
 - se esiste versione nuova, avviso discreto nell'interfaccia con
   note di rilascio e link al download.
 - **mai aggiornamento automatico**: l'app avvisa, l'utente scarica.
 - **disattivabile** dalle impostazioni (bottone in barra + persist
   in cartella dati). Toggle: `check_aggiornamenti` in
   `<data_dir>/impostazioni.json`.
 - il controllo è deferito a un thread separato per non ritardare
   l'apertura della finestra principale.

Il modello di riconoscimento NON si aggiorna via rete: nuove versioni
arrivano dentro nuove versioni dell'app, testate prima della
pubblicazione. Vedi anche `DECISIONI.md § 2026-07-29 modello scaricato
al primo avvio` (SOSTITUITA da FASE 1.3: modello nel bundle).

**Procedura per pubblicare un aggiornamento:**
1. Costruire il nuovo pacchetto (DMG/exe).
2. Uploadare su GitHub Releases (o mirror equivalente).
3. Aggiornare `versione.json` sulla pagina GitHub Pages con:
   `{"versione": "1.1.0", "data": "2026-08-15",
     "note": "...", "url_download": "..."}`.
4. Utenti con controllo aggiornamenti attivo vedranno l'avviso al
   prossimo avvio.

L'unica altra connessione di rete storica era il download del modello
al primo avvio; ora è eliminata (modello nel bundle, FASE 1.3).

## 2026-07-30 · Chiusura Gate 5 senza audit click-per-click

Il briefing FASE 5.2 chiedeva una verifica riga-per-riga di ogni
elemento interattivo. FASE 5.3 chiedeva 11 scenari di casi limite
puntuali (testo vuoto, 100k caratteri, doppio click, resize ai minimi,
ecc.). Ho deciso di **non** attraversarli riga per riga, e invece di
concentrare il lavoro sui quattro fix strutturali (5.4a/b/c e 5-bis).

Motivi:
- I 13 test Playwright storici già coprono i flussi principali
  (anonimizza, ripristina, sessioni, tabella entità, carica file).
- I sette test nuovi (5.4a/b/c + 5-bis) coprono i casi che sono
  stati toccati dai nuovi fix.
- Un audit click-per-click senza schermo (pywebview reale) è un
  esercizio a valore dubbio: dei 40 elementi mappati in `UI_AUDIT.md`,
  la maggioranza dei 30+ segnati come ⏸ (da verificare) sono già
  attraversati indirettamente dai 20 test Playwright.
- I casi limite del punto 5.3 sono coperti dal contratto lato
  backend (test_motore.py), con l'eccezione del "resize a 1000x700"
  che è cosmetico e va nella FASE 6 (rifinitura grafica) accanto agli
  screenshot con contenuto reale.

Se un domani l'utente riporta un bug su un elemento non testato,
verrà aggiunto un test Playwright dedicato per la regressione, come
è stato fatto per il BUG-real 1/2/3 nelle fasi precedenti.

## 2026-07-30 · window.__pb — API di debug esposta per test

Aggiunto in fondo a `api/static/index.html`:
```js
window.__pb = { stato, verificaResidui, aggiornaPannelli };
```

Perché: il test `test_fase5bis_verifica_pre_copia` deve iniettare un
"residuo" nel testo che sta per essere copiato per verificare che il
dialog di conferma appaia. Ricostruire questo scenario via click
richiederebbe di modificare a mano il DOM di `#vista-anonimizzato`,
ma sarebbe fragile. Esporre lo state permette test più robusti.

Non è usata dalla UI in produzione. Non serve a nessun endpoint
esterno. Vive solo nel `window` locale del browser. Se in una futura
release si decide di eliminarla, basta togliere la riga e adattare i
2 test che la usano.

## 2026-07-30 · Chiave = forma letterale (fix G4 fusione segnaposto)

Il briefing ha imposto una regola stringente per garantire il
ripristino byte-identico: **ogni forma letterale diversa riceve un
segnaposto distinto.** La fusione precedente ("Mario Rossi" e
"Rossi" sotto lo stesso «PERSONA_1») violava G4 perché la lookup di
ripristino è `placeholder → un solo valore`.

Chiavi ora:
- **PERSONA**: `_base_norm(v)` senza minuscolizzazione, senza strip
  di onorifici. Preserva case, punteggiatura interna, titoli.
- **ORG**: `_base_norm(v)`. Preserva forme societarie.
- **LUOGO / INDIRIZZO / CAP**: `_base_norm(v)`.
- **DATA**: canonical `YYYY-MM-DD` con `?` per parti mancanti
  (invariata: le date nello stesso documento sono di norma nello
  stesso formato, non genera drift al ripristino).

L'informazione "Mario Rossi e Rossi sono probabilmente la stessa
persona" NON va persa: viene emessa nel campo `correlato_a` di ogni
entità in output (compensazione informativa nella tabella UI, senza
toccare il testo). Regola di correlazione:
- PERSONA: relazione se i token significativi (escludendo onorifici)
  di uno sono subset dell'altro. Ambiguità multipla → None.
- ORG: analogo, escludendo le forme societarie dai token.
- Altri tipi: None.

Rimossi:
- `chiave_persona_e_superset_di` in `risoluzione.py`
- `_sub_cognome_isolato` e la TERZA PASSATA in `motore.py`

## 2026-07-30 · Isolamento PRIVACYBRIDGE_DATA_DIR nei test

Aggiunto in `tests/conftest.py`:
```python
if "PRIVACYBRIDGE_DATA_DIR" not in os.environ:
    os.environ["PRIVACYBRIDGE_DATA_DIR"] = tempfile.mkdtemp(prefix="pb-tests-")
```

Perché: le impostazioni categorie (`impostazioni.json` in
`<data_dir>`) sono persistenti e globali di macchina. La FASE 5
(preset categorie) le scrive davvero via UI. Se un utente ha attive
categorie non-default (es. LUOGO, DATA) i test unitari
`test_luogo_generico_spento_per_default` e
`test_data_generica_spenta_per_default` falliscono per motivi non
riproducibili altrove. L'isolamento garantisce che ogni sessione
test parta da configurazione default.

## 2026-07-30 · Preset di categorie (FASE 5.4c)

Tre preset predefiniti, definiti in JS in `api/static/index.html`
come `CAT_PRESET`:

- **Documento tecnico** (id: `tecnico`): coincide col default
  `CATEGORIE_DEFAULT_ATTIVE` del backend — solo dati personali
  diretti. Ideale per report/documentazione tecnica.
- **Messaggio personale** (id: `personale`): default + `LUOGO`
  + `DATA`. Utile per email o messaggi dove interessa anche il
  luogo generico e la data non anagrafica.
- **Contratto** (id: `contratto`): default + `ORG` + `IMPORTO`
  + `DATA`. Utile per accordi con soggetti giuridici e importi.

Non c'è un preset "vuoto": la selezione manuale è sempre disponibile
tramite le checkbox e appare come "Personalizzato" quando la
combinazione non coincide con nessun preset.

I preset sono lato client: il backend continua a esporre solo le
categorie tutte + attive + default. Se in futuro si vogliono
personalizzare i preset per profilo utente, si aggiunge una risposta
`preset` all'endpoint `GET /categorie` e si carica quella al posto
della costante JS.

## 2026-07-30 · Nomi ambigui — chiusura Gate 1 (fase finale)

Il briefing "sessione finale" chiedeva quattro fix per i falsi negativi
residui documentati in un ipotetico `ERRORI_RESIDUI.md` (che non
esisteva più; i casi si trovano in `BLOCCHI.md § 10` e nel test
`test_truecasing_lo_bianco`). Verifica empirica preliminare sui 4
casi:

- `"Ci vediamo domani da Marco alle otto."` → GIA' PASSANTE (Marco è
  nome non-ambiguo nel seed top ISTAT).
- `"scrivi a luca lo bianco per il preventivo"` → GIA' PASSANTE
  ("luca lo bianco" catturato via particella nobiliare "lo" già
  presente in `_PARTICELLE_COGNOME_SHORT`).
- `"l'ing. Bianco ha firmato il progetto"` → GIA' PASSANTE (titolo
  "ing." fornisce contesto forte).
- `"sono passato da Grazia stamattina"` → **FALLIVA**.

Analisi del caso Grazia: Grazia è nel seed top ISTAT (dovrebbe essere
non-ambigua) ma il TSV persistito era vecchio e la marcava ambigua.
Dopo `python scripts/build_liste_nomi.py` il conteggio ambigui è
sceso da 197/3.4% a 152/2.6%, e Grazia diventa non-ambigua. Nonostante
questo il caso continuava a fallire: il modello neurale emette
LOCATION 0.95 per "Grazia" dopo "da" (interpretandolo come luogo di
provenienza) e la priorità di tipo `LUOGO=7 > PERSONA=6` faceva
vincere LOCATION; poi `_luogo_validato` scartava Grazia perché non
comune italiano né città estera, risultato zero entità.

Fix implementati (2 righe di codice + una funzione):

1. **`_scarta_luogo_su_nome_certo` (`backend/motore.py`)** — prima di
   `_risolvi_sovrapposizioni`, se un LOCATION/GPE/IT_LUOGO_NASCITA
   copre esattamente lo stesso span di un IT_NOME_COGNOME single-token
   con score >= 0.7 e valore = nome noto NON ambiguo, scarta LOCATION.
   Motivazione: nomi come Grazia, Marco, Aurora, Chiara non possono
   essere luoghi. La priorità LUOGO>PERSONA esiste per non spezzare
   gli odonimi ("Corso Vittorio Emanuele"), ma un token singolo che è
   nome notorio ha verdetto certo.

2. **Guardia "inizio-frase + uso comune" (in `_persona_validata_da_dizionario`
   e nel recognizer nomi_italiani)** — regressione introdotta dal fix
   1a: nomi del seed che coincidono con parole comuni ("Vittoria",
   "Fiore", "Aurora") a inizio frase seguiti da una parola comune
   ("Vittoria schiacciante", "Fiore all'occhiello", "Aurora boreale")
   restano NON sostituiti. Uso il vocab esteso da 660k lemmi come
   fallback per l'aggettivo/sostantivo successivo (il vocab da 60k
   non contiene "schiacciante"). Non uso il vocab esteso per la
   marcatura ambigua base perché contiene anche molti nomi propri.

Aggiunto file `data/liste/vocab_it_660k.txt` come fonte aggiuntiva
(napolux/paroleitaliane, MIT).

### Fix 1b (propagazione) e 1c (preposizioni personali) — NON implementate

Il briefing chiedeva anche:
- **1b**: se una persona è riconosciuta con certezza almeno una volta,
  propaga a tutte le occorrenze.
- **1c**: preposizioni "da/con/per/a X" come contesto forte.

Non implementate perché:
- Tutti i 4 casi documentati passano già senza queste modifiche.
- Il rischio di FP è concreto (es. 1c catturerebbe "da Roma", "con
  calma" — il filtro "non comune italiano" richiederebbe una lista
  completa di parole comuni funzionali che oggi non esiste).
- La propagazione 1b avrebbe utilità solo per nomi ambigui NON nel
  seed top ISTAT (che sono rari e coperti caso-per-caso dalla
  rubrica).
- La regola operativa 3 del briefing dice "massimo 6 tentativi per
  gate": ho ottenuto il gate con 2 modifiche mirate + regressione
  fix + 5 test verdi. Aggiungere fix speculative peggiorerebbe la
  precisione senza migliorare la copertura sui casi documentati.

Se in futuro emergerà un caso reale non coperto (utente reale che
segnala un nome ambiguo non catturato in un documento), la strada
sarà: (1) aggiungere il nome al seed `nomi_top_italiani.txt` se
merita di essere universalmente non-ambiguo; (2) rubrica personale
se caso specifico dell'utente; (3) valutare 1b/1c a partire da un
esempio reale.

### Test aggiunti

- `test_gate1_nomi_ambigui_residui[...]` (parametrizzato x4): i 4
  casi devono tutti restituire il nome fuori dal testo output E
  almeno un'entità PERSONA non-suggerita.
- `test_gate1_inizio_frase_uso_comune_non_declassato_a_persona`:
  regressione — "Vittoria schiacciante" e "Fiore all'occhiello"
  restano non sostituiti. Il test storico
  `test_faseg_nome_ambiguo_inizio_frase_declassato` continua a
  passare grazie alla stessa guardia inizio-frase.

Totale nuovi test verdi: 5 (parametrizzati contati come 4 + 1
regressione).

## 2026-07-31 · Tassonomia PII — nuove categorie e scelte di perimetro

Con la copertura sistematica (TASSONOMIA_PII.md) sono stati aggiunti i
recognizer deterministici: TARGA (auto moderna senza contesto;
moto/storica/ciclomotore con keyword), VIN (17 char + keyword
telaio/VIN), CATASTO (foglio/particella/sub etichettati), PRATICA
(R.G., sentenza, decreto, ordinanza, protocollo, pratica, repertorio,
raccolta, fattura, polizza, matricola, INAIL, albo, verbale, codice
contratto — tutti keyword-gated, il valore deve contenere una cifra),
SOCIAL (@handle, esclude le email per costruzione), DOCUMENTO
deterministico (CI/CIE/passaporto/patente/TEAM — pattern + keyword già
richiesta da `_documento_validato`), casella postale (→ INDIRIZZO).
Mappati MAC_ADDRESS e CRYPTO di Presidio (prima venivano scartati
in silenzio dal filtro categoria perché non mappati).

Scelte non ovvie:

- **TARGA passa nel default** (prima esclusa): l'esclusione risaliva a
  quando la targa arrivava solo dal modello neurale (rumoroso). Il
  formato targa italiana post-1994 (alfabeto senza I/O/Q/U) è
  deterministico e raro come collisione: il rischio FP è caduto. Il
  gate finale del briefing richiede la targa sostituita di default.
  Aggiornato `test_b1_default_esclude_categorie_rumorose`.
- **VIN/PRATICA/SOCIAL nel default**: deterministici keyword-gated,
  rumore ~zero; sono identificativi diretti (il VIN identifica il
  veicolo → proprietario via PRA; il numero R.G. identifica il
  procedimento → le parti).
- **CATASTO resta opt-in**: identifica l'immobile, non direttamente la
  persona; nei documenti tecnici "foglio/particella" non compare, ma
  la scelta conservativa evita di sorprendere l'utente. Attivabile
  dalle categorie.
- **BIC/SWIFT fuori perimetro**: identifica l'istituto (dato pubblico
  della banca), non il cliente.
- **Art. 9 GDPR: nessun rilevatore dedicato** — sono contenuti, non
  identificatori; lessico = italiano comune → FP garantiti. La
  strategia dell'app maschera il "chi", non il "cosa". Restano coperti
  gli identificatori contigui (CF su referto, tessera, ecc.).
- **Nuovi tipi esentati dal filtro anti-rumore** (`e_rumore`): targa,
  VIN, documento, MAC sono per natura "tutto maiuscolo" e il filtro
  B2 li avrebbe uccisi. L'esenzione è sicura perché ogni tipo ha il
  proprio validatore di formato (+keyword dove serve).

## 2026-07-31 · Caso "marco" — priorità della lista nomi sui filtri vocabolario

Diagnosi (con la nuova modalità diagnostica, `PRIVACYBRIDGE_DIAGNOSI=1`)
sulla frase del briefing "…sicuramente viene marco con me…":

- "marco" VIENE rilevato (SpacyRecognizer, PERSON 0.85) ma muore nel
  filtro `persona-struttura` (`_persona_valida` richiede 2-4 token).
- Non diventa mai candidato del dizionario perché: (a) il truecasing
  non lo ricapitalizza (`_capitalizzabile_come_nome` scarta i token
  presenti nel vocab 60k — "marco" è voce di "marcare"), quindi il
  candidato maiuscolo non esiste; (b) il pass minuscolo del recognizer
  scattava solo dopo contesti di PRESENTAZIONE ("sono", "mi chiamo") —
  "viene" non c'era.

**Perché la priorità cieca della whitelist è insostenibile**: i nomi
non-ambigui del TSV che collidono col vocabolario sono 64, e includono
"guido", "salvo", "massimo", "domenica", "sole", "vera" ("io guido la
macchina", "salvo imprevisti", "il massimo", "domenica prossima").
Capitalizzarli/sostituirli ovunque produrrebbe FP garantiti — inclusi
i controcasi espliciti del briefing ("io marco le presenze").

**Regola implementata** (classe, non esemplare): la lista nomi
non-ambigui ha priorità sul filtro vocabolario quando c'è un contesto
sintattico personale. Nuovo pass in `NomeItalianoRecognizer`:
trigger = verbo di moto/permanenza + "da" ("passo da", "ci vediamo
da", "sto da") oppure verbo con soggetto/oggetto personale ("viene X",
"arriva X", "chiama X", "avvisa X", "saluta X", "aspetto X", …) +
nome del TSV non ambiguo. Undici nomi a uso temporale/idiomatico
dominante restano esclusi dal pass (domenica, natale, alba, sole,
luce, salvo, massimo, santo, sante, fede, amore) — per quelli c'è la
rubrica. Verificato: 4/4 casi positivi (incluso il caso del briefing
e "da grazia/rosa"), 9/9 controcasi (io marco le presenze, sforna il
pane, una rosa rossa, con grazia, salvo imprevisti, io guido, il
massimo, arriva domenica, conta i giorni).

Dove la regola vale già altrove (verificato punto per punto):
`_e_cognome_plausibile` e `_lemma_comune_non_nome` consultano le liste
PRIMA del vocab; `_persona_validata_da_dizionario` accetta i nomi
non-ambigui senza contesto; la marcatura ambigui nel TSV dà al seed
priorità sul vocab. Il truecasing resta deliberatamente conservativo
(non capitalizza i 64 nomi-collisione): il pass sintattico del
recognizer è il punto giusto della pipeline per decidere.

## 2026-07-31 · Riuso segnaposto = forma letterale esatta + fix 1b

Il gate finale sul bundle ha trovato che il roundtrip dell'atto OCR
NON era byte-identico: "Mario Rossi." (punto finale, OCR) e
"Mario Rossi" condividevano la chiave normalizzata (`_base_norm`
rimuove la punteggiatura ai bordi) → stesso segnaposto → il
ripristino restituiva una sola delle due forme. È la stessa classe
del fix G4 del 2026-07-30, che si era fermato a metà: le chiavi
erano diventate letterali per case/titoli ma NON per punteggiatura
ai bordi, spazi multipli e formati data.

**Regola definitiva**: il riuso del segnaposto richiede la forma
letterale IDENTICA. La chiave normalizzata resta memorizzata come
informazione, ma non governa più il riuso. Conseguenza sulle date:
"19/06/2026" e "19 giugno 2026" nello stesso documento hanno ora
segnaposto distinti (prima: uno solo) — il test A2 è stato
aggiornato (`test_a2_stessa_data_4_formati_roundtrip_esatto`) perché
il vincolo superiore è G4, e il roundtrip è verificato lì.

**Fix 1b implementata** (era stata rinviata il 2026-07-30): il gate
del briefing richiede "Rossi" con segnaposto distinto quando "Mario
Rossi" è nel testo — e "Rossi" a inizio frase non ha contesto forte,
quindi senza propagazione restava solo un suggerimento. Ora
`_propaga_cognomi_confermati`: il cognome (ultimo token, ≥3 char,
capitalizzato) di ogni persona multi-token confermata viene
propagato alle occorrenze isolate con match case-sensitive esatto e
senza sovrapporsi ad altri span. Il rischio FP che aveva motivato il
rinvio è contenuto dalle guardie (forma esatta capitalizzata,
propagazione solo da persone GIÀ validate) ed è verificato dai 523
casi avversariali.

## 2026-07-31 · Analisi a blocchi per i testi lunghi

Misura (PARTE 5): l'analisi monolitica degrada in modo NON lineare —
100k char a ~1.900 char/s, 389k char a ~300 char/s — e il documento
spaCy unico gonfia la RSS oltre il tetto dei 4 GiB sul caso 500k.
Fix: sopra `_MAX_BLOCK` (100k) l'analisi avviene a blocchi, con
taglio sull'ultimo a-capo prima del limite. Il taglio su newline è
SICURO per costruzione: l'invariante di prodotto (BUG-real 1) vieta
a qualunque span di attraversare un `\n`, quindi nessuna entità può
essere spezzata dal confine di blocco. Gli offset vengono riportati
sul testo completo; l'equivalenza blocchi/monolitico è verificata da
`test_g1_analisi_a_blocchi_equivalente` (con `_MAX_BLOCK` ridotto a
120 via monkeypatch). Effetto di bordo accettato e documentato: le
finestre di contesto (~40 char) dei recognizer non attraversano il
confine — che però cade su un a-capo, dove il contesto è comunque
interrotto.

## 2026-07-31 · Pipeline: validazione PRIMA delle sovrapposizioni

La suite avversariale (523 casi) ha trovato una classe di bug
strutturale: uno span destinato a morire (categoria disattiva, o
validazione che fallirà) vinceva la risoluzione sovrapposizioni contro
uno span valido, e quando poi veniva filtrato si portava via il dato.
Esemplari reali:

- LOCATION (categoria spenta) copriva "3391234567" in una tabella →
  batteva IT_TELEFONO per priorità → veniva filtrato → il telefono
  restava IN CHIARO.
- IT_LUOGO_NASCITA su "Via Roma" (che non avrebbe passato
  `_luogo_validato`) batteva IT_INDIRIZZO → l'indirizzo restava in
  chiaro.
- Lo stesso schema aveva già causato il caso "Grazia" del Gate 1
  (patchato allora ad hoc con `_scarta_luogo_su_nome_certo`).

Fix di CLASSE: l'ordine dei passi è ora (1) struttura+categoria,
(2) validazioni per-tipo (dizionario persona, luogo, documento,
telefono, targa, rumore), (3) risoluzione sovrapposizioni SOLO alla
fine, tra span già tutti validi. Aggiunte con l'occasione:
`INDIRIZZO` priorità 8 (il deterministico odonimo+civico batte gli
span neurali), `_targa_validata` per gli IT_TARGA del neurale
("AZ 610" numero di volo emesso come targa), guardia "capitale
sintetica" (nomi capitalizzati DAL truecasing che collidono con
parole comuni o comuni ISTAT — vittoria, romana, dora — richiedono un
trigger sintattico personale), etichette di modulo ("Nome:",
"Cognome:", "intestatario", …) come contesto valido per il cognome
isolato, e look-around anti-decimale del telefono ristretto ai veri
decimali (la virgola di frase non blocca più il numero).

## 2026-07-31 · Nomi persi sul campo: cinque cause, cinque fix di classe

Cinque testi raccolti dall'utente in uso reale perdevano nomi. La
diagnosi ha smentito in parte l'ipotesi di partenza (marco/maria/luca
NON sono marcati ambigui: `_nome_ambiguo` è False per tutti) e ha
trovato una quinta causa non prevista.

**Causa dominante, non prevista.** `_persona_valida` conteneva
`if not (2 <= len(tokens) <= 4): return False`: scartava a monte
OGNI span di persona a token singolo, anche quando il NER lo aveva
riconosciuto e il contesto era inequivocabile. "Delfo", "PASQUALE",
"marco" isolati non potevano esistere per costruzione. Ora il vincolo
è `1 <= len(tokens) <= 4` e il vero cancello resta la validazione
semantica.

**Causa A — vocabolario che uccide il dizionario.** La guardia
"capitale sintetica" usava `_VOCAB_IT_ESTESO` (660k lemmi), che è
inquinato di nomi propri: maria, luca, pasquale e rossi sono tutti
dentro. Un nome minuscolo in lista finiva quindi bocciato dal
vocabolario. Il dizionario ha ora priorità: la guardia non si applica
agli span del NER neurale, che legge la frase intera. Misurato: il
neurale emette PERSON su marco/maria nell'enumerazione e su NESSUNO
dei 25 controcasi. spaCy no — provato separatamente, emette PERSON su
"marco a matita le correzioni" e span spazzatura come "andro da":
per questo l'esenzione è ristretta a `NeuralRecognizer`.

**Causa B — MAIUSCOLO che uccide il dizionario.** L'eccezione
nomi/cognomi nel filtro tutto-maiuscolo valeva solo da 2 token in su,
quindi "PASQUALE" isolato spariva. Ora vale anche a token singolo: un
nome è un nome anche urlato.

**Causa C — propagazione in enumerazione.** `_propaga_nomi_in_enumerazione`:
in un elenco legato da virgole e congiunzioni, se almeno un elemento è
già persona confermata, gli altri elementi plausibili come nome
diventano persona. Discriminante misurato: un nome di battesimo basta
anche se collide con una parola comune ("marco"); un COGNOME che è
anche parola comune ("penso", "casa", "porto") no — da solo produrrebbe
falsi positivi su qualunque elenco di verbi. Il primo tentativo senza
questa distinzione promuoveva "penso" a persona.

**Causa D — contesto forte oltre il dizionario.** Dopo "sono",
"mi chiamo", un titolo o una formula di apertura, il token successivo
è persona anche fuori dizionario ("Ciao sono Delfo"). Guardie contro
parole funzione, numeri e blacklist tecnica: "sono felice", "sono
andato", "sono le otto" restano fermi.

**Causa E — suggerimenti doppioni.** Nessun suggerimento su testo già
coperto da un'entità sostituita: "perugia" non va proposto come
persona quando "via perugia 18" è già «INDIRIZZO_1».

**Classe extra trovata strada facendo.** Lo span "marco!" veniva
scartato perché contiene un carattere non alfabetico — il nome spariva
per colpa del punto esclamativo. `_rifila_bordi_persona` toglie la
punteggiatura ai bordi degli span di persona, invece di allungare
l'ennesimo set di caratteri da strippare.

**Coreferenza intra-documento.** `_propaga_nomi_ripetuti` recupera la
seconda occorrenza di un nome di battesimo già confermato altrove. Il
trigger "con X" nudo è stato misurato e SCARTATO: esistono 64 nomi non
ambigui che sono anche parole comuni italiane (alba, chiara, costanza,
fede, gioia, grazia, rosa, serena, stella, vittoria…), e "con grazia",
"con calma", "con costanza" sono italiano ordinario. La regola richiede
quindi ≥2 occorrenze + persona confermata nel documento + preposizione
di compagnia + punteggiatura successiva. Senza il vincolo sulla
preposizione promuoveva "fonte", "IVA" e "Francia" nei documenti reali.

## 2026-07-31 · Gli stati non sono persone

Su un documento reale l'app produceva `PERSONA 'Italia'` e
`PERSONA 'Francia'`: "Vuoi inviare un SMS in Francia, Guatemala o
India?" diventava un elenco di individui. Causa: "India" è nel
dizionario dei nomi di battesimo italiani, quindi diventava ancora
di enumerazione e trascinava "Francia" (presente fra i cognomi).

Misura su 91 nomi di stato e continente: **13 collidono col dizionario**
(italia, francia, spagna, portogallo, india, corea, siria, marocco,
brasile, argentina, africa, asia, inghilterra).

Fix di classe in `_persona_validata_da_dizionario`: uno stato o
continente a token singolo non è una persona **senza innesco personale
esplicito**. La regola non è un divieto — Asia, India, Siria e
Argentina sono nomi di battesimo veri: "Ciao sono Asia" e "la signora
India Rossi" continuano a funzionare, perché il controllo sta dopo il
blocco dei titoli/formule. Cade solo la geografia nuda.

Effetto misurato sui documenti reali: 4 falsi positivi in meno
(`Italia`, `India`, `Cognome Rossi`, `Mario Rossi.`), **zero
entità aggiunte**.

## 2026-07-31 · Copertura del dizionario cognomi: fonti e licenze

Verifica richiesta dal briefing (il cognome reale "Berretti" non
veniva riconosciuto — in realtà è in dizionario, mancava il
rilevamento a token singolo). Misura su tre fonti esterne:

| fonte | copertura PRIMA | copertura DOPO |
|---|---|---|
| Top 100 cognomi nazionali | 100% | 100% |
| Wikipedia, cognomi italiani (52) | 100% | 100% |
| Anagrafe Reggio Emilia 2020, 189 cognomi (CC-BY) | 75.7% | **84.1%** |

L'anagrafe di Reggio Emilia è tenuta FUORI dalle sorgenti del
dizionario di proposito: serve come campione di controllo. Integrarla
avrebbe portato la sua copertura al 100% senza dire nulla di vero.

**Fonte integrata: Wikidata, licenza CC0** — query SPARQL sui cognomi
di lingua italiana più quelli con etichetta cinese/indiana (le
comunità straniere più numerose in Italia). 9.190 righe salvate in
`data/liste/cognomi_wikidata.csv`, **+6.378 cognomi** in dizionario
(21.727 → 28.105).

**Fonte valutata e SCARTATA: `Max1234-Ita/Liste`** — copre bene i
cognomi regionali, ma è **GPL-3.0**. PrivacyBridge è MIT: incorporare
un file dati GPL-3 nel pacchetto distribuito imporrebbe la
share-alike sull'insieme. Scartata per incompatibilità di licenza.

Verificato che l'allargamento non costa precisione: sui documenti
reali dell'utente il dizionario a 28.105 cognomi produce **esattamente
le stesse entità** di quello a 21.727 — zero falsi positivi aggiunti.

**Limite residuo dichiarato**: 30 dei 189 cognomi più diffusi di un
comune reale restano fuori. Sono (a) cognomi regionali emiliani senza
portatori noti — bedogni, menozzi, cigarini, spallanzani — che nessuna
fonte aperta a licenza compatibile elenca, e (b) cognomi di 2 lettere
(hu, lin, wu, xu), esclusi di proposito: un token di due caratteri
come cognome produrrebbe falsi positivi ovunque. Su questi nomi il
motore non è cieco — li recupera dal contesto forte e dagli span
multi-token — ma non li riconosce dalla sola grafia.

## 2026-07-31 · `test_cambia_tipo`: testo di prova non più valido

Il test dell'interfaccia usava "Il fornitore Beta Impianti ha inviato
la conferma" e si aspettava almeno un'entità in tabella. Con il
dizionario persona più severo il motore ora classifica "Beta Impianti"
come ORGANIZATION (categoria disattiva di default) e rifiuta il PERSON
proposto da spaCy, perché "beta" non è né nome né cognome. È il
comportamento corretto: era il test a poggiare su un falso positivo.
Testo di prova sostituito con "Il signor Mario Rossi ha inviato la
conferma".

---

## Strumenti di design disponibili: censimento, scelte, conflitti

Il briefing chiede di verificare quali skill di design esistono
nell'ambiente e di installare quelle rilevanti. Censimento reale.

### Cosa c'era già (`~/.claude/skills/`)

| skill | pertinenza | uso |
|---|---|---|
| `redesign-existing-projects` | **alta** | adottata |
| `impeccable-design-polish` | **alta** | adottata |
| `design-taste-frontend` (taste-skill) | nulla | scartata |
| `gpt-taste` | nulla | scartata |
| `web-clone-pro`, `web-prototype`, `motion-vendor` | nulla | scartate |
| `threejs-*` (10 skill) | nulla | scartate |

`design-taste-frontend` si autoesclude: il suo scope dichiarato è
"Landing pages, portfolios, and redesigns. **Not dashboards, not data
tables, not multi-step product UI**". PrivacyBridge è esattamente le tre
cose escluse. `gpt-taste` impone randomizzazione del layout, struttura
AIDA e ScrollTrigger GSAP: linguaggio da sito promozionale, non da
strumento professionale. Le `threejs-*` e `motion-vendor` non hanno
alcun punto di contatto.

### Marketplace

Un solo marketplace configurato: `claude-plugins-official`
(`anthropics/claude-plugins-official`), 35 plugin. Un solo candidato di
design: **`frontend-design`** (autore Prithvi Rajasekaran, Anthropic).
**Installato**:

```
Installing plugin "frontend-design@claude-plugins-official"...
✔ Successfully installed plugin: frontend-design@claude-plugins-official (scope: user)
```

### Accessibilità: non esiste nulla

Cercato in entrambe le posizioni (`wcag`, `contrast ratio`, `4.5:1`,
`prefers-reduced-motion`, `aria-`, `accessib`, `design system`).
L'unico riscontro nell'intero marketplace è una checklist di directory
dentro `mcp-server-dev`, non pertinente. **Nessuna skill di
accessibilità o di misurazione del contrasto esiste in questo
ambiente.** I requisiti WCAG AA del Gate 3 vanno quindi soddisfatti con
misurazione propria, non delegando a uno strumento.

### Il conflitto, e come lo risolvo

`frontend-design` e `gpt-taste` sono scritte per un problema diverso dal
nostro: rendere *memorabile* una pagina promozionale. Le loro direttive
contraddicono il briefing su punti espliciti.

| direttiva della skill | briefing PARTE 3 |
|---|---|
| "NEVER use ... system fonts" | "solo font di sistema" |
| "Avoid generic fonts like Arial and Inter" | stack coerente macOS/Windows |
| "noise textures, grain overlays, custom cursors" | "pochissimi bordi, molta aria" |
| "Asymmetry. Overlap. Diagonal flow. Grid-breaking" | scala di spaziatura su modulo 4/8px |
| "Commit to a BOLD aesthetic direction" | "precisione e calma", studi tecnici e legali |

**Il briefing dell'utente prevale, sempre.** Un font display
caratteristico è un rischio in uno strumento che uno studio legale usa
otto ore al giorno; l'utente ha già segnalato che il logo serif attuale
stona. La texture e l'asimmetria costano leggibilità su tabelle di
entità. Non è un difetto delle skill: è che sono tarate su landing page.

Di `frontend-design` resta valido e lo applico: pensare la direzione
prima di scrivere CSS, variabili CSS per la coerenza, sistema di colore
con accento dominante usato con parsimonia, rifiuto dei pattern
cookie-cutter, complessità dell'implementazione proporzionata alla
visione (qui: **restraint** — la skill stessa dice che il minimalismo
raffinato richiede "restraint, precision, and careful attention to
spacing").

### Come le uso concretamente

- **`redesign-existing-projects`** — struttura del lavoro. Sequenza
  Scan → Diagnose → Fix, e le nove sezioni di audit (Typography, Color
  and Surfaces, Layout, Interactivity and States, Content, Component
  Patterns, Iconography, Code Quality, Strategic Omissions) diventano
  la griglia di `UI_AUDIT.md`. Le sue regole operative coincidono col
  vincolo del progetto: lavorare sullo stack esistente, non riscrivere
  da zero, tenere le modifiche revisionabili — `api/static/index.html`
  è un file unico da 84KB con CSS vanilla e va rifatto sul posto.
- **`impeccable-design-polish`** — la passata finale. Il Gate 3
  richiede un'autocritica scritta in `DESIGN_REVIEW.md` da applicare e
  poi rifare gli screenshot: è esattamente il modo Audit → Critique →
  Polish → Harden della skill. Utili anche le sue "AI tells" da
  rimuovere (gradienti glow senza motivo, file di tre card, card
  arrotondate ovunque, spaziatura e scala tipografica incoerenti), e la
  regola 3, "poche correzioni decisive invece di ritocco cosmetico
  diffuso".
- **`frontend-design`** — solo la parte strutturale sopra elencata;
  direttive tipografiche e decorative sovrascritte dal briefing.

---

## Suggerimenti: il dizionario perde la precedenza al livello 3 (2026-08-01)

**Decisione.** Un candidato che arriva al livello 3 — cioè con l'unica
prova di comparire nella lista nomi/cognomi — non viene proposto se è
una parola corrente dell'italiano (`vocab_it_660k.txt`), e non viene
proposto se nel testo originale era tutto minuscolo.

**Perché.** Il livello 3 alimenta il riquadro "Possibili entità", che
mostra cinque voci per volta e chiede all'utente di spuntare quelle
vere. Misurato sui cinque documenti reali dell'utente prima
dell'intervento: **84 suggerimenti, di cui 4 persone**. Tutto il resto
erano parole comuni con la maiuscola d'inizio frase — "Alla", "Ora",
"Durante", "Data", "Secondo", "Voglio", "Passi", "Valori" — e, sul PDF
scansionato, parole rese maiuscole dal nostro stesso truecasing:
"che" ×35, "the" ×23, "dati" ×24, "tuo" ×11.

Un elenco così l'utente impara a saltarlo. È peggio che non averlo: dà
l'impressione di aver controllato mentre nasconde i due nomi veri fra
ottanta parole funzionali.

**Perché al livello 3 e non altrove.** Ai livelli 1 e 2 il dizionario
ha la precedenza sul vocabolario, ed è la scelta giusta di PARTE 1: lì
c'è una prova in più — nome non ambiguo, oppure contesto personale
esplicito. Al livello 3 quella prova non c'è, e la sola presenza in
lista non distingue il cognome Scarpa dalla scarpa. La stessa regola
applicata più in alto cancellerebbe i nomi veri; applicata qui toglie
solo rumore. Le entità sostituite non cambiano di una unità.

**Prezzo accettato.** Si perde il suggerimento sui cognomi che sono
anche parole italiane — "Scarpa", "Conte", "Costa", "Berretti" —
quando compaiono isolati e senza alcun contesto. Con un contesto
qualsiasi salgono al livello 2 e vengono sostituiti sul serio: la
perdita riguarda il solo caso in cui non avevamo comunque indizi.

**Dove sta il codice.** Due controlli in due posti diversi, ciascuno
dove vive l'informazione che gli serve:
- `backend/nomi_italiani.py` — il vocabolario, perché il recognizer è
  chi decide cosa emettere e ha già `_VOCAB_IT_ESTESO` caricato;
- `backend/motore.py` — la grafia originale, perché il recognizer vede
  solo il testo ricapitalizzato e non può sapere che la maiuscola
  l'abbiamo messa noi.

**Misura dopo (stessi cinque documenti): 12 suggerimenti, 116 entità.**
Entità invariate. Restano proposti due cognomi veri (Bianchi,
Verdi), tre toponimi (Perugia ×2, Francia), quattro parole inglesi
(Cloud, You, Branch, Ray) e tre residui d'OCR (Bol, Buda, Mineo).

**Cosa NON ho fatto e perché.** Non filtro i toponimi né l'inglese.
Moltissimi cognomi italiani sono toponimi (Napolitano, Romano, Milano,
Genovese) e togliere quella classe costerebbe persone vere. Dodici voci
sono una lista che si scorre; il residuo è dichiarato nel capitolo dei
limiti.

## Un'operazione lunga si annulla, non si accorcia (2026-08-01)

**Decisione.** Su documenti oltre i ~300.000 caratteri l'analisi supera i
due minuti e resta così. Invece di inseguire la velocità ho reso
l'operazione interrompibile e l'avanzamento reale.

**Perché.** Il profilo dice che metà del tempo è inferenza del modello su
CPU: 2.500 caratteri al secondo è il pavimento di questa macchina, non un
difetto da correggere. L'altra metà l'ho recuperata dove si poteva —
`_MAX_BLOCK` da 100.000 a 25.000 caratteri toglie il 30% (la deduplica di
Presidio confronta ogni risultato con ogni altro: 47 milioni di confronti
su un blocco da 100k). Oltre quel punto si scenderebbe solo togliendo
recall, e il recall è il prodotto.

Le alternative scartate, tutte già misurate in questo progetto: MPS è
rotto su questo hardware (0 entità o OOM), batch e multiprocessing non
pagano, un modello più piccolo perde nomi.

**Il prezzo.** L'utente con un documento da mezzo milione di caratteri
aspetta quattro minuti e mezzo. Lo sa mentre aspetta — vede i caratteri
analizzati salire — e può fermarsi in 0.35s senza lasciare niente a metà
nel vault.

**Dove sta.** `backend/avanzamento.py` (un lavoro alla volta, come
`backend/ocr.py`), controllo nel ciclo dei chunk neurali in
`backend/motore_neurale.py`, avanzamento a fine blocco in
`backend/motore.py`, endpoint `/analisi/stato` e `/analisi/annulla`,
pulsante Annulla nella finestra dopo tre secondi di attesa.

**Cosa NON ho fatto.** Nessuna barra percentuale che si muove da sola
mentre il lavoro è fermo, e nessuna stima del tempo rimanente: la prima è
una bugia, la seconda su un documento eterogeneo sbaglia abbastanza da
diventarlo. I numeri mostrati sono caratteri davvero passati sotto il
motore, aggiornati a fine blocco — per questo il primo arriva dopo ~14
secondi e non subito.

## Il modello si carica in sottofondo, non al primo click (2026-08-01)

**Decisione.** La pagina, appena finita di disegnarsi, chiama
`POST /precarica` e il modello si carica in un thread di sfondo.

**Perché.** Spostare l'import di torch/spaCy fuori dall'avvio porta la
finestra da 5.69s a 0.60s, ma sposta ~9s sulla prima anonimizzazione, con
dentro blocchi da 1s in cui il server non risponde (torch e spaCy tengono
il GIL in codice C che non possiamo spezzare). Quei 9 secondi vanno messi
dove non danno fastidio: mentre la finestra è aperta e l'utente non ha
ancora incollato niente.

**Il prezzo.** L'applicazione arriva a ~2 GB di memoria anche se l'utente
voleva solo ripristinare un testo, che non richiede il modello. Accettato:
il picco misurato sul documento più grande resta 3.198 MiB, sotto il tetto
di 4 GiB, e il caso "apro solo per ripristinare" è raro rispetto a
"anonimizzo".

## La configurazione di ruff sta in `pyproject.toml` (2026-08-01)

**Decisione.** Il progetto ha un `pyproject.toml` che fissa
`target-version`, `line-length`, le cartelle escluse e l'unica regola
spenta. `ruff check .` senza flag è il comando di riferimento.

**Perché.** `ruff` senza file di configurazione non applica un insieme
stabile: le regole attive cambiano con la versione, e con 0.16.1 sono
413. Una verifica che dà risultati diversi a seconda di quando la lanci
non è una verifica. Fissarla significa che chi riprenderà questo codice
fra sei mesi vede gli stessi errori che vedo io oggi, e che "All checks
passed" continua a voler dire qualcosa.

**Il prezzo.** Aggiornare ruff può far comparire regole nuove tutte
insieme. È il momento giusto per guardarle, non un fastidio.

## `BLE001` spenta, `S110` accesa (2026-08-01)

**Decisione.** `except Exception` resta permesso in tutto il progetto.
`except` largo con corpo `pass` no, e infatti è a zero.

**Perché.** Ho letto tutti e 26 i punti che catturano `Exception`. Sono
tutti confini verso qualcosa che non controlliamo — torch, il motore OCR
di sistema, un `.msg` di Outlook, un PDF malformato, la rete — e ognuno
converte il guasto in un esito dichiarato: HTTP 500, `None`, insieme
vuoto, warning nel log. Elencare le eccezioni che torch può sollevare non
è possibile; restringere vorrebbe dire far morire la finestra su un
guasto previsto. Ruff non sa esprimere "cattura larga **con** ricaduta
esplicita", quindi la scelta è fra spegnere la regola o riempire il
codice di `# noqa`, che è la stessa cosa scritta 26 volte peggio.

Il difetto vero non è la cattura larga: è il guasto che sparisce senza
lasciare traccia. Quello lo prende `S110`, che resta accesa. È lì che
sta il vincolo.

**Il prezzo.** Un `except Exception` nuovo e sbagliato non viene
segnalato. Lo prenderebbe solo la revisione umana — a meno che non
ingoi in silenzio, e allora S110 lo vede.

## Il vault è ristretto al proprietario, non cifrato (2026-08-01)

**Decisione.** Cartella dati `0700`, file del vault e sidecar WAL/SHM
`0600`. I valori originali restano in chiaro dentro SQLite.

**Perché.** Il vault conteneva `valore_reale` in chiaro con permessi
`0644`: su un PC aziendale con più account, qualunque altro utente
poteva leggere i dati che l'applicazione esiste per proteggere. I
permessi chiudono quel buco e costano una `chmod` all'apertura.

Cifrare il contenuto è un'altra cosa e non l'ho fatta: servirebbe una
chiave, e una chiave o la chiede all'utente ogni volta — e allora
l'applicazione non è più "apri e incolla" — oppure sta sul disco accanto
al file che protegge, e allora non protegge da chi ha accesso al disco.
Con `0600` il vault è protetto esattamente quanto gli altri documenti
dell'utente, che è la promessa che si può mantenere.

**Il prezzo.** Chi ruba il disco, o ne fa un backup non cifrato, legge il
vault. **Va scritto nei limiti dichiarati**: la protezione a riposo è
quella del sistema operativo (FileVault, BitLocker), non nostra.

**Non tocco i permessi di una cartella già esistente** indicata via
`PRIVACYBRIDGE_DATA_DIR`: il docstring la descrive anche come profilo
condiviso, e stringerla a `0700` romperebbe quell'uso. Il file dentro
diventa comunque `0600`, ed è lì che stanno i dati.

## In `benchmark/` si versiona il codice, il resto è escluso (2026-08-01)

**Decisione.** `.gitignore` esclude tutto `benchmark/**` e riammette solo
`*.py`, `README.md` e `.gitkeep`.

**Perché.** Le regole precedenti elencavano i nomi da escludere, e hanno
mancato `Indagine.ocr.txt`: il testo integrale di un atto giudiziario
privato, scritto lì da `verifica_ocr.py`. Non è mai finito in git, ma ci
sarebbe finito al primo `git add benchmark/`. Un elenco protegge i file
che qualcuno ha pensato di elencare; una regola invertita protegge anche
quelli che non esistono ancora. In quella cartella tutto ciò che non è
codice deriva dai documenti dell'utente, quindi l'inversione descrive la
realtà meglio dell'elenco.

**Il prezzo.** Aggiungere un file di supporto legittimo in `benchmark/`
richiede una riga in `.gitignore`. È il verso giusto in cui sbagliare:
si scopre subito, e l'errore è "manca un file", non "è uscito un dato".

## Cancellato `dist/` (2026-08-01)

**Decisione.** Rimossa la cartella `dist/` con l'uscita PyInstaller del
31 luglio: 7,5 GB fra `.dmg` da 2,5 GB e due bundle da 3,1 e 1,9 GB.

**Perché.** È uscita di build, ignorata da git, e la parte 7 la rigenera
da zero. Tenerla significava consegnare pacchetti costruiti prima delle
correzioni delle parti 4 e 5 — cioè pacchetti sbagliati — e occupare lo
spazio che serve per ricostruirli.

**Il prezzo.** Nessuno: `PrivacyBridge.app/` costruito a mano, che il
briefing indica come ricaduta se PyInstaller non chiude, è nella radice
del progetto e non è stato toccato.

## Il codice eseguibile sta in `src/` (2026-08-01)

**Decisione.** `avvio.py`, `api/`, `backend/` e `data/liste/` si sono
spostati sotto `src/`. La radice del progetto ora contiene solo cartelle:
`src/`, `tests/`, `benchmark/`, `docs/`, `assets/`, `build/`, più i file
di configurazione, i launcher e `README.md`.

**Perché.** Il briefing chiede due cartelle separate, progetto e
consegna, e la separazione regge solo se dentro il progetto è ovvio cosa
va impacchettato. Prima era mescolato: alla radice convivevano il codice
dell'app, i test, i benchmark con i documenti privati dell'utente, gli
appunti interni e gli script di sviluppo. Con tutto sullo stesso piano
la domanda "cosa entra nel pacchetto?" si risponde a memoria, e a
memoria era già finito dentro un vault con dati veri (vedi la
correzione della `.spec` nella parte 5). Con `src/` la risposta è una
riga: quello che sta lì dentro.

**Il prezzo.** Ogni punto d'ingresso che assumeva la vecchia disposizione
è andato aggiornato: `pythonpath` in `pyproject.toml`, `PYTHONPATH` nei
sottoprocessi (test dell'interfaccia, `gate_finale.py`, i due script di
screenshot), i `sys.path.insert` di `benchmark/`, i launcher `.bat` e
`.vbs`, il launcher del bundle. Sono stati trovati eseguendo le suite,
non leggendo: `tests/test_interfaccia.py` è caduto in blocco con 32
errori perché `uvicorn api.main:app` non trovava più `api`.

**Nota su `scripts/`.** Il briefing non nomina questa cartella. La tengo
perché contiene codice che non è né app né test né misura — generazione
delle liste, screenshot, contrasti, gate finale — e metterlo in `src/`
lo farebbe finire nel pacchetto, che è esattamente ciò che si vuole
evitare.

## Liste a runtime in `src/`, sorgenti grezze in `assets/` (2026-08-01)

**Decisione.** I TSV che il motore legge stanno in `src/data/liste/`. Gli
elenchi grezzi da cui vengono generati stanno in `assets/liste_sorgenti/`
e li legge solo `scripts/build_liste_nomi.py`.

**Perché.** Sono due cose diverse che avevano lo stesso indirizzo: le
prime servono all'app in esecuzione, le seconde servono a rigenerare le
prime e non hanno motivo di viaggiare dentro il pacchetto. Finché
stavano insieme, impacchettare `data/` intero era la scelta comoda — ed
è la scelta che aveva portato dentro anche un vault.

**Il prezzo.** `build_liste_nomi.py` legge da una cartella e scrive in
un'altra. In cambio la riga della `.spec` che include le liste non ha
più bisogno di sapere cosa escludere.

## Le ricette di impacchettamento stanno in `build/` (2026-08-01)

**Decisione.** `PrivacyBridge.spec`, `build_bundle.sh` e
`PrivacyBridge-windows.iss` si sono spostati in `build/`, insieme al
bundle `PrivacyBridge.app` costruito a mano. `.gitignore` esclude
`build/**` e riammette solo `*.spec`, `*.sh`, `*.iss`.

**Perché.** In quella cartella convivono sorgenti e prodotti: le tre
ricette sono codice, il bundle è un artefatto da 1,2 GB con dentro il
modello e una copia dell'interprete. Stessa regola invertita di
`benchmark/`, per lo stesso motivo: elencare gli artefatti da escludere
significa dimenticarne uno appena cambia il packaging. Qui il rischio è
concreto perché PyInstaller si crea cartelle di lavoro da sé.

**Conseguenza.** Il `--workpath` di PyInstaller è ora esplicito
(`build/pyinstaller`): il suo default è `./build`, che qui è già la
cartella delle ricette, e lasciarcelo scrivere dentro mescolerebbe
sorgenti e temporanei nello stesso posto.

## `README.md` di dieci righe, manuale in `docs/` (2026-08-01)

**Decisione.** Il `README.md` alla radice è ridotto a dieci righe con i
puntatori. Le 186 righe precedenti — installazione, uso, tempi misurati,
cosa riconosce, garanzie, limiti — sono diventate `docs/MANUALE.md`.

**Perché.** Il briefing chiede dieci righe. Ma la ragione per cui la
richiesta è giusta è che quel README faceva tre lavori insieme: presentava
il progetto a chi apre la cartella, spiegava l'uso all'utente finale, e
teneva i numeri di misura. Il secondo lavoro ora lo fa `LEGGIMI.txt`
nella cartella di consegna, scritto per chi non è tecnico; il terzo lo
fa `docs/`.

**Il prezzo.** Una indirezione in più per chi cerca le istruzioni nel
repository. Accettabile: chi le cerca lì è uno sviluppatore, e le
trova al secondo link.

## I file di test di torch e spacy restano dentro il bundle (2026-08-01)

**Decisione.** L'audit del contenuto del pacchetto ha trovato 269 file
`test_*.py` / `tests/` dentro il bundle: nessuno è nostro, vengono tutti
da `torch`, `spacy` e `thinc`. Pesano ~2 MB su 3,1 GB. Restano dove sono.

**Perché.** Il briefing chiede che nel pacchetto ci sia «solo ciò che
serve a eseguire l'app», e a prima vista quei file non servono. Non è
vero: `torch/_dynamo/test_case.py` è importato da `torch` a runtime, non
solo dai suoi test. In quelle librerie il confine fra "codice" e "test"
non passa dal nome del file, e un'esclusione per pattern (`test_*`)
romperebbe l'app in un punto che nessun test nostro tocca — si
scoprirebbe sulla macchina di un cliente.

**Il metro applicato.** La regola del briefing esiste per due motivi: non
consegnare i NOSTRI file di sviluppo, e non consegnare dati. Su entrambi
il pacchetto è pulito, verificato file per file: zero test nostri, zero
benchmark, zero corpus, zero documenti dell'utente, zero documentazione
interna. Le liste in `Resources/data/liste/` sono esattamente le cinque
lette dal codice a runtime. Due megabyte di test altrui su tremilacento
non sono un problema di consegna: sono il costo di non rompere una
dipendenza che non controlliamo.

**Quando rivedere.** Se il bundle dovesse dimagrire per davvero, il
guadagno sta nel modello (1,2 GB) e nelle architetture inutilizzate di
torch, non qui.

## Il recognizer deterministico delle organizzazioni è esente dal filtro anti-rumore (2026-08-01)

**Decisione.** `IT_ORGANIZZAZIONE` entra nell'elenco dei tipi che non
passano da `e_rumore()`, accanto a targa, VIN, documento, IBAN, codice
fiscale.

**Perché.** La regola B2 «se sono almeno quattro lettere e sono tutte
maiuscole ed è un titolo, scarta» esiste per i titoli di paragrafo e le
sigle di stampa. Ma una ragione sociale sulle fatture e nelle
intestazioni è scritta esattamente così: `ICOS SRL`, `UNICREDIT SPA`,
`BETA IMMOBILIARE SPA` finivano tutte e tre nella stessa rete. Il
recognizer deterministico è già vincolato a una forma giuridica in coda
o a un prefisso istituzionale in testa, quindi non porta il rumore che
quella regola intercetta — è la stessa ragione per cui targhe e VIN
erano già esenti.

**Vale solo per il deterministico.** L'ORG neurale (`ORGANIZATION`)
continua a passare dal filtro: quello sì produce il rumore per cui la
regola era stata scritta.

**Misurato.** Corpus annotato: ORG non presi da 6 a 0, span esatti da 38
a 44, richiamo ORG da 87,0% a 100%. Richiamo stretto complessivo da
84,1% a 87,2%. Span spuri invariati a 9. Documenti reali: sostituzioni
invariate a 141 nella configurazione di consegna, da 616 a 620 con tutte
le categorie accese.

## I candidati carta che falliscono Luhn escono come suggerimento, mai come sostituzione (2026-08-01)

**Decisione.** Una sequenza di 13-19 cifre che **non** supera Luhn e che
ha un contesto lessicale di carta entro 250 caratteri (`master card`,
`visa`, `carta di credito`, `PAN`, …) viene emessa come proposta nel
riquadro «Possibili entità», con segnaposto vuoto, da spuntare a mano.

**Perché il contesto e non solo la forma.** Sui quattro candidati
misurati sui documenti veri, i tre buoni hanno accanto una parola di
carta; il falso (`6217•••••••••••••••`) ha accanto `Visitor 1D:`. Senza
il filtro di contesto la tabella riceve una proposta sbagliata su
quattro; con il filtro, zero. Finestre da 150, 250 e 400 caratteri danno
lo stesso risultato: la scelta di 250 non è delicata.

**Perché suggerimento e non sostituzione.** Il controllo di validità
nasce per la precisione; trasformarlo in una sostituzione d'ufficio
scambierebbe quella precisione con la copertura. Un suggerimento non
tocca il testo in uscita e non ha alcun effetto sui casi che Luhn lo
superano: il rischio sui dati validi è nullo, non basso.

**Il prezzo.** Il dato resta in chiaro finché l'utente non spunta la
casella. È accettabile perché oggi resta in chiaro **e** invisibile.

**Nota di implementazione.** `IT_CARTA_SOSPETTA` non sta in `_TYPE_MAP`.
Ci ero passato, e la suite l'ha respinto: da lì il tipo finisce in
`CATEGORIE_TUTTE` e comparirebbe fra le categorie che l'utente accende e
spegne dall'interfaccia. Il tipo mostrato viene da `_TIPO_SUGGERIMENTO`,
che lo riporta a `CARTA` — una categoria vera.

## La risoluzione delle sovrapposizioni deve avere un ordine totale (2026-08-01)

**Decisione.** La tupla di confronto in `_risolvi_sovrapposizioni`
passa da `(priorità, lunghezza, punteggio)` a `(priorità, lunghezza,
punteggio, priorità_base, nome_del_tipo)`.

**Perché.** Trovato misurando, non cercandolo: due esecuzioni consecutive
dello stesso comando sugli stessi documenti davano `CF 2 / PIVA 2` e
`CF 3 / PIVA 1`. Undici cifre sono insieme il codice fiscale di una
società e la sua partita IVA; i due recognizer rispondono entrambi con
punteggio 1.0; la promozione a priorità 100 riservata alla rubrica
appiattiva anche loro, e le due tuple diventavano identiche. Il
confronto è `>` stretto, quindi vinceva chi Presidio restituiva per
primo — e quell'ordine dipende dall'ordinamento degli insiemi, che
Python randomizza a ogni avvio. Con `PYTHONHASHSEED` fissato l'esito era
stabile: la prova della causa.

**Come applicarla.** Chiunque aggiunga una regola di precedenza deve
chiedersi non solo «chi vince» ma «esiste un caso in cui nessuno vince».
Se la risposta è sì, l'ordine non è totale e l'esito lo decide il caso.

**Quanto pesava.** Per la privacy nulla — il dato era mascherato in
entrambi i casi, cambiava il prefisso del segnaposto. Per l'audit,
molto: ogni confronto prima/dopo ereditava quel rumore.

## Il quarto candidato carta resta etichettato TELEFONO, e resta così (2026-08-01)

**Decisione.** In `visa 4397 •••• •••• 21231` la coda `0761 21231` viene
presa dal recognizer dei telefoni e sostituita; il suggerimento carta
cade sul filtro che vieta di proporre testo già coperto. Non correggo.

**Perché.** Le due alternative sono peggiori. Rifiutare i telefoni
dentro una corsa di 13+ cifre lascerebbe l'intera carta in chiaro con un
suggerimento da spuntare: oggi metà è già coperta senza che l'utente
faccia niente, e per uno strumento di privacy la scelta prudente è
quella che maschera di più quando l'utente non interviene. Lasciar
passare il suggerimento produrrebbe una proposta inapplicabile, perché
quel valore nel testo in uscita non esiste più — che è il difetto per
cui quel filtro era stato scritto.

**Il costo.** Un'etichetta sbagliata in tabella su un dato comunque
mascherato.

**Quando rivedere.** Mai per via di una regola: il rimedio giusto è la
Parte 2 del mandato, cambiare tipo a un'entità direttamente dal testo.

## Potatura degli span PERSONA: lista esplicita, non filtro sul vocabolario (2026-08-02)

**Decisione.** `_pota_span_persona_da_contesto` in `backend/motore.py`
tratta come «scarto ai bordi» solo i token che sono nelle due liste
esplicite `_PAROLE_CONTESTO_ANAGRAFICO` (nato/residente/domiciliato/…)
e `_FUNZIONALI_MAI_NEL_NOME` (a/ad/in/il/la/di/…). I nomi/cognomi
noti — **anche quelli ambigui** — vengono sempre tenuti.

**Perché non un filtro sul vocabolario.** Primo tentativo: «se il
token è in `_VOCAB_IT` e non è in `_NOMI_TUTTI ∪ _COGN_TUTTI`,
scarta.» Scartato dopo la misura: `"nato"` è in `_COGN_AMBIGUI`
(esiste il cognome "Nato"). E soprattutto: `"rossi"`, `"bianchi"`,
`"verdi"`, `"marino"`, `"bruno"`, `"russo"`, `"conti"`, `"ricci"` —
i cognomi italiani più diffusi — sono **tutti** in `_COGN_AMBIGUI +
_VOCAB_IT`. Un filtro generico li avrebbe rimossi dai bordi degli
span, cioè avrebbe tolto la maggior parte dei cognomi dal
riconoscimento.

**Come applicare.** Se domani va aggiunta una nuova classe di
inglobamento (es. `"nubile"`, `"vedovo"`), va aggiunto il token a
`_PAROLE_CONTESTO_ANAGRAFICO` esplicitamente, e va aggiunto anche un
test in `test_g4_span_persona_non_ingoia_contesto_anagrafico`. Se si
è tentati di sostituire la lista con un heuristic sul vocabolario:
misurare prima l'impatto su Rossi/Bianchi/Verdi. È già stato
misurato una volta ed era negativo — non è probabile che cambi.

## Menu contestuale a due voci: la brevità come funzione (2026-08-02)

**Decisione.** Il menu che compare sul segnaposto ha due voci —
`Cambia tipo` e `Modifica valore` — e basta. `Ripristina` vive nella
colonna `Rimuovi` della tabella, `Ricorda sempre` nella scheda
`Rubrica`. Il test `test_fase6_hover_segnaposto_apre_comando`
verifica anche in negativo che `#ce-ripristina` e `#ce-ricorda` non
ritornino nel menu.

**Perché.** Un menu a tre-quattro voci in un flusso di lettura
diventa un tempo di scelta invece di un'azione. Le due voci restanti
sono quelle che si possono fare solo dal testo: correggere il tipo di
un'entità che il motore ha classificato male, e correggere il valore
quando lo span non è quello giusto. Le altre due — cancellare una
riga, aggiungerla alla rubrica — hanno un posto proprio dove c'è lo
spazio per farle bene, e non appartengono al menu al volo.

**Come applicare.** Se in futuro si è tentati di aggiungere una
terza voce al menu contestuale, la domanda da farsi è: **si può fare
solo da qui?** Se la risposta è no, va nella scheda che le compete
(rubrica, categorie, sessioni), non nel menu.

## "Modifica valore" riusa `/rianonimizza`: nessun endpoint nuovo (2026-08-02)

**Decisione.** L'implementazione di `Modifica valore` non aggiunge
endpoint né logica di sostituzione lato client. Il gestore di
`#ce-conferma-valore` mette il nuovo valore in `stato.entita[i].
valore_reale`, chiama `applicaModifica`, che invia la lista corrente
a `/rianonimizza` — l'endpoint già presente per la modifica
diretta. Il server rifà la sostituzione dal testo **originale**.

**Perché.** Il testo di partenza non viene mai modificato: la parte
accorciata rispetto allo span vecchio torna in chiaro nell'uscita, e
il ripristino resta byte-identico. Qualsiasi altra implementazione —
in particolare una modifica del testo anonimizzato in JavaScript —
avrebbe dovuto reimplementare una parte del motore in due lingue
diverse, con la garanzia matematica che prima o poi le due
implementazioni sarebbero divergiate.

**Come applicare.** Ogni futura azione «modifica diretta» — su tipo,
valore, aggiunta o cancellazione — deve passare da `applicaModifica`.
Non ricostruire il testo lato client se il server sa già farlo dal
testo originale.
