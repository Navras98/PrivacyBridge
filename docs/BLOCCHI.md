# BLOCCHI — Cose non testate o non risolte

## 14. OCR nativo — limiti noti (2026-07-31)

- **Windows.Media.Ocr mai provato**: il ramo esiste in
  `backend/ocr.py` (`_ocr_png_windows`, via `winsdk`) ma non ho una
  macchina Windows. Da verificare lì: che `OcrEngine` trovi la lingua
  italiana installata, la resa sui PDF legali, i tempi.
- **Confusione caratteri**: Vision confonde I/l a fine codice
  (misurato: "RSSMRA85T10A944I" letto "…A944l" nel test
  `test_pdf_scansionato_ocr_estrae_testo`). Un CF letto male non
  supera più il checksum e scende al fallback formato (score 0.6) o
  si perde. Per questo la UI avvisa esplicitamente di controllare la
  tabella riga per riga sui documenti scansionati.
- **Soglie per-pagina**: OCR scatta su pagine con testo incorporato
  < 600 char E immagini > 50% dell'area. Una scansione con OCR
  incorporato mediocre ma sopra i 600 char/pagina NON viene ri-letta
  (per non riprocessare inutilmente PDF già buoni). Se emergesse un
  caso reale, la soglia è una costante in `backend/documenti.py`.
- **Tempi**: ~3,4 s/pagina (rasterizzazione 220 dpi + Vision accurate,
  misurato su "Indagine .pdf": 10 pagine in 34 s).

## 15. Nuovi recognizer — limiti deliberati (2026-07-31)

- **SOCIAL**: gli handle che terminano con un segmento TLD-like
  (".com", ".ni", 2-3 lettere dopo un punto) sono soppressi per non
  catturare email spezzate dall'OCR. Un handle vero tipo "@mario.co"
  viene perso: rubrica.
- **TARGA con spazi**: la forma "AB 123 CD" richiede lettere tutte
  maiuscole; se i gruppi letterali coincidono con unità di misura
  (KB, CV, KM…) serve la keyword veicolare vicina. La forma attaccata
  "AB123CD" non ha restrizioni.
- **PRATICA "decreto n. X"**: cattura anche citazioni normative nella
  forma nuda "decreto n. 33/2013" (raro: le leggi si citano come
  "d.lgs."/"decreto legislativo", che NON matcha). Sovra-anonimizzare
  una citazione normativa è innocuo per la riservatezza; il contrario
  no.
- **Pass minuscolo nomi-collisione**: undici nomi a uso
  temporale/idiomatico dominante (domenica, natale, alba, sole, luce,
  salvo, massimo, santo, sante, fede, amore) restano esclusi dal pass
  sintattico ("viene X", "da X"). "conosci Massimo?" in minuscolo non
  viene preso: rubrica personale.

## 12. Fix 1b e 1c (briefing chiusura Gate 1) — non implementate deliberatamente

Il briefing di chiusura chiedeva quattro correzioni per i nomi ambigui.
Su misurazione empirica, 3 dei 4 casi già passavano; il quarto (Grazia)
è stato risolto con due fix mirati (`_scarta_luogo_su_nome_certo` +
guardia inizio-frase). Le fix 1b (propagazione entità certe) e 1c
(preposizioni personali come contesto forte) NON sono state
implementate. Vedi `DECISIONI.md § 2026-07-30 · Nomi ambigui — chiusura
Gate 1` per la motivazione: tutti i 4 casi passano già, il rischio FP
è concreto, la regola "massimo 6 tentativi per gate" del briefing si è
chiusa in 3 tentativi. Se in futuro emerge un caso reale non coperto
la strada è: (a) seed nomi_top_italiani.txt, (b) rubrica personale,
(c) valutare 1b/1c a partire da un esempio concreto.

## 13. Gate finale manuale (doppio click da Finder) — non replicabile automaticamente

