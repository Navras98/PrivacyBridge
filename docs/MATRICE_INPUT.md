# MATRICE_INPUT — Come il testo arriva all'app, provato davvero

Data: 2026-07-31. Ogni riga riporta l'esito REALE osservato, con la
fonte della prova: `tests/test_documenti.py` (21 test),
`benchmark/matrice_input.py` (runner della matrice, in
`verifica_tutto.sh`), `tests/test_avversariale.py` (523 casi),
documenti reali in `benchmark/documenti_utente/`.

Legenda esito: **OK** = comportamento corretto verificato; **OK con
limite** = funziona con un limite documentato (rimando a BLOCCHI.md).

## 1. Formato

| Input | Cosa deve succedere | Esito | Prova |
|---|---|---|---|
| Testo incollato | analisi diretta | OK | tutta la suite |
| PDF con livello testo | estrazione pdfplumber | OK | `test_carica_pdf`; 4 PDF reali utente |
| PDF scansionato | OCR nativo (Vision) su tutte le pagine; avviso in UI; se OCR assente → errore esplicito | OK | `test_pdf_scansionato_ocr_estrae_testo`; "Indagine .pdf" reale |
| PDF misto (pagine scansionate) | OCR solo sulle pagine povere (testo <600 char + immagine >50% area), si tiene il testo più lungo | OK | `test_pdf_misto_solo_pagine_povere_in_ocr`; "Indagine .pdf": 10/25 pagine ri-lette, 23.553→30.252 char |
| PDF scansione con OCR incorporato buono | si usa il testo incorporato, niente ri-OCR | OK | "Atto giudiziario": 4.000+ char/pag, 32 entità |
| DOCX | estrazione python-docx | OK | `test_carica_docx` |
| DOC vecchio (binario) | NON supportato: errore chiaro "formato non supportato" con elenco ammessi | OK (fuori perimetro) | `test_estensione_non_supportata`; API 400 |
| ODT | estrazione odfpy | OK | `test_carica_odt` |
| RTF | striprtf | OK | `test_carica_rtf` |
| TXT / MD | lettura diretta (charset detection) | OK | `test_carica_txt`, `test_carica_md` |
| CSV / XLSX | righe → testo tabellare | OK | `test_carica_csv`, `test_carica_xlsx` |
| HTML | testo senza tag | OK | `test_carica_html` |
| EML / MSG | header+corpo | OK | `test_carica_eml` (+ `carica_msg`) |
| File corrotto / binario | errore gestito, mai crash | OK | `test_pdf_corrotto_…`, `test_txt_binario_…` |

## 2. Struttura

| Input | Cosa deve succedere | Esito | Prova |
|---|---|---|---|
| Prosa continua | entità rilevate | OK | matrice + tutta la suite |
| Tabelle (tab/colonne) | ogni cella trattata; nessuno span attraversa celle/righe | OK | matrice "tabella"; `test_g2_tabella_e_due_colonne`. Fix di classe 2026-07-31: uno span di categoria disattiva non può più "mangiare" il dato di una cella (bug LOCATION→TELEFONO) |
| Elenchi puntati | entità rilevate | OK | matrice "elenco puntato"; avversariale "elenco" |
| Titoli in MAIUSCOLO | il titolo NON viene sostituito (rumore); i dati deterministici dentro un titolo SÌ | OK | matrice "titolo MAIUSCOLO"; avversariale posizione "titolo" (36 valori) |
| Due colonne (PDF) | nessuno span attraversa l'a-capo | OK | matrice "due colonne"; `test_g2_no_span_attraverso_newline` |
| Intestazioni/piè ripetuti | stessa entità → stesso segnaposto in ogni pagina | OK | matrice "intestazioni ripetute" |
| Note a piè di pagina | entità rilevate anche lì | OK | matrice "nota a piè di pagina" |
| Moduli con campi etichettati | "Nome:", "Cognome:", "Codice fiscale:", "Luogo di nascita:" riconosciuti come contesto | OK | matrice "modulo campi etichettati". Fix di classe 2026-07-31: le etichette di modulo sono ora contesto valido per il cognome isolato |

