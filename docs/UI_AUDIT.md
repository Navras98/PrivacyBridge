# UI_AUDIT — PrivacyBridge

Data avvio audit: 2026-07-30. Fonte: `api/static/index.html` (1903 righe,
markup + CSS + JS in un unico file), riferimento incrociato con
`api/main.py` per gli endpoint.

Ogni riga documenta: **cosa dovrebbe fare**, **cosa fa**, **esito**.
Gli esiti sono:

- ✅ funziona come atteso
- 🟡 funziona ma ha un difetto documentato più sotto
- ❌ rotto o assente
- ⏸ da verificare al passo 5.2/5.3

L'inventario di questa sezione è statico (dal codice). Il file viene
aggiornato nei passi 5.2 (funzionamento), 5.3 (casi limite) e 5.4
(fix mirati).

---

## 1. Barra superiore (`<header class="barra">`)

| Rif. | Elemento | Cosa dovrebbe fare | Cosa fa (codice) | Esito |
|---|---|---|---|---|
| 1.1 | `.marchio` "PrivacyBridge" | Wordmark, non cliccabile | Testo statico. | ✅ |
| 1.2 | `.scheda[data-tab="anonimizza"]` | Apre vista Anonimizza | `apriScheda("anonimizza")`, alterna `hidden` sulle due `.vista`, sposta `aria-selected`. | ⏸ |
| 1.3 | `.scheda[data-tab="ripristina"]` | Apre vista Ripristina | Come sopra, tab "ripristina". | ⏸ |
| 1.4 | `#sel-sessione` | Cambia sessione attiva | `apriSessione(id)`: azzera lavoro corrente, ricarica tabella vuota, pannelli vuoti. Le entità restano nel vault. | ⏸ |
| 1.5 | `#btn-nuova` "Nuova sessione" | Crea nuovo id e diventa attivo | Genera 12-hex via `crypto.getRandomValues`, azzera pannelli, aggiunge la voce al select. | ⏸ |
| 1.6 | `#btn-elimina` "Elimina sessione" | Cancella la sessione dal vault | `confirm()` bloccante, poi `DELETE /sessioni/{id}`, azzera lavoro, crea nuova sessione. | ⏸ |
| 1.7 | `#btn-categorie` "Categorie" | Apre dialog categorie | `apriCategorie()`: fetch `/categorie`, disegna checkbox. | ⏸ |
| 1.8 | `#btn-rubrica` "Rubrica" | Apre dialog rubrica | `apriRubrica()`: fetch `/rubrica`, elenco. | ⏸ |
| 1.9 | `#btn-info` "i" | Apre dialog informazioni | `apriInfo()`. | ⏸ |

**Osservazioni statiche:**

- La barra ha ben **6 pulsanti** oltre al selettore, in una riga sola.
  Su schermi 1000×700 (minimo dichiarato) va verificato che non si
  spezzi (5.3).
- Nessuno dei pulsanti della barra ha stato disabilitato: `#btn-elimina`
  è sempre cliccabile anche senza sessioni caricate. La funzione fa
  early return su `!stato.sessione` (riga 1378) ma senza dare feedback.
  → possibile miglioria 5.2.
- Il `confirm()` di `#btn-elimina` è un dialog nativo del browser,
  non integrato col sistema visivo. Coerente ma brutale. Accettabile
  in questa fase.

---

## 2. Dialog Categorie (`#velo-categorie`)

