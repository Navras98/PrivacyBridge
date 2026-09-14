# Corpus documenti utente

Cartella di verifica sui **tuoi** documenti reali, non simulati.
Il misuratore `benchmark.utente` legge questa cartella e riporta:
- sostituzioni totali
- quante sono dati sensibili veri (secondo annotazione)
- rumore, elencato uno per uno

Il corpus resta LOCALE alla tua macchina — non viene versionato in git
(regola `.gitignore`: `benchmark/documenti_utente/*.pdf`,
 `*.docx`, `*.eml`, ecc.).

## Come metterci i file

1. Copia i file (uno o più) in questa cartella:
   ```
   benchmark/documenti_utente/
   ├── whitepaper_var.pdf
   ├── guida_deploy.md
   └── contratto_2026.docx
   ```
   Formati supportati: tutti quelli che l'app apre — pdf, docx, txt,
   md, csv, eml, msg, rtf, odt, xlsx, html.

2. Per ciascun file, crea un `.veri.json` a fianco con l'elenco dei
   dati sensibili veri (che TU consideri PII). Esempio:
   ```
   benchmark/documenti_utente/whitepaper_var.veri.json
   ```
   Contenuto:
   ```json
   {
     "dati_sensibili": [
       "Mario Rossi",
       "andrem.rossi@example.it",
       "IT60X0542811101000000123456"
     ]
   }
   ```
   Se un file non ha il `.veri.json` di annotazione, il misuratore lo
   segnala ma non lo esclude — conterà tutte le sostituzioni come
   "non annotate" (né vere né rumore).

3. Esegui:
   ```
   venv/bin/python -m benchmark.utente
   ```
   L'output finisce anche in `benchmark/documenti_utente_output.txt`.

## Interpretazione dei risultati

Per ogni file:
- `sost` = numero di entità sostituite nel testo
- `veri` = quante corrispondono a `dati_sensibili`
- `rumore` = quante NON corrispondono (elencate una per una nell'output)
- `veri_persi` = quante erano annotate ma NON sostituite

Obiettivo per un documento tecnico "puro" (poco o zero contenuto
personale): 0-3 sostituzioni, tutte veri. Se il tuo whitepaper ha
60+ sostituzioni con 2 dati sensibili veri, il rumore è 58 — troppo.

## Privacy dei file di test

I file in questa cartella non escono mai dalla macchina:
- sono ignorati da git
- il misuratore gira offline
- il vault di test è isolato in `/tmp/pb_utente_vault.db`
