# TASSONOMIA_PII — Copertura sistematica dei dati personali italiani

Data: 2026-07-31. Derivata dall'art. 4 GDPR ("dato personale = qualsiasi
informazione riferibile a una persona identificata o identificabile"),
declinata sulla realtà italiana.

Legenda **Stato**:
- **coperto** — recognizer attivo, test verdi, categoria attiva per default.
- **coperto (opt-in)** — recognizer attivo ma categoria spenta per default
  (l'utente la accende quando serve).
- **parziale** — coperto solo in alcune forme/condizioni (dettagliato).
- **fuori perimetro** — deliberatamente non rilevato in automatico, con
  motivazione; la rete di sicurezza è la tabella entità + rubrica personale.

Legenda **Rilevamento**: *det.* = deterministico (regola/formato/carattere
di controllo, arriva al ~100% e non dipende dal modello); *sem.* =
semantico (serve il modello neurale/dizionario); *det.+kw* = formato
deterministico ma con parola-chiave contestuale obbligatoria (formati
troppo generici da soli).

---

## 1. Identità e anagrafica

| Dato | Formato | Rilevamento | Stato |
|---|---|---|---|
| Nome + cognome | testo | sem. (rizzo-pii + dizionario 5.868 nomi / 21.727 cognomi, 3 livelli) | **coperto** (PERSONA) |
| Nome di battesimo isolato | testo | sem. (dizionario, livelli 1-3) | **coperto** (PERSONA); ambigui senza contesto → suggerimento |
| Soprannome | testo libero | — | **fuori perimetro**: nessuna lista chiusa possibile; rubrica personale |
| Nome da nubile | testo ("nata Bianchi") | sem. | **parziale**: se il modello lo emette come PERSONA è coperto; nessun pattern dedicato ("nata X" collide con luogo di nascita). Rubrica |
| Data di nascita | 6+ formati data con contesto ("nato il", "d.d.n.") | det.+kw | **coperto** (DATA_NASCITA) |
| Luogo di nascita/residenza | toponimo con contesto ("nato a", "residente a") + lista comuni ISTAT | det.+kw | **coperto** (LUOGO_NASCITA) |
| Cittadinanza | "italiana", "romena"… | sem. | **fuori perimetro**: parole singole frequentissime, alto rischio FP (vedi BLOCCHI.md § 9) |
| Sesso | "M"/"F"/"maschile"… | — | **fuori perimetro**: 1-2 caratteri o parole comuni, mai identificante da solo |
| Stato civile | 4-5 valori discreti | — | **fuori perimetro** (BLOCCHI.md § 9) |
| Età | "47 anni" | — | **fuori perimetro**: numero comune, identifica solo combinato; combinazioni forti (data nascita) già coperte |

## 2. Identificativi rilasciati dallo Stato

| Dato | Formato | Rilevamento | Stato |
|---|---|---|---|
| Codice fiscale persona | 16 char, checksum mod-26 | det. | **coperto** (CF), anche minuscolo, fallback formato per CF con typo |
| Codice fiscale ente | 11 cifre + keyword | det.+kw | **coperto** (CF) |
| Partita IVA | 11 cifre, checksum Luhn-like, anche con spazi | det. | **coperto** (PIVA) |
| Carta d'identità cartacea | AA 1234567 | det.+kw ("carta d'identità", "C.I.") | **coperto** (DOCUMENTO) — recognizer dedicato + validazione formato+keyword |
| CIE (nuovo formato) | CA00000AA | det.+kw | **coperto** (DOCUMENTO) |
| Passaporto | AA1234567, no checksum | det.+kw ("passaporto") | **coperto** (DOCUMENTO). Senza keyword NON rilevato (per design: il formato da solo genera FP, vedi BLOCCHI.md § 1) |
| Patente | AB1234567C / formati UE | det.+kw ("patente") | **coperto** (DOCUMENTO; anche IT_DRIVER_LICENSE di Presidio) |
| Tessera sanitaria | = codice fiscale | det. | **coperto** (CF) |
| Tessera TEAM | 20 cifre, inizia 80380 per l'Italia | det.+kw ("tessera") | **coperto** (DOCUMENTO) |
| Permesso di soggiorno | 9 alfanumerici, no checksum | det.+kw ("permesso di soggiorno") | **coperto** (DOCUMENTO, via formato generico + keyword) |
| Matricola INPS | 10 cifre | det.+kw ("matricola INPS") | **coperto** (PRATICA) |
| Posizione INAIL | cifre | det.+kw ("INAIL") | **coperto** (PRATICA) |
| Iscrizione albo professionale | numero | det.+kw ("iscrizione albo") | **coperto** (PRATICA) |

## 3. Contatto e recapito

| Dato | Formato | Rilevamento | Stato |
|---|---|---|---|
| Email | RFC 5322 | det. | **coperto** (EMAIL, Presidio) |
| PEC | = email (dominio .pec/legalmail…) | det. | **coperto** (EMAIL — stessa sintassi) |
| Telefono mobile | 3xx… con/senza +39 | det. | **coperto** (TELEFONO, regex stringente anti-decimali) |
| Telefono fisso | 0xx… | det. | **coperto** (TELEFONO) |
| Indirizzo residenza/domicilio | odonimo + toponimo + civico | det. | **coperto** (INDIRIZZO) |
| CAP | 5 cifre + keyword contestuale | det.+kw | **coperto** (CAP) |
| Casella postale | "C.P. 123", "Casella Postale 123" | det.+kw | **coperto** (INDIRIZZO) |
| Handle social (@nome) | @[a-z0-9_.]{2,30} | det. | **coperto** (SOCIAL) — esclude le email per costruzione |
| Profilo social (URL) | URL | det. | **coperto (opt-in)** (URL — categoria spenta per default: nei documenti tecnici gli URL sono quasi sempre non personali) |
| ID di messaggistica | formato libero per app | — | **fuori perimetro**: nessun formato univoco; @handle Telegram è coperto da SOCIAL; il resto via rubrica |

## 4. Finanziari

| Dato | Formato | Rilevamento | Stato |
|---|---|---|---|
| IBAN italiano | IT + 25, mod-97 | det. | **coperto** (IBAN), anche a gruppi di 4 e minuscolo |
| IBAN estero | ISO 13616, mod-97, lunghezze per paese | det. | **coperto** (IBAN) |
| BIC/SWIFT | 8/11 char | — | **fuori perimetro**: identifica l'istituto, non il cliente — è un dato pubblico della banca (il BIC di Intesa è su ogni sito). Da solo non è dato personale |
| Carta di pagamento | 13-19 cifre, Luhn | det. | **coperto** (CARTA, Presidio CreditCard) |
| Conto corrente non-IBAN | "c/c n. …", formato libero | — | **fuori perimetro**: dal 2008 l'IBAN è lo standard; il numero conto nudo non ha formato validabile. Tabella/rubrica |
| Numero polizza | alfanumerico + keyword | det.+kw ("polizza n.") | **coperto** (PRATICA) |
| Codice cliente bancario | formato libero per istituto | — | **fuori perimetro**: nessun formato; rubrica |
| Wallet crypto | base58/bech32/hex | det. | **coperto (opt-in)** (CRYPTO, Presidio — spento per default, raro nei documenti target) |

## 5. Veicoli

| Dato | Formato | Rilevamento | Stato |
|---|---|---|---|
| Targa auto (dal 1994) | AA000AA, alfabeto senza I/O/Q/U, anche con spazi/trattini | det. | **coperto** (TARGA) — senza bisogno di contesto |
| Targa provinciale storica | sigla + 6 cifre | det.+kw ("targa") | **coperto** (TARGA) |
| Targa moto | 2 lettere + 5 cifre | det.+kw | **coperto** (TARGA) |
| Targa ciclomotore/speciale | 5-7 alfanumerici | det.+kw | **parziale**: coperto solo con keyword adiacente; il formato da solo è troppo generico |
| Targa rimorchio | X[A-Z]000AA | det. | **coperto** (TARGA, rientra nel formato moderno) |
| VIN (telaio) | 17 char senza I/O/Q | det.+kw ("telaio", "VIN") | **coperto** (VIN) |
| Numero libretto | formato non pubblico/stabile | — | **fuori perimetro**: nessun formato validabile; rubrica |

## 6. Immobili e catasto

| Dato | Formato | Rilevamento | Stato |
|---|---|---|---|
| Dati catastali | "foglio N particella N sub N" (+abbreviazioni fg./part./mapp.) | det. | **coperto (opt-in)** (CATASTO — spento per default: identifica l'immobile, non direttamente la persona; attivabile o via preset) |
| Indirizzo immobile | = indirizzo | det. | **coperto** (INDIRIZZO) |
| Codice contratto locazione | 6-20 alfanumerici + keyword | det.+kw ("codice identificativo contratto") | **coperto** (PRATICA) |

## 7. Lavoro e istruzione

| Dato | Formato | Rilevamento | Stato |
|---|---|---|---|
| Datore di lavoro | nome azienda | sem. | **coperto (opt-in)** (ORG — spenta per default: nei documenti tecnici i nomi azienda sono per lo più marchi pubblici; recall ~56%, BLOCCHI.md § 2) |
| Qualifica/professione | testo | — | **fuori perimetro**: JOB_TITLE scartato per design (BLOCCHI.md § 9) |
| Matricola aziendale | cifre + keyword | det.+kw ("matricola") | **coperto** (PRATICA) |
| Istituto scolastico | nome ente | sem. | **coperto (opt-in)** (ORG) |
| Matricola universitaria | cifre + keyword | det.+kw ("matricola universitaria") | **coperto** (PRATICA) |

## 8. Digitali

| Dato | Formato | Rilevamento | Stato |
|---|---|---|---|
| Indirizzo IPv4 | dotted quad | det. | **coperto (opt-in)** (IP — spento per default: nei documenti tecnici è rumore) |
| Indirizzo IPv6 | RFC 4291 | det. | **coperto (opt-in)** (IP, Presidio IpRecognizer) |
| MAC address | 6 coppie hex | det. | **coperto (opt-in)** (MAC, Presidio MacAddress) |
| Identificativi dispositivo | IMEI (15 cifre, Luhn), serial vari | — | **fuori perimetro**: rari nei documenti target; IMEI senza keyword collide con altri numeri a 15 cifre. Rubrica |
| Cookie ID | stringa opaca | — | **fuori perimetro**: indistinguibile da qualsiasi token tecnico |
| Nome utente (non-@) | testo libero | — | **fuori perimetro**: semantico e senza formato; @handle coperto da SOCIAL |

## 9. Documenti e procedimenti

| Dato | Formato | Rilevamento | Stato |
|---|---|---|---|
| Numero di pratica | "pratica n. X" | det.+kw | **coperto** (PRATICA) |
| Numero di protocollo | "prot. n. X" | det.+kw | **coperto** (PRATICA) |
| R.G. giudiziario | "R.G. 1234/2023" | det.+kw | **coperto** (PRATICA) |
| Numero sentenza/decreto/ordinanza | "sentenza n. 89/2021" | det.+kw | **coperto** (PRATICA) |
| Atto notarile | "rep. N racc. N" | det.+kw | **coperto** (PRATICA) |
| Numero fattura | "fattura n. X" | det.+kw | **coperto** (PRATICA) |
| Numero verbale | "verbale n. X" | det.+kw | **coperto** (PRATICA) |
| Numero spedizione | 1Z… (UPS), GLS…, 8-12 cifre + keyword corriere | det.+kw | **coperto (opt-in)** (SPEDIZIONE) |

## 10. Categorie particolari (art. 9 GDPR)

Salute, appartenenza sindacale, convinzioni religiose/filosofiche,
opinioni politiche, orientamento sessuale, dati biometrici e genetici,
origine razziale o etnica.

**Decisione: nessun rilevamento automatico dedicato** (motivata in
DECISIONI.md § 2026-07-31). In sintesi:

1. Sono *contenuti*, non *identificatori*: "il paziente è diabetico" non
   identifica nessuno se il nome del paziente è già mascherato. La
   strategia dell'app è mascherare gli identificatori (chi), non i
   contenuti (cosa).
2. Il lessico è l'italiano comune ("depressione", "sindacato",
   "cattolico"): un rilevatore automatico produrrebbe valanghe di FP e
   renderebbe il testo inutilizzabile per l'assistente AI a valle.
3. I codici che veicolano dati sanitari in forma identificante (codice
   fiscale su referto, numero tessera, MEDICAL_LICENSE) sono già coperti
   (CF, DOCUMENTO, SANITARIO).

Rete di sicurezza: la tabella entità permette di aggiungere a mano
qualsiasi frase; la rubrica personale rende permanente la scelta.

---

## Riepilogo operativo

- Categorie **attive per default**: PERSONA, EMAIL, TELEFONO, IBAN, CF,
  PIVA, CARTA, CAP, INDIRIZZO, SANITARIO, DOCUMENTO, DATA_NASCITA,
  LUOGO_NASCITA, **TARGA**, **VIN**, **PRATICA**, **SOCIAL** (le ultime
  quattro aggiunte 2026-07-31).
- Categorie **opt-in**: LUOGO, ORG, DATA, IMPORTO, URL, IP, MAC, CRYPTO,
  CATASTO, SPEDIZIONE.
- Ogni recognizer deterministico nuovo ha test con casi validi, non
  validi e al limite in `tests/test_tassonomia.py`.
- Gate falsi positivi: benchmark su `benchmark/documenti_utente/`
  (documenti reali) prima/dopo — nessuna sostituzione in più che non sia
  un dato personale vero (output in `benchmark/documenti_utente_output.txt`).