| Rif. | Elemento | Cosa dovrebbe fare | Cosa fa | Esito |
|---|---|---|---|---|
| 2.1 | `#cat-lista input[type=checkbox]` | Attiva/disattiva categoria | `salvaCategorie()` su ogni change → `POST /categorie`. | ⏸ |
| 2.2 | `#btn-cat-default` "Ripristina default" | Reset alle categorie default_attive | Copia `default_attive`, rigenera checkbox, salva. | ⏸ |
| 2.3 | `#cat-conteggio` | Mostra "N attive" | Aggiornato dopo ogni disegno/salvataggio. | ⏸ |
| 2.4 | `#btn-cat-chiudi` "Chiudi" | Chiude dialog | `chiudiCategorie()` toggles `hidden`. | ⏸ |
| 2.5 | Click su velo (fuori dialog) | Chiude dialog | `veloCategorie.click` verifica `ev.target === veloCategorie`. | ⏸ |
| 2.6 | ESC | Chiude dialog | Handler `keydown` a documento. | ⏸ |
| 2.7 | Trap focus dentro dialog | Non implementato | `Tab` esce dal dialog verso lo sfondo. | 🟡 nota A11y-1 |

---

## 3. Dialog Rubrica (`#velo-rubrica`)

| Rif. | Elemento | Cosa dovrebbe fare | Cosa fa | Esito |
|---|---|---|---|---|
| 3.1 | `#rub-testo` | Testo da anonimizzare | Input di testo, `Enter` triggera Aggiungi. | ⏸ |
| 3.2 | `#rub-tipo` | Tipo entità per la voce | Popolato da `stato.tipi` in `popolaTipiRub()`. | ⏸ |
| 3.3 | `#btn-rub-aggiungi` "Aggiungi" | Aggiunge voce | `POST /rubrica`, ricarica elenco. Non filtra duplicati lato UI. | ⏸ |
| 3.4 | `#btn-rub-importa` "Importa CSV" | Apre file picker | Click delega a `#rub-file`. | ⏸ |
| 3.5 | `#rub-file` (hidden) | File CSV | Al `change` → `importaRubricaCSV(f)` → `POST /rubrica/importa`. | ⏸ |
| 3.6 | `#rub-conteggio` | "N voci" | Aggiornato dopo caricaRubrica. | ⏸ |
| 3.7 | `.b-rimuovi` su ogni riga | Elimina voce | `DELETE /rubrica?testo=...`, ricarica. **Nessuna conferma**. | 🟡 nota UX-1 |
| 3.8 | `#btn-rubrica-chiudi` "Chiudi" | Chiude dialog | Toggle hidden. | ⏸ |
| 3.9 | Click velo / ESC | Chiude dialog | Come categorie. | ⏸ |
| 3.10 | Trap focus / Tab | Non implementato | Come categorie. | 🟡 A11y-1 |

**Osservazioni:**

- Nota UX-1: eliminazione voce rubrica è definitiva ma senza conferma.
  Basta un click accidentale sulla × per perdere una voce anche
  ricorrente. Da correggere in 5.2 (aggiungere `confirm()` o richiedere
  doppio click).

---

## 4. Dialog Informazioni (`#velo-info`)

| Rif. | Elemento | Cosa dovrebbe fare | Cosa fa | Esito |
|---|---|---|---|---|
| 4.1 | `.marchio` "PrivacyBridge" | Titolo | Statico. | ✅ |
| 4.2 | `.versione` "Versione 1.0" | Versione | Statica hardcoded — non allineata a `app.version` di FastAPI (che è "1.0.0"). | 🟡 nota UX-2 |
| 4.3 | `.firma` "© 2026 Andrea Sforna — Licenza MIT" | Copyright | Statico. | ✅ |
| 4.4 | `#chk-aggiornamenti` (checkbox) | Attiva/disattiva controllo aggiornamenti | Al change → `POST /aggiornamenti/imposta`. | ⏸ |
| 4.5 | `#check-nota` | "Versione corrente: X. Ultimo controllo: Y." | Aggiornato in `caricaStatoAggiornamento()`. | ⏸ |
| 4.6 | `#btn-info-chiudi` "Chiudi" | Chiude dialog | Toggle hidden. | ⏸ |
| 4.7 | Click velo / ESC | Chiude dialog | ESC handler dedicato. | ⏸ |

**Nota UX-2:** far leggere la versione da `/health` o da un endpoint
dedicato invece di hardcodare, così è impossibile disallineare.
Rimando alla FASE 5.5 (pulizia).

