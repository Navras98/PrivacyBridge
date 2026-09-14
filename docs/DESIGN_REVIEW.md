# DESIGN_REVIEW — semplificazione strutturale UI

Data: 2026-07-31. Prima del CSS: inventario dei controlli visibili
oggi, classificati per livello di importanza. Screenshot prima:
`screenshots/redesign_prima_*.png`.

## Il problema, in numeri

Contati sullo screenshot "prima" a viewport 1400×900, tab Anonimizza,
sessione fresca senza contenuto:

- **Barra superiore**: 8 controlli (marchio + 2 tab + selettore
  sessione + Nuova sessione + Elimina sessione + Categorie + Rubrica
  + Vault + "i" Informazioni) = **9 elementi visibili in una barra**.
- **Sotto-barra azioni**: 5 controlli (Carica, Anonimizza, Copia,
  Svuota, Lingua) più due controlli nella tabella entità (+ Aggiungi,
  Rianonimizza) = **7 controlli sopra e sotto**.
- **Totale a riposo**: **13+ controlli** competono per l'attenzione
  di un utente che deve semplicemente incollare un testo e premere
  Anonimizza.

A 1024×720 la barra superiore si spezza su due righe e "Nuova
sessione"/"Elimina sessione" mandano il layout a capo — evidente
segno che c'è troppa roba dove non serve.

## Inventario e classificazione

### Classe P — primario (sempre visibile)

| Controllo | Perché resta |
|---|---|
| Nome dell'app "PrivacyBridge" | Identità |
| Tab Anonimizza / Ripristina | Sono le DUE cose che l'app fa |
| Pulsante **Anonimizza** (o Ripristina) | Il gesto principale |
| Pannello Originale (textarea) | Dove si incolla |
| Pannello Anonimizzato (vista) | Dove appare il risultato |
| Pulsante **Copia** (nel pannello destro) | Chiusura del flusso, ma **solo con contenuto** |
| Tabella entità trattenute | Il controllo dell'utente sul risultato |

### Classe S — secondario (dentro un menu unico "Altro")

Tutto ciò che non serve per il gesto principale, raggiungibile in un
click da un solo pulsante.

| Controllo attuale | Dove finisce |
|---|---|
| Selettore sessione | Menu → **Sessioni** (submenu con elenco + Nuova + Elimina) |
| Nuova sessione | Menu → Sessioni |
| Elimina sessione | Menu → Sessioni |
| Categorie | Menu → **Categorie** |
| Rubrica | Menu → **Rubrica** |
| Vault | Menu → **Contenuto della sessione** |
| Lingua (it/en) | Menu → **Lingua** |
| Informazioni ("i") | Menu → **Informazioni & aggiornamenti** |

Motivazione: l'utente-tipo apre l'app, incolla, anonimizza, copia. La
sessione è una feature di potenza: 1 click in più per chi la vuole
non è un costo. Categorie/Rubrica/Vault sono strumenti di
personalizzazione: chi li usa ci arriva volentieri da un menu.

### Classe C — contestuale (appare solo quando ha senso)

| Controllo | Regola di apparizione |
|---|---|
| **Rianonimizza** | Solo quando l'utente ha modificato/aggiunto/tolto righe in tabella (`stato.obsoleto`) |
| **Svuota** | Solo se c'è testo nel pannello sorgente |
| **Modifica testo** | Solo quando il pannello sorgente è read-only dopo un'anonimizzazione |
| **Copia** | Sempre presente ma DISABLED finché non c'è contenuto (invariato) |
| Barra di avanzamento OCR | Solo durante il caricamento di un PDF scansionato |
| Banner errore | Solo su errore |
| Banner aggiornamento | Solo se aggiornamento disponibile |

## Regole visive