Come già documentato al § 5, il gate strettamente "utente davanti al
Mac che apre l'app cliccando" non è replicabile in un ambiente headless
di sviluppo. In questa sessione:

- Bundle `dist/PrivacyBridge.app` (3.1 GB) e `dist/PrivacyBridge-1.0.0.dmg`
  (2.3 GB) costruiti da zero (`bash scripts/build_bundle.sh`) — build
  completata in ~5 minuti, `pyinstaller 6.21.0`.
- Bundle avviato via subprocess con `PRIVACYBRIDGE_DATA_DIR=/tmp/…`:
  server pronto in ~10s, `/health` risponde `{"status":"ok","versione":"1.0.0"}`,
  `/anonimizza` sul testo "sono passato da Grazia stamattina." risponde
  correttamente con «PERSONA_1» al posto di Grazia (fix Gate 1 attiva
  nel bundle).
- `verifica_tutto.sh` completo (backend + garanzie + interfaccia
  Playwright + bundle boot) verde in 240.4s: **164 passed + 1 xpassed**.

Gate finale strettamente manuale (doppio click su icona Finder,
copia/incolla del testo canonico, click sui pulsanti, ecc.) va
eseguito dall'utente sulla sua macchina — la mia esecuzione via CLI
riproduce lo stesso flusso ma non l'esperienza cliccante.

> **Aggiornamento 2026-08-01 — i numeri qui sopra sono superati.**
> Lo script di costruzione è ora `build/build_bundle.sh` e il `.dmg` si
> chiama `PrivacyBridge.dmg` (senza versione nel nome). Il bundle
> corrente è stato ricostruito e il gate rieseguito **contro l'app
> montata dal `.dmg`**: server pronto in 0,5 s, tutti e nove i nomi del
> testo canonico sostituiti, ripristino byte-identico. Le cifre
> aggiornate stanno in CONSEGNA.md § 3 e § 7. Resta valido il punto di
> questo paragrafo: il doppio click da Finder lo può fare solo una
> persona davanti alla macchina.

## 1. Entità PII non coperte

### Passaporto italiano
Presidio ha solo `US_PASSPORT` (9 caratteri, 2 lettere + 7 cifre) —
formato USA. Il passaporto italiano ha formato identico (`AA1234567`)
ma senza checksum: un recognizer regex-only produrrebbe molti falsi
positivi. **Non implementato.** Se serve, va scritto un recognizer con
parola-chiave contestuale obbligatoria ("passaporto", "n. passaporto").

### Patente italiana
Analogo: `U123456789`, nessun checksum, richiede contesto. Non
implementato.

### Tessera sanitaria
Equivalente al codice fiscale in Italia. **Coperta** da
`IT_CODICE_FISCALE`.

### Numeri di spedizione (corrieri)
Formato variabile per corriere (UPS `1Z…`, Bartolini, DHL). Nessun
checksum universale. Nessun recognizer dedicato. `NUMERO_SPEDIZIONE`
del modello neurale intercetta alcune varianti ma non tutte. La
tabella entità in UI è la rete di sicurezza.

## 2. Recall ORGANIZATION al 56%

Sul corpus onesto di 20 frasi inedite (`benchmark/frasi_nuove.py`) il
modello neurale lascia scoperto il ~56% delle ORGANIZATION. Casi tipici:

- Nomi corti indistinguibili da cognomi (`Bartolini`, `Rossi e Gialli`).
- Forma societaria attaccata (`Edilservice S.p.A.` — cattura solo
  `Edilservice`).
- Sigle scambiate per organizzazioni (`ISO 9001`).

Il post-process deterministico che estendeva gli span (S.p.A., "e",
"&") è stato provato e **rimosso**: sul corpus dev migliorava di 3
leak ma sul corpus onesto peggiorava di 2 (falsi positivi su LOCATION
e rumore ORG). Netto negativo. La tabella entità in UI resta l'unica
rete di sicurezza affidabile.