---

## 5. Banner (`#banner`, `#banner-agg`)

| Rif. | Elemento | Cosa dovrebbe fare | Cosa fa | Esito |
|---|---|---|---|---|
| 5.1 | `#banner` | Mostra errore/avviso | `mostraErrore(msg, marca)` scrive testo, toglie `hidden`. `role="alert"` → screen reader annuncia. | ⏸ |
| 5.2 | `#banner-chiudi` × | Chiude banner | Toggle hidden. | ⏸ |
| 5.3 | `#banner-agg` | Avviso nuova versione | Mostrato solo se `/aggiornamenti` risponde con `nuova_versione`. | ⏸ |
| 5.4 | `#agg-link` "Scarica" | Apre URL download | `target="_blank" rel="noopener"`. In pywebview: si apre nel browser di sistema. | ⏸ |
| 5.5 | `#agg-chiudi` × | Chiude banner aggiornamento | Toggle hidden. | ⏸ |

---

## 6. Vista Anonimizza — barra azioni

| Rif. | Elemento | Cosa dovrebbe fare | Cosa fa | Esito |
|---|---|---|---|---|
| 6.1 | `#btn-carica` "Carica" | Apre file picker | Delega click a `#file` hidden. | ⏸ |
| 6.2 | `#file` (hidden) | File documento | Al change → `POST /carica`, riempie `#ta-originale`. Reset del `value` per permettere ri-selezione dello stesso file. | ⏸ |
| 6.3 | `#btn-anonimizza` "Anonimizza" | Chiama backend | Disabilita se stesso durante la chiamata → previene doppio click. | ⏸ |
| 6.4 | `#btn-copia` "Copia" | Copia testo anonimizzato | `disabled` finché `!haRisultato`. Feedback: bottone diventa "Copiato" per 1200ms. Nessuna verifica pre-copia (FASE 5-bis). | 🟡 nota FASE 5-bis |
| 6.5 | `#btn-svuota` "Svuota" | Azzera testo e risultato | `azzeraLavoro()`. Non chiede conferma. | ⏸ |
| 6.6 | `#sel-lingua` | Forza lingua | Passato in payload di `/anonimizza`. Default Italiano. | ⏸ |
| 6.7 | `#stato` | Messaggio di lavorazione | `creaStato()`: `lavora` con delay 300ms, `fatto`, `fioco`. | ⏸ |

**Nota FASE 5-bis:** il pulsante Copia va integrato con la verifica
finale prima della copia (scan del testo per pattern residui). Vedi
task 9 nel piano.

---

## 7. Vista Anonimizza — pannello sinistro (Originale)

| Rif. | Elemento | Cosa dovrebbe fare | Cosa fa | Esito |
|---|---|---|---|---|
| 7.1 | `#ta-originale` | Textarea del testo originale | Input diretto o riempito da `/carica`. `spellcheck="false"` (evita rumore visivo). | ⏸ |
| 7.2 | `#vista-originale` | Vista con `<mark>` sui valori sensibili | Popolata dopo Anonimizza, con `mark.valore[data-ph="..."]`. | ⏸ |
| 7.3 | `#btn-modifica` "Modifica testo" | Torna in modalità editing | Ripopola textarea da `stato.originale`, mostra `#ta-originale`. | ⏸ |
| 7.4 | `#metriche-sx` | Contatore caratteri | Aggiornato su `input` e dopo Anonimizza. | ⏸ |

**Osservazione:** dopo Anonimizza il pannello si commuta in modalità
"confronto" (textarea nascosta, div letto con highlights) e appare
"Modifica testo" per tornare indietro. Corretto ma non ovvio all'utente
non tecnico. La testa del pannello resta uguale — nessuna indicazione
"stai vedendo l'evidenziato". Nota UX-3.

---

## 8. Vista Anonimizza — pannello destro (Anonimizzato)

