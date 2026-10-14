# PrivacyBridge — manuale

**Anonimizzazione locale reversibile di documenti.**
I dati non lasciano mai il tuo computer.

Uno strumento desktop pensato per chi gestisce dati di clienti (studi
tecnici, di ingegneria, commercialisti) e vuole usare un assistente
AI cloud senza inviargli nomi, IBAN, codici fiscali o email reali.
Il flusso è: incolli il testo → l'app sostituisce i dati sensibili
con segnaposto (`«PERSONA_1»`, `«IBAN_1»`, …) → copi il testo pulito
nell'assistente AI → riporti la risposta nell'app in modalità
"Ripristina" → i valori reali tornano al loro posto.

## Come si installa (macOS)

1. Apri `PrivacyBridge.dmg`.
2. Trascina l'icona su **Applicazioni**.
3. Prima apertura: tasto destro sull'icona → **Apri** (l'app non è
   firmata da Apple; questo è normale per un'app open-source
   distribuita senza sviluppatore a pagamento).

## Come si installa (Windows)

1. Doppio click su `PrivacyBridge-Setup.exe`.
2. Segui l'installer (scelta cartella, collegamento Menu Start).
3. Al primo avvio Windows Defender può mostrare "Windows ha
   protetto il PC": clicca **Ulteriori informazioni** →
   **Esegui comunque**. Anche questo è normale per un exe non
   firmato con certificato commerciale.

## Come si usa

1. Apri PrivacyBridge (doppio click sull'icona). La finestra si
   apre in pochi secondi.
2. **Anonimizza**: incolla o carica un documento (PDF, DOCX, TXT,
   MD, CSV, EML, MSG, RTF, ODT, XLSX, HTML). Clicca **Anonimizza**.
3. Verifica i valori nella tabella "Entità trattenute": correggi
   quelli sbagliati, aggiungi quelli mancati, ignora i suggeriti
   che non ti servono. Se cambi qualcosa, clicca **Rianonimizza**.
4. Clicca **Copia**. Se l'app trova pattern che sembrano dati
   personali NON sostituiti, ti chiede conferma prima di
   copiare — ultimo controllo a occhio.
5. Incolla il testo nell'assistente AI (ChatGPT, Claude,
   Gemini, …), fai le tue domande, prendi la risposta.
6. Torna in PrivacyBridge, tab **Ripristina**, incolla la
   risposta, clicca **Ripristina**. I valori reali tornano.

## Tempi reali misurati

Su un portatile Intel i7-8750H (CPU, no GPU/MPS), con solo le
categorie di dati sensibili diretti attive (default):

| Dimensione testo | Tempo |
|---|---|
| 1.000 caratteri (un'email) | < 1 s |
| 10.000 caratteri (una pagina densa) | ~7 s |
| 25.000 caratteri (poche pagine) | ~22 s |
| 50.000 caratteri (un capitolo) | ~43 s |
| 100.000 caratteri (documento lungo) | ~125 s (~2 min) |

Su hardware più veloce (Apple Silicon M-series recenti, i9/Ryzen
di ultima generazione) i tempi possono essere ~4-5 volte più bassi
(l'utente ha misurato 25.9 s per 100.000 caratteri su una
configurazione più prestante).

La UI resta reattiva durante l'analisi: puoi scrivere in altri
campi, aprire dialog, cambiare tab. Il messaggio "Analisi in
corso — nomi, codici e recapiti vengono individuati…" ti tiene
informato.

## Cosa riconosce

Attivo di default:

- **Persona** (nome + cognome), anche in minuscolo se il contesto lo
  chiarisce ("ciao sono mario rossi")
- **Codice fiscale** (validato con la formula ufficiale)
- **Partita IVA** (11 cifre, checksum)
- **IBAN** (mod-97, italiano ed europeo)
- **Carta di credito** (Luhn)
- **Email, telefono, CAP, indirizzo** (anche casella postale)
- **Tessera sanitaria, documento d'identità** (CI, CIE, passaporto,
  patente, tessera TEAM — con parola chiave nel testo)
- **Data di nascita, luogo di nascita** (con contesto "nato a…",
  "residente a…")
- **Targa** (formato italiano, anche con spazi/trattini) e **numero
  di telaio VIN** (con parola chiave "telaio"/"VIN")
- **Numeri di pratica e procedimento** (R.G., sentenza, decreto,
  protocollo, fattura, polizza, matricola INPS/INAIL, atto notarile)
- **Handle social** (@nome.utente)

L'elenco completo dei tipi con formato e stato è in
[TASSONOMIA_PII.md](TASSONOMIA_PII.md).