## 3. Grafia

| Input | Cosa deve succedere | Esito | Prova |
|---|---|---|---|
| Tutto minuscolo | truecasing + pass sintattico; entità rilevate | OK | matrice "tutto minuscolo"; caso "marco" chiuso (DECISIONI.md) |
| Tutto MAIUSCOLO | persone in caps rilevate; titoli non toccati | OK | matrice "tutto MAIUSCOLO"; avversariale "caps-lock" (10 nomi) |
| Maiuscole corrette | caso base | OK | matrice |
| Errori di battitura | i dati con checksum tollerano typo (fallback formato con score ridotto); i nomi con typo NON sono garantiti (tabella entità come rete) | OK con limite | recognizer CF/IBAN/PIVA fallback; BLOCCHI.md |
| Accenti sbagliati (`e'`) | nessun impatto sul rilevamento | OK | matrice "accenti sbagliati" |
| Spaziature anomale da PDF (`M ario  Rossi`) | entità spezzate NON garantite; il testo non viene corrotto | OK con limite | matrice "spaziature anomale"; è il limite noto dei token spezzati |

## 4. Lingua

| Input | Cosa deve succedere | Esito | Prova |
|---|---|---|---|
| Italiano | pipeline completa | OK | tutto |
| Inglese | `lingua="en"` esplicito → spaCy en + recognizer standard; il rilevamento automatico privilegia l'italiano (design: default it) | OK | matrice "inglese (lingua=en)" |
| Misto it/en | trattato come italiano; i deterministici (email, IBAN…) linguaggio-indipendenti | OK | matrice "misto it/en" |
| Nomi stranieri in testo italiano | rilevati dal neurale quando in forma nome+cognome; nomi rari singoli non garantiti | OK con limite | matrice "nomi stranieri" (Zofia Kowalska ✓); BLOCCHI.md limiti |
| Dialetto | nessun supporto dedicato: parole dialettali = parole sconosciute; i dati deterministici funzionano comunque | OK con limite | design |

## 5. Dimensione

| Input | Esito osservato (misura pulita, `prestazioni_output.txt`) |
|---|---|
| Poche parole ("Chiama Mario.") | OK — 0,1 s |
| Una pagina (~1.700 char) | OK — ~1 s |
| Cinquanta pagine (~100k char) | OK — 64 s |
| Duecento pagine (~500k char) | OK — 310 s (~5′), picco RAM 2.980 MiB < 4 GiB |

Il tempo è lineare (~1.600 char/s costante a ogni taglia) grazie
all'analisi a blocchi introdotta il 2026-07-31 (prima degradava a
~300 char/s su 389k char, vedi DECISIONI.md). Il roundtrip resta
byte-identico a ogni taglia; la finestra non si blocca (elaborazione
in thread) e l'operazione lunga resta interrompibile
(`test_interruzione_sicura`).

## 6. Qualità

| Input | Cosa deve succedere | Esito | Prova |
|---|---|---|---|
| Testo pulito | caso base | OK | tutto |
| Testo da OCR con errori (0→O, I→l) | i dati INTATTI vengono presi; un CF/IBAN con caratteri sbagliati perde il checksum (fallback formato o perso) → avviso UI sui documenti scansionati | OK con limite | matrice "testo da OCR"; `test_g2_output_ocr_non_corrotto`; BLOCCHI.md § 14 |
| Caratteri di controllo / codifica sporca | nessun crash, entità rilevate, testo non corrotto | OK | matrice "caratteri di controllo" |

## Nota di metodo

I casi sintetici di questa matrice verificano il COMPORTAMENTO
(funziona / non corrompe / gestisce l'errore), non il recall. Il
recall dichiarato viene dai documenti reali:
`benchmark/documenti_utente_output.txt` (7/7 veri, 0 rumore sul file
annotato; 8 file elaborati).
