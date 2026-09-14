# AUDIT DI PRECISIONE — dove PrivacyBridge sbaglia ancora

Data: 2026-08-01. Hardware: Intel i7-8750H, macOS 15 (Darwin 24.6.0),
CPU only. Ogni numero di questo documento viene da un comando eseguito
su questa macchina; nessuno è stimato, nessuno è ricordato.

Questo non è un documento di rassicurazione. È l'elenco degli errori che
il motore commette ancora, raggruppati per **causa** e non per esemplare,
ciascuno con quanti casi sono, che percentuale rappresentano, e che cosa
costerebbe togliere quella causa.

Indice:

1. [Come è stata fatta la misura](#1-come-è-stata-fatta-la-misura)
2. [Le due baseline](#2-le-due-baseline)
3. [Falsi negativi, per causa](#3-falsi-negativi-per-causa)
4. [Falsi positivi, per causa](#4-falsi-positivi-per-causa)
5. [Errori di tipo](#5-errori-di-tipo)
6. [I tre limiti dichiarati, riaperti](#6-i-tre-limiti-dichiarati-riaperti)
7. [Proposte, ordinate per rapporto guadagno/rischio](#7-proposte-ordinate-per-rapporto-guadagnorischio)
8. [Quello che non propongo, e perché](#8-quello-che-non-propongo-e-perché)

---

## 1. Come è stata fatta la misura

### 1.1 Due misure diverse, perché servono a due domande diverse

I documenti veri dell'utente (`benchmark/documenti_utente/`, 8 file, 247k
caratteri) dicono **quanto il motore sbaglia**: si legge l'uscita e si
vede che cosa ha toccato e che cosa ha lasciato. Non dicono **quanto
manca**, perché non sono annotati: senza annotazione non esiste il
denominatore.

Il corpus annotato (`tests/corpus_annotato.py`, 76 frasi, 195 span
segnati uno per uno) è l'unico posto dove il richiamo si calcola invece
di stimarlo. È testo scritto per i test, quindi **non vale come misura
del prodotto**: vale come misura relativa fra un prima e un dopo, e come
diagnostica per capire quale classe di errore si sta guardando.

Regola applicata in tutto il documento: **i numeri che descrivono il
prodotto vengono dai documenti dell'utente. I numeri che descrivono una
classe di errore vengono dal corpus.** Non sono intercambiabili e non
vengono sommati.

### 1.2 Due errori di misura trovati e corretti prima di misurare

Il primo giro di audit ha riportato **616 sostituzioni** dove la baseline
di consegna diceva 141. Nessuna delle due cifre era sbagliata: erano
misure di due cose diverse.

**Errore 1 — il benchmark leggeva le impostazioni dell'utente.**
`_leggi_categorie_attive()` legge
`~/Library/Application Support/PrivacyBridge/impostazioni.json`. L'utente
sta usando l'app al lavoro e ha acceso tutte e 27 le categorie; ha anche
una rubrica personale non vuota (`_leggi_termini_rubrica()` restituiva
`{'donati'}`). Ogni benchmark eseguito su questa macchina stava quindi
misurando *la configurazione dell'utente di oggi*, non il prodotto.

Correzione di classe: `benchmark/__init__.py` espone `isola()`, che
sposta la cartella dati in una temporanea **prima** che qualunque cosa di
`backend` venga importata, e `CATEGORIE_CONSEGNA`, la lista esplicita
delle 17 categorie accese per difetto. Ogni script di benchmark ora
chiama `isola()` a livello di modulo e passa `categorie_attive`
esplicitamente. Verificato: `impostazioni lette = {}`,
`rubrica letta = set()`, baseline riprodotta a 141 esatte.

**Errore 2 — i file derivati inquinavano la cartella dei documenti.**
`benchmark.utente` elenca i file di `documenti_utente/` e li tratta tutti
come documenti. I dump di testo prodotti da `verifica_ocr.py` e dalla
cache dell'audit finivano lì dentro: 17 "documenti" invece di 8, e 349
sostituzioni invece di 141, contando due volte le stesse entità. Il
difetto è precedente a questa sessione.

Correzione di classe: tutto il testo derivato va in
`documenti_utente/estratti/`. `iterdir()` + `is_file()` esclude le
sottocartelle, quindi una regola sola sostituisce qualunque lista di
suffissi da ignorare.

### 1.3 Gli strumenti scritti per questo audit

| Script | Che cosa misura |
|---|---|
| `benchmark/audit_precisione.py` | Ogni entità emessa col suo contesto (falsi positivi) + scansione del **testo in uscita** con 10 schemi indipendenti e volutamente larghi (falsi negativi) |
| `benchmark/misura_corpus.py` | Richiamo e precisione per tipo sul corpus annotato, distinguendo span sbagliato da tipo sbagliato |
| `benchmark/ocr_opzioni.py` | Quattro configurazioni dell'OCR di sistema sulle stesse pagine |
| `benchmark/ocr_normalizza.py` | Guadagno **e danno** della normalizzazione delle confusioni OCR prima del rilevamento |

La scansione dei residui non riusa i recognizer dell'applicazione. Se
usasse la stessa logica che sta valutando non troverebbe mai nulla: usa
schemi indipendenti, tolleranti agli errori dell'OCR, che sbagliano per
eccesso di proposte. Filtrarle è compito di chi legge, ed è stato fatto a
mano, voce per voce.

---

## 2. Le due baseline

### 2.1 Documenti reali dell'utente — configurazione di consegna

`venv/bin/python -m benchmark.audit_precisione` (17 categorie accese,
quelle di fabbrica):

| Documento | Caratteri | Entità attive | Suggerite | Residui grezzi |
|---|---:|---:|---:|---:|
| Analisi Sangue … verifica glutine.pdf | 1.583 | 8 | 1 | 6 |
| Hetepi_Agent_AI.pdf | 90.696 | 4 | 1 | 2 |
| Indagine .pdf | 30.252 | 67 | 8 | 19 |
| Portafoglio_Intelligence.pdf | 46.382 | 1 | 0 | 0 |
| README.md | 2.085 | 3 | 0 | 0 |
| Atto_giudiziario.pdf | 47.782 | 36 | 2 | 26 |
| hetepi_simulato.txt | 1.637 | 7 | 0 | 0 |
| rizzo-pii-report.pdf | 26.516 | 15 | 7 | 2 |
| **TOTALE** | **246.933** | **141** | **19** | **55** |

141 è identico alla baseline di consegna: la misura è di nuovo ermetica.
I 55 "residui grezzi" sono proposte dello scanner larghe, non falsi
negativi: la classificazione a mano è al capitolo 3.

Con tutte e 28 le categorie accese: **616 attive, 12 suggerite, 15
residui**. Per tipo: LUOGO 258, ORG 111, DATA 78, PERSONA 69, URL 25,
EMAIL 24, TELEFONO 18, IMPORTO 7, CARTA 5.

### 2.2 Corpus annotato — richiamo per tipo

`venv/bin/python -m benchmark.misura_corpus` (tutte le categorie accese:
misura di che cosa il motore è capace, non di che cosa è acceso):

```
tipo            att.  esatto  parz.  t.err  manc.  richiamo  spuri
--------------------------------------------------------------------
PERSONA           54      49      2      0      3     94.4%      0
ORG               46      22     10      8      6     87.0%      1
LUOGO             28      16      1     11      0    100.0%      5
DATA              21      19      0      2      0    100.0%      2
EMAIL             11      11      0      0      0    100.0%      0
TELEFONO           8       8      0      0      0    100.0%      0
PIVA               6       5      1      0      0    100.0%      0
CAP                5       5      0      0      0    100.0%      0
CF                 5       5      0      0      0    100.0%      0
IBAN               4       4      0      0      0    100.0%      0
URL                3       1      2      0      0    100.0%      0
IP                 2       1      1      0      0    100.0%      0
CARTA              2       2      0      0      0    100.0%      0
--------------------------------------------------------------------
TOTALE           195     148     17     21      9     95.4%      9

richiamo largo (span anche imperfetto):  95.4%
richiamo stretto (span e tipo esatti):   75.9%
span spuri (non annotati):               9
```

Le due colonne dicono cose diverse e vanno lette insieme. Il **richiamo
largo** è quello che conta per la privacy: il dato è stato coperto, anche
se con un'etichetta o un confine imperfetti. Il **richiamo stretto**
conta per la leggibilità dell'uscita e per la tabella che l'utente deve
controllare.

### 2.3 Una cifra dichiarata che non torna

`CONSEGNA.md` § 9.3 dice: **"Organizzazioni: recall ~56%"**. Misurato
ora: **87,0% largo, 47,8% stretto** (22 span esatti su 46). Nessuno dei
due è 56%. La cifra dichiarata veniva da una sessione precedente, con un
corpus diverso, e non è mai stata rimisurata su questo.

Va corretta in `CONSEGNA.md`, e va detto perché è successo: **un numero
ricordato non è un numero verificato.** È lo stesso errore già annotato
nel capitolo 9 a proposito delle e-mail ("avevo scritto 2, rimisurate
sono 3"). Le due occorrenze insieme dicono che il difetto non è
l'attenzione di chi scriveva: è che mancava un comando che rifacesse la
misura. Ora c'è, ed è `benchmark/misura_corpus.py`.

---

## 3. Falsi negativi, per causa

Metodo: scansione del **testo anonimizzato in uscita** — cioè di ciò che
davvero uscirebbe dal computer — con 10 schemi indipendenti. Le 55
proposte grezze sono state lette una per una e classificate. Dei 55
residui, **9 sono falsi negativi veri**; gli altri 46 sono dati fuori
perimetro, categorie spente per scelta, o artefatti dello scanner.

| Causa | Casi veri | % dei residui | Ricorrenza |
|---|---:|---:|---|
| A. Separatore di telefono non previsto (`.` e `/`) | 3 | 5,5% | strutturale, ogni documento italiano |
| B. E-mail sfigurata dall'OCR | 2 | 3,6% | solo su scansione |
| C. Sequenza carta che non supera Luhn | 3 (su 4 candidati) | 5,5% | solo su scansione |
| D. Span troncato che lascia in chiaro il resto del nome | 1 | 1,8% | strutturale |
| E. Nome dopo un a capo | 1 | 1,8% | strutturale, testo impaginato |
| — Categoria spenta per scelta (DATA, ORG) | 37 | 67,3% | per progetto |
| — Artefatti dello scanner larghe | 9 | 16,4% | non è un difetto del motore |

### A. Separatore non previsto — 3 casi, la causa più netta

Tre numeri di telefono restano in chiaro in `Atto_giudiziario.pdf`, tutti con contesto esplicito:

```
075/9115329       ctx: "tel."
075.5098004       ctx: "n. di fax"
075.5731533       ctx: "contattare telefonicamente il n."
```

La causa non è il contesto né il dizionario: è una riga di regex.
`_TEL_IT_REGEX` (`src/backend/recognizers.py:435`) ammette come
separatori **solo spazio e trattino**. Il commento accanto dice che
l'esclusione fu deliberata: *"chi scrive '+39.333.1234567' è raro; chi
scrive metriche con punto è comune"*.

La prova che l'esclusione è troppo larga sta nello stesso documento:
**due di questi tre numeri sono già mascherati altrove nella stessa
pagina, nella forma con lo spazio** (`075 5731533`, `075 5098004`). Il
motore conosce quei numeri. Li perde solo quando l'autore ha battuto un
punto invece di uno spazio.

Misura della sostituzione della classe di separatori con `[\s\-./]`, con
il lookahead negativo esteso a `/`:

```
                     ATTUALE   PROPOSTA
deve trovare (9)        5/9       9/9
non deve trovare (18)  18/18     18/18
```

Le 18 esche includono `03/10/2025 09:23`, `23.06.2002 ore 06.30`,
`0,92`, `0.987 0.990`, `30/12/2013`, `18/05/2017`, `art. 0/2019`,
`prot. 0123/2026`, `delibera 0447/98`, `versione 3.0.1`,
`coordinate 45.4642 9.1900`, `€ 1.234,56`, `cap 06100`. Nessuna viene
presa né prima né dopo: i lookbehind e lookahead che già escludevano le
date e i decimali continuano a farlo, perché guardano le **cifre
adiacenti**, non i separatori interni.

**Costo**: una riga. **Rischio**: da riverificare sulle 606 prove
avversariali e sulla matrice a 22 casi. **Guadagno misurato**: 3 falsi
negativi veri su documento reale, e una classe intera chiusa.

### B. E-mail sfigurata dall'OCR — 2 casi

```
rossi @esempio.it        spazio prima della chiocciola
support @mocha.ni         spazio prima della chiocciola
```

Sono gli stessi indirizzi che il motore maschera correttamente altrove:
un carattere di troppo li rende invisibili. La terza e-mail citata in
`CONSEGNA.md` (`…ufficio@.pec.esempio.it`, punto subito dopo la
chiocciola) è una PEC di una questura — un ente, non una persona — e la
classifico fuori perimetro, non come falso negativo.

Il vincolo che governa questa correzione è **G4, il ripristino byte per
byte**. Non si può normalizzare il testo prima del rilevamento: ogni
carattere tolto sposta tutte le posizioni successive e il ripristino non
torna più al documento originale. La correzione ammissibile è una sola:
**riconoscere la forma corrotta con la corruzione dentro lo span**, così
che a essere sostituito sia esattamente `rossi @esempio.it`, spazio
compreso, e il ripristino rimetta esattamente quei caratteri.

### C. Sequenze carta che non superano Luhn — 3 casi veri su 4 candidati

```
3977•••••••••••      15 cifre  Luhn NO  ctx "#"           → PII vera
4347 ••••••••••••    16 cifre  Luhn NO                     → PII vera
5544•••••••••••      15 cifre  Luhn NO  ctx "master card"  → PII vera
6217•••••••••••••••  19 cifre  Luhn NO  ctx "Visitor 1D:"  → falso positivo
```

Tre su quattro sono varianti sfigurate di carte vere già presenti nel
documento: `4347 ••••••••••••` è `4397 •••• •••• 2131` con una cifra
letta male. Il controllo di Luhn, che serve a tenere alta la precisione,
qui **causa la fuga**: scarta il candidato proprio perché è corrotto,
cioè proprio nel caso in cui il dato è più a rischio.

Il quarto caso mostra perché non basta togliere Luhn: `Visitor 1D:` è un
identificativo di sessione, e senza il checksum entrerebbe. La
discriminante disponibile è il **contesto lessicale**: `master card`,
`visa`, `carta di credito`, `#` compaiono accanto ai tre veri e non
accanto al falso.

### D–E. Span troncato e nome dopo un a capo — 2 casi

```
Avv. DONATELLA «PERSONA_6» SANGRO     nome e cognome restano in chiaro
Dott.ssa⏎Avila                        il cognome è su un'altra riga
```

Nel primo caso il motore ha preso il **secondo** nome della sequenza e
lasciato in chiaro il primo e il cognome — è il caso peggiore, perché la
tabella mostra un'entità e l'utente crede che la riga sia coperta.

---

## 4. Falsi positivi, per causa

Metodo: le 67 entità di `Indagine .pdf` — il documento scansionato — sono
state lette una per una col loro contesto. È il documento con la densità
di errore più alta, e quindi quello che rende visibili le classi.

Su 37 entità PERSONA, **17 sono falsi positivi (46%)**. Sugli altri
documenti, digitali, la stessa lettura non ha trovato falsi positivi
PERSONA. La differenza non è statistica: è che l'OCR produce frammenti
che somigliano a nomi.

| Causa | Casi | Esempi |
|---|---:|---|
| Enti e uffici trattati come persona | 5 | `Polizia`, `polizia`, `SICUREZZA`, `DELLA PUBBLICA SICUREZZA`, `Mario Polizia` |
| Frammenti prodotti dall'OCR | 5 | `cei cati`, `cati`, `Suri`, `enni`, `uma` |
| Parole inglesi comuni | 3 | `hope`, `may`, `May` (dalla data `Z4-May-DE`) |
| Nomi propri dentro espressioni fisse | 2 | `Valentino` (San Valentino), `Natale` (Babbo Natale) |
| Sequenze di parole comuni | 2 | `della tua`, `sulla carta di credito` |

Fuori da PERSONA, sullo stesso documento: `0131268` (TELEFONO, spazzatura
OCR) è un falso positivo netto; `5652 AH` (CAP) è un codice postale
olandese, formalmente giusto ma fuori perimetro dichiarato.

Sul corpus annotato gli span spuri sono 9 su 195 (4,6%), e le classi si
ripetono: `Buongiorno` ×2 e `portale` e `Appaltatore` come LUOGO,
`lunedì` e `venerdì` come DATA, `Sig` come ORG.

**Osservazione che vale più dei singoli casi**: quasi tutti i falsi
positivi sono **innocui per la privacy e dannosi per la leggibilità**.
Mascherano una parola che non andava mascherata; non lasciano uscire
niente. Il costo è che gonfiano la tabella e fanno perdere fiducia in
essa. Il rimedio giusto non è alzare le soglie — che farebbe salire i
falsi negativi, che sono il danno vero — ma **rendere immediata la
correzione**. È esattamente ciò che chiede la Parte 2 di questo mandato.

---

## 5. Errori di tipo

Sono i casi in cui lo span è perfetto e l'etichetta è sbagliata. **Non
sono fughe di dati**: il valore è mascherato, il ripristino funziona, la
tabella mostra una categoria imprecisa.

Sul corpus: 21 su 195 span (10,8%).

| Classe | Casi | Che cosa succede |
|---|---:|---|
| Enti pubblici etichettati LUOGO | 8 | `Comune di Rimini`, `Comune di Milano` ×2, `Comune di Bergamo`, `Regione Lombardia` ×2, `Costruzioni Meridionali SPA`, `Beta Immobiliare SPA` |
| Indirizzi etichettati INDIRIZZO invece di LUOGO | 9 | Discutibile che sia un errore: INDIRIZZO è più preciso di LUOGO |
| Città etichettate LUOGO_NASCITA | 2 | Il contesto è "nato a" ma la città è citata per altro |
| `Siena` etichettata PERSONA | 1 | Toponimo che è anche cognome |

Sui documenti reali, due casi visti a mano: `0761 21231` etichettato
TELEFONO è in realtà un frammento della carta `4397 •••• •••• 2131`
(mascherato comunque, nessuna fuga); `2252•••••••••317319` etichettato
CARTA è un numero di conto PayPal — dato sensibile, tipo sbagliato.

Gli 8 enti pubblici etichettati LUOGO sono la classe che vale la pena
chiudere, perché ha una causa sola e deterministica: `Comune di X` è una
struttura fissa, e il motore prende `X`.

---

## 6. I tre limiti dichiarati, riaperti

### 6.1 Organizzazioni

**Numeri reali** (corpus, 46 span ORG): 22 esatti (47,8%), 10 parziali,
8 con tipo errato, 6 mancanti. Richiamo largo 87,0%.

Le tre classi di errore, esaminate una per una:

**Mancanti (6, 13,0%) — nome tutto maiuscolo con forma societaria senza
punti.** `ICOS SRL` ×3, `UNICREDIT SPA` ×2, `BETA IMMOBILIARE SPA`.
Tutti e sei lo stesso schema. `src/backend/motore_neurale.py` conferma
che **non esiste alcun recognizer deterministico per le organizzazioni**:
ORG è affidata interamente al modello neurale, e il modello su
`NOME SRL` senza punti non ha appigli morfologici.

**Parziali (10, 21,7%) — il nucleo viene preso, l'involucro no.**
`Ing. Bianchi & Partners` → `Bianchi` (come PERSONA), `Studio Rosa &
Associati` → `Rosa`, `Comune di Cesenatico` → `Cesenatico`, `Ordine degli
Ingegneri di Brescia` → `Brescia`, `Cooperativa Muratori SNC` →
`Cooperativa Muratori`. Il dato è coperto ma l'uscita resta leggibile in
modo sbagliato: *"il ricorso di ⟦PERSONA_3⟧ & Partners"* dice ancora che
si tratta di uno studio associato.

**Tipo errato (8, 17,4%)** — vedi capitolo 5.

**Prova di fattibilità di un recognizer deterministico.** Ho scritto tre
schemi — suffisso di forma societaria, prefisso di ente, forma
`Nome & Associati/Partners` — e li ho misurati contro le annotazioni del
corpus:

```
ORG annotati 46 — span ESATTO: 43   non presi: 3   spuri: 0
```

I tre non presi sono `ENEL ENERGIA` ×2 e `Croce Rossa Italiana`: nomi di
marca senza alcun segnale morfologico, che restano al modello neurale.
**Zero span spuri su 76 frasi.**

Questo porterebbe il richiamo stretto ORG da 47,8% a 93,5% sul corpus.
Il numero però è misurato su testo scritto per i test: **prima di
implementare va verificato il tasso di falsi positivi sui documenti veri
dell'utente**, ed è la misura riportata nel capitolo 7.

Va detto anche il contesto d'uso: **ORG è spenta per difetto**, quindi
per l'app di fabbrica questo non è un miglioramento della privacy.
Lo è per questo utente, che ha tutte le categorie accese.

### 6.2 OCR

**Domanda 1 — l'OCR di sistema ha manopole non usate che aiutano?**

`backend/ocr.py` usa già il livello `Accurate`, le lingue `it-IT`+`en-US`
e la correzione linguistica. Restano inutilizzate la risoluzione (fissa a
220 DPI) e le ipotesi alternative (`topCandidates_(1)`, cioè solo la
migliore). Quattro varianti sulle stesse 25 pagine, stessa pipeline di
rilevamento a valle:

```
variante        caratteri   entità   residui   tempo
attuale           37.181       69        9     49,0s
dpi300            37.292       65        9     52,8s
senza_lingua      38.079       68        9     38,8s
candidati         37.179       69       10     50,1s
```

**Nessuna manopola aiuta. Risposta misurata: no.**

- **300 DPI è peggio**, non meglio: 65 entità contro 69, e il 7,8% di
  tempo in più. Non riduce gli errori, li **sposta**: la stessa carta
  letta `3977•••••••••••` a 220 DPI diventa `3077•••••••••••` a 300.
- **Spegnere la correzione linguistica** non recupera le e-mail (l'ipotesi
  era che fosse lei a "correggerle" verso parole italiane): 68 entità
  contro 69, gli stessi 9 residui, con gli indirizzi corrotti identici.
  È però **il 21% più veloce**, il che apre una domanda diversa —
  prestazioni, non precisione — che annoto e non tratto qui.
- **Tenere le prime tre ipotesi e scegliere quella che supera Luhn**
  peggiora: 10 residui invece di 9, perché produce una *seconda* variante
  corrotta dello stesso numero (`225278097738617319` accanto a
  `2252780977238617319`) e raddoppia il candidato invece di risolverlo.

Nota di onestà sul confronto: questo script rasterizza e legge con OCR
**tutte** le 25 pagine, mentre l'app legge il livello di testo dove c'è e
usa l'OCR solo sulle 10 pagine che ne sono prive. Per questo i caratteri
sono 37k invece di 30k e i residui 9 invece di 7. Il confronto **fra le
quattro varianti** resta valido, perché tutte e quattro lavorano sulle
stesse pagine; il confronto con i numeri di `CONSEGNA.md` no.

**Domanda 2 — normalizzare le confusioni tipiche prima del rilevamento?**

Tre varianti sul testo che l'app estrae davvero da `Indagine .pdf`
(30.252 caratteri), stessa configurazione di consegna:

| Variante | Entità | Nuove | Perse | Δ lunghezza |
|---|---:|---:|---:|---:|
| originale (riferimento) | 67 | — | — | 0 |
| globale (`0`→`O`, `1`→`I`, `5`→`S`, `8`→`B` ovunque) | 49 | +2 | **−20** | 0 |
| mirata (solo dentro finestre già a forma di dato) | 67 | 0 | 0 | 0 |
| `rn`→`m` | 66 | +6 | −7 | **−46** |

**Risposta misurata: no, in tutti e tre i modi, e per tre ragioni
diverse.**

**La normalizzazione globale è un disastro: −18 entità nette.** Il
motivo è ovvio a posteriori e va detto: in italiano le cifre stanno nei
telefoni, e trasformare ogni `0` in `O` distrugge i telefoni per
riparare i codici. Delle 20 entità perse, **14 sono numeri di telefono**
(`3201234567`, `06-1234567`, `061234567`, …) e 4 sono carte di credito
valide che smettono di esserlo. Le 2 "nuove" sono spazzatura: la carta
`5574••••••••••••` riclassificata come IBAN `SS7444226O24O9O7`.

**La normalizzazione mirata non fa niente: +0, −0.** È il risultato più
istruttivo dei tre. L'ho scritta perché era l'obiezione ovvia alla
variante globale — correggere solo dentro le finestre che hanno già la
forma di un codice fiscale o di una sequenza di 11-19 cifre — e non
cambia una sola entità. Il motivo è che **le confusioni che l'OCR
commette su questo documento non sono lettera↔cifra**: sono cifra→cifra
sbagliata (`4397`→`4347`, `5574`→`5544`). Nessuna tabella di
sostituzione carattere-per-carattere può ripararle, perché non c'è
niente di formalmente anomalo da riconoscere: `4347` è un numero
perfettamente valido, solo diverso da quello vero.

**`rn`→`m` corrompe dati veri e rompe G4.** Accorcia il testo di 46
caratteri — quindi il ripristino byte per byte non è più possibile — e
il danno non è teorico: trasforma `Fornari` (il cognome del soggetto del
documento, che il motore oggi riconosce correttamente) in `Fomari`, e con
esso `fornari@example.it` in `fomari@example.it`. Le "6 nuove" entità sono
le versioni corrotte delle 7 perse.

Nota metodologica: la variante mirata è quella che avrei implementato se
mi fossi fermato al ragionamento. Misurarla è costato venti minuti e ha
evitato di scrivere un modulo inutile.


### 6.3 Sequenze che non superano i checksum

Il mandato propone da sé la soluzione: emettere come **suggerimento** i
candidati che hanno la forma giusta e falliscono il checksum, invece di
scartarli. È la proposta corretta e la sostengo, con due precisazioni che
vengono dalla misura.

**Precisazione 1 — non è una novità nel codice, è un'estensione.** CF e
P.IVA hanno già questa struttura: in `recognizers.py`, un codice fiscale
di 16 caratteri con carattere di controllo sbagliato non viene scartato,
viene emesso con `score = 0.6`. Quello che manca è lo stesso trattamento
per le carte, dove il recognizer di Presidio scarta su Luhn e non è nostro.

**Precisazione 2 — il suggerimento va condizionato al contesto.** Dei 4
candidati misurati, 3 sono PII vera e 1 no. Emetterli tutti come
suggerimenti significa una proposta sbagliata su quattro in una tabella
che l'utente deve fidarsi di leggere. Le parole `master card`, `visa`,
`carta`, `#` compaiono accanto ai tre veri e non accanto a `Visitor 1D:`.

Il punto che rende questa proposta la più sicura di tutte: **un
suggerimento non sostituisce niente**. Ha `placeholder` vuoto, sta nel
riquadro "Possibili entità", e va spuntato a mano. La precisione dei casi
validi non viene toccata in nessun modo, perché il percorso dei casi
validi non cambia. Il costo di sbagliare è una riga di troppo in un
elenco di proposte; il costo di non farlo è un numero di carta che esce
in chiaro.

---

## 7. Proposte, ordinate per rapporto guadagno/rischio

Quattro proposte, tutte deterministiche e senza nuove dipendenze.
Ordinate per rapporto fra guadagno misurato e rischio.

| # | Proposta | Guadagno misurato | Rischio | Costo |
|---|---|---|---|---|
| 1 | Separatori `.` e `/` nei telefoni | 3 falsi negativi veri su documento reale | **basso** — 18/18 esche ancora rifiutate | una riga |
| 2 | Candidati carta che falliscono Luhn emessi come **suggerimento** | 3 PII vere su 4 candidati non più scartate in silenzio | **nullo sui casi validi** — un suggerimento non sostituisce niente | un recognizer + filtro di contesto |
| 3 | Recognizer deterministico per le organizzazioni | corpus: span esatti ORG da 22/46 a 43/46. Reali: 9 span, 9 organizzazioni, **0 falsi positivi** | **basso** | ~80 righe di schemi + prove |
| 4 | E-mail con lo spazio prima della chiocciola | 2 falsi negativi veri | **medio** — vedi sotto | un recognizer + condizione |

### Proposta 1 — separatori di telefono

Sostituire in `_TEL_IT_REGEX` la classe `[\s\-]` con `[\s\-./]`, ed
estendere i lookaround con `(?<!\d/)` e `(?!/\d)`.

Misurato sopra: 9/9 forme vere prese, 0/18 esche. Chiude una classe
intera — nessun documento italiano scrive i telefoni in un solo modo — e
la prova che il rischio è basso è che le esche rifiutate lo sono per un
motivo indipendente dal separatore: i lookaround guardano le **cifre
adiacenti**, e una data resta una data qualunque punteggiatura abbia
dentro.

Da riverificare prima di dichiararla fatta: le 606 prove avversariali e
i 22 casi della matrice di input.

### Proposta 2 — candidati carta come suggerimento

È la proposta del mandato, e la misura la conferma. Va aggiunta una
condizione che il mandato non prevedeva: **il contesto lessicale**.

Sui 4 candidati misurati, i 3 veri hanno accanto `master card`, `#`, o
un'altra carta valida entro poche righe; il falso (`6217•••••••••••••••`)
ha accanto `Visitor 1D:`. Senza il filtro, la tabella dei suggerimenti
riceve una proposta sbagliata su quattro; con il filtro, zero.

Perché il rischio è **nullo e non solo basso**: un suggerimento ha
`placeholder` vuoto, non tocca il testo in uscita, e vive nel riquadro
"Possibili entità" che va spuntato a mano. Il percorso dei casi che
superano Luhn non cambia di una riga. Il caso peggiore è una proposta di
troppo in un elenco di proposte; il caso migliore è un numero di carta
che non esce in chiaro da un computer.

### Proposta 3 — recognizer deterministico per le organizzazioni

Tre schemi: forma societaria in coda (`… S.r.l.`, `… SPA`, `… Inc.`),
ente in testa (`Comune di …`, `Procura della Repubblica …`, `ASST …`),
e studio associato (`… & Associati`, `… & Partners`).

**Misurato sul corpus annotato** (46 span ORG): 43 span esatti, 3 non
presi, **0 spuri**. I tre non presi sono `ENEL ENERGIA` ×2 e
`Croce Rossa Italiana` — marchi senza segnale morfologico, che restano
al modello neurale.

**Misurato sui documenti veri dell'utente** — la misura che conta,
perché il corpus è testo scritto per i test:

```
Analisi Sangue … glutine.pdf   'Regione Umbria'
Indagine .pdf                  'CHECKING UniCredit S.p.A.'
                               'Paypal Holdings Inc.'
                               'Procura della Repubblica'
                               'Procura della Repubblica di Perugia-'
                               'Procura di Perugia'
                               'Tribunale di Perugia'
Atto_giudiziario.pdf     'Tribunale Ordinario di Perugia'  ×2
rizzo-pii-report.pdf           'Edilnord S.r.l.'
```

9 span distinti su 246.933 caratteri. **Tutti e nove sono
organizzazioni: nessun falso positivo.** Due hanno il confine
imperfetto — un trattino di fine riga in coda, e la parola `CHECKING`
prodotta dall'OCR in testa — che è un difetto di leggibilità, non di
privacy.

Due difetti trovati durante la messa a punto e già corretti negli schemi
misurati sopra, entrambi di classe:

- **`Ordine` senza articolo è ambiguo in italiano.** `N. Ordine Postel:
  816213` è un numero d'ordine, non l'albo professionale. Richiedere
  `Ordine degli|dei|delle` toglie l'intera classe.
- **Gli schemi attraversavano gli a capo**, incollando la fine di una
  riga all'inizio della successiva: `Confirmed: Two Random⏎CHECKING
  UniCredit S.p.A.` diventava un unico span. Sostituire `\s` con
  `[ \t]` dentro gli schemi toglie l'intera classe.

Va detto onestamente quanto vale: **ORG è spenta per difetto**, quindi
per l'app di fabbrica questo non cambia niente in termini di privacy.
Vale per questo utente, che lavora con tutte le categorie accese, e vale
come correzione di una cifra dichiarata sbagliata in `CONSEGNA.md`.

### Proposta 4 — e-mail con lo spazio prima della chiocciola

Guadagno certo (2 falsi negativi veri, entrambi indirizzi personali su
documento scansionato) ma rischio più alto delle altre tre: una regola
che accetta spazi attorno alla chiocciola può agganciare, su testo
normale, la fine di una frase e l'inizio della successiva. Va
condizionata — al fatto che il documento contenga pagine lette con OCR,
oppure a un dominio di primo livello plausibile — e la condizione va
misurata sugli otto documenti prima di tenerla.

Il vincolo non negoziabile: **la corruzione deve stare dentro lo span.**
Ciò che viene sostituito dev'essere esattamente `rossi @esempio.it`,
spazio compreso, perché il ripristino rimetta esattamente quei caratteri.
Nessuna normalizzazione a monte, per la ragione già misurata al
capitolo 6.2 e per G4.

### Non implemento ora

**Span troncati e nomi dopo un a capo** (cause D ed E, 2 casi). La causa
sta dentro il modello neurale e nella fusione degli span, non in una
regola che si possa aggiungere. Il costo è alto, il guadagno misurato è
2 casi, e c'è un rimedio migliore in arrivo: la **Parte 2** di questo
mandato rende la correzione immediata sul testo, che è la risposta
giusta sia agli span troncati sia ai 17 falsi positivi del capitolo 4.
Un motore che sbaglia il confine e un'interfaccia che permette di
correggerlo in due click valgono più di un motore che sbaglia meno e
costringe a rileggere tutto.


---

## 8. Quello che non propongo, e perché

**Modelli locali aggiuntivi o dipendenze pesanti.** Escluso dal mandato,
e correttamente: il pacchetto è già a 1,2 GB per il modello neurale, e
l'app deve girare su qualunque computer. Tutte le proposte del capitolo 7
sono deterministiche o riusano ciò che è già nel pacchetto.

**Normalizzare il testo prima del rilevamento.** Rompe G4, il ripristino
byte per byte, che è la garanzia su cui l'intero prodotto si regge. La
misura del capitolo 6.2 dice anche che non converrebbe comunque.

**Alzare le soglie per ridurre i falsi positivi.** I falsi positivi
misurati sono innocui per la privacy (mascherano di troppo) e i falsi
negativi sono il danno vero. Alzare le soglie scambierebbe un fastidio
con una fuga. La strada giusta per i falsi positivi è la correzione
immediata sul testo — la Parte 2.

**Un dizionario di enti, marche e ragioni sociali.** Chiuderebbe
`ENEL ENERGIA` e `Croce Rossa Italiana`, ma è una lista che invecchia,
va mantenuta e non generalizza: tre casi su 195 non giustificano un file
da aggiornare a mano per sempre.

**Rilevare le categorie particolari dell'art. 9 GDPR.** Resta fuori
perimetro come dichiarato in `CONSEGNA.md` § 9.2: sono contenuti, non
identificatori.

---

## 9. Che cosa è stato implementato, e quanto è valso davvero

Tre proposte su quattro implementate. Ogni riga di questo capitolo è il
confronto fra la misura di prima e la misura di dopo, sugli stessi
comandi del capitolo 1.

### 9.1 Il quadro d'insieme

Corpus annotato (`venv/bin/python -m benchmark.misura_corpus`):

```
                          prima      dopo
richiamo largo            95,4%      98,5%
richiamo stretto          75,9%      87,2%
span spuri                    9          9
ORG esatti su 46             22         44
ORG con tipo sbagliato        8          0
ORG non presi                 6          0
```

Documenti reali, configurazione di consegna
(`venv/bin/python -m benchmark.audit_precisione`):

```
                          prima      dopo
sostituzioni attive         141        141
suggerimenti                 19         22
residui in uscita            55         55
```

Documenti reali, tutte le categorie accese:

```
                          prima      dopo
sostituzioni attive         616        620
suggerimenti                 12         14
residui in uscita            15         15
```

Il richiamo stretto sale di undici punti e nessuna delle due misure
peggiora in nessuna colonna. Gli span spuri restano nove: le tre
correzioni non hanno prodotto un solo falso positivo nuovo.

### 9.2 Perché sui documenti reali le sostituzioni non salgono

**141 prima, 141 dopo.** Va detto chiaramente invece di nasconderlo
dietro il guadagno sul corpus.

Il motivo è che il guadagno grosso — le organizzazioni — sta in una
categoria **spenta per difetto**. Con tutte le categorie accese le
sostituzioni salgono da 616 a 620 e le ORG da 111 a 117 (le tre in più
rispetto a 620−616 vengono da span che prima uscivano come LUOGO). Con
la configurazione di fabbrica, ORG non viene nemmeno valutata.

I tre telefoni con il separatore `.` o `/` sono già dentro il 141: erano
falsi negativi, ora sono presi, ma la stessa cifra usciva già mascherata
altrove nel documento e il totale delle **entità distinte** non cambia.
Il guadagno è che ora la stessa cifra ha lo stesso esito ovunque
compaia — che è precisamente la classe di difetto, non il numero.

I candidati carta sono la voce che si muove: **19 → 22 suggerimenti**,
tre numeri di carta veri che prima sparivano in silenzio e ora arrivano
all'utente come proposta da spuntare.

### 9.3 Il quarto candidato carta non affiora, e va detto

Su quattro candidati misurati al capitolo 3.C, ne affiorano **tre**. Il
quarto è `4397 •••• •••• 21231`, in `Indagine .pdf`:

```
visa 4397 •••• •••• 21231 - mario rossi - Importo £ 1,69.
```

Il recognizer lo trova. Poi il pezzo di coda `0761 21231` viene preso
dal recognizer dei telefoni — nove cifre, prefisso `0761`, forma di un
fisso italiano perfettamente valida — e sostituito. A quel punto il
suggerimento cade sul filtro che vieta di proporre testo già coperto da
un'entità sostituita, e l'uscita è `4397 •••• «TELEFONO_1»`.

La classe è chiara: **una sequenza lunga di cifre spezzata dagli spazi
contiene sotto-sequenze che hanno la forma di un numero di telefono.**

Non la correggo, e la ragione è che le due alternative sono peggiori
della situazione attuale:

- *Rifiutare i telefoni dentro una corsa di 13+ cifre.* Il numero
  smetterebbe di essere mascherato del tutto: uscirebbe l'intera carta
  in chiaro più un suggerimento da spuntare. Oggi metà è già coperta
  senza che l'utente faccia niente. Per uno strumento di privacy la
  scelta prudente è quella che maschera di più quando l'utente non
  interviene.
- *Lasciar passare il suggerimento nonostante la sovrapposizione.* Il
  valore proposto (`4397 •••• •••• 21231`) non esiste più nel testo in
  uscita, dove ora c'è `4397 •••• «TELEFONO_1»`. Sarebbe un
  suggerimento inapplicabile — esattamente il difetto per cui quel
  filtro era stato scritto.

Il costo reale è un'etichetta sbagliata in tabella (`TELEFONO` invece di
`CARTA`) su un dato comunque mascherato. **La Parte 2 di questo mandato
è il rimedio giusto**: cambiare tipo a un'entità direttamente dal testo,
in due click, senza che nessuna regola debba indovinare.

### 9.4 Un difetto trovato mentre misuravo: il tipo non era deterministico

Non era nel mandato e non l'avevo previsto. È emerso dal confronto fra
due esecuzioni consecutive dell'**identico** comando sugli **identici**
documenti: `CF 2 / PIVA 2` la prima volta, `CF 3 / PIVA 1` la seconda.

Riprodotto in cinque processi nuovi sulla stessa frase:

```
Il Sig. Mario Rossi, C.F. RSSMRA85H12F205Z, P.IVA 12345678901, ...

CF=RSSMRA85H12F205Z | PERSONA=Mario Rossi | PIVA=12345678901
CF=RSSMRA85H12F205Z | CF=12345678901     | PERSONA=Mario Rossi
CF=RSSMRA85H12F205Z | CF=12345678901     | PERSONA=Mario Rossi
```

**Causa.** In `_risolvi_sovrapposizioni` un match con `score == 1.0`
viene promosso a priorità 100 — la regola che dà precedenza assoluta
alla rubrica personale. Undici cifre sono insieme un codice fiscale di
società e una partita IVA, i due recognizer rispondono tutti e due con
1.0, e le due tuple di confronto diventavano **identiche**. Il confronto
è `>` stretto, quindi vinceva chi arrivava per primo — e l'ordine con cui
Presidio restituisce i risultati cambia da un processo all'altro
(dipende dall'ordinamento degli insiemi, randomizzato a ogni avvio di
Python). Con `PYTHONHASHSEED` fissato l'esito era stabile: la prova che
la causa era quella.

**Correzione.** Aggiungere in coda alla tupla la priorità di base e il
nome del tipo, così l'ordine è **totale**: a parità di tutto il resto
vince il tipo con priorità più alta in tabella, e a parità anche di
quella l'ordine alfabetico. Nessuna scelta arbitraria resta al caso.

**Quanto era grave.** Per la privacy, nulla: il dato era mascherato in
entrambi i casi, solo con un prefisso diverso. Per la fiducia
nell'app, parecchio — lo stesso documento anonimizzato due volte dava
due tabelle diverse. Per questo audit, di più ancora: **ogni confronto
prima/dopo ereditava quel rumore**, e senza la correzione i numeri del
capitolo 9.1 non sarebbero riproducibili.

È la quarta volta in questo progetto che un difetto di *misura* si
rivela più importante del difetto misurato. Le altre tre stanno al
capitolo 1.2.

### 9.5 Che cosa resta aperto

- **Proposta 4** (e-mail con lo spazio prima della chiocciola, 2 casi
  veri) non implementata. Il rischio resta quello descritto al capitolo
  7 e la condizione di sicurezza va misurata sugli otto documenti prima
  di tenerla.
- **`ENEL ENERGIA` e `Croce Rossa Italiana`** restano span parziali:
  marchi senza segnale morfologico, per i quali servirebbe il dizionario
  che il capitolo 8 rifiuta.
- **I 13 errori di tipo residui sul corpus** sono quasi tutti LUOGO
  (11 su 13) e riguardano la distinzione fra toponimo e ente, che è
  semantica e non morfologica.

### 9.6 Il difetto sfuggito a questo audit: PERSONA che ingloba il contesto anagrafico

Trovato dall'utente il 2026-08-02 (sera) usando l'app sul lavoro
vero. Il capitolo 3 di questo audit **non lo aveva visto**, e il
motivo è metodologicamente istruttivo.

**Il caso reale.**

```
IN : "Ciao sono Matteo Rossi nato a Roma il 15 maggio 1975"
OUT: "Ciao sono «PERSONA_1» ad «LUOGO_NASCITA_1» il «DATA_NASCITA_1»"
```

`«PERSONA_1»` catturava `"Matteo Rossi nato"` — il participio
incluso. Effetti:

- la parola *nato* spariva dall'uscita: il downstream perdeva il
  contesto anagrafico;
- *nato a/il* è l'**indicatore di contesto** che il recognizer
  LUOGO_NASCITA/DATA_NASCITA usa per innescarsi: un innesco stava
  dentro lo span del vicino;
- G4 byte-identico sembrava tenere solo per via del valore
  memorizzato nel vault, ma qualunque modifica manuale della sequenza
  dei segnaposto avrebbe rotto la ricostruzione.

**Perché il capitolo 3 non lo aveva contato.** L'audit misurava
gli *span imperfetti* con l'annotazione del corpus (76 frasi curate).
Nel corpus non c'era un caso `Nome + Cognome + "nato" + "a/il"` con
un LUOGO_NASCITA immediatamente adiacente — la classe più deleteria.
Le sette frasi introdotte dal nuovo test in
`tests/test_garanzie.py::test_g4_span_persona_non_ingoia_contesto_anagrafico`
sono la copertura che mancava, e ora sono nel gate.

**La correzione.** Nuova funzione
`_pota_span_persona_da_contesto` (in `backend/motore.py`), agganciata
al pipeline subito dopo `_rifila_bordi_persona`. Toglie dai bordi
degli span PERSONA/IT_NOME_COGNOME i token che sono:

- parole di **contesto anagrafico** — `nato/nata`, `residente`,
  `domiciliato`, `originario`, `coniugato`, `chiamato`, `detto`,
  `presso`, `ha/è/era/sono` — enumerati in `_PAROLE_CONTESTO_ANAGRAFICO`;
- **funzionali monosillabici** — `a`, `ad`, `in`, `il/la/lo`,
  `un/una`, `di/da/del/della/…`, `con/per/su/…` — in
  `_FUNZIONALI_MAI_NEL_NOME`.

I nomi e cognomi noti — **anche quelli ambigui** (`Rossi`, `Bianchi`,
`Verdi`, `Marino`, `Bruno`, `Russo`: tutti in `_COGN_AMBIGUI` e nel
vocabolario italiano) — vengono sempre tenuti. Onorifici e particelle
nobiliari (`de`, `di`, `van`, `von`, …) restano ai bordi.

**Perché non un filtro sul vocabolario.** Primo tentativo scartato
dopo la misura: `"nato"` è in `_COGN_AMBIGUI` (esiste il cognome
"Nato"). Se avessi usato la regola «se il token è in `_VOCAB_IT` e
non è in `_NOMI_TUTTI ∪ _COGN_TUTTI`, scarta», avrei sbagliato
sull'80% dei cognomi italiani più comuni (Rossi, Bianchi, Verdi,
Marino, Bruno, Russo, Conti, Ricci). Un elenco esplicito è meno
elegante ma **verificabile riga per riga** e non peggiora nei casi
di bordo.

**Misura prima/dopo.** Suite completa 882 passed. Corpus: richiamo
largo invariato (98,5%), stretto −0,5% (87,2% → 86,7%) — dentro il
rumore, e giustificato dalla protezione contro una classe di
falsi positivi. Documenti reali: sostituzioni attive 141 → 138,
**residui in uscita 55 → 55**. Le tre sostituzioni in meno sono su
`Indagine .pdf` (67 → 64) e sono precisamente falsi positivi da
inglobamento di contesto, non fughe. La metrica che conta — i
residui — non si è mossa.

**Lezione metodologica.** L'audit ha misurato *quello che il corpus
mostrava*. Il difetto vero è arrivato da un caso che il corpus non
copriva. Un audit ordinato per causa può sembrare completo e non
esserlo se la libreria di casi non tocca ogni classe. Il rimedio non
è un audit più lungo — è **il test G4 di classe** che ora vive nel
gate: qualunque futura versione del motore che rompa la potatura
degli span PERSONA fallirà, senza dover aspettare che un utente lo
usi sul lavoro vero.