| Rif. | Elemento | Cosa dovrebbe fare | Cosa fa | Esito |
|---|---|---|---|---|
| 8.1 | `#vista-anonimizzato` | Testo con chip `<span class="segnaposto">` | Popolato dopo anonimizza. | ⏸ |
| 8.2 | `#vuoto-dx` "Incolla o carica…" | Stato vuoto | Nascosto se `haRisultato`. | ⏸ |
| 8.3 | `#metriche-dx` | "N valori trattenuti · N occorrenze · N caratteri" | Aggiornato in `aggiornaPannelli()`. | ⏸ |
| 8.4 | `.gola` centrale (perforazione) | Elemento firma del design | `aria-hidden="true"`. Passaggio mouse su valore/segnaposto → `#tacca` mostra allineamento. | ⏸ |

---

## 9. Vista Anonimizza — tabella entità

| Rif. | Elemento | Cosa dovrebbe fare | Cosa fa | Esito |
|---|---|---|---|---|
| 9.1 | `.c-num` | Numero riga | Indice + 1. | ✅ |
| 9.2 | `.c-ph` (Placeholder) | Chip col nome del segnaposto | Se assegnato: chip verderame. Se vuoto: "assegnato alla rianonimizzazione". | ⏸ |
| 9.3 | `.in-valore` (input) | Modifica valore reale | Su `input`: aggiorna `stato.entita`, segnala `obsoleto`. | ⏸ |
| 9.4 | `.sel-tipo` (select) | Cambia tipo entità | Su `change`: aggiorna, segnala obsoleto. Include tipo corrente anche se non nella lista base. | ⏸ |
| 9.5 | `.c-occ` (Occorrenze) | Conteggio | Da backend. `null`/`undefined` → "—". | ⏸ |
| 9.6 | `.b-rimuovi` × | Elimina riga | Splice + ridisegna + obsoleto. Nessuna conferma. | ⏸ |
| 9.7 | `#btn-aggiungi` "+ Aggiungi" | Riga vuota | Push oggetto placeholder="", focus sul valore. | ⏸ |
| 9.8 | `#btn-rianonimizza` "Rianonimizza" | Riapplica mappa corretta | `POST /rianonimizza`. | ⏸ |
| 9.9 | `#tabella-vuota` | Stato vuoto | Mostrato se `stato.entita.length === 0`. | ⏸ |

**BUG STRUTTURALE identificato (FASE 5.4a — bug reale, non solo miglioria):**
Il backend emette entità normali E entità con `suggerito: true`
(livello 3 del recognizer nomi ambigui) nella STESSA lista. L'UI le
mette tutte nella tabella entità senza distinzione. Le suggerite hanno
`placeholder=""` e vengono visualizzate come **"assegnato alla
rianonimizzazione"** — identiche a righe aggiunte manualmente
dall'utente. Effetti:

1. Utente vede righe "extra" che non ha creato lui e non capisce da
   dove vengono (`Gatto`, `Fiore`, `Aurora` per testo ordinario).
2. Se preme Rianonimizza, i valori suggeriti diventano attivi
   silenziosamente — sostituendo parole del testo che l'utente non
   intendeva anonimizzare.
3. Il commento nel codice `motore.py:1152` recita *"la UI li mostrerà
   in una sezione Possibili entità con la casella non spuntata"* ma
   **quella sezione non esiste**.

→ Fix in FASE 5.4a: sezione dedicata, casella non spuntata, ordinata
per confidenza/frequenza, con limite di visualizzazione.