Spenti di default (accendibili dal pulsante **Categorie**, o
selezionabili in blocco tramite i **preset**):

- Luogo generico, organizzazione, data generica, importo, URL, IP,
  MAC address, wallet crypto, numero di spedizione, riferimento
  catastale

## Cosa NON fa

- **Non chiama internet.** Nessuna telemetria, nessun cloud.
  L'unica connessione facoltativa è il controllo aggiornamenti
  all'avvio (disattivabile dal dialog Informazioni).
- **Non è perfetto.** Il riconoscimento neurale può mancare
  qualcosa o sbagliare. La tabella "Entità trattenute" è la tua
  rete di sicurezza: puoi correggere prima di copiare. La
  verifica pre-copia scandisce il testo alla ricerca di pattern
  residui e chiede conferma se ne trova.
- **PDF scansionati**: l'app usa l'OCR nativo del sistema (Vision
  su macOS, Windows OCR su Windows) sulle pagine senza testo,
  mostrando l'avanzamento pagina per pagina. Attenzione: su una
  scansione il rilevamento è meno affidabile (l'OCR può sbagliare
  caratteri, e un codice fiscale letto male non supera più il
  controllo di validità) — l'app te lo segnala e la tabella entità
  va controllata riga per riga. Se l'OCR di sistema non è
  disponibile, l'app lo dice e suggerisce un OCR esterno.

Il capitolo onesto sui limiti residui — con i numeri misurati su
documenti veri — è in [CONSEGNA.md](CONSEGNA.md).

## Sei garanzie di prodotto

Verificabili in ogni momento con `python tests/test_garanzie.py`:

1. **Deterministico** — stesso testo, stesso output, sempre.
2. **Mai corrompe il testo** — nessuna sostituzione a metà parola,
   nessuna che attraversa un a-capo, nessuno scambio di segnaposto.
3. **Zero fughe sui dati strutturati** — IBAN, CF, PIVA, email,
   telefono, carta di credito verificati aritmeticamente.
4. **Ripristino esatto** — `Ripristina(Anonimizza(X)) == X`,
   byte per byte.
5. **Segnaposto coerenti** — la stessa forma scritta ha sempre lo
   stesso segnaposto nell'intera sessione. Forme diverse (es.
   "Mario Rossi" vs "Rossi") hanno segnaposto distinti, ma la
   tabella entità mostra quale è correlato a quale.
6. **Mai silenzioso** — ogni sostituzione compare nella tabella
   prima che tu copi.

## Limiti noti

Vedi [BLOCCHI.md](BLOCCHI.md) per l'elenco completo. In breve:

- Su documenti scansionati (OCR) il rilevamento è meno affidabile:
  caratteri letti male fanno perdere i controlli di validità.
  Rimedio: controllo della tabella riga per riga (l'app avvisa).
- Nomi che coincidono con parole comuni ("massimo", "domenica",
  "salvo") in testo minuscolo senza contesto personale non vengono
  presi. Rimedio: **Rubrica personale** per i nomi ricorrenti.
- Recall organizzazioni ~56% (categoria spenta per default).
  Rimedio: correzione in tabella.
- Windows non è stato ancora testato su una macchina reale (il
  codice è portabile, lo script Inno Setup pronto; vedi
  `BLOCCHI.md § 11`).
- Il vault **non è cifrato**: è protetto dai permessi del
  filesystem (0600) e dalla cifratura del disco (FileVault,
  BitLocker). Chi copia il disco da spento legge i valori.

## Struttura del progetto

```
PrivacyBridge/
├── src/                     # tutto il codice eseguibile
│   ├── avvio.py             #   entry point (macOS/Windows)
│   ├── api/                 #   FastAPI + index.html (UI)
│   ├── backend/             #   motore, vault, rubrica, OCR
│   └── data/liste/          #   dizionari italiani (nomi, cognomi, comuni)
├── tests/                   # motore, tassonomia, avversariale,
│                            #   documenti+OCR, garanzie, UI
├── benchmark/               # corpora di misura + doc utente + matrice
├── docs/                    # manuale, decisioni, progresso, limiti,
│                            #   tassonomia, design, screenshot
├── scripts/                 # generazione liste, screenshot, contrasti,
│                            #   gate finale
├── assets/                  # icone e liste sorgenti (input di scripts/)
└── build/                   # ricette di impacchettamento (.spec, .sh,
                             #   .iss) e bundle costruito
```

## Licenza

MIT — © 2026 Andrea Sforna. Vedi `LICENSE`.
Attribuzioni delle dipendenze (modello neurale, dizionari nomi/
cognomi, vocabolario italiano, spaCy, Presidio) in `NOTICE.txt`.