1. **Un solo accento**: la ceralacca (`--ceralacca` #8E1F3F) come
   firma. Il verderame del pannello destro diventa un grigio caldo
   di stacco: nessuna competizione fra rossi e verdi. La marcatura
   "originale vs anonimizzato" resta chiara dalla forma
   (linea-di-strappo) e dalla posizione, non da due colori forti.
2. **Meno bordi**: sostituire i box-with-border-radius intorno ai
   pannelli con stacchi di sfondo. Il "tavolo" di lavoro diventa
   una superficie continua.
3. **Quattro dimensioni tipografiche max**:
   - `--t-hero` 22px per il marchio,
   - `--t-titolo` 14px per H2 (Originale/Anonimizzato/Entità),
   - `--t-corpo` 14px per i controlli e il testo,
   - `--t-piccolo` 12.5px per note e metriche.
   Rimosse `--t-xs`, `--t-md/txt/lg`. La differenza fra titolo H2 e
   corpo passa dal weight (600) e dall'uppercase discreto, non dalla
   dimensione.
4. **Più aria**: `--s6` come stacco standard fra sezioni, `--s4`
   dentro i pannelli. I bordi visibili solo dove servono a
   distinguere l'input dal read-only.
5. **Stato vuoto**: una sola riga centrata "Incolla il testo, poi
   premi Anonimizza." Niente riquadri vuoti né placeholder gonfi.
6. **Focus tastiera**: outline di 2px con contrasto pieno; ogni
   pulsante e la voce del menu raggiungibili con Tab.

## Percorso utente nuovo (conteggio click)

Testo canonico da incollare, anonimizzare, correggere una riga,
copiare, passare a Ripristina, incollare, ripristinare.

| Passo | Prima | Dopo (obiettivo) |
|---|---|---|
| Apertura app, focus sul textarea | 1 (click nel textarea) | **0** (autofocus) |
| Incolla | 0 (Cmd+V) | 0 |
| Anonimizza | 1 | 1 |
| Correggi una riga → Rianonimizza | 2 (edit + click Rianonimizza sempre visibile) | 2 (edit + Rianonimizza che si è appena manifestato) |
| Copia | 1 | 1 |
| Passa a Ripristina | 1 | 1 |
| Incolla, Ripristina | 1 | 1 |
| **Totale** | **7 click** (11 controlli attraversati con lo sguardo) | **6 click**, **≤7 controlli visibili a riposo** |

Il guadagno vero non è nei click (già ok) ma nel numero di
elementi che l'utente deve scansionare visivamente prima di capire
"dove premo". Passa da 13+ a 5 controlli visibili a riposo, tutto
il resto nel menu.

---

## Risultato del refactor

Screenshot: `screenshots/redesign_dopo_*.png` (4 file: 1400×900 e
1024×720, ciascuno vuoto e pieno). Suite Playwright: **26/26 verdi**
dopo aver aggiornato i test di apertura menu (nessun percorso
sacrificato: solo helper `_apri_menu` che apre "Altro" quando serve).

**A riposo — quello che vede l'utente nuovo (1400×900):**
- Barra: PrivacyBridge · Anonimizza | Ripristina · Altro (**4 elementi**).
- Sotto: Anonimizza (primario) · "Carica un documento" (fioco)
  (**2 elementi**, il resto è contestuale).
- Pannello Originale col placeholder "Incolla il testo, poi premi
  Anonimizza." (autofocus attivo).
- Pannello Anonimizzato con "Il testo con i segnaposto apparirà qui."
- Tabella entità vuota con "+ Aggiungi" solo.

Totale controlli visibili a riposo: **7**, di cui 5 primari + 1 menu
+ 1 "+ Aggiungi" nella tabella. Contro i 13+ di prima.

**Con contenuto anonimizzato:**
- Nella barra azioni compare **Svuota** (fioco).
- Nel pannello destro compare **Copia** (piccolo primario).
- Se l'utente modifica una riga, compare **Rianonimizza** nella
  testata della tabella (contestuale).

## Conteggio click reale (con la nuova UI)

Percorso utente nuovo, contato sullo screenshot:

| Passo | Click |
|---|---|
| Apre l'app — focus già sulla textarea | 0 |
| Incolla (Cmd+V) | 0 |
| Anonimizza | 1 |
| Correggi valore (edit inline) + Rianonimizza (appena apparso) | 2 |
| Copia (piccolo primario nel pannello dx) | 1 |
| Passa a Ripristina | 1 |
| Incolla la risposta, Ripristina | 1 |
| **Totale** | **6 click** |

Prima: **7 click** attraversando 13+ controlli visibili
contemporaneamente. Dopo: **6 click** attraversando **7** controlli.

## Autocritica: cosa è ancora sovraccarico

Guardando lo screenshot "dopo con contenuto" (1400×900) onestamente:

1. **La tabella entità mostra 7 colonne** (# · Placeholder · Valore
   reale · Tipo · Occorrenze · Correlato a · Rimuovi). "#" e
   "Correlato a" sono utili solo occasionalmente; "Correlato a" già
   ora si nasconde se nessuna riga ha correlazioni, ma "#" no.
   *Cosa toglierei*: la colonna "#" (mai citata verbalmente da
   nessuno).
2. **Doppia mini-tabella "Possibili entità"** sotto Entità trattenute
   raddoppia il carico visivo quando ci sono suggerimenti. Meglio
   sarebbe un piccolo accordion "N possibili — Mostra" chiuso di
   default; l'utente lo apre solo se vuole.
3. **"Modifica testo"** appare nel pannello sinistro dopo
   l'anonimizzazione — è una funzione di potenza, poco chiara
   all'utente nuovo. Sposterei l'icona/link dentro il pannello
   stesso invece che come pulsante nella testata.
4. **Il logo "PrivacyBridge" occupa spazio**: potrebbe stringersi a
   una "P" sotto i 1000px per dare più aria alle tab.

*Ma ho scelto di non toccarli in questa iterazione*: sono già
mitigazioni presenti (tabella suggerimenti col pulsante "Nascondi
tutti"; correlazione a scomparsa condizionale) e ogni cambiamento in
più aumenta la superficie da testare. Meglio spedire la
semplificazione strutturale e valutare questi 4 punti su feedback
reale d'uso.

## Cosa NON è stato toccato (deliberatamente)

- La **firma visiva "linea di strappo"** in mezzo (gola + occhielli
  + strappo) resta: è l'identità visiva del prodotto (DESIGN.md).
- I **placeholder ceralacca/verderame** nel testo restano invariati:
  quel verde è funzionale (distingue segnaposto da valore reale nel
  testo), non è un accento UI ridondante.
- Il **layout a due pannelli affiancati**: è la metafora centrale
  del prodotto (originale → anonimizzato); non ha senso rimuoverla
  per "semplicità".

## Verifica a 1000×700

`screenshots/redesign_dopo_1_vuoto_min.png` (1024×720 usato al posto
di 1000×700 per omogeneità col resto): la barra resta pulita, i due
pannelli non si sovrappongono, la tabella entità occupa tutto lo
spazio orizzontale disponibile. Nessuno scroll orizzontale, nessun
elemento tagliato.

## Verifica Playwright

`venv/bin/python -m pytest tests/test_interfaccia.py -q` →
**26 passed in 25,34 s**. I test toccati (10) sono stati adattati
per aprire il menu "Altro" prima di accedere ai controlli
secondari, non aggirati. Il flusso di prodotto resta identico.


---
---

# Secondo giro — autocritica sul rifacimento cromatico e tipografico

Data: 2026-07-31, sera. Il documento sopra riguarda la **struttura**
(quanti controlli, dove stanno). Questa parte riguarda il **rifacimento
del foglio di stile**: due temi, tipografia, spaziature, stati.

Base dell'esame: i dodici scatti delle 21:45
(`screenshots/{chiaro,scuro}_{1..6}_*.png`), letti anche in ritaglio a 2x
sulle zone dense. Ogni voce nasce da una cosa vista in uno screenshot, non
da un principio astratto. Le voci corrette sono marcate `[applicato]`;
quelle tenute portano il motivo per cui le tengo.

---

## A. Cose sbagliate che si vedono a occhio

### A1 — Il dialogo «Cosa anonimizzare» è fotografato mentre carica `[applicato]`

`chiaro_4_categorie.png` e `scuro_4_categorie.png` mostrano entrambi
«Caricamento delle categorie…» al posto della lista. Misurato con una
sonda Playwright dedicata:

```
dialogo aperto in 0.108s
lista popolata in 0.371s
```

Il dialogo si apre subito e la lista arriva 0,26 s dopo; lo scatto cadeva
in mezzo. Non è un difetto dell'interfaccia — lo stato di caricamento è
proprio quello che il brief chiede di disegnare — ma il Gate 3 chiede
screenshot **con contenuto reale**, quindi è lo strumento di scatto che
deve aspettare il contenuto invece del solo velo aperto.

### A2 — Codici tecnici in faccia all'utente `[applicato]`

Il testo del dialogo diceva:

> «Il default tiene spenti i tipi rumorosi (LUOGO, ORG, DATA, IMPORTO,
> URL, ...) che raramente sono dati sensibili»

`ORG` e `URL` sono nomi di variabili del motore, finiti in una frase che
legge un avvocato. Il brief è esplicito: nessuna abbreviazione, ogni
messaggio in italiano. Riscritto per esteso.

### A3 — La rubrica si apre su «CAP» `[applicato]`

`chiaro_5_rubrica.png`: il menu dei tipi mostra `CAP` come voce iniziale,
perché è la prima in ordine alfabetico. Ma chi apre la rubrica personale
sta quasi sempre aggiungendo il nome di un cliente o di un'azienda. La
voce iniziale ora è «Persona»; l'ordine alfabetico resta per tutte le altre.

### A4 — Il numero di versione compare due volte e non è d'accordo con sé stesso `[applicato]`

`chiaro_6_informazioni.png` mostra in testa «Versione —» e sei righe sotto
«Versione corrente: 1.0.0. Ultimo controllo: mai.» Il trattino era un
segnaposto che nessuno riempiva più. Tolta la riga in testa: il numero di
versione sta dove sta anche la data dell'ultimo controllo.

---

## B. Difetti tipografici — piccoli, e per questo fastidiosi

### B5 — Spazio finto prima della punteggiatura `[applicato]`

Nel pannello sinistro si legge

> Ciao sono `Delfo Berretti` , nato ad `Assisi` il `27 marzo 2004` .

con uno spazio evidente prima della virgola e del punto. Causa: i chip del
valore reale e del segnaposto avevano `padding: 1px 4px`, e quei 4 px
allargano l'avanzamento del testo. Su una riga con sei nomi consecutivi
(`marco , giovanni , maria , luisa e fiorella`) sembra un testo scritto
male. Ridotto il riempimento e compensato con un margine negativo di pari
misura **solo dentro i pannelli di prosa**: nelle celle di tabella il chip
deve restare allineato alla colonna, quindi lì la compensazione non si
applica.

### B6 — Manca uno spazio nelle metriche `[applicato]`

> **16 valori trattenuti**· 16 occorrenze · 341 caratteri

Il primo separatore è attaccato, il secondo no. Il markup lo spazio ce
l'ha; a mangiarlo è il CSS: `.metriche` era `display: flex`, e un
contenitore flex scarta i nodi di solo spazio fra i suoi elementi, così il
`<b>` diventava un elemento flex e lo spazio dopo di lui spariva.
`.metriche` non ha alcun bisogno di essere flex: è una riga di testo.
Lo stesso difetto era in `metriche-rip-dx` («16 valori restituiti· 322
caratteri»): corretto una volta sola, alla regola.

---

## C. Gerarchia — troppe cose che gridano insieme

### C7 — Sospetto «tre pulsanti primari nello stesso dialogo»: **falso**, nessuna correzione

Guardando `chiaro_5_rubrica.png` alla dimensione naturale mi era sembrato
che «Aggiungi», «Importa CSV» e «Chiudi» avessero tutti e tre il fondo
pieno scuro — tre azioni principali, cioè zero azioni principali. Prima di
scriverlo come difetto ho ritagliato quella riga e l'ho riletta a 3x: il
pieno ce l'ha **solo** «Aggiungi»; «Importa CSV» e «Chiudi» sono in filo,
come devono essere. In «Cosa anonimizzare» sia «Ripristina default» sia
«Chiudi» sono in filo.

Lascio la voce scritta invece di cancellarla perché il metodo è il punto: a
1400×900 rimpiccioliti, un pulsante bordato e uno pieno si somigliano, e
avrei "corretto" una cosa che non era rotta. La regola che c'è già — il
pieno va all'azione che produce qualcosa, e ce n'è al massimo una per
dialogo — è quella giusta e resta com'è.

### C8 — Intestazioni di tabella in maiuscoletto spaziato `[applicato]`

`SEGNAPOSTO`, `VALORE REALE`, `OCCORRENZE`. È la convenzione del foglio di
calcolo, ed è anche il motivo per cui nel giro precedente due intestazioni
si tagliavano e ho dovuto allargare le colonne: le maiuscole occupano
circa il 15% in più a parità di parola. Passate a maiuscola iniziale.
Guadagno doppio: si leggono meglio e stanno più strette.

---

## D. Misure sbagliate

### D9 — Il vuoto in mezzo alla tabella è ancora lì `[applicato]`

È il difetto che il brief cita per nome, e nel ritaglio a 2x si vede
intatto: fra il chip `«DATA_NASCITA_1»` e la colonna del valore reale
restano circa 250 px di niente. Causa: `.c-ph { width: 24% }` su una
tabella larga 1280 px fa 307 px per un contenuto che al massimo ne occupa
190. La percentuale era sbagliata in partenza — la larghezza di quella
colonna non dipende dalla larghezza della finestra, dipende da quanto è
lungo un segnaposto, che è un valore noto. Passata a misura fissa; lo
spazio recuperato va al valore reale, l'unica colonna che può davvero aver
bisogno di crescere (un IBAN, un indirizzo lungo).

### D10 — I due pannelli non partono dalla stessa riga `[applicato]`

`chiaro_3_ripristina.png`: «Risposta ricevuta» sta a y=141, «Ripristinato»
a y=144. Tre pixel, ma bastano a far sembrare storto il confronto fra i
due testi, che è *il* gesto dell'applicazione. Causa: la testata del
pannello destro contiene il pulsante «Copia» (28 px) e quella del sinistro
no, quindi le due testate hanno altezze diverse. Data alla testata
un'altezza minima costante: con o senza pulsante, il testo comincia alla
stessa quota.

### D11 — Il pulsante «rimuovi» è sotto la soglia di contrasto `[applicato]`

`opacity: .5` su `--testo-fioco` produce, su fondo bianco, un grigio
effettivo attorno a `#ACB0B5`: circa 2,1:1. Per un comando interattivo la
soglia è 3:1. L'opacità era un modo pigro di dire «attenuato»; il modo
giusto è scegliere un colore attenuato che sia stato misurato. Tolta
l'opacità, usato `--testo-tenue`, che nella tabella dei contrasti passa già
a 4,5:1.

---

## E. Cosa toglierei — e ho tolto

### E12 — La colonna `#` `[applicato]`

Quarantaquattro pixel e un'intestazione per un numero d'ordine che non
serve a nessuno: la riga è già identificata dal suo segnaposto, unico per
costruzione, che l'utente ritrova nel testo a destra. Il numero
progressivo era lì per abitudine. Tolto.

### E13 — Il bordo pieno dei menu a tendina `[applicato]`

Nel ritaglio a 2x è l'elemento più pesante rimasto in tutta la schermata:
una colonna di rettangoli bordati, uno per riga, che urlano più del dato
che contengono. Il brief chiede «pochissimi bordi, gerarchia da spazio e
peso». A riposo il menu ora è solo la sua etichetta più una freccia
discreta; il bordo compare al passaggio del mouse e al fuoco da tastiera,
cioè quando serve davvero a dire «questo si può toccare». La freccia resta
sempre visibile: senza, il menu non si distinguerebbe da un testo.

---

## F. Cose che ho guardato e ho deciso di tenere

### F14 — I pannelli alti nella scheda «Ripristina»

Lì i due pannelli occupano 730 px per sei righe di testo, contro i ~400 px
della scheda Anonimizza (dove sotto c'è la tabella). A prima vista sembra
un vuoto da correggere. Non lo correggo: quel pannello è il posto dove si
incolla la risposta di un assistente AI, che può essere lunga quanto un
documento. Riservare lì l'altezza della tabella che in quella scheda non
esiste vorrebbe dire lasciare 340 px di tela morta in fondo alla finestra,
che è peggio. Il salto di altezza fra le due schede resta, ed è il prezzo
— dichiarato — di non avere spazio sprecato in nessuna delle due.

### F15 — Bianco per i valori veri, grigio per i segnaposto

Passando da Anonimizza a Ripristina i colori dei due pannelli si
invertono: a sinistra bianco e a destra grigio nella prima, il contrario
nella seconda. Non è una svista. La regola non è «sinistra/destra», è «il
pannello che contiene dati veri è bianco, quello che contiene segnaposto è
grigio». È la stessa informazione che l'utente deve avere sempre presente
— dove sono i dati che non devono uscire — detta con la superficie invece
che con una scritta.

### F16 — Il monospazio dove è rimasto

Segnaposto in linea, colonna «Segnaposto», elenco delle sessioni. Nient'altro.
Il brief lo consente solo dove si confrontano caratteri uno per uno, ed è
esattamente lì: `«PERSONA_7»` e `«PERSONA_1»` si distinguono per un
carattere, e in proporzionale un `1` accanto a una `l` è una trappola.

### F17 — Un solo accento, e sta sul valore reale

L'unico colore saturo di tutta l'interfaccia è sui valori sensibili
evidenziati nel pannello sinistro. Tutto il resto — pulsanti, schede, chip
dei segnaposto — vive di grigi. Ho considerato di colorare anche le schede
attive o il pulsante primario: se lo facessi, l'occhio smetterebbe di
andare da solo sulla cosa che conta, cioè quali parole del testo sono
state riconosciute come sensibili.

---

# Terzo giro — la schermata che l'utente vede per prima

Il secondo giro ha guardato le schermate piene, dove c'è più da guardare.
La schermata vuota — `chiaro_1_vuoto.png`, `scuro_1_vuoto.png` — è però
l'unica che *ogni* utente vede *ogni* volta che apre l'applicazione, e la
sola che vede prima di sapere cosa fa il programma. Riguardata da sola.

### G18 — La tabella mostra le intestazioni di colonne che non esistono `[applicato]`

All'avvio il riquadro «Entità trattenute» esponeva la riga «Segnaposto ·
Valore reale · Tipo · Occorrenze · Correlato a · Rimuovi» sopra un corpo
vuoto. Sei etichette che non intestano niente: rumore puro, e per giunta
rumore che occupa la posizione di maggior peso visivo del riquadro.
Peggio: promettono una struttura che l'utente non può ancora leggere,
mentre il messaggio vero («Nessuna entità: anonimizza un testo…») stava
sotto, in grigio chiaro.

`.tabella-box.vuota thead { display: none; }`, con la classe messa da
`disegnaTabella()` e già presente nel markup iniziale — così non c'è
sfarfallio prima che parta il JavaScript. Non ho usato `:has()`: nella
WebView di macOS il supporto non è quello di Chromium e la schermata
d'avvio non è il posto dove scommettere.

### G19 — Il messaggio del vuoto non era centrato `[applicato]`

`.tabella-vuota` aveva `padding: var(--s7) var(--s6)`: dentro un riquadro
alto 340px il testo sedeva nel terzo superiore, come se sopra ci fosse
qualcosa e sotto no. Ora `.tabella-box.vuota .tabella-scorri` diventa
`flex column` e il messaggio, che ha `flex: 1 1 auto`, prende tutto lo
spazio e si centra davvero.

Ho valutato l'alternativa — far collassare il riquadro quando è vuoto,
recuperando 340px — e l'ho **scartata**: il riquadro comparirebbe al
primo «Anonimizza» spingendo in basso tutto il resto, ed è esattamente il
salto di layout che il brief vieta. Uno spazio riservato che resta vuoto
è il prezzo di una pagina che non si muove sotto le mani.

### G20 — «qui.» orfano sulla seconda riga `[applicato]`

«Il testo con i segnaposto apparirà qui.» andava a capo dopo «apparirà»,
lasciando «qui.» da solo. Il riflesso sbagliato era allargare `max-width`
finché la frase entrava: una misura scelta su *quella* frase, che si
rompe alla prima parola cambiata o alla prima traduzione.

`text-wrap: balance` risolve la classe: il browser distribuisce le parole
fra le righe invece di riempire la prima fino al limite, per qualunque
testo. Dove non è supportato il testo va a capo come prima — degrada, non
si rompe. Applicato a `.vuoto` e `.tabella-vuota`, cioè a tutti i
messaggi di stato vuoto, non solo a quello che avevo sotto gli occhi.

### G21 — Il percorso di click, misurato invece che ricordato

Il brief chiede che il percorso resti 3-4 click. Nei documenti c'era un
conteggio fatto a mano leggendo il codice: un conteggio a mano non si
accorge del click che si aggiunge sei mesi dopo. Ora
`test_percorso_click_resta_breve` installa un ascoltatore sugli eventi
`click` con `isTrusted`, percorre i tre compiti principali e legge il
contatore dal browser.

```
percorso di click misurato:
  anonimizza e copia: 2 click
  correggi e ricopia: 2 click
  ripristina e copia: 3 click
```

Alla prima stesura il test dava 9 click sul terzo tratto. Non era la UI:
registravo un ascoltatore nuovo a ogni tratto e ognuno incrementava lo
stesso contatore, quindi il terzo tratto contava tre volte ogni click.
Vale la pena scriverlo perché è il modo tipico in cui una misura
sbagliata sopravvive: 9 è abbastanza plausibile da poterci credere.


---

# Quarto giro — la firma, e la rifinitura dopo la modifica diretta

Contesto: la PARTE 2 ha aggiunto due gesti diretti sul testo (passare sul
segnaposto per correggerlo, selezionare a sinistra per anonimizzare).
Nessuno dei due lascia un segno sullo schermo finché non lo si prova.
Questo giro serve a metterli in vista e a firmare il prodotto.

Screenshot: `docs/screenshots/prima_*` e `docs/screenshots/dopo_*`, sei
schermate per tema, ventiquattro file. Stessa finestra (1400×900), stesso
testo di prova, stessa sequenza di click: le differenze sono le mie, non
del caso.

## H22 — La firma fissa passava sotto la tabella `[applicato, dopo un errore]`

Prima stesura: `position: fixed; right: 24px; bottom: 8px`, dentro il
margine inferiore di `main`. Il ragionamento era che `main` chiude con
24px di padding e una riga da 11px ancorata a 8px dal fondo ci sta
dentro. Il ragionamento era giusto **e la conclusione sbagliata**, perché
`main` è il contenitore che scorre: appena la tabella supera l'altezza
della finestra, il contenuto passa *sotto* l'elemento fisso.

Non è un'ipotesi: si vede in `dopo_chiaro_2_anonimizzato.png` della prima
tornata di screenshot, con «PrivacyBridge by @Andrea Sforna» scritto a
cavallo della riga `«PERSONA_3»` tagliata a metà. Cioè esattamente
l'etichetta appiccicata sopra il contenuto che il brief vieta. L'avevo
verificato con un test che passava — misurava la distanza dalle metriche
del pannello, che stanno 380px più in su, e quindi non misurava niente.

Correzione: la firma esce da `position: fixed` e diventa l'ultima riga
della colonna del corpo, sorella di `header` e `main`. Costa 19px di
altezza, non si sovrappone mai, e resta visibile sempre perché `main`
scorre dentro di sé. Il test è stato rifatto sulla proprietà che era
saltata davvero — `test_firma_non_copre_il_contenuto_quando_si_scorre`
crea il documento che produce lo scorrimento, va a fondo pagina e
verifica che nessun riquadro finisca sotto la firma:

```
assert altezza > 0, "il caso non è stato riprodotto: main non scorre"
```

Quella riga è la parte che conta. Un test che verifica l'invariante senza
prima riprodurre la condizione che la rompe è il test che avevo scritto
la prima volta.

## H23 — Il grigio che avevo scelto per la firma non passa AA `[applicato]`

Volevo `--testo-tenue`, il più smorto della scala, perché «discreta».
Aggiunto l'accostamento a `scripts/misura_contrasti.py`, misurato:

```
Testo tenue su sfondo (firma del prodotto)   4.41:1   4.5  SOTTO SOGLIA
```

4,41:1 contro 4,5:1. Sarebbe passato inosservato a occhio e sarebbe stato
l'unico punto dell'applicazione fuori norma. La firma usa `--testo-fioco`
(5,68:1 sulla tela chiara, 7,57:1 su quella scura). La discrezione la
fanno il corpo — 11px, il più piccolo della scala, nessun corpo nuovo — e
la posizione ai margini; non un grigio illeggibile.

Per la stessa ragione la gerarchia interna della firma è di peso e non di
tinta: `PrivacyBridge` a 600, il resto a 400. Sbiadire il «by» avrebbe
riaperto lo stesso problema su un pezzo più piccolo.

Vale la pena dirlo chiaro: il valore l'ho scoperto perché ho aggiunto la
misura *prima* di guardare lo schermo. A occhio avrei detto che andava
bene.

## H24 — La firma era ancorata alla finestra, non al foglio `[applicato]`

Seconda stesura, secondo errore: `padding: 0 24px` su un elemento largo
quanto il `body`. Ma il contenuto vive dentro `.vista`, che ha
`max-width: 1280px` e sta centrata. A 1400px la firma finiva 36px più a
destra del bordo del pannello — su uno schermo largo se ne sarebbe andata
per conto suo, staccata dal foglio che dovrebbe firmare.

La firma prende la stessa geometria di colonna: `max-width: calc(1280px +
48px)`, `margin: 0 auto`. Ora il suo bordo destro cade sul bordo destro
del pannello, e ci resta a qualunque larghezza. Verificato in
`test_firma_in_basso_a_destra` con tolleranza 2px contro il riquadro
reale di `#pannello-dx`.

Nota su come è stato misurato: il primo tentativo leggeva il riquadro del
contenitore, che è largo quanto la finestra e comincia a `x = 0`. Il test
diceva «la firma non è a destra» ed era vero del `div`, falso di quello
che si vede. Si misurano gli span del testo.

## H25 — Sedici e otto, non otto e otto `[applicato]`

Con la firma nel flusso, `main` non ha più bisogno dei suoi 24px di
fondo. Ho provato 8px sopra e 8px sotto: simmetrico, e sbagliato. Quando
il tavolo scorre, l'ultima riga della tabella resta tagliata a metà a
pochi pixel dalla firma, in un grigio vicino: due righe piccole della
stessa tinta a 8px di distanza si leggono come una riga in più della
tabella.

16px sopra, 8px sotto. La separazione dal contenuto conta più della
vicinanza al bordo, e il totale — 35px — è il margine di prima più
esattamente la riga che ha guadagnato.

## H26 — I due gesti nuovi non li vedeva nessuno `[applicato]`

Questo è il difetto più grave del giro, ed è di sostanza, non di pixel.
La PARTE 2 ha aggiunto due modi di lavorare direttamente sul testo. Sullo
schermo non c'era **niente** che li annunciasse: bisognava passare il
mouse sopra un segnaposto per caso, o selezionare una parola per caso.
Una funzione che non si può scoprire vale zero.

I sottotitoli dei pannelli erano il posto giusto perché esistono già e
sono contestuali — cambiano quando c'è un risultato.

| | prima | dopo |
|---|---|---|
| sinistra | `valori sensibili evidenziati — clicca Modifica per riscrivere` | `valori evidenziati — seleziona per anonimizzare` |
| destra | `pronto per l'invio` (fisso) | `passa su un segnaposto per correggerlo` (a risultato pronto) |

«clicca Modifica» se n'è andato: il pulsante che nomina sta due
centimetri più a destra e si spiega da solo. Era un'istruzione che
spiegava un pulsante visibile, mentre il gesto invisibile non lo spiegava
nessuno. A destra «pronto per l'invio» resta finché il pannello è vuoto —
lì è una promessa; a risultato pronto la rassicurazione la portano già la
riga delle metriche («16 valori trattenuti») e il pulsante «Copia».

Costo: nessuno. Nessun elemento nuovo, nessun pixel di altezza in più.

## H27 — Il sottotitolo poteva spingere il pulsante fuori dal pannello `[applicato]`

Trovato mentre allungavo i sottotitoli. `.testa` è un flex con titolo,
sottotitolo e pulsante; il sottotitolo non aveva `min-width: 0`, e un
flex non scende sotto il proprio contenuto. Alla larghezza minima della
finestra (800px) il sottotitolo avrebbe spinto il pulsante oltre il bordo
del pannello — che ha `overflow: hidden`, quindi il pulsante **sparisce**
invece di stringersi.

`min-width: 0` più `text-overflow: ellipsis`: ora il sottotitolo cede per
primo, che è giusto — è l'unico pezzo della testata che si può accorciare
senza perdere una funzione. Il difetto c'era già prima di questo giro;
l'ho visto solo perché stavo cambiando quel testo.

## H28 — Le due righe di metriche non si somigliavano `[applicato]`

A destra `<b>16 valori trattenuti</b> · 16 occorrenze · 341 caratteri`, a
sinistra `322 caratteri` tutto grigio. Stesso posto, stessa altezza,
stessa funzione, due forme diverse: si leggevano come due componenti
diversi. Ora anche a sinistra il numero è in nero — `<b>322</b>
caratteri` — così entrambe le righe hanno la stessa ancora visiva.

Non ho messo in grassetto tutta la frase a sinistra: «322 caratteri» non
è un fatto importante quanto «16 valori trattenuti», e la simmetria non
deve arrivare a dire una cosa falsa sulla gerarchia.

## Cose che ho guardato e non ho toccato

- **Il riquadro vuoto delle entità occupa 340px a schermo vuoto.** È il
  prezzo già pagato in G19 perché la pagina non salti al primo
  «Anonimizza». Confermato, non riaperto.
- **La riga tagliata a metà in fondo alla tabella.** È l'affordance dello
  scorrimento e va bene che si veda. Il problema era la firma sopra, non
  il taglio.
- **Il menu a tendina della colonna «Tipo» è largo quanto la colonna**,
  con un centinaio di pixel fra l'etichetta e la freccia. Stringerlo
  vorrebbe dire scegliere una larghezza sul tipo più lungo di oggi
  («Documento d'identità»), e romperla al primo tipo nuovo. Lasciato.
- **Il colore e la spaziatura del comando diretto.** Ha già la sua
  transizione (opacità più 2px di risalita, 160ms sulla curva di sistema)
  e l'anello di fuoco globale. Non c'era niente da rifinire.