**Evidenza empirica** (`python -m backend.motore` con testo "il gatto
dorme vicino al camino" — 2026-07-30):

```
INPUT:  il gatto dorme vicino al camino
OUTPUT: il gatto dorme vicino al camino
ENTITA: 1
  [SUG] ph="" val="gatto" tipo=PERSONA occ=1
```

Il testo non è modificato (corretto: i suggeriti non sostituiscono),
ma la riga arriva nella lista `entita` e finisce nella tabella UI
come "assegnato alla rianonimizzazione". Se l'utente clicca
Rianonimizza (magari dopo aver aggiunto altre voci), quel valore
viene applicato.

---

## 10. Vista Ripristina

| Rif. | Elemento | Cosa dovrebbe fare | Cosa fa | Esito |
|---|---|---|---|---|
| 10.1 | `#btn-ripristina` "Ripristina" | Chiama `/deanonimizza` | Disabilita durante la chiamata. | ⏸ |
| 10.2 | `#btn-copia-rip` "Copia" | Copia ripristinato | `disabled` finché `!ripristinato`. | ⏸ |
| 10.3 | `#btn-svuota-rip` "Svuota" | Azzera vista ripristina | Reset completo del pannello. | ⏸ |
| 10.4 | `#stato-rip` | Messaggio | Come `#stato`. | ⏸ |
| 10.5 | `#ta-risposta` | Textarea risposta LLM | Input diretto. `spellcheck="false"`. | ⏸ |
| 10.6 | `#vista-ripristinato` | Testo ripristinato con `<span class="ignoto">` sui segnaposto residui | Popolato dopo ripristina. | ⏸ |
| 10.7 | `#vuoto-rip` "Incolla una risposta…" | Stato vuoto | Nascosto se ripristinato. | ⏸ |
| 10.8 | `#avviso-rip` | Warning segnaposto sconosciuti / non trovati | Mostrato se `report.warning` o `report.non_trovati` non vuoti. | ⏸ |

**Osservazione:** manca completamente un modo per **vedere il
contenuto del vault** in questa vista. L'utente che apre l'app oggi e
vuole ripristinare un testo di ieri non ha modo di sapere quali
segnaposto la sessione contiene. Documentato in `BLOCCHI.md § 7`
→ fix in FASE 5.4b.

---

## 11. Elementi decorativi non interattivi

Tutti da `aria-hidden="true"` o senza aria:

- `.gola` (perforazione centrale), `.occhiello` alto/basso
- `.tacca` (evidenziatore posizione)
- `.dorsale` (barra colorata in cima ai pannelli, in CSS)

Nessun problema di accessibilità: sono decorazioni visive dichiarate.

---

## 12. Accessibilità — sommario problemi (A11y-*)

| Cod. | Problema | Gravità |
|---|---|---|
| A11y-1 | Nessun trap del focus nei dialog | Media |
| A11y-2 | Nessun `<label>` esplicito per `.in-valore` (usa `aria-label` per riga) | Bassa |
| A11y-3 | ESC chiude solo un dialog per volta anche se ne apri due (impossibile in pratica; ma se un futuro banner si sovrappone → ok, banner ha X) | Bassa |
| A11y-4 | `#btn-modifica` compare senza cambio di focus né annuncio → screen reader non lo scopre | Media |
| A11y-5 | Highlight `mark.valore.acceso` è solo cambio colore/ombra — nessuna alternativa non-cromatica | Bassa (info ridondante) |

---

## 13. Endpoint API mappati alla UI

Dal codice `api/main.py` (linee riferite):

| Endpoint | Metodo | Consumato in `index.html` | Esito |
|---|---|---|---|
| `/anonimizza` | POST | ✅ btn-anonimizza | ✅ |
| `/rianonimizza` | POST | ✅ btn-rianonimizza | ✅ |
| `/deanonimizza` | POST | ✅ btn-ripristina | ✅ |
| `/carica` | POST | ✅ file input | ✅ |
| `/sessioni` | GET | ✅ caricaSessioni | ✅ |
| `/sessioni/{id}` | GET | ❌ nessuna chiamata | 🟡 morto |
| `/sessioni/{id}` | DELETE | ✅ btn-elimina | ✅ |
| `/tipi` | GET | ✅ caricaTipi | ✅ |
| `/categorie` | GET/POST | ✅ | ✅ |
| `/aggiornamenti` | GET | ✅ | ✅ |
| `/aggiornamenti/imposta` | POST | ✅ | ✅ |
| `/rubrica` | GET/POST/DELETE | ✅ | ✅ |
| `/rubrica/importa` | POST | ✅ | ✅ |
| `/` | GET | (bootstrap) | ✅ |
| `/health` | GET | ❌ nessuna chiamata dalla UI (usato da avvio.py) | ✅ |

**Endpoint 🟡:** `GET /sessioni/{id}` è definito nell'API (righe
174-191 di `api/main.py`) ma la UI non lo chiama mai. Serve
esattamente al "vista consultativa del vault" della FASE 5.4b: è già
pronto lato server. Ottimo — l'audit ha già rivelato un pezzo di
lavoro fatto.

