# DESIGN.md — PrivacyBridge

Sistema visivo per l'interfaccia di PrivacyBridge.
Destinatari: studi tecnici, di ingegneria, commercialisti. Utente **non tecnico**,
che usa lo strumento ogni giorno sui dati dei propri clienti.

Il lavoro dell'interfaccia è **uno solo**: dare la certezza visiva che i dati
sensibili sono stati tolti, prima che il testo venga mandato altrove.
Tutto ciò che non serve a questo scopo è decorazione e va tagliato.

---

## 1. Il concetto: due mondi separati da una linea di strappo

L'app tratta due materiali diversi, non due "viste" della stessa cosa:

| | **Originale** | **Anonimizzato** |
|---|---|---|
| Cos'è | Il documento vero, con i dati del cliente | Il testo reso inerte |
| Dove vive | Su questa macchina | Fuori, verso l'LLM |
| Metafora | Carta sigillata con **ceralacca** | Rame ossidato, **verderame** |
| Stato | Vivo, riferito a una persona reale | Inerte, non riferisce più a nessuno |

La coppia ceralacca ↔ verderame non è "rosso = pericolo / verde = ok".
È **sigillato ↔ ossidato**: due stati fisici di un materiale, non due livelli di
allarme. Il verderame è la patina che si forma quando il metallo *ha smesso di
reagire* — è esattamente ciò che succede a un dato anonimizzato.

Questa dualità deve essere riconoscibile ovunque, alla scala del documento e
alla scala del singolo token.

---

## 2. Palette

Sei valori dichiarati. Tutte le tinte intermedie si derivano con `color-mix()`,
mai con nuovi hex sparsi.

| Variabile | Hex | Nome | Ruolo dichiarato |
|---|---|---|---|
| `--grafite` | `#1E2126` | Grafite | Testo primario, titoli, barra superiore, banner di errore. Nero-neutro caldo, **mai** `#000`. |
| `--zinco` | `#CFD5DB` | Zinco | Sfondo applicazione. È il **banco di lavoro**: grigio freddo medio su cui i pannelli poggiano come oggetti. |
| `--foglio` | `#FBFBFA` | Foglio | Superficie del pannello **Originale**. Bianco appena caldo = carta. |
| `--acciaio` | `#E4E8EC` | Acciaio | Superficie del pannello **Anonimizzato**. Pallido e freddo = materiale che è passato dalla macchina. |
| `--ceralacca` | `#8E1F3F` | Ceralacca | Il dato **vero**. Bordo-dorsale del pannello Originale, sottolineatura dei valori sensibili, colonna "Valore" in tabella. |
| `--verderame` | `#125A52` | Verderame | Il dato **trattenuto/sostituito**. Dorsale del pannello Anonimizzato, chip segnaposto, contatore "valori trattenuti". |

```css
:root {
  --grafite:    #1E2126;
  --zinco:      #CFD5DB;
  --foglio:     #FBFBFA;
  --acciaio:    #E4E8EC;
  --ceralacca:  #8E1F3F;
  --verderame:  #125A52;

  /* derivate — nessun hex nuovo */
  --testo:        var(--grafite);
  --testo-fioco:  color-mix(in srgb, var(--grafite) 55%, var(--zinco));
  --bordo:        color-mix(in srgb, var(--grafite) 18%, var(--zinco));
  --bordo-forte:  color-mix(in srgb, var(--grafite) 34%, var(--zinco));
  --vel-cera:     color-mix(in srgb, var(--ceralacca) 12%, transparent);
  --vel-verde:    color-mix(in srgb, var(--verderame) 12%, transparent);
}
```

**Contrasto verificato** (tutti ≥ AA su testo normale):

- grafite su zinco → 10.9:1
- grafite su acciaio → 13.1:1
- ceralacca su foglio → 8.5:1
- verderame su acciaio → 6.5:1
- verderame su foglio → 8.1:1

**Regola vincolante:** ceralacca **non è** il colore d'errore. Gli errori di
sistema (backend giù, file illeggibile) usano un banner pieno `--grafite` con
testo `--foglio` e un'etichetta esplicita. Nessuna settima tinta. Se ceralacca
significasse anche "errore", perderebbe il suo unico significato — "questo è un
dato reale del tuo cliente" — che è il messaggio più importante dell'app.

---

## 3. Tipografia

**Solo font di sistema. Nessun `@font-face`, nessun `<link>` a Google Fonts.**
L'app funziona offline: caricare font remoti è inaccettabile.

```css
:root {
  --f-titolo: ui-serif, "New York", "Iowan Old Style",
              "Cambria", Georgia, "DejaVu Serif", serif;
  --f-corpo:  -apple-system, BlinkMacSystemFont, "SF Pro Text",
              "Segoe UI Variable", "Segoe UI", system-ui,
              "Roboto", "Helvetica Neue", Arial, sans-serif;
  --f-mono:   ui-monospace, "SF Mono", SFMono-Regular, Menlo,
              "Cascadia Code", "Cascadia Mono", Consolas,
              "DejaVu Sans Mono", monospace;
}
```