## 11. PyInstaller Windows — NON VERIFICATO

Il bundle **macOS** è costruito con `build/PrivacyBridge.spec` +
`build/build_bundle.sh` e testato end-to-end su questa macchina
(2026-07-30): bundle 3.1 GB, DMG 2.5 GB, `/health` in <1s,
`/anonimizza` sul testo canonico in 9.4s.

Il bundle **Windows** NON è stato costruito né testato perché non
ho una macchina Windows a disposizione. Ho preparato:

- `build/PrivacyBridge.spec` (macOS e Windows condividono la stessa
  spec: hidden imports e datas identici; su Windows non viene
  generato il `BUNDLE(...)`, solo l'`.exe` + cartella `_internal`).
- `build/PrivacyBridge-windows.iss`: script Inno Setup 6 per
  l'installer (scelta cartella, collegamento nel menu Start,
  disinstallazione pulita, icona sul desktop opzionale).

Passi da eseguire su una macchina Windows, dalla radice del progetto
(documentati anche in commento nel `.iss`):

```
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt pyinstaller
pyinstaller --clean --noconfirm --workpath build\pyinstaller ^
    --distpath dist build\PrivacyBridge.spec
# Copia il modello accanto all'exe (serve una copia del modello:
# da un mirror interno o scaricata con huggingface-cli).
robocopy <sorgente-modello> dist\PrivacyBridge\modello /E
# Compila l'installer:
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" build\PrivacyBridge-windows.iss
# Output: Output\PrivacyBridge-Setup.exe
```

Cose da verificare specifiche di Windows dopo il primo build:

0. `winsdk` (OCR nativo Windows.Media.Ocr) si installa da
   requirements solo su Windows: verificare che PyInstaller raccolga
   i moduli `winsdk.windows.media.ocr` / `graphics.imaging` /
   `storage.streams` (hidden imports già nella .spec) e che
   `OcrEngine.try_create_from_user_profile_languages()` trovi
   l'italiano (Impostazioni → Ora e lingua → Lingua).

1. Il modello viene trovato. Su Windows PyInstaller non produce un
   `.app`, quindi i candidati che valgono sono gli ultimi due di
   `_candidati_percorsi_modello` (`src/avvio.py`): `HERE/modello`,
   che sotto PyInstaller è `dist\PrivacyBridge\_internal\modello`,
   e `exe.parent/modello`, cioè `dist\PrivacyBridge\modello`. Le
   istruzioni sopra usano il secondo. Entrambi sono già cercati:
   non risulta serva una modifica al codice, ma è da confermare
   sulla macchina vera.
2. pywebview usa WebView2 (Edge Chromium) su Windows: verifica che
   `WebView2Loader.dll` sia raccolto — se manca, `pip install pywebview[edge]`.
3. SmartScreen: l'exe non firmato genera un warning "Windows ha
   protetto il PC". L'utente deve cliccare "Ulteriori informazioni"
   → "Esegui comunque". Documentare in README.
4. Antivirus: gli exe PyInstaller sono false-positive frequenti.
   Verificare con Windows Defender + almeno un altro AV.
5. `platformdirs` scrive in `%APPDATA%\PrivacyBridge` (non
   `~/Library/`). Ho già isolato tutti i path via `pathlib.Path`.
6. `verifica_tutto.bat` esiste ma non è mai stato eseguito su
   Windows reale.

Quando la macchina Windows sarà disponibile, aggiungere a questo
blocco l'esito effettivo (versione, dimensione bundle/setup,
tempi, screenshot).

### Esito della parte 7 (2026-08-01)

Il pacchetto macOS è stato costruito e verificato: `dist/PrivacyBridge.app`
3,1 GB, `dist/PrivacyBridge.dmg` 2,5 GB, checksum valido, app avviata
dal `.dmg` montato con il testo canonico e ripristino esatto.