---

## Riepilogo iniziale (statico) — cose da correggere in FASE 5.4/5.5

| ID | Categoria | Descrizione | Fase |
|---|---|---|---|
| BUG-UI-1 | Bug funzionale | Suggeriti mescolati con entità nella tabella | 5.4a |
| BUG-UI-2 | Mancanza | Vista consultativa vault assente | 5.4b |
| BUG-UI-3 | Mancanza | Preset categorie assenti | 5.4c |
| BUG-UI-4 | Bug funzionale | Copia non esegue verifica finale | 5-bis |
| UX-1 | UX | Eliminazione voce rubrica senza conferma | 5.2 |
| UX-2 | Coerenza | Versione app hardcoded nella UI | 5.5 |
| UX-3 | Chiarezza | Modalità confronto non ha etichetta | 5.2 |
| A11y-1 | A11y | Focus trap dialog | 5.2 |
| A11y-4 | A11y | Focus non spostato quando compare `#btn-modifica` | 5.2 |
| DEAD-1 | Codice morto | `GET /sessioni/{id}` non chiamato (verrà usato in 5.4b) | 5.5 |

---

## Prossimi passi

- **5.2** — Verificare uno per uno tutti i punti ⏸ con test Playwright
  o interazione manuale, e riportare qui.
- **5.3** — Casi limite (testo vuoto, 100k, ecc.).
- **5.4** — Fix BUG-UI-1/2/3.
- **5.5** — Pulizia.
- **5-bis** — 6 garanzie + verifica pre-copia.

---

## Chiusura audit — 2026-07-30

Le sotto-fasi 5.4 e 5-bis sono state chiuse (fix reali con test
dedicati). Le 5.2 (verifica click-per-click) e 5.3 (11 casi limite
integrali) NON sono state percorse riga per riga: motivi e copertura
alternativa nella tabella qui sotto. La motivazione della scelta è in
`DECISIONI.md` § 2026-07-30 (chiusura Gate 5 senza audit click-per-click).

### Esiti finali dei bug identificati nella FASE 5.1

| ID | Descrizione | Esito | Copertura di test |
|---|---|---|---|
| BUG-UI-1 | Suggeriti mescolati alle entità | ✅ FIXED (5.4a) | 3 test Playwright `test_fase5a_*` |
| BUG-UI-2 | Vault consultativo assente | ✅ FIXED (5.4b) | `test_fase5b_vault_vista_consultativa` |
| BUG-UI-3 | Preset categorie assenti | ✅ FIXED (5.4c) | `test_fase5c_preset_categorie` |
| BUG-UI-4 | Copia senza verifica finale | ✅ FIXED (5-bis) | 2 test `test_fase5bis_*` |
| UX-1 | Rimozione voce rubrica senza conferma | ✅ FIXED (5.5) | `confirm()` aggiunto |
| UX-2 | Versione hardcoded nella UI | ✅ FIXED (5.5) | letta da `/health` |
| UX-3 | Modalità confronto senza etichetta | ⏳ rimandato | — |
| A11y-1 | Focus trap dialog | ⏳ rimandato | — |
| A11y-4 | Focus quando compare btn-modifica | ⏳ rimandato | — |
| DEAD-1 | `GET /sessioni/{id}` non chiamato | ✅ non più morto | ora usato dalla vault view |