**Stack cross-piattaforma dichiarato**. Su macOS resta il primo termine
(`New York`, `SF Pro Text`, `SF Mono`); su Windows scivola su
`Cambria`/`Segoe UI`/`Cascadia Code`; su Linux su `DejaVu Serif` /
Roboto / DejaVu Sans Mono. Non si scarica nulla, non si distribuisce
nessun file di font: tutte le voci sono presenti nelle installazioni di
default dei rispettivi sistemi.

Il carattere del sistema è ovviamente diverso — Cambria non è New York —
ma i tre ruoli restano coerenti: serif elegante per titoli, geometrico
umanista per il corpo, monospaziato leggibile per i pannelli. L'identità
regge perché non dipende da un singolo font ma dal contrasto fra i tre
ruoli, dalla scala tipografica e dalla palette.

### Tre ruoli, tre lavori diversi

**`--f-titolo` — New York (serif).**
Wordmark, intestazioni dei pannelli, titoli di sezione. Usato **piccolo e
compatto** (11–22px), mai come display. Motivazione: lo studio professionale
italiano lavora su atti, perizie, contratti. Il serif àncora l'app al mondo del
documento invece che a quello della dashboard SaaS. Le intestazioni di pannello
vanno in maiuscoletto con `letter-spacing: .07em` — leggono come intestazioni di
protocollo, non come titoli editoriali.

**`--f-corpo` — SF Pro Text.**
Etichette, pulsanti, tabella entità, metriche, messaggi di stato. Tutto ciò che
si scorre in fretta e non si legge davvero. Deve sparire.

**`--f-mono` — SF Mono.**
**Entrambi** i pannelli di testo, tutti i segnaposto, tutti i valori in tabella,
l'ID di sessione. Questa è una scelta funzionale, non estetica: con lo stesso
monospaziato a sinistra e a destra le due colonne si allineano riga per riga, e
la sostituzione di `Mario Rossi` con `[PERSONA_1]` si legge come un cambio di
**materiale** e non come uno scivolamento del layout. L'utente può confrontare
le due colonne con l'occhio, senza contare.

### Scala tipografica

Scala modulare ~1.22, arrotondata a px interi. Densa: è uno strumento di lavoro,
non una landing page.

```css
:root {
  --t-xs:  11px;   /* etichette metriche, badge, maiuscoletti */
  --t-sm:  12.5px; /* tabella, testo secondario */
  --t-md:  14px;   /* corpo UI, pulsanti — base */
  --t-txt: 13.5px; /* i due pannelli di testo (mono) */
  --t-lg:  17px;   /* titoli di sezione */
  --t-xl:  22px;   /* wordmark */

  --lh-stretta: 1.35;  /* titoli */
  --lh-ui:      1.5;   /* corpo */
  --lh-testo:   1.7;   /* pannelli mono — respiro per i chip inline */
}
```

### Spaziature, raggi, tratti

Unità base 4px.

```css
:root {
  --s1: 4px;  --s2: 8px;   --s3: 12px;  --s4: 16px;
  --s5: 24px; --s6: 32px;  --s7: 48px;

  --r-pannello: 12px;  /* superfici grandi */
  --r-controllo: 7px;  /* pulsanti, select, campi */
  --r-chip: 4px;       /* segnaposto e badge */

  --tratto: 1px;              /* bordo standard, con stacco tonale visibile */
  --dorsale: 3px;             /* barra d'identità in testa ai pannelli */
  --gola: 32px;               /* larghezza della gola fra i pannelli */
  --passo-strappo: 12px;      /* passo della perforazione */
}
```

I raggi sono **deliberati e percepibili**. I bordi non sono filetti da 0.5px:
sono 1px con uno stacco tonale reale (`--bordo`), rinforzati dalla dorsale da
3px. Le superfici hanno un'ombra bassa e corta
(`0 1px 0 rgba(30,33,38,.06), 0 2px 6px rgba(30,33,38,.07)`) che le stacca dallo
zinco senza farle galleggiare.

---

## 4. Elemento firma — **La Linea di Strappo**

> La cosa per cui questa interfaccia si riconosce.

Fra i due pannelli non c'è un divisore. C'è una **gola di 32px** che contiene una
perforazione verticale: trattini da 1px × 6px, passo 12px, in
`--bordo-forte`. Alle due estremità della gola, un **occhiello**: un anello di
14px, 1.5px di tratto, come il foro di un raccoglitore d'archivio.

Non è una decorazione: è l'affermazione centrale del prodotto. *Questi due testi
sono staccabili lungo una linea controllata. Quello a destra si strappa via e si
manda fuori. Quello a sinistra resta qui.*