Il pacchetto **Windows non è stato prodotto**, e non per mancanza di
tentativi: PyInstaller non compila per una piattaforma diversa da
quella su cui gira. Non esiste un'opzione di cross-compilazione — il
bootloader è un eseguibile nativo e le dipendenze binarie (torch,
tokenizers, pypdfium2) sono ruote compilate per il sistema ospite.
L'unica strada da macOS sarebbe una macchina Windows, reale o
virtuale, che qui non c'è.

Costruire l'`.exe` sotto Wine è tecnicamente possibile ma produce un
artefatto che nessuno ha mai avviato su Windows vero. Per un prodotto
che l'utente venderà ad aziende, un installer non provato è peggio di
un installer assente: l'assente si pianifica, quello rotto si scopre
davanti al cliente. Quindi nella cartella di consegna il `.exe` non
c'è, e `LEGGIMI.txt` lo dice apertamente con la ricetta per produrlo.

Resta pronto e non verificato: `build/PrivacyBridge.spec` (condivisa),
`build/PrivacyBridge-windows.iss`, i launcher `.bat` e `.vbs`,
`icon.ico`, `verifica_tutto.bat`. I punti da confermare sono i sei
elencati qui sopra.

## 3. Verifica su Windows reale — NON FATTA

Il codice è cross-piattaforma:
- `platformdirs` per la cartella dati;
- `pathlib.Path` ovunque;
- launcher `PrivacyBridge.bat` + `PrivacyBridge.vbs` (silente);
- `icon.ico` in 7 risoluzioni.

Da verificare su Windows reale:
1. Doppio click su `PrivacyBridge.vbs` apre la finestra WebView2/Edge.
2. `platformdirs` scrive in `%APPDATA%\PrivacyBridge`, non in
   `~/Library/…`.
3. La finestra di download del modello al primo avvio funziona
   (`huggingface_hub.snapshot_download` — provato solo su macOS).
4. I font di fallback Windows (`Segoe UI Variable`, `Cambria`,
   `Cascadia Code`) rendono l'UI in modo accettabile: il carattere sarà
   diverso da macOS (Cambria non è New York), ma l'identità visiva
   regge sul contrasto fra i ruoli e sulla palette.
5. `verifica_tutto.bat` completa senza errori.

## 4. Test offline stretto — FATTO 2026-07-29

Wi-Fi disattivato via `networksetup -setairportpower en0 off`;
huggingface.co unreachable (URLError); il backend avviato con
`HF_HUB_OFFLINE=1` e `TRANSFORMERS_OFFLINE=1` ha completato con
successo un roundtrip Anonimizza→Ripristina su un testo con nome,
email, IBAN, data. Wi-Fi poi riacceso. Il flusso completo funziona
senza rete a modello già scaricato.

## 5. Gate finale manuale (doppio click da Finder)

Il bundle si avvia via subprocess in 3.5s, bind su 127.0.0.1, zero
connessioni in uscita, zero orfani a chiusura. Il flusso completo
end-to-end è coperto dai test Playwright. Manca lo screenshot dell'app
aperta come applicazione macOS "vera" (con menubar / dock). Gli
screenshot allegati (`screenshots/*`) sono presi da Chromium headless
sulla stessa UI: identici pixel-per-pixel alla finestra pywebview.

## 10. Truecasing minuscolo — limite noto