### Gate 2 — audit UI (2026-07-30 secondo giro)

Sei casi funzionali che il briefing chiedeva di verificare dopo la
FASE 5 (allora saltati). Ognuno ha ora un test Playwright dedicato.

| Caso | Test | Esito |
|---|---|---|
| Testo 100.000 caratteri, UI reattiva | `test_gate2_ui_regge_100k_caratteri` | ✅ |
| Doppio click su Anonimizza | `test_gate2_doppio_click_anonimizza` | ✅ |
| Resize a 1000×700, no overflow | `test_gate2_resize_minimo` | ✅ |
| Ripristino senza segnaposto → conteggio 0 chiaro | `test_gate2_ripristino_senza_segnaposto` | ✅ |
| Ripristino con segnaposto d'altra sessione → avviso | `test_gate2_ripristino_segnaposto_altra_sessione` | ✅ |
| Eliminazione ultima sessione → app usabile | `test_gate2_elimina_ultima_sessione` | ✅ |

**Note ai casi:**

- **100k caratteri**: il test verifica l'invariante UI (input
  accettato, contatore aggiornato, altri controlli reattivi anche
  dopo input grande). NON invoca il backend perché l'inferenza del
  neurale su 100k su hardware Intel i7-8750H CPU-only impiega ~90s
  (misure: 25k→18s, 50k→44s, 100k→~90s). Il messaggio di stato
  "Analisi in corso" informa l'utente durante l'attesa.
- **Resize a 1000×700**: c'era overflow orizzontale di 113px. Ho
  aggiunto una media query `@media (max-width: 1200px)` che
  comprime i gap della barra, nasconde l'etichetta "Sessione" e
  riduce la dimensione dei pulsanti. Nessun elemento tagliato.
- **Doppio click**: il handler già disabilitava il bottone durante
  la chiamata; test lo conferma.

### Migliorie applicate durante Gate 2

- `.barra` gap ridotto da `--s5` a `--s4` (più compatto anche a
  viewport standard).
- Media query per viewport ≤ 1200px: comprime la barra.

**Note sui rimandati (⏳):**

- **UX-3**: la modalità confronto è già segnalata visivamente
  (highlight `<mark>` sui valori) e la testa del pannello è coerente
  (dorsale ceralacca). Un'etichetta esplicita è un miglioramento
  cosmetico, non un bug funzionale. Va nella FASE 6 (rifinitura
  grafica).
- **A11y-1 / A11y-4**: sono migliorie di accessibilità, non
  regressioni. Vanno affrontate insieme in un giro dedicato di test
  screen-reader/tastiera (fuori dall'ambito di questa fase). Le altre
  A11y-2/3/5 sono di bassa gravità.

### Coperture di test finali

| Corpus | Test | Esito |
|---|---|---|
| backend / motore | tests/test_motore.py | 121 pass + 1 xpassed |
| documenti | tests/test_documenti.py | 19 pass |
| garanzie prodotto | tests/test_garanzie.py | 9 pass (nuovo, FASE 5-bis) |
| interfaccia (Playwright) | tests/test_interfaccia.py | 20 pass (13 storici + 7 nuovi) |

**Totale: 170 test verdi** in 128s (esecuzione locale 2026-07-30).

### Ultimo tocco: `window.__pb` per test (DECISIONE 2026-07-30)

Per rendere testabile il flusso della verifica pre-copia in isolamento
(iniettare un residuo nel testo in uscita) senza dover ricostruire
tutto lo stato via click, ho esposto una piccola API di test:

```js
window.__pb = { stato, verificaResidui, aggiornaPannelli };
```

Non è usata dal codice di produzione. Non espone credenziali. Serve
esclusivamente a Playwright per test end-to-end. Documentata in
`DECISIONI.md`.