```css
.gola {
  width: var(--gola);
  background-image: repeating-linear-gradient(
    to bottom,
    var(--bordo-forte) 0 6px,
    transparent 6px var(--passo-strappo)
  );
  background-size: 1px 100%;
  background-position: center;
  background-repeat: repeat-y;
}
```

### Il motivo è frattale: stessa forma, due scale

**Scala documento — la gola.** Separa i due pannelli.

**Scala token — il chip segnaposto.** Ogni `[PERSONA_1]` nel pannello destro ha
il **bordo sinistro dentellato** con le stesse scallopature da 3px: si legge
come il margine di qualcosa che è stato strappato via lì.

```css
.segnaposto {
  font-family: var(--f-mono);
  font-size: .95em;
  color: var(--verderame);
  background: var(--vel-verde);
  border-radius: 0 var(--r-chip) var(--r-chip) 0;
  padding: 1px var(--s2) 1px 7px;
  box-shadow: inset 2px 0 0 var(--verderame);
  mask-image: repeating-radial-gradient(
    circle at left, transparent 0 2px, #000 2px 3px
  );
  mask-size: 6px 6px;   /* dentellatura solo sul filo sinistro */
}
```

Il valore reale corrispondente nel pannello sinistro porta la stessa dentellatura
in `--ceralacca` e una sottolineatura **piena** da 2px (mai punteggiata: il
punteggiato dice "incerto", e qui non c'è incertezza).

### L'interazione che chiude il concetto

Passando il mouse su un valore a sinistra **o** sul suo segnaposto a destra, si
illuminano entrambi contemporaneamente e nella gola compare un singolo trattino
pieno all'altezza della coppia — il punto esatto in cui il dato è stato staccato.
È l'unica animazione del sistema (120ms, `ease-out`). Nient'altro si muove.

### Identità dei due pannelli

| | Sinistra | Destra |
|---|---|---|
| Superficie | `--foglio` | `--acciaio` |
| Dorsale (3px in testa) | `--ceralacca` | `--verderame` |
| Titolo | ORIGINALE | ANONIMIZZATO |
| Sottotitolo | *resta su questa macchina* | *pronto per l'invio* |

Il sottotitolo è la rassicurazione che l'utente non tecnico deve poter leggere
senza chiedere niente a nessuno. È testo, non un'icona: le icone di lucchetto si
interpretano, le frasi no.

### Chiusura del ciclo

A elaborazione conclusa la dorsale destra diventa piena, a tutta larghezza del
pannello, e la riga metriche riporta:

> **7 valori trattenuti** · 12 occorrenze · 4.203 caratteri

**"Trattenuti"**, non "rimossi" né "mascherati". Dice la cosa giusta: quei valori
sono *rimasti indietro*, dalla parte sicura della linea di strappo. E il verbo
prepara il ripristino — ciò che è trattenuto si può restituire.

### Vincolo anti-kitsch

La perforazione esiste **a due scale e basta**: la gola e il chip. Non compare su
pulsanti, schede, tabelle, bordi di sezione o intestazioni. Se comparisse
ovunque diventerebbe texture, e una texture non afferma niente.

---

## 5. Applicazione alle superfici esistenti

- **Barra superiore** — piena `--grafite`, wordmark in New York 22px, a destra
  l'indicatore di sessione in `--f-mono` `--t-xs`. Tinta unita: **nessun
  gradiente**.
- **Schede Anonimizza / Ripristina** — la scheda attiva prende la dorsale da 3px
  del mondo verso cui porta: verderame per *Anonimizza*, ceralacca per
  *Ripristina* (il ripristino riporta i dati veri: è il verso opposto).
- **Tabella entità** — colonna *Valore* in ceralacca, colonna *Segnaposto* con il
  chip dentellato. Righe alte 34px, zebratura assente, separatori `--bordo`.
- **Barra azioni** — un solo pulsante pieno `--grafite`. Tutti gli altri sono
  contorni su `--bordo-forte`. Una sola azione primaria per schermata.
- **Badge tipo entità** (PERSONA, CF, IBAN…) — `--f-corpo` `--t-xs`
  maiuscoletto, contorno `--bordo-forte`, **nessuna tinta propria**. Se ogni tipo
  avesse un colore, la coppia ceralacca/verderame smetterebbe di significare
  qualcosa.

---

## 6. Autocritica del piano

Ho riletto quanto sopra chiedendomi: *lo produrrei identico per un CRM, un
gestionale di magazzino o un tool di note?* Dove la risposta è stata sì, ho
cambiato. Ecco cosa e perché.

### 6.1 Le quattro trappole — verifica

**1 — Crema + serif ad alto contrasto + terracotta.** Evitata, ma **c'è mancato
poco**: la prima stesura aveva sfondo `#F4F0E8` e New York a 28px. Il serif da
solo non è la trappola; la trappola è la tripletta. Ho cambiato lo sfondo in
zinco freddo (`#CFD5DB`), tolto il terracotta a favore di ceralacca/verderame, e
ho **retrocesso il serif da display a etichetta** (max 22px, in maiuscoletto).
Vincolo che mi do: se in futuro il serif tornasse sopra i 24px *e* lo sfondo
scivolasse verso il caldo, va sostituito con SF Pro Display in `-0.02em`.

**2 — Quasi-nero con un solo accento acido.** Evitata due volte: il tema è
chiaro, e gli accenti sono **due**, semanticamente accoppiati. Ceralacca `#8E1F3F`
non è vermiglio (è desaturato e scuro) e verderame `#125A52` non è verde acido
(è ossidato, quasi teal). Nessuno dei due funziona come "colore di allarme", ed
è voluto.

**3 — Impaginato tipo giornale, filetti sottilissimi, raggio zero.** Evitata:
raggi espliciti 12/7/4px, bordi da 1px con stacco tonale reale, dorsali da 3px
e ombre percepibili. Le superfici sono **oggetti su un banco**, non colonne su
una pagina.

**4 — Dark mode con gradiente blu.** Evitata. Non c'è dark mode, non c'è blu,
e in tutto il sistema **non esiste un solo gradiente** — solo tinte piene. Il
gradiente era il difetto principale del tentativo precedente (`index.html`
attuale, `header.top` con `linear-gradient(120deg, #0b1a3a … #1d4ed8)` e Inter
caricato da Google Fonts): decorava senza dire nulla.

### 6.2 Cosa ho cambiato rileggendomi

**Il divisore è diventato la linea di strappo.** Prima stesura: due card uguali
con un `border-left` e un accento diverso. È il layout diff di GitHub, di ogni
comparatore JSON, di ogni editor di traduzioni — non nasce da questo prodotto.
Ho sostituito il divisore con una gola perforata e occhielli d'archivio, e ho
reso i due pannelli **materialmente diversi** (foglio caldo ↔ acciaio freddo)
invece che identici e ricolorati. Il punto: qui i due lati non sono "prima e
dopo", sono *cosa resta* e *cosa parte*. Una simmetria pulita mentiva.

**Il chip ha preso la dentellatura.** Il segnaposto era un normale pill
arrotondato con sfondo tenue — il badge di qualsiasi tag input al mondo. Facendo
tornare il motivo dello strappo alla scala del token, il sistema è diventato
frattale: la stessa affermazione a due scale. È la differenza fra una palette e
un linguaggio.

**Ho tolto i colori per tipo di entità.** Avevo assegnato una tinta a PERSONA, CF,
IBAN, EMAIL… Sembra utile e invece è distruttivo: con otto colori a schermo,
ceralacca e verderame diventano due tinte fra le altre e la dualità — l'unica
cosa che l'utente deve capire — sparisce. I tipi ora si distinguono per
**etichetta testuale**, che peraltro un utente non tecnico legge meglio di una
legenda cromatica da memorizzare.

**Ho vietato a ceralacca di significare "errore".** Era il riflesso ovvio
(rosso = errore) e avrebbe distrutto il concetto: se ceralacca marca sia i dati
del cliente sia i guasti del backend, l'utente impara che il colore vuol dire
"attenzione generica" e smette di leggerlo come "questo è un dato vero". Gli
errori usano grafite pieno più testo esplicito. Costa una convenzione in meno e
salva l'unico significato che conta.

**Ho scelto "trattenuti" al posto di "rimossi".** Il lessico è design, non copy.
"Rimossi" suggerisce distruzione e spaventa chi deve poi ripristinare;
"trattenuti" descrive esattamente cosa fa il vault e prepara il verso inverso.

### 6.3 Rischi residui che accetto consapevolmente

- **La dentellatura in `mask-image` è delicata.** Su rendering imprecisi degrada.
  Fallback previsto: `box-shadow: inset 2px 0 0` in tinta, che conserva il filo
  sinistro marcato anche senza le scallopature.
- **New York è il punto più fragile del sistema.** È l'unica scelta che potrebbe
  scivolare verso la trappola 1. Sopravvive perché sta su zinco freddo, piccolo e
  in maiuscoletto. Se in prova sembrerà "libro" invece che "protocollo", va
  sostituito senza rimpianti — il concetto della linea di strappo non dipende da
  lui.
- **Tema chiaro unico.** Nessun dark mode. Non è una dimenticanza: la carta è la
  metafora portante, e una versione scura obbligherebbe a reinventare ceralacca
  e verderame perdendo la lettura "sigillato ↔ ossidato". Meglio un tema che
  significa qualcosa che due che non significano niente.
