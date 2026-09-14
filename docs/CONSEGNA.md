# CONSEGNA — PrivacyBridge 1.0

Data: 2026-08-01. Sessione conclusiva. Questo documento è il resoconto
di consegna: cosa c'è, quanto è stato misurato davvero, e — nel
capitolo 9 — cosa il prodotto **non** copre.

Hardware di misura: Intel i7-8750H, macOS 15 (Darwin 24.6.0), CPU
only. Ogni numero in questo documento viene da un comando eseguito su
questa macchina; nessuno è stimato.

Documenti precedenti: `CONSEGNA_2026-07-29.md`, `CONSEGNA_2026-07-31.md`.

1. [Le due cartelle](#1-le-due-cartelle)
2. [Che cosa fa](#2-che-cosa-fa)
3. [Verifica finale](#3-verifica-finale)
4. [Tempi reali misurati](#4-tempi-reali-misurati)
5. [Documenti reali dell'utente](#5-documenti-reali-dellutente--file-per-file)
6. [Interfaccia: schermate e contrasti](#6-interfaccia--schermate-e-contrasti)
7. [I pacchetti](#7-i-pacchetti)
8. [Installazione](#8-installazione-istruzioni-per-lutente-finale)
9. [**Capitolo finale onesto — cosa NON copre**](#9-capitolo-finale-onesto--cosa-privacybridge-non-copre)

---

## 1. Le due cartelle

### `~/Desktop/PrivacyBridge/` — il progetto

```
PrivacyBridge/
├── src/                    codice eseguibile
│   ├── avvio.py            punto d'ingresso (finestra pywebview)
│   ├── api/                FastAPI + interfaccia (static/index.html)
│   ├── backend/            motore, NLP, OCR, documenti, vault, rubrica
│   └── data/liste/         le 5 liste lette a runtime
├── tests/                  8 suite, 861 test
├── benchmark/              misure su documenti reali (documenti_utente/ esclusa da git)
├── docs/                   MANUALE, CONSEGNA, DECISIONI, BLOCCHI, PROGRESSO, screenshots/
├── assets/                 sorgenti grezze delle liste, icone
├── build/                  ricette di impacchettamento (.spec, .sh, .iss)
├── scripts/                utilità di sviluppo (gate, screenshot, contrasti, liste)
├── README.md               dieci righe
├── LICENSE  NOTICE.txt     MIT + licenze delle dipendenze
├── pyproject.toml          configurazione di ruff e pytest
├── requirements.txt
├── verifica_tutto.sh / .bat
└── PrivacyBridge.vbs / .bat   launcher Windows da sorgente
```

### `~/Desktop/PrivacyBridge-App/` — la consegna

```
PrivacyBridge-App/
├── LEGGIMI.txt          6.416 byte — istruzioni per chi non è tecnico
└── PrivacyBridge.dmg    2.517.917.588 byte (2,3 GB)
```

`PrivacyBridge-Setup.exe` **non c'è**. Il motivo è al § 7.3 e nel
`LEGGIMI.txt` stesso, dichiarato all'utente e non taciuto.

---

## 2. Che cosa fa

L'utente ha un documento con dentro nomi di clienti, IBAN, codici
fiscali, recapiti, e vuole farlo leggere a ChatGPT, Claude o Gemini.
PrivacyBridge sostituisce quei dati con segnaposto:

```
Il sig. Mario Rossi, IBAN IT60X0542811101000000123456
                    ↓
Il sig. «PERSONA_1», IBAN «IBAN_1»
```

Il testo con i segnaposto va all'assistente AI; la risposta torna in
PrivacyBridge e il ripristino rimette i valori veri **byte per byte**.
L'assistente non ha mai visto i dati reali, e niente esce dal computer:
il modello di riconoscimento gira in locale, anche senza connessione.

Formati letti: PDF (anche scansionati, con OCR di sistema), Word,
Excel, e-mail, testo semplice, e altri.

Tipi riconosciuti oggi: persone, luoghi e date di nascita, IBAN, codici
fiscali, partite IVA, e-mail, telefoni, targhe, VIN, dati catastali,
numeri di pratica (R.G., sentenze, protocolli, polizze, fatture),
documenti d'identità, handle social, carte di pagamento, indirizzi.
Le organizzazioni sono riconosciute ma disattivate per impostazione
predefinita (§ 9.3).

## 3. Verifica finale

### 3.1 `verifica_tutto.sh` — output completo in `verifica_tutto_output.txt`

```
----------------------------------------------------------------
Riepilogo
----------------------------------------------------------------
  backend    : rc=0  tempo=89.3s
  tassonomia : rc=0  tempo=14.4s
  avversarial: rc=0  tempo=49.9s
  matrice    : rc=0  tempo=558.9s
  documenti  : rc=0  tempo=169.0s
  garanzie   : rc=0  tempo=83.0s
  interfaccia: rc=0  tempo=95.9s
  bundle     : rc=0  tempo=26.1s
  totale     : tempo=1087.0s
----------------------------------------------------------------
STATO: OK — tutte le suite passate.
```

Che cosa c'è dentro ciascuna riga:

| Suite | Esito | Copre |
|---|---|---|
| backend | `132 passed, 1 xpassed` | motore, documenti, OCR |
| tassonomia | `69 passed` | i recognizer deterministici, uno per tipo di dato |
| avversariale | `606 passed` | casi generati sistematicamente, non scelti a mano |
| matrice input | `MATRICE: 22/22 esiti conformi` | formato × struttura × grafia × lingua × dimensione × qualità |
| documenti | `141 sostituzioni su 8 file`, precisione 100% sugli annotati, 0 veri persi | i PDF veri dell'utente (§ 5) |
| garanzie | `21 passed` | le sei garanzie di prodotto |
| interfaccia | `32 passed` | Playwright, l'app vera in Chromium headless |
| bundle | `/health = {"status":"ok","versione":"1.0.0"}` | l'app impacchettata si avvia e risponde |

**Totale: 860 test passati + 1 xpassed.** L'unico `xfail` è documentato
(truecasing di `"luca lo bianco"`, BLOCCHI.md § 10) e resta un limite
scelto, non un test rotto.

La riga del bundle merita una nota: la verifica prova
`dist/PrivacyBridge.app`, cioè **il binario dentro il `.dmg` che riceve
l'utente**, non il codice di sviluppo. Fino a oggi puntava al bundle
montato a mano in `build/`; l'ho corretto perché una verifica che
controlla un artefatto diverso da quello consegnato non verifica la
consegna.

### 3.2 Gate finale — `scripts/gate_finale.py`

Eseguito **avviando il bundle**, non il server di sviluppo. Testo
canonico del briefing, quello con nove nomi di cui cinque in minuscolo
e uno tutto maiuscolo.

```
[gate] avviato bundle pid=56374
[gate] server pronto in 0.5s (soglia gate: 5s)
[gate] anonimizza in 12.2s
[gate] OK tipi riconosciuti: ['DATA_NASCITA', 'EMAIL', 'IBAN', 'LUOGO_NASCITA', 'PERSONA', 'PIVA', 'TARGA', 'TELEFONO']
[gate] OK tutti i 9 nomi sostituiti: ['Delfo Berretti', 'marco', 'giovanni', 'maria', 'luisa', 'fiorella', 'luca', 'PASQUALE', 'Berretti']
[gate] OK targa FG771XD sostituita
[gate] OK 'Delfo Berretti' → «PERSONA_1», 'Berretti' → «PERSONA_9» (correlato_a=«PERSONA_1»)
[gate] OK correzione in tabella (ORG aggiunta a mano) applicata
[gate] OK ripristino byte-identico (dopo la correzione)
[gate] OK PDF scansionato caricato in 24s — 30252 char, pagine OCR: [3, 10, 11, 12, 13, 15, 16, 23, 24, 25]
[gate] OK PDF legale: 67 entità in 27s, roundtrip byte-identico
[gate] OK tema chiaro → scuro, contenuto invariato
[gate] OK screenshot 04/05/06/07 generati

============================================================
GATE FINALE: OK
============================================================
  avvio server: 0.5s
  anonimizza:   12.2s
  tipi:         ['DATA_NASCITA', 'EMAIL', 'IBAN', 'LUOGO_NASCITA', 'PERSONA', 'PIVA', 'TARGA', 'TELEFONO']
  entità:       16
  ripristino:   byte-identico ✓
```

I punti che il briefing chiedeva esplicitamente, e come sono andati:

- **finestra entro 5 secondi** → 0,5 s;
- **tutti i nomi**, compresi `marco`, `maria`, `luca` minuscoli e
  `PASQUALE` maiuscolo → 9 su 9;
- **`Berretti` distinto da `Delfo Berretti`** → «PERSONA_9» contro
  «PERSONA_1», legati da `correlato_a` così che l'utente veda che sono
  la stessa persona senza che il segnaposto li confonda;
- **correzione di un'entità in tabella** → aggiunta a mano
  un'organizzazione, riapplicata;
- **ripristino byte per byte dopo la correzione** → identico;
- **stesso giro sul PDF legale scansionato** (25 pagine, 10 rilette
  dall'OCR) → 67 entità, roundtrip identico;
- **stesso giro cambiando tema chiaro → scuro** → contenuto invariato.

Ciò che resta fuori da questo gate, e va detto: il doppio click
sull'icona nel Finder. Il gate avvia il bundle come processo e pilota
l'interfaccia vera, ma "una persona che clicca l'icona sulla sua
scrivania" non è riproducibile da uno script (BLOCCHI.md § 5 e § 13).

### 3.3 Analisi statica

```
$ ./venv/bin/ruff check .
All checks passed!
```

## 4. Tempi reali misurati

Sorgente: `benchmark/prestazioni_output.txt`, misura pulita su CPU.
Nessun numero è stimato o interpolato.

### 4.1 Avvio

| | |
|---|---|
| Avvio a freddo, API pronta (3 tentativi) | 0,58 / 0,47 / 0,50 s — **peggiore 0,58 s** (soglia 5 s) |
| Caricamento del motore neurale | 9,48 s, RSS da 27 a 2.134 MiB |

Il caricamento del modello è pagato **una volta sola e in sottofondo**,
non all'avvio: la finestra compare in mezzo secondo.

### 4.2 Documenti reali — tempo per documento

| Documento | Caratteri | Estrazione | Anonimizza | Ripristino | Entità | RSS MiB |
|---|---|---|---|---|---|---|
| Analisi Sangue … glutine.pdf | 1.583 | 0,4 s | 1,0 s | 0,001 s | 8 | 2.609 |
| Hetepi_Agent_AI.pdf | 90.696 | 3,4 s | 34,4 s | 0,023 s | 4 | 2.912 |
| Indagine .pdf (OCR, 10 pagine) | 30.252 | **21,6 s** | 14,3 s | 0,007 s | 67 | 3.198 |
| Portafoglio_Intelligence.pdf | 46.382 | 1,9 s | 19,5 s | 0,013 s | 1 | 3.198 |
| Atto_giudiziario.pdf | 47.782 | 3,2 s | 28,4 s | 0,018 s | 36 | 3.198 |
| hetepi_simulato.txt | 1.637 | 0,0 s | 1,0 s | 0,003 s | 7 | 3.198 |
| rizzo-pii-report.pdf | 26.516 | 2,3 s | 14,2 s | 0,009 s | 15 | 3.198 |

Ogni riga verifica anche il **ripristino identico byte per byte**.
Il ripristino è sempre sotto i 25 millesimi di secondo: è una
sostituzione di stringhe, non un'analisi.

L'estrazione di `Indagine .pdf` costa 21,6 s contro i 2-3 s degli altri
perché dieci pagine vanno rilette dall'OCR: **~2 s per pagina
scansionata**, ed è tempo che si paga solo su quel tipo di documento.

### 4.3 Curva di scala

| Caratteri | Anonimizza | Caratteri/s | Ripristino | RSS MiB |
|---|---|---|---|---|
| 100.000 | 55,0 s | 1.818 | 0,044 s | 3.198 |
| 500.000 | 278,2 s | 1.797 | 0,174 s | 3.198 |

Il throughput è **lineare** (1.818 → 1.797 c/s, −1,2% a cinque volte la
taglia) e la memoria non cresce: è l'effetto dell'analisi a blocchi.
Prima di quel lavoro, un documento da 389k degradava a ~300 c/s con
6,1 GiB di RSS.

Regola pratica per l'utente: **~30 secondi ogni 50.000 caratteri**,
cioè circa 25 pagine.

### 4.4 Requisiti verificati

```
memoria sotto 4096 MiB      OK — picco 3198 MiB
finestra entro 5s           OK — peggiore 0.58s
oltre 120s interrompibile   OK — si ferma in 0.35s
operazione più lunga misurata: 278.2s
```

L'annullamento è stato provato davvero, non dichiarato: su un documento
da 500.000 caratteri, interrotto a 30 s, l'operazione si ferma in
**0,35 s** e restituisce esito `annullata`. Durante l'analisi il server
resta reattivo: 387 chiamate a `/health` durante un'analisi da 90k
caratteri, mediana **1 ms**, peggiore **27 ms**.

## 5. Documenti reali dell'utente — file per file

Otto documenti veri, forniti dall'utente, mai scritti da me. Sorgente:
`benchmark/documenti_utente_output.txt`, rigenerato da
`python -m benchmark.utente` dentro `verifica_tutto.sh`. La cartella
`benchmark/documenti_utente/` è esclusa da git e da ogni pacchetto.

| # | File | KB | Caratteri | Sostituzioni |
|---|---|---|---|---|
| 1 | Analisi Sangue … verifica glutine.pdf | 132,2 | 1.583 | 8 |
| 2 | Hetepi_Agent_AI.pdf | 187,4 | 90.696 | 4 |
| 3 | Indagine .pdf (25 pagine scansionate) | 3.310,3 | 30.252 | 67 |
| 4 | Portafoglio_Intelligence.pdf | 66,7 | 46.382 | 1 |
| 5 | README.md | 2,1 | 2.085 | 3 |
| 6 | Atto_giudiziario.pdf | 773,5 | 47.782 | 36 |
| 7 | hetepi_simulato.txt (annotato) | 1,6 | 1.637 | 7 |
| 8 | rizzo-pii-report.pdf | 9.153,0 | 26.516 | 15 |
| | **Totale** | | **247.000 ca.** | **141** |

```
TOTALE: 141 sostituzioni su 8 file (1 annotati, 7 non annotati)
Precisione (solo file annotati): 100.0%  (7 veri / 7 emessi)
Veri persi (sfuggiti al motore): 0
```

Come leggere questi numeri, onestamente:

- **Solo il file 7 è annotato**, cioè solo lì esiste una verità di
  riferimento contro cui calcolare precisione e richiamo in modo
  automatico: 7 dati veri su 7, zero rumore, zero persi.
- Sugli altri sette la precisione **non** è calcolabile
  automaticamente. Per il file 3 — il caso peggiore, un PDF interamente
  scansionato — l'ho controllata a mano, entità per entità: i numeri
  stanno al § 9.3 e non sono lusinghieri.
- Il file 4 (46.382 caratteri, **1 sola sostituzione**) e il file 2
  (90.696 caratteri, **4**) sono la prova che il rumore sui documenti
  tecnici resta praticamente a zero: un motore che "vede nomi ovunque"
  qui ne avrebbe prodotti decine.
- Il file 6 è un atto d'appello reale: 36 sostituzioni su 47.782
  caratteri — e-mail e PEC, persone, P.IVA, CAP, due numeri di ruolo
  generale (categoria PRATICA), telefoni.

## 6. Interfaccia — schermate e contrasti

### 6.1 Screenshot: ogni schermata, nei due temi

Rigenerati con `python scripts/screenshot_ui.py` contro l'interfaccia
corrente. In `docs/screenshots/`:

| # | Schermata | Chiaro | Scuro |
|---|---|---|---|
| 1 | Avvio, nessun contenuto | `chiaro_1_vuoto.png` | `scuro_1_vuoto.png` |
| 2 | Anonimizzato: due pannelli, tabella entità | `chiaro_2_anonimizzato.png` | `scuro_2_anonimizzato.png` |
| 3 | Scheda Ripristina con testo ripristinato | `chiaro_3_ripristina.png` | `scuro_3_ripristina.png` |
| 4 | Dialogo "Cosa anonimizzare" | `chiaro_4_categorie.png` | `scuro_4_categorie.png` |
| 5 | Dialogo "Rubrica personale" | `chiaro_5_rubrica.png` | `scuro_5_rubrica.png` |
| 6 | Dialogo "Informazioni & aggiornamenti" | `chiaro_6_informazioni.png` | `scuro_6_informazioni.png` |

Più le quattro del gate finale, prese durante l'esecuzione sul bundle:
`04_gate_finale_anonimizza.png`, `05_gate_finale_ripristina.png`,
`06_gate_finale_scuro_anonimizza.png`,
`07_gate_finale_scuro_ripristina.png`.

**Nota di metodo.** Le dodici schermate erano state prese ieri sera alle
22:46; `index.html` è stato modificato stamattina alle 09:30. Erano
quindi immagini di una versione che non è quella consegnata. Le ho
rigenerate (11:46) e riguardate una per una: se avessi allegato le
vecchie, la prova sarebbe stata falsa proprio nel documento che dice di
non fidarsi delle dichiarazioni senza prova.

Gli screenshot vengono da Chromium headless sulla stessa UI servita
dall'app: identici alla finestra pywebview, che è un WebView sullo
stesso HTML. Manca — ed è dichiarato in BLOCCHI.md § 5 — la
fotografia dell'app aperta come applicazione macOS con menubar e dock.

### 6.2 Contrasti misurati

Non stimati: `scripts/misura_contrasti.py` legge le variabili colore
direttamente da `src/api/static/index.html` (non da una copia a mano,
che si disallineerebbe) e calcola il rapporto WCAG 2.1 per ogni
accostamento che l'utente vede davvero, nei due temi. Soglie applicate:
4,5:1 per il testo normale, 3,0:1 per i componenti d'interfaccia.

| Accostamento | Chiaro | Scuro | Soglia |
|---|---|---|---|
| Testo su superficie (pannello sinistro, tabelle, dialoghi) | 16,91 | 13,32 | 4,5 |
| Testo su superficie-2 (pannello destro anonimizzato) | 14,42 | 12,10 | 4,5 |
| Testo su sfondo (tela dell'applicazione) | 15,36 | 14,47 | 4,5 |
| Testo attenuato su superficie (note, sottotitoli, metriche) | 6,26 | 6,97 | 4,5 |
| Testo attenuato su superficie-2 (intestazioni di tabella) | 5,33 | 6,33 | 4,5 |
| Testo attenuato su sfondo (stato, barra azioni) | 5,68 | 7,57 | 4,5 |
| Testo tenue su superficie (segnaposto dei campi) | 4,86 | 5,89 | 4,5 |
| Accento su superficie (valore reale evidenziato) | 8,69 | 7,97 | 4,5 |
| Accento su velo d'accento (chip del valore reale) | 7,36 | 7,41 | 4,5 |
| Testo su superficie-3 (chip del segnaposto, righe al passaggio) | 13,27 | 10,55 | 4,5 |
| Testo inverso su fondo inverso (pulsante primario, banner) | 15,22 | 14,47 | 4,5 |
| Bordo di controllo su superficie (campi, liste, pulsanti) | 3,46 | 3,55 | 3,0 |
| Bordo di controllo su sfondo (pulsanti nella barra azioni) | 3,14 | 3,86 | 3,0 |
| Anello di fuoco su superficie | 8,69 | 7,97 | 3,0 |
| Anello di fuoco su sfondo | 7,89 | 8,65 | 3,0 |
| Indicatore di lavorazione su sfondo | 7,89 | 8,65 | 3,0 |

```
ESITO: tutti gli accostamenti rispettano WCAG 2.1 AA.
```

32 accostamenti su 32, nessuno sotto soglia. Il più stretto è
3,14:1 (bordo dei pulsanti nella barra azioni, tema chiaro) contro una
soglia di 3,0: è un margine sottile e va tenuto d'occhio se la palette
cambia — lo script esce con codice 1 se scende.

## 7. I pacchetti

### 7.1 macOS — costruito, verificato, provato

| | |
|---|---|
| Bundle | `dist/PrivacyBridge.app` — 3,1 GB |
| Immagine disco | `dist/PrivacyBridge.dmg` — 2.517.917.588 byte (2,3 GB) |
| Copia di consegna | `~/Desktop/PrivacyBridge-App/PrivacyBridge.dmg` |
| Costruttore | PyInstaller 6.21.0, ricetta in `build/PrivacyBridge.spec` |
| Firma | assente (nessun certificato Apple) |

Il `.dmg` non è stato solo prodotto: è stato **verificato e montato**.
`hdiutil verify` → *"checksum is VALID"*; montato su
`/Volumes/PrivacyBridge` mostra `PrivacyBridge.app` e il collegamento
ad `Applications`, cioè la finestra d'installazione classica.

Dentro il bundle, tutto ciò che serve a funzionare senza rete e senza
Python installato: interprete, dipendenze, e il modello neurale da
1,2 GB in `Contents/Resources/modello`.

### 7.2 Contenuto del pacchetto — audit

Il briefing chiede di elencare il contenuto e togliere qualunque file
di sviluppo. Cercati uno per uno e **non trovati**:

| Cercato | Esito |
|---|---|
| Nostri test (`tests/`) | assenti |
| Benchmark e corpus | assenti |
| Documenti dell'utente (`*.pdf`, `Indagine*`, `Hetepi*`) | assenti |
| Vault, impostazioni, log (`vault.db*`, `impostazioni.json`, `log.txt`) | assenti |
| Sorgenti grezze delle liste (`cognomi_paolosarti.txt`, `nomi_sigpwned.csv`, `*wikidata*`) | assenti |
| Documentazione interna (`docs/`) | assente |
| Script di sviluppo (`scripts/`) | assenti |

Presente e verificato riga per riga contro il codice che lo apre:
`Contents/Resources/data/liste/` con esattamente i cinque file letti a
runtime (`cognomi_italiani.tsv`, `comuni_italiani.txt`,
`nomi_italiani.tsv`, `vocab_it_60k.txt`, `vocab_it_660k.txt`) — nessun
peso morto. `api/static/` con il solo `index.html`.

**Unica eccezione, consapevole**: 269 file di test di `torch`, `spacy`
e `thinc` (~2 MB su 3,1 GB) restano dentro, perché
`torch/_dynamo/test_case.py` è importato da torch a runtime e
un'esclusione per pattern `test_*` romperebbe l'app in un punto che
nessun nostro test tocca. Motivazione estesa in DECISIONI.md.

### 7.3 Windows — assente, e dichiarato

Non esiste nessun `PrivacyBridge-Setup.exe`, né in `dist/` né nella
cartella di consegna. PyInstaller non compila per un sistema diverso da
quello su cui gira, e questa è una macchina macOS.

Sono pronti e mai eseguiti: `build/PrivacyBridge.spec` (condivisa fra i
due sistemi), `build/PrivacyBridge-windows.iss` (Inno Setup: scelta
della cartella, collegamento nel menu Start, disinstallazione pulita),
i launcher `.bat`/`.vbs`, `icon.ico` in 7 risoluzioni,
`verifica_tutto.bat`.

La scelta di non consegnare un `.exe` costruito sotto Wine è
deliberata: per un prodotto che va venduto ad aziende, un installer non
provato è peggio di un installer assente. L'assente si pianifica;
quello rotto si scopre davanti al cliente. I cinque comandi da dare su
un PC Windows sono in BLOCCHI.md § 11, e il `LEGGIMI.txt` dice
all'utente che il file non c'è e perché.

## 8. Installazione (istruzioni per l'utente finale)

**macOS**
1. Doppio click su `PrivacyBridge.dmg`.
2. Trascinare l'icona di PrivacyBridge sulla cartella Applicazioni.
3. **La prima volta**: tasto destro sull'icona → "Apri" → "Apri" di
   nuovo nella finestra di avviso. Serve solo la prima volta.
   Motivo: l'app non è firmata con un certificato Apple (99 €/anno),
   quindi macOS blocca il primo avvio per prudenza.
4. La finestra si apre da sola. Non serve internet.

**Windows** (quando l'installer esisterà)
1. Doppio click su `PrivacyBridge-Setup.exe`.
2. Se compare "Windows ha protetto il PC": "Ulteriori informazioni" →
   "Esegui comunque". Stessa ragione del punto 3 di macOS.
3. Seguire l'installer; il programma compare nel menu Start.
4. Disinstallazione: Impostazioni → App → PrivacyBridge.

Le stesse istruzioni, scritte per chi non è tecnico, sono in
`~/Desktop/PrivacyBridge-App/LEGGIMI.txt`.

## 9. Capitolo finale onesto — cosa PrivacyBridge NON copre

Questo capitolo esiste perché il prodotto verrà venduto ad aziende. Un
limite dichiarato si gestisce con una procedura; una rassicurazione
falsa si scopre davanti al cliente.

### 9.1 La regola generale

**PrivacyBridge riduce il lavoro, non lo elimina.** Non è un sistema di
anonimizzazione certificata e non va presentato come tale. È uno
strumento che trova la grande maggioranza dei dati personali e li mette
in una tabella che una persona deve leggere prima di copiare il testo
fuori. La tabella non è un dettaglio dell'interfaccia: è il punto in
cui la responsabilità passa dalla macchina all'utente, ed è per questo
che l'app non permette di saltarla.

Chi vende il prodotto dovrebbe promettere questo: *"trova quasi tutto,
ti mostra cosa ha trovato, e ti fa correggere prima di uscire"*. Non
questo: *"garantisce che nessun dato personale esca"*.

### 9.2 Tipi di dato fuori perimetro (scelta deliberata)

| Fuori perimetro | Perché |
|---|---|
| Soprannomi, username non-`@`, ID di messaggistica, codici cliente interni, cookie/device ID, numero libretto veicolo, conto corrente non-IBAN | Nessun formato validabile. Un rilevatore produrrebbe più falsi positivi del valore che aggiunge. |
| BIC/SWIFT | È un dato pubblico della banca, non della persona. |
| Cittadinanza, sesso, stato civile, età, professione, titolo di studio | Sono parole comuni o valori discreti: mascherarli automaticamente rovinerebbe il testo senza proteggere nessuno. |
| **Categorie particolari art. 9 GDPR** (salute, sindacato, religione, opinioni politiche, orientamento sessuale, biometria) | **Nessun rilevamento dedicato.** Sono contenuti, non identificatori. L'app maschera il *chi* — nome, CF, tessera sanitaria, recapiti — non il *cosa*. Chi deve oscurare anche una diagnosi lo fa a mano dalla tabella. |

La rete di sicurezza per tutti questi casi è la stessa: selezione nel
testo → "aggiungi entità", oppure la rubrica personale per i termini
che ricorrono sempre (nomi di clienti abituali, codici interni).

### 9.3 Dove il rilevamento peggiora — con i numeri

**Documenti scansionati (OCR).** È il limite più importante e il meno
intuitivo. Verifica reale su `Indagine .pdf`, 25 pagine di cui 10
rilette dall'OCR, **tutte le 67 entità controllate una per una a mano**:

| Esito | Conteggio |
|---|---|
| Dato personale vero, span corretto | 40 |
| Dato vero ma trascritto male dall'OCR | 1 |
| Dato vero con span parziale (nome troncato, cognome mancante) | 8 |
| Falso positivo (rumore OCR scambiato per dato) | 18 |
| **Totale** | **67** |

- **Precisione "ha toccato un dato vero": 49/67 = 73,1%**
- **Precisione stretta (span esatto): 40/67 = 59,7%**

E i **falsi negativi**, che contano di più. Misurati non sull'elenco
delle entità ma sul **testo anonimizzato in uscita**, cioè su ciò che
davvero uscirebbe dal computer: **3 e-mail e 4 sequenze di cifre da
carta di pagamento restano in chiaro.**

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

La causa è meccanica, non statistica:

- **E-mail.** Due hanno **uno spazio prima della chiocciola**, messo lì
  dall'OCR: `rossi @esempio.it`, `support @mocha.ni`. Non sono
  indirizzi diversi da quelli mascherati — sono gli stessi, resi
  invisibili al rilevatore da un carattere di troppo. La terza, una
  PEC, ha **un punto subito dopo la chiocciola** (`…ufficio@.pec…`) e non
  supera la validazione del dominio.
- **Carte di pagamento.** Su 12 sequenze candidate, 4 valori distinti
  superano il controllo di Luhn e vengono mascherati. Le altre no, e
  tre delle quattro superstiti sono **varianti sfigurate di carte
  vere**: `5544•••••••••••` è `5574••••••••••••` con due cifre lette
  male; `3977•••••••••••` e `4347 ••••••••••••` sono lo stesso numero
  di `4397 •••• •••• 2131`. L'OCR sbaglia una cifra, Luhn fallisce, e
  il candidato viene scartato **proprio dal controllo che serve a
  evitare i falsi positivi**.

Vale la pena notare come sono nate queste due righe: nella prima
stesura di questo capitolo avevo scritto "2 e-mail", riportando un
conteggio fatto in una sessione precedente. Rimisurato sull'uscita
vera, sono 3. La differenza è una PEC di una questura. Un numero
ricordato non è un numero verificato.

Qui sta il punto scomodo, e va detto per intero: sul documento
scansionato la validazione di formato lavora contro di noi. Su testo
digitale è ciò che tiene la precisione alta; su testo OCR è ciò che
lascia passare il dato corrotto. Non è un bug da correggere con una
soglia: allentare Luhn o accettare spazi dentro le e-mail
riempirebbe di falsi positivi tutti gli altri documenti. È un limite
strutturale del riconoscimento su scansione.

Su un documento scansionato, quindi: l'app avvisa che sta lavorando su
una scansione, ma la tabella va letta **riga per riga**, e il testo in
uscita va riletto. Non è un caso d'uso da delegare.

**Lingue diverse dall'italiano.** Il dizionario di nomi e cognomi, il
truecasing e il modello neurale sono tarati sull'italiano. L'inglese
funziona in modo ridotto (`lingua=en`, recognizer standard Presidio).
Altre lingue e i dialetti non hanno supporto. I rilevatori
deterministici — IBAN, e-mail, telefoni, targhe, P.IVA, CF — funzionano
in qualunque lingua, perché guardano il formato.

**Nomi stranieri rari.** Riconosciuti nella forma nome+cognome dal
modello neurale; il nome straniero isolato e raro sfugge, perché il
dizionario è italiano. Rimedio: rubrica personale.

**Nomi che coincidono con parole comuni.** Undici esclusioni esplicite
(`massimo`, `domenica`, `salvo`, `sole`, …). In minuscolo e senza
contesto sintattico personale non vengono sostituiti. È un prezzo
pagato consapevolmente: l'alternativa è rovinare "salvo imprevisti" e
"domenica prossima" in ogni documento.

**Spaziature anomale dei PDF.** `"M ario  Rossi"` — i token spezzati
dall'estrazione non sono garantiti.

**Organizzazioni: richiamo 100% largo, 95,7% stretto** (44 span esatti
su 46 nel corpus annotato). La cifra scritta qui in precedenza —
«recall ~56%» — era **sbagliata**: veniva ricordata da una sessione
precedente su un corpus diverso e non era mai stata rimisurata. Il
comando che la verifica è `venv/bin/python -m benchmark.misura_corpus`.

I due span ancora imperfetti sono `ENEL ENERGIA` e `Croce Rossa
Italiana`: marchi senza forma giuridica in coda né prefisso
istituzionale in testa, che restano al modello neurale. La categoria
resta **disattivata per impostazione predefinita**, ma ora per scelta di
perimetro — il nome di un'azienda non è un dato personale — e non per
scarsa affidabilità. Nel testo del gate, `Edilservice S.p.A.`
correttamente **non** viene sostituita finché l'utente non attiva la
categoria o la aggiunge a mano.

Dettaglio della misura e delle correzioni in `docs/AUDIT_PRECISIONE.md`.

### 9.4 Limiti che non riguardano il rilevamento

**Il vault non è cifrato a riposo.** I valori reali stanno in un
database SQLite nella cartella utente, protetto dai permessi del
filesystem (file `0600`, cartella `0700`) e dalla cifratura del disco.
Se l'utente ha FileVault (o BitLocker) spento e il portatile viene
rubato, quel file è leggibile. È scritto nel `LEGGIMI.txt` con la
raccomandazione esplicita di tenere la cifratura del disco accesa. Una
cifratura applicativa richiederebbe una passphrase da chiedere a ogni
avvio: scelta rimandata, non dimenticata (DECISIONI.md).

**La sessione vive in memoria.** Fra "Copia" e "Ripristina" l'app non
va chiusa: la corrispondenza segnaposto → valore reale sta lì. È detto
al passo 7 del `LEGGIMI.txt`.

**Windows non è mai stato provato.** Vedi § 7.3: il codice è
portabile e l'installer è scritto, ma nessuno ha mai avviato questo
programma su un PC Windows. Finché quel passaggio non viene fatto, la
compatibilità Windows è una previsione ragionata, non un fatto.

**Documenti molto grandi costano minuti.** 500.000 caratteri sono
~4 minuti e mezzo di analisi. L'operazione è interrompibile e mostra
l'avanzamento, ma non è istantanea e non lo diventerà su CPU.

### 9.5 Cosa richiederà manutenzione

| Cosa | Come | Quando |
|---|---|---|
| Verifica su Windows reale | I sei punti di BLOCCHI.md § 3 + i cinque comandi di § 11 | Prima di vendere a un cliente Windows |
| Dizionari nomi/cognomi/comuni | `scripts/build_liste_nomi.py` (fonti e licenze in DECISIONI.md) | Annuale, o quando sfugge un nome comune |
| Modello neurale | Procedura documentata: si rimisura il benchmark PRIMA di sostituirlo | Alla prossima revisione del modello |
| Nuovi formati di identificativi (targhe, documenti) | Recognizer deterministico + caso in `tests/test_tassonomia.py` | Quando cambia la normativa |
| Casi segnalati dagli utenti | `PRIVACYBRIDGE_DIAGNOSI=1` dice in trenta secondi perché un dato non è stato preso; la correzione va fatta sulla *classe*, con un caso in `test_avversariale.py` | Continuo |
| Firma del codice | 99 €/anno Apple Developer + certificato Windows: toglie i due avvisi di sicurezza al primo avvio | Quando il prodotto va a clienti che non accettano l'avviso |

### 9.6 In una riga

PrivacyBridge fa bene una cosa: prende un documento italiano, ci trova
dentro quasi tutti i dati personali, li sostituisce in modo
**reversibile byte per byte** e mette in tabella ciò che ha fatto perché
una persona lo controlli. Su testo digitale italiano è affidabile. Su
scansioni serve controllo riga per riga. Fuori dall'italiano è poco più
dei rilevatori di formato. E su Windows, oggi, è una promessa non
ancora verificata.