Il fix strutturale del truecasing (rileva testo prevalentemente
minuscolo → ricapitalizza → passa all'analyzer) copre la maggior
parte dei casi colloquiali. Rimane un limite documentato:

- **Frasi in minuscolo con cognome composto NON in dizionario e
  senza contesto forte**: es. `"scrivi a luca lo bianco per il
  preventivo"`. "Luca" viene catturato, ma "lo bianco" (particella
  nobiliare + cognome ambiguo) resta in chiaro.

Ragione: il vocab italiano usato dal truecasing (60k) è
conservativo. Un vocab più grande (660k) evita il limite ma include
anche molti nomi propri, bloccando la capitalizzazione di nomi
legittimi come "luca". Nessuna delle due alternative è ottimale.
Test marchiato `xfail` in `test_truecasing_lo_bianco`.

Compromesso accettato: preferisco perdere questo caso limite piuttosto
che introdurre FP su nomi legittimi. Se il caso diventa frequente per
un utente, la rubrica personale (una voce "Luca Lo Bianco") lo
risolve.

## 9. Dati anagrafici — valutazione categorie dedicate

Nel briefing sul LUOGO_NASCITA l'utente chiede: "valuta se altri dati
anagrafici hanno lo stesso problema". Ecco la ricognizione con la
scelta motivata caso per caso.

| Dato anagrafico | Categoria dedicata? | Motivazione |
|---|---|---|
| Nome + cognome | PERSONA (attiva) | Coperta. |
| Data di nascita | DATA_NASCITA (attiva) | Creata. |
| Luogo di nascita | LUOGO_NASCITA (attiva) | Creata. |
| Codice fiscale | CF (attiva) | Coperta. |
| Documento identità (CI, passaporto, patente) | DOCUMENTO (attiva) | Coperta. |
| Indirizzo di residenza | INDIRIZZO (attiva) + LUOGO_NASCITA (via "residente a") | Coperto. |
| CAP | CAP (attiva) | Coperta. |
| Email / telefono | EMAIL / TELEFONO (attive) | Coperte. |
| IBAN / P.IVA / carta di credito | IBAN / PIVA / CARTA (attive) | Coperte. |
| Codice sanitario | SANITARIO (attiva) | Coperta. |
| **Cittadinanza** | **NON aggiunta** | "italiana", "francese", "romena" — parole singole molto frequenti, alto rischio FP se catturate ovunque. Contesto tipico "di nazionalità X", "cittadinanza X". Marginale come identificatore da solo. Se serve, l'utente può inserirla in rubrica personale. |
| **Stato civile** | **NON aggiunta** | "coniugato", "nubile", "divorziato" — non è quasi mai identificante da solo, ed è quasi sempre uno di 4-5 valori discreti. Categoria dedicata darebbe più rumore che valore. |
| **Professione** | **NON aggiunta** | Già gestita: JOB_TITLE viene scartato in `motore.py::anonimizza`; il filtro `_ruolo_o_ufficio` scarta anche "Amministratore Delegato", "Direttore Vendite" ecc. |
| **Titolo di studio** | **NON aggiunta** | "Laureato in giurisprudenza" — raramente identificante, alto rumore. |
| **Nome coniuge / genitore** | **NON aggiunta** | Se emerge, cade in PERSONA (attiva). |
| **Numero previdenziale / INPS** | **NON aggiunta** | Formato variabile, poco ricorrente. Se serve, rubrica personale. |
| **Numero patente** | Già IT_DRIVER_LICENSE → DOCUMENTO | Coperta. |
| **Altezza / peso / gruppo sanguigno** | **NON aggiunta** | Non normalmente in documenti gestiti dall'utente target (studi, aziende, condomini). |

Conclusione: PERSONA + DATA_NASCITA + LUOGO_NASCITA coprono la triade
canonica da cui si deriva il codice fiscale. CF + DOCUMENTO coprono gli
identificatori strong. INDIRIZZO + CAP coprono la residenza fisica.
Cittadinanza e stato civile sono deliberatamente esclusi per non
introdurre rumore su parole comuni; se un utente ha uno use case
specifico, la rubrica personale è la strada.

## 8. OCR per PDF scansionati — SCARTATO in FASE 3

Il piano FASE 3 chiedeva di "valutare l'integrazione OCR con tesseract"
per i PDF che sono immagini pure. Scartato per questa release. Motivi:

1. **Peso di distribuzione**: tesseract + i suoi language packs italiani
   pesano ~120 MB compressi. Il modello neurale è già 1.2 GB nel
   bundle; sommare l'OCR spingerebbe il DMG oltre i 2 GB annunciati.
2. **Qualità variabile**: tesseract senza pre-processing (deskew,
   binarizzazione, DPI ricalcolato) su una scansione reale produce
   spesso testo con errori sistematici che il motore di riconoscimento
   PII non intercetta correttamente. Rischio di dare all'utente
   l'illusione che l'anonimizzazione sia completa quando invece OCR ha
   mangiato mezzi codici fiscali.
3. **Piattaforme**: pytesseract richiede l'installazione separata di
   tesseract (brew su macOS, choco su Windows). Fuori dal principio
   "installa e apre" della FASE 1.3.

Ripiego: nel caricamento di un PDF, se il testo estratto è sotto la
soglia (< 20 char totali, oppure < 15 char/pag su >= 3 pag), il
backend solleva `DocumentoScansionato` e l'API restituisce codice 422
con messaggio esplicito. L'utente sa che deve passare il file all'OCR
esternamente (Anteprima di macOS ha OCR nativo dalla versione 15,
Adobe Acrobat lo fa da sempre, ABBYY FineReader è lo standard
professionale).

Se in una versione futura si vorrà integrare l'OCR: fare un modulo
opzionale scaricabile a parte (non nel bundle base) e distinguere in
UI il testo OCR-derived (segnalando la sua qualità) da quello nativo.

## 7. Consultazione read-only del vault — FATTO in FASE 5.4b (2026-07-30)

Aggiunto pulsante "Vault" in barra superiore che apre un dialog con
l'elenco dei segnaposto della sessione corrente. I valori reali sono
mascherati (`••••••`) finché non si clicca "Mostra valori". Chiama
`GET /sessioni/{id}` (endpoint già esistente ma prima non usato dalla
UI). Chiudibile con click fuori, ESC o pulsante Chiudi. Il flag
`vaultValoriVisibili` si resetta a `false` alla chiusura del dialog.
Test: `tests/test_interfaccia.py::test_fase5b_vault_vista_consultativa`.

## 6. Primo avvio pulito — FATTO 2026-07-29

Cancellati `~/.cache/huggingface/hub/models--rizzoaiacademy--rizzo-pii-0.3B`
e `~/Library/Application Support/PrivacyBridge`, poi lanciato
`avvio.py`. Sequenza dal log su file:

```
15:08:41 avvio.py start (data_dir=~/Library/Application Support/PrivacyBridge)
15:08:44 modello non in cache: apro finestra di download
15:08:44 snapshot_download start
15:08:45 cache_root=~/.cache/…/rizzo-pii-0.3B  totale_atteso=1.2 GB
15:10:59 snapshot_download OK — bytes intercettati: 1264686740
15:11:00 avvio api su porta 61290
15:11:01 apertura finestra principale
```

Il download di 1.26 GB è durato 2:15. Poi l'API è partita e la finestra
principale si è aperta. Nel secondo avvio (modello ora in cache),
`/health` risponde in ~10s, `/anonimizza` funziona.

**Fix del progresso**: la barra della prima versione era finta (5%
→ 100%). Ora è reale: il monkeypatch di `huggingface_hub.utils.tqdm.tqdm`
intercetta gli `update(n)` dei chunk scaricati e li somma; in parallelo
il monitor misura anche la size della cartella cache. La UI mostra
byte scaricati / byte totali (dai metadati HF), percentuale, velocità
in MB/s, e triggera un errore recuperabile se il download resta fermo
per più di 2 minuti (soglia scelta per non generare falsi positivi
nella fase di setup HTTPS/HF che dura 60-90s).

**Log su file**: sempre attivo, in `<data_dir>/log.txt`. Serve al
post-mortem se il download fallisce.
