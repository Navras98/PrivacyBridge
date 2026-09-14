# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Corpus annotato per test di regressione del motore PrivacyBridge.

Ogni entrata ha:
    - id: identificativo univoco (frase_1 ... frase_76)
    - testo: la frase originale
    - entita: lista di dict con start, end, tipo
    - categoria: "email_studio", "contratto", "cliente"

Le annotazioni sono manuali e fanno da ground truth per recall e precision.
Codici fiscali, partite IVA, IBAN e numeri di carta sono fittizi ma superano
i rispettivi checksum, cosi' da attivare i validatori di backend/recognizers.py.
"""

from __future__ import annotations

CorpusEntry = dict[str, object]
CorpusList = list[CorpusEntry]

CORPUS: CorpusList = [
    {
        "id": "frase_1",
        "categoria": "email_studio",
        "testo": (
            "Gentile Ing. Mario Rossi, in allegato trova il computo metrico "
            "revisionato dello Studio Tecnico Associati; per qualsiasi "
            "chiarimento scriva a segreteria@studiotecnicoassociati.it oppure "
            "chiami il 02 45871234."
        ),
        "entita": [
            {"start": 13, "end": 24, "tipo": "PERSONA"},  # Mario Rossi
            {"start": 81, "end": 105, "tipo": "ORG"},  # Studio Tecnico Associati
            {"start": 142, "end": 178, "tipo": "EMAIL"},  # segreteria@studiotecnicoassociati.it
            {"start": 196, "end": 207, "tipo": "TELEFONO"},  # 02 45871234
        ],
    },
    {
        "id": "frase_2",
        "categoria": "email_studio",
        "testo": (
            "Buongiorno, sono Sigismondo Bellavista dello studio Ing. Bianchi & "
            "Partners: le confermo il sopralluogo del 14 marzo 2025 presso il "
            "cantiere di Via Garibaldi 27, Bergamo."
        ),
        "entita": [
            {"start": 17, "end": 38, "tipo": "PERSONA"},  # Sigismondo Bellavista
            {"start": 52, "end": 75, "tipo": "ORG"},  # Ing. Bianchi & Partners
            {"start": 108, "end": 121, "tipo": "DATA"},  # 14 marzo 2025
            {"start": 144, "end": 160, "tipo": "LUOGO"},  # Via Garibaldi 27
            {"start": 162, "end": 169, "tipo": "LUOGO"},  # Bergamo
        ],
    },
    {
        "id": "frase_3",
        "categoria": "email_studio",
        "testo": (
            "Come da accordi telefonici, l'arch. Anna Verdi trasmetterà la "
            "relazione geologica entro venerdì; il file sarà disponibile su "
            "https://cloud.tecnoprogetti.it/pratiche/2025."
        ),
        "entita": [
            {"start": 36, "end": 46, "tipo": "PERSONA"},  # Anna Verdi
            {"start": 88, "end": 95, "tipo": "DATA"},  # venerdì
            {"start": 125, "end": 169, "tipo": "URL"},  # https://cloud.tecnoprogetti.it/pratiche/2025
        ],
    },
    {
        "id": "frase_4",
        "categoria": "email_studio",
        "testo": (
            "Restiamo in attesa di un cortese riscontro e cogliamo l'occasione "
            "per porgere i nostri più cordiali saluti."
        ),
        "entita": [],
    },
    {
        "id": "frase_5",
        "categoria": "email_studio",
        "testo": (
            "Il collega Ermenegildo Fumagalli ha caricato i rilievi sul server "
            "interno raggiungibile all'indirizzo IP 192.168.14.22; le credenziali "
            "sono state inviate separatamente."
        ),
        "entita": [
            {"start": 11, "end": 32, "tipo": "PERSONA"},  # Ermenegildo Fumagalli
            {"start": 105, "end": 118, "tipo": "IP"},  # 192.168.14.22
        ],
    },
    {
        "id": "frase_6",
        "categoria": "email_studio",
        "testo": (
            "Si comunica che lo Studio Tecnico Associati ha trasferito la sede in "
            "Corso Vittorio Emanuele 118, 20122 Milano, con nuovo recapito "
            "telefonico +39 02 76001234."
        ),
        "entita": [
            {"start": 19, "end": 43, "tipo": "ORG"},  # Studio Tecnico Associati
            {"start": 69, "end": 96, "tipo": "LUOGO"},  # Corso Vittorio Emanuele 118
            {"start": 98, "end": 103, "tipo": "CAP"},  # 20122
            {"start": 104, "end": 110, "tipo": "LUOGO"},  # Milano
            {"start": 142, "end": 157, "tipo": "TELEFONO"},  # +39 02 76001234
        ],
    },
    {
        "id": "frase_7",
        "categoria": "email_studio",
        "testo": (
            "Per la fatturazione elettronica dei servizi di direzione lavori si "
            "prega di utilizzare la partita IVA 01234567897 dello studio e il "
            "codice destinatario indicato in calce."
        ),
        "entita": [
            {"start": 102, "end": 113, "tipo": "PIVA"},  # 01234567897
        ],
    },
    {
        "id": "frase_8",
        "categoria": "email_studio",
        "testo": (
            "Egregio dottor Hans Mueller, la ringraziamo per l'invito al workshop "
            "di Monaco di Baviera del 3 aprile; parteciperà il nostro "
            "responsabile strutture."
        ),
        "entita": [
            {"start": 15, "end": 27, "tipo": "PERSONA"},  # Hans Mueller
            {"start": 72, "end": 89, "tipo": "LUOGO"},  # Monaco di Baviera
            {"start": 94, "end": 102, "tipo": "DATA"},  # 3 aprile
        ],
    },
    {
        "id": "frase_9",
        "categoria": "email_studio",
        "testo": (
            "Ricordiamo che gli uffici resteranno chiusi per la pausa estiva e "
            "che le pratiche in corso saranno evase alla riapertura."
        ),
        "entita": [],
    },
    {
        "id": "frase_10",
        "categoria": "email_studio",
        "testo": (
            "Le trasmetto in copia l'ing. Chen Wei "
            "(chen.wei@tecnoprogetti-int.com) che seguirà la parte impiantistica "
            "della commessa."
        ),
        "entita": [
            {"start": 29, "end": 37, "tipo": "PERSONA"},  # Chen Wei
            {"start": 39, "end": 69, "tipo": "EMAIL"},  # chen.wei@tecnoprogetti-int.com
        ],
    },
    {
        "id": "frase_11",
        "categoria": "email_studio",
        "testo": (
            "La segreteria di TecnoProgetti SRL resta a disposizione al numero "
            "035 4571890 dal lunedì al venerdì, oppure via e-mail all'indirizzo "
            "info@tecnoprogetti.it."
        ),
        "entita": [
            {"start": 17, "end": 34, "tipo": "ORG"},  # TecnoProgetti SRL
            {"start": 66, "end": 77, "tipo": "TELEFONO"},  # 035 4571890
            {"start": 133, "end": 154, "tipo": "EMAIL"},  # info@tecnoprogetti.it
        ],
    },
    {
        "id": "frase_12",
        "categoria": "email_studio",
        "testo": (
            "Il sottoscritto, geom. Paolo Bianchi, dichiara di aver eseguito il "
            "collaudo dell'impianto in data 07/02/2025 presso l'immobile di "
            "Piazza Dante 5, Verona."
        ),
        "entita": [
            {"start": 23, "end": 36, "tipo": "PERSONA"},  # Paolo Bianchi
            {"start": 98, "end": 108, "tipo": "DATA"},  # 07/02/2025
            {"start": 130, "end": 144, "tipo": "LUOGO"},  # Piazza Dante 5
            {"start": 146, "end": 152, "tipo": "LUOGO"},  # Verona
        ],
    },
    {
        "id": "frase_13",
        "categoria": "email_studio",
        "testo": (
            "In allegato al presente messaggio sono riportate le note tecniche "
            "discusse in riunione, prive di riferimenti anagrafici."
        ),
        "entita": [],
    },
    {
        "id": "frase_14",
        "categoria": "email_studio",
        "testo": (
            "Dorotea Morricone ha aggiornato il cronoprogramma: la consegna degli "
            "elaborati definitivi slitta al 30 settembre 2025."
        ),
        "entita": [
            {"start": 0, "end": 17, "tipo": "PERSONA"},  # Dorotea Morricone
            {"start": 100, "end": 117, "tipo": "DATA"},  # 30 settembre 2025
        ],
    },
    {
        "id": "frase_15",
        "categoria": "contratto",
        "testo": (
            "L'appalto è affidato all'impresa Costruzioni Meridionali SPA, con "
            "sede legale in Napoli, partita IVA 12345678903, di seguito "
            "denominata Appaltatore."
        ),
        "entita": [
            {"start": 33, "end": 60, "tipo": "ORG"},  # Costruzioni Meridionali SPA
            {"start": 81, "end": 87, "tipo": "LUOGO"},  # Napoli
            {"start": 101, "end": 112, "tipo": "PIVA"},  # 12345678903
        ],
    },
    {
        "id": "frase_16",
        "categoria": "contratto",
        "testo": (
            "Il corrispettivo sarà liquidato mediante bonifico sull'IBAN "
            "IT60X0542811101000000123456 intestato a Costruzioni Meridionali SPA "
            "entro trenta giorni dalla data fattura."
        ),
        "entita": [
            {"start": 60, "end": 87, "tipo": "IBAN"},  # IT60X0542811101000000123456
            {"start": 100, "end": 127, "tipo": "ORG"},  # Costruzioni Meridionali SPA
        ],
    },
    {
        "id": "frase_17",
        "categoria": "contratto",
        "testo": (
            "Il presente contratto è stipulato tra il Comune di Cesenatico e lo "
            "studio Ing. Bianchi & Partners in data 12 gennaio 2026."
        ),
        "entita": [
            {"start": 41, "end": 61, "tipo": "ORG"},  # Comune di Cesenatico
            {"start": 74, "end": 97, "tipo": "ORG"},  # Ing. Bianchi & Partners
            {"start": 106, "end": 121, "tipo": "DATA"},  # 12 gennaio 2026
        ],
    },
    {
        "id": "frase_18",
        "categoria": "contratto",
        "testo": (
            "Le parti convengono che ogni modifica al presente atto dovrà "
            "risultare da accordo scritto, a pena di nullità."
        ),
        "entita": [],
    },
    {
        "id": "frase_19",
        "categoria": "contratto",
        "testo": (
            "Il committente, sig. Mario Rossi, nato a Firenze il 01/01/1980, "
            "codice fiscale RSSMRA80A01H501U, conferisce incarico professionale "
            "per la progettazione esecutiva."
        ),
        "entita": [
            {"start": 21, "end": 32, "tipo": "PERSONA"},  # Mario Rossi
            {"start": 41, "end": 48, "tipo": "LUOGO"},  # Firenze
            {"start": 52, "end": 62, "tipo": "DATA"},  # 01/01/1980
            {"start": 79, "end": 95, "tipo": "CF"},  # RSSMRA80A01H501U
        ],
    },
    {
        "id": "frase_20",
        "categoria": "contratto",
        "testo": (
            "L'incarico è conferito alla società TecnoProgetti SRL, con sede in "
            "Via dell'Industria 42, 24040 Zingonia, C.F. e P.IVA 09876543217."
        ),
        "entita": [
            {"start": 36, "end": 53, "tipo": "ORG"},  # TecnoProgetti SRL
            {"start": 67, "end": 88, "tipo": "LUOGO"},  # Via dell'Industria 42
            {"start": 90, "end": 95, "tipo": "CAP"},  # 24040
            {"start": 96, "end": 104, "tipo": "LUOGO"},  # Zingonia
            {"start": 119, "end": 130, "tipo": "PIVA"},  # 09876543217
        ],
    },
    {
        "id": "frase_21",
        "categoria": "contratto",
        "testo": (
            "Il direttore dei lavori, arch. Anna Verdi (C.F. VRDNNA75M41F205E), "
            "assume le funzioni previste dall'art. 101 del D.Lgs. 50/2016."
        ),
        "entita": [
            {"start": 31, "end": 41, "tipo": "PERSONA"},  # Anna Verdi
            {"start": 48, "end": 64, "tipo": "CF"},  # VRDNNA75M41F205E
        ],
    },
    {
        "id": "frase_22",
        "categoria": "contratto",
        "testo": (
            "L'appaltatore si impegna a rispettare tutte le norme vigenti in "
            "materia di sicurezza sui luoghi di lavoro e di tutela ambientale."
        ),
        "entita": [],
    },
    {
        "id": "frase_23",
        "categoria": "contratto",
        "testo": (
            "Per ogni controversia relativa all'esecuzione del presente appalto "
            "sarà competente in via esclusiva il Foro di Bologna."
        ),
        "entita": [
            {"start": 111, "end": 118, "tipo": "LUOGO"},  # Bologna
        ],
    },
    {
        "id": "frase_24",
        "categoria": "contratto",
        "testo": (
            "Il subappaltatore Edilizia Fumagalli SNC, rappresentato dal sig. "
            "Ermenegildo Fumagalli, dovrà consegnare la documentazione antimafia "
            "entro il 15/03/2026."
        ),
        "entita": [
            {"start": 18, "end": 40, "tipo": "ORG"},  # Edilizia Fumagalli SNC
            {"start": 65, "end": 86, "tipo": "PERSONA"},  # Ermenegildo Fumagalli
            {"start": 142, "end": 152, "tipo": "DATA"},  # 15/03/2026
        ],
    },
    {
        "id": "frase_25",
        "categoria": "contratto",
        "testo": (
            "La lettera d'incarico è inviata a mezzo PEC all'indirizzo "
            "appalti@pec.costruzionimeridionali.it e, per conoscenza, a "
            "d.morricone@studiotecnicoassociati.it."
        ),
        "entita": [
            {"start": 58, "end": 95, "tipo": "EMAIL"},  # appalti@pec.costruzionimeridionali.it
            {"start": 117, "end": 154, "tipo": "EMAIL"},  # d.morricone@studiotecnicoassociati.it
        ],
    },
    {
        "id": "frase_26",
        "categoria": "contratto",
        "testo": (
            "Il pagamento dell'acconto è vincolato alla presentazione della "
            "polizza fideiussoria emessa in favore del Comune di Rimini entro il "
            "28 febbraio 2026."
        ),
        "entita": [
            {"start": 105, "end": 121, "tipo": "ORG"},  # Comune di Rimini
            {"start": 131, "end": 147, "tipo": "DATA"},  # 28 febbraio 2026
        ],
    },
    {
        "id": "frase_27",
        "categoria": "contratto",
        "testo": (
            "Ai sensi dell'art. 3 della legge 136/2010, l'appaltatore comunica il "
            "conto corrente dedicato IT92K0306901626100000012345 acceso presso la "
            "filiale di Torino."
        ),
        "entita": [
            {"start": 93, "end": 120, "tipo": "IBAN"},  # IT92K0306901626100000012345
            {"start": 149, "end": 155, "tipo": "LUOGO"},  # Torino
        ],
    },
    {
        "id": "frase_28",
        "categoria": "cliente",
        "testo": (
            "Gentile sig.ra Maria Garcia, le confermiamo che l'ordine n. 4471 "
            "sarà consegnato al deposito di Palermo entro il 5 maggio 2025."
        ),
        "entita": [
            {"start": 15, "end": 27, "tipo": "PERSONA"},  # Maria Garcia
            {"start": 96, "end": 103, "tipo": "LUOGO"},  # Palermo
            {"start": 113, "end": 126, "tipo": "DATA"},  # 5 maggio 2025
        ],
    },
    {
        "id": "frase_29",
        "categoria": "cliente",
        "testo": (
            "Il cliente ci ha segnalato un disservizio sulla linea 0577 289145 "
            "attiva presso la filiale di Siena."
        ),
        "entita": [
            {"start": 54, "end": 65, "tipo": "TELEFONO"},  # 0577 289145
            {"start": 94, "end": 99, "tipo": "LUOGO"},  # Siena
        ],
    },
    {
        "id": "frase_30",
        "categoria": "cliente",
        "testo": (
            "Vi informiamo che il listino prezzi allegato sostituisce "
            "integralmente quello precedente e resta valido fino a nuova "
            "comunicazione."
        ),
        "entita": [],
    },
    {
        "id": "frase_31",
        "categoria": "cliente",
        "testo": (
            "Per il rinnovo dell'abbonamento è stata addebitata la carta "
            "4539123456789017 intestata al sottoscritto, come da mandato già "
            "firmato."
        ),
        "entita": [
            {"start": 60, "end": 76, "tipo": "CARTA"},  # 4539123456789017
        ],
    },
    {
        "id": "frase_32",
        "categoria": "cliente",
        "testo": (
            "La ringraziamo per aver scelto TecnoProgetti SRL: il suo referente "
            "commerciale sarà John Smith, raggiungibile al 348 7712345 o "
            "all'indirizzo j.smith@tecnoprogetti.it."
        ),
        "entita": [
            {"start": 31, "end": 48, "tipo": "ORG"},  # TecnoProgetti SRL
            {"start": 84, "end": 94, "tipo": "PERSONA"},  # John Smith
            {"start": 113, "end": 124, "tipo": "TELEFONO"},  # 348 7712345
            {"start": 141, "end": 165, "tipo": "EMAIL"},  # j.smith@tecnoprogetti.it
        ],
    },
    {
        "id": "frase_33",
        "categoria": "cliente",
        "testo": (
            "Il fornitore Metalgraf SAS ha aggiornato i dati bancari: il nuovo "
            "IBAN è IT80Q0100503382000000218000, mentre la partita IVA resta "
            "11223344554."
        ),
        "entita": [
            {"start": 13, "end": 26, "tipo": "ORG"},  # Metalgraf SAS
            {"start": 73, "end": 100, "tipo": "IBAN"},  # IT80Q0100503382000000218000
            {"start": 130, "end": 141, "tipo": "PIVA"},  # 11223344554
        ],
    },
    {
        "id": "frase_34",
        "categoria": "cliente",
        "testo": (
            "Restiamo a disposizione per eventuali chiarimenti e vi auguriamo "
            "buon lavoro."
        ),
        "entita": [],
    },
    {
        "id": "frase_35",
        "categoria": "cliente",
        "testo": (
            "La spedizione è stata affidata a Trasporti Bellavista SNC e sarà "
            "consegnata in Via Roma 14, 09124 Cagliari, all'attenzione del sig. "
            "Sigismondo Bellavista."
        ),
        "entita": [
            {"start": 33, "end": 57, "tipo": "ORG"},  # Trasporti Bellavista SNC
            {"start": 79, "end": 90, "tipo": "LUOGO"},  # Via Roma 14
            {"start": 92, "end": 97, "tipo": "CAP"},  # 09124
            {"start": 98, "end": 106, "tipo": "LUOGO"},  # Cagliari
            {"start": 132, "end": 153, "tipo": "PERSONA"},  # Sigismondo Bellavista
        ],
    },
    {
        "id": "frase_36",
        "categoria": "cliente",
        "testo": (
            "Come richiesto dal Sig. Rossi, le inviamo il preventivo aggiornato: "
            "il documento è scaricabile da "
            "https://www.studiotecnicoassociati.it/preventivi/2026-0142."
        ),
        "entita": [
            {"start": 24, "end": 29, "tipo": "PERSONA"},  # Rossi
            {"start": 98, "end": 156, "tipo": "URL"},  # https://www.studiotecnicoassociati.it/preventivi/2026-0142
        ],
    },
    {
        "id": "frase_37",
        "categoria": "cliente",
        "testo": (
            "Il nostro tecnico Hans Mueller sarà presso la vostra sede di Bolzano "
            "martedì 9 giugno per la manutenzione programmata dei quadri "
            "elettrici."
        ),
        "entita": [
            {"start": 18, "end": 30, "tipo": "PERSONA"},  # Hans Mueller
            {"start": 61, "end": 68, "tipo": "LUOGO"},  # Bolzano
            {"start": 69, "end": 85, "tipo": "DATA"},  # martedì 9 giugno
        ],
    },
    {
        "id": "frase_38",
        "categoria": "cliente",
        "testo": (
            "Per completare la pratica di rimborso ci occorrono il codice fiscale "
            "del titolare, MLLGPP72L28E463X, e una copia del documento d'identità "
            "in corso di validità."
        ),
        "entita": [
            {"start": 83, "end": 99, "tipo": "CF"},  # MLLGPP72L28E463X
        ],
    },
    {
        "id": "frase_39",
        "categoria": "cliente",
        "testo": (
            "La fattura n. 233/2026 è stata trasmessa all'indirizzo "
            "amministrazione@metalgraf-sas.eu; in caso di mancata ricezione "
            "contattate lo 0432 501199."
        ),
        "entita": [
            {"start": 55, "end": 87, "tipo": "EMAIL"},  # amministrazione@metalgraf-sas.eu
            {"start": 132, "end": 143, "tipo": "TELEFONO"},  # 0432 501199
        ],
    },
    {
        "id": "frase_40",
        "categoria": "cliente",
        "testo": (
            "Vi comunichiamo che il portale clienti sarà raggiungibile dal nuovo "
            "indirizzo https://clienti.metalgraf.eu e che il vecchio server "
            "10.0.3.117 verrà dismesso il 31 dicembre 2026."
        ),
        "entita": [
            {"start": 78, "end": 106, "tipo": "URL"},  # https://clienti.metalgraf.eu
            {"start": 131, "end": 141, "tipo": "IP"},  # 10.0.3.117
            {"start": 160, "end": 176, "tipo": "DATA"},  # 31 dicembre 2026
        ],
    },
    {
        "id": "frase_41",
        "categoria": "email_studio",
        "testo": (
            "Buongiorno, il geom. Luca Bianco ha consegnato la relazione di calcolo "
            "allo Studio Rosa & Associati; copia per conoscenza all'ing. Marta Fiore."
        ),
        "entita": [
            {"start": 21, "end": 32, "tipo": "PERSONA"},  # Luca Bianco
            {"start": 76, "end": 99, "tipo": "ORG"},  # Studio Rosa & Associati
            {"start": 131, "end": 142, "tipo": "PERSONA"},  # Marta Fiore
        ],
    },
    {
        "id": "frase_42",
        "categoria": "email_studio",
        "testo": (
            "L'avv. Marco De Luca ha ricevuto l'incarico di assistenza legale per la "
            "commessa di ICOS SRL e risponde all'indirizzo "
            "m.deluca@studiolegaledeluca.it."
        ),
        "entita": [
            {"start": 7, "end": 20, "tipo": "PERSONA"},  # Marco De Luca
            {"start": 84, "end": 92, "tipo": "ORG"},  # ICOS SRL
            {"start": 118, "end": 148, "tipo": "EMAIL"},  # m.deluca@studiolegaledeluca.it
        ],
    },
    {
        "id": "frase_43",
        "categoria": "email_studio",
        "testo": (
            "La perizia strutturale è firmata dall'ing. Andrea Rossi Bianchi e "
            "controfirmata dalla dott.ssa Chiara Verdi Fiorini di Beta Immobiliare "
            "SPA."
        ),
        "entita": [
            {"start": 43, "end": 63, "tipo": "PERSONA"},  # Andrea Rossi Bianchi
            {"start": 95, "end": 115, "tipo": "PERSONA"},  # Chiara Verdi Fiorini
            {"start": 119, "end": 139, "tipo": "ORG"},  # Beta Immobiliare SPA
        ],
    },
    {
        "id": "frase_44",
        "categoria": "email_studio",
        "testo": (
            "Il collaudatore Giuseppe Colombo ci ha chiesto i disegni as-built entro "
            "il 12 maggio 2026; la richiesta è già stata girata a Cooperativa "
            "Muratori SNC."
        ),
        "entita": [
            {"start": 16, "end": 32, "tipo": "PERSONA"},  # Giuseppe Colombo
            {"start": 75, "end": 89, "tipo": "DATA"},  # 12 maggio 2026
            {"start": 125, "end": 149, "tipo": "ORG"},  # Cooperativa Muratori SNC
        ],
    },
    {
        "id": "frase_45",
        "categoria": "email_studio",
        "testo": (
            "Alla riunione di coordinamento erano presenti Federico Dell'Acqua, "
            "Silvia Della Vedova e il rappresentante di Fratelli Fumagalli & C. SAS."
        ),
        "entita": [
            {"start": 46, "end": 65, "tipo": "PERSONA"},  # Federico Dell'Acqua
            {"start": 67, "end": 86, "tipo": "PERSONA"},  # Silvia Della Vedova
            {"start": 110, "end": 137, "tipo": "ORG"},  # Fratelli Fumagalli & C. SAS
        ],
    },
    {
        "id": "frase_46",
        "categoria": "email_studio",
        "testo": (
            "Ti inoltro il messaggio di Antonio Lo Russo (a.lorusso@icos-srl.it), "
            "referente per le pratiche catastali depositate al Comune di Milano."
        ),
        "entita": [
            {"start": 27, "end": 43, "tipo": "PERSONA"},  # Antonio Lo Russo
            {"start": 45, "end": 66, "tipo": "EMAIL"},  # a.lorusso@icos-srl.it
            {"start": 119, "end": 135, "tipo": "ORG"},  # Comune di Milano
        ],
    },
    {
        "id": "frase_47",
        "categoria": "email_studio",
        "testo": (
            "La pratica edilizia seguita dall'arch. Elena Pace è stata protocollata "
            "dal Comune di Bergamo in data 04/09/2026."
        ),
        "entita": [
            {"start": 39, "end": 49, "tipo": "PERSONA"},  # Elena Pace
            {"start": 75, "end": 92, "tipo": "ORG"},  # Comune di Bergamo
            {"start": 101, "end": 111, "tipo": "DATA"},  # 04/09/2026
        ],
    },
    {
        "id": "frase_48",
        "categoria": "email_studio",
        "testo": (
            "Il perito Stefano Forti e la collega Giulia Belli hanno completato il "
            "rilievo termografico presso la sede di UNICREDIT SPA in Piazza Cordusio "
            "2, Milano."
        ),
        "entita": [
            {"start": 10, "end": 23, "tipo": "PERSONA"},  # Stefano Forti
            {"start": 37, "end": 49, "tipo": "PERSONA"},  # Giulia Belli
            {"start": 109, "end": 122, "tipo": "ORG"},  # UNICREDIT SPA
            {"start": 126, "end": 143, "tipo": "LUOGO"},  # Piazza Cordusio 2
            {"start": 145, "end": 151, "tipo": "LUOGO"},  # Milano
        ],
    },
    {
        "id": "frase_49",
        "categoria": "email_studio",
        "testo": (
            "Per la pratica di allaccio si prega di contattare il referente di ENEL "
            "ENERGIA, ing. Vincenzo Marino, al numero 06 88991234."
        ),
        "entita": [
            {"start": 66, "end": 78, "tipo": "ORG"},  # ENEL ENERGIA
            {"start": 85, "end": 100, "tipo": "PERSONA"},  # Vincenzo Marino
            {"start": 112, "end": 123, "tipo": "TELEFONO"},  # 06 88991234
        ],
    },
    {
        "id": "frase_50",
        "categoria": "email_studio",
        "testo": (
            "Il tecnico Roberto D'Agostino ha trasmesso alla Regione Lombardia la "
            "documentazione integrativa richiesta il 18 ottobre 2026."
        ),
        "entita": [
            {"start": 11, "end": 29, "tipo": "PERSONA"},  # Roberto D'Agostino
            {"start": 48, "end": 65, "tipo": "ORG"},  # Regione Lombardia
            {"start": 109, "end": 124, "tipo": "DATA"},  # 18 ottobre 2026
        ],
    },
    {
        "id": "frase_51",
        "categoria": "email_studio",
        "testo": (
            "Confermo che la dott.ssa Paola La Malfa parteciperà al tavolo tecnico "
            "con Agenzia delle Entrate previsto a Roma."
        ),
        "entita": [
            {"start": 25, "end": 39, "tipo": "PERSONA"},  # Paola La Malfa
            {"start": 74, "end": 95, "tipo": "ORG"},  # Agenzia delle Entrate
            {"start": 107, "end": 111, "tipo": "LUOGO"},  # Roma
        ],
    },
    {
        "id": "frase_52",
        "categoria": "email_studio",
        "testo": (
            "L'ing. Sandro Del Vecchio dello Studio Tecnico Associati coordinerà i "
            "rapporti con ASST Papa Giovanni XXIII per il cantiere ospedaliero."
        ),
        "entita": [
            {"start": 7, "end": 25, "tipo": "PERSONA"},  # Sandro Del Vecchio
            {"start": 32, "end": 56, "tipo": "ORG"},  # Studio Tecnico Associati
            {"start": 83, "end": 107, "tipo": "ORG"},  # ASST Papa Giovanni XXIII
        ],
    },
    {
        "id": "frase_53",
        "categoria": "contratto",
        "testo": (
            "Il sottoscritto MARIO ROSSI, nato a Roma il 01/01/1980, codice fiscale "
            "RSSMRA80A01H501U, dichiara di accettare integralmente le clausole che "
            "seguono."
        ),
        "entita": [
            {"start": 16, "end": 27, "tipo": "PERSONA"},  # MARIO ROSSI
            {"start": 36, "end": 40, "tipo": "LUOGO"},  # Roma
            {"start": 44, "end": 54, "tipo": "DATA"},  # 01/01/1980
            {"start": 71, "end": 87, "tipo": "CF"},  # RSSMRA80A01H501U
        ],
    },
    {
        "id": "frase_54",
        "categoria": "contratto",
        "testo": (
            "TRA la società ICOS SRL, con sede in Torino, E il sig. LUIGI DE LUCA, di "
            "seguito denominato Committente, si conviene quanto segue."
        ),
        "entita": [
            {"start": 15, "end": 23, "tipo": "ORG"},  # ICOS SRL
            {"start": 37, "end": 43, "tipo": "LUOGO"},  # Torino
            {"start": 55, "end": 68, "tipo": "PERSONA"},  # LUIGI DE LUCA
        ],
    },
    {
        "id": "frase_55",
        "categoria": "contratto",
        "testo": (
            "Il presente atto è sottoscritto da GIOVANNA DI MARCO, legale "
            "rappresentante di BETA IMMOBILIARE SPA, partita IVA 03456789019."
        ),
        "entita": [
            {"start": 35, "end": 52, "tipo": "PERSONA"},  # GIOVANNA DI MARCO
            {"start": 79, "end": 99, "tipo": "ORG"},  # BETA IMMOBILIARE SPA
            {"start": 113, "end": 124, "tipo": "PIVA"},  # 03456789019
        ],
    },
    {
        "id": "frase_56",
        "categoria": "contratto",
        "testo": (
            "Le lavorazioni saranno eseguite dall'impresa Cooperativa Muratori SNC "
            "sotto la direzione operativa del geom. Alberto Marino."
        ),
        "entita": [
            {"start": 45, "end": 69, "tipo": "ORG"},  # Cooperativa Muratori SNC
            {"start": 109, "end": 123, "tipo": "PERSONA"},  # Alberto Marino
        ],
    },
    {
        "id": "frase_57",
        "categoria": "contratto",
        "testo": (
            "Il corrispettivo sarà accreditato sull'IBAN IT05M0503412345000000067890 "
            "intestato a Fratelli Fumagalli & C. SAS entro sessanta giorni."
        ),
        "entita": [
            {"start": 44, "end": 71, "tipo": "IBAN"},  # IT05M0503412345000000067890
            {"start": 84, "end": 111, "tipo": "ORG"},  # Fratelli Fumagalli & C. SAS
        ],
    },
    {
        "id": "frase_58",
        "categoria": "contratto",
        "testo": (
            "Il collaudo statico è affidato all'ing. Chiara Del Monte, iscritta "
            "all'Ordine degli Ingegneri di Brescia al numero 3421."
        ),
        "entita": [
            {"start": 40, "end": 56, "tipo": "PERSONA"},  # Chiara Del Monte
            {"start": 71, "end": 104, "tipo": "ORG"},  # Ordine degli Ingegneri di Brescia
        ],
    },
    {
        "id": "frase_59",
        "categoria": "contratto",
        "testo": (
            "Il presente contratto è stipulato tra Poste Italiane SPA e la Croce "
            "Rossa Italiana per la fornitura di servizi logistici di emergenza."
        ),
        "entita": [
            {"start": 38, "end": 56, "tipo": "ORG"},  # Poste Italiane SPA
            {"start": 62, "end": 82, "tipo": "ORG"},  # Croce Rossa Italiana
        ],
    },
    {
        "id": "frase_60",
        "categoria": "contratto",
        "testo": (
            "Il responsabile unico del procedimento, arch. Nicola Bruno Esposito, è "
            "nominato ai sensi dell'art. 31 del D.Lgs. 50/2016."
        ),
        "entita": [
            {"start": 46, "end": 67, "tipo": "PERSONA"},  # Nicola Bruno Esposito
        ],
    },
    {
        "id": "frase_61",
        "categoria": "contratto",
        "testo": (
            "La garanzia definitiva è prestata in favore del Comune di Milano dal "
            "legale rappresentante Alessandro Ferrari Del Monte entro il 20 dicembre "
            "2026."
        ),
        "entita": [
            {"start": 48, "end": 64, "tipo": "ORG"},  # Comune di Milano
            {"start": 91, "end": 119, "tipo": "PERSONA"},  # Alessandro Ferrari Del Monte
            {"start": 129, "end": 145, "tipo": "DATA"},  # 20 dicembre 2026
        ],
    },
    {
        "id": "frase_62",
        "categoria": "contratto",
        "testo": (
            "Il subappalto è autorizzato limitatamente alle opere di scavo, come "
            "dichiarato dal sig. Emilio Colombo e dalla sig.ra Rita Rosa."
        ),
        "entita": [
            {"start": 88, "end": 102, "tipo": "PERSONA"},  # Emilio Colombo
            {"start": 118, "end": 127, "tipo": "PERSONA"},  # Rita Rosa
        ],
    },
    {
        "id": "frase_63",
        "categoria": "contratto",
        "testo": (
            "Ogni comunicazione relativa al presente atto sarà inviata a mezzo PEC "
            "all'indirizzo contratti@pec.icos-srl.it e, per conoscenza, a Beta "
            "Immobiliare SPA."
        ),
        "entita": [
            {"start": 84, "end": 109, "tipo": "EMAIL"},  # contratti@pec.icos-srl.it
            {"start": 131, "end": 151, "tipo": "ORG"},  # Beta Immobiliare SPA
        ],
    },
    {
        "id": "frase_64",
        "categoria": "contratto",
        "testo": (
            "Le parti eleggono domicilio presso lo studio dell'avv. Marco De Luca in "
            "Via Manzoni 12, 20121 Milano."
        ),
        "entita": [
            {"start": 55, "end": 68, "tipo": "PERSONA"},  # Marco De Luca
            {"start": 72, "end": 86, "tipo": "LUOGO"},  # Via Manzoni 12
            {"start": 88, "end": 93, "tipo": "CAP"},  # 20121
            {"start": 94, "end": 100, "tipo": "LUOGO"},  # Milano
        ],
    },
    {
        "id": "frase_65",
        "categoria": "cliente",
        "testo": (
            "Gentile sig.ra Anna Bianco, la informiamo che la pratica di rimborso è "
            "stata trasmessa ad Agenzia delle Entrate in data 03/03/2026."
        ),
        "entita": [
            {"start": 15, "end": 26, "tipo": "PERSONA"},  # Anna Bianco
            {"start": 90, "end": 111, "tipo": "ORG"},  # Agenzia delle Entrate
            {"start": 120, "end": 130, "tipo": "DATA"},  # 03/03/2026
        ],
    },
    {
        "id": "frase_66",
        "categoria": "cliente",
        "testo": (
            "Il suo referente commerciale è il dott. Matteo Di Marco, contattabile al "
            "340 5567891 oppure via e-mail a m.dimarco@betaimmobiliare.it."
        ),
        "entita": [
            {"start": 40, "end": 55, "tipo": "PERSONA"},  # Matteo Di Marco
            {"start": 73, "end": 84, "tipo": "TELEFONO"},  # 340 5567891
            {"start": 105, "end": 133, "tipo": "EMAIL"},  # m.dimarco@betaimmobiliare.it
        ],
    },
    {
        "id": "frase_67",
        "categoria": "cliente",
        "testo": (
            "La fornitura sarà consegnata da Poste Italiane SPA all'attenzione della "
            "sig.ra Laura Fiore presso Via Torino 8, 10121 Torino."
        ),
        "entita": [
            {"start": 32, "end": 50, "tipo": "ORG"},  # Poste Italiane SPA
            {"start": 79, "end": 90, "tipo": "PERSONA"},  # Laura Fiore
            {"start": 98, "end": 110, "tipo": "LUOGO"},  # Via Torino 8
            {"start": 112, "end": 117, "tipo": "CAP"},  # 10121
            {"start": 118, "end": 124, "tipo": "LUOGO"},  # Torino
        ],
    },
    {
        "id": "frase_68",
        "categoria": "cliente",
        "testo": (
            "Come da accordi con il sig. Salvatore Lo Russo, l'addebito sulla carta "
            "5370123456789008 è stato effettuato il 15 aprile 2026."
        ),
        "entita": [
            {"start": 28, "end": 46, "tipo": "PERSONA"},  # Salvatore Lo Russo
            {"start": 71, "end": 87, "tipo": "CARTA"},  # 5370123456789008
            {"start": 110, "end": 124, "tipo": "DATA"},  # 15 aprile 2026
        ],
    },
    {
        "id": "frase_69",
        "categoria": "cliente",
        "testo": (
            "Il nostro tecnico Davide Pace effettuerà il sopralluogo presso la sede "
            "di ENEL ENERGIA martedì 7 luglio."
        ),
        "entita": [
            {"start": 18, "end": 29, "tipo": "PERSONA"},  # Davide Pace
            {"start": 74, "end": 86, "tipo": "ORG"},  # ENEL ENERGIA
            {"start": 87, "end": 103, "tipo": "DATA"},  # martedì 7 luglio
        ],
    },
    {
        "id": "frase_70",
        "categoria": "cliente",
        "testo": (
            "La posizione intestata a GIUSEPPINA D'AGOSTINO, codice fiscale "
            "DGSGPP85A41F205X, è stata presa in carico dalla filiale di UNICREDIT "
            "SPA."
        ),
        "entita": [
            {"start": 25, "end": 46, "tipo": "PERSONA"},  # GIUSEPPINA D'AGOSTINO
            {"start": 63, "end": 79, "tipo": "CF"},  # DGSGPP85A41F205X
            {"start": 122, "end": 135, "tipo": "ORG"},  # UNICREDIT SPA
        ],
    },
    {
        "id": "frase_71",
        "categoria": "cliente",
        "testo": (
            "Vi confermiamo che la dott.ssa Valentina Belli seguirà il vostro dossier "
            "per conto di ICOS SRL fino alla chiusura della commessa."
        ),
        "entita": [
            {"start": 31, "end": 46, "tipo": "PERSONA"},  # Valentina Belli
            {"start": 86, "end": 94, "tipo": "ORG"},  # ICOS SRL
        ],
    },
    {
        "id": "frase_72",
        "categoria": "cliente",
        "testo": (
            "Il reclamo del sig. Gianni Forti relativo alla fornitura è stato "
            "inoltrato a Metalgraf SAS e, per competenza, alla Regione Lombardia."
        ),
        "entita": [
            {"start": 20, "end": 32, "tipo": "PERSONA"},  # Gianni Forti
            {"start": 77, "end": 90, "tipo": "ORG"},  # Metalgraf SAS
            {"start": 115, "end": 132, "tipo": "ORG"},  # Regione Lombardia
        ],
    },
    {
        "id": "frase_73",
        "categoria": "cliente",
        "testo": (
            "L'appuntamento con la signora Carla Della Vedova è confermato per il 22 "
            "novembre 2026 presso lo sportello di Verona."
        ),
        "entita": [
            {"start": 30, "end": 48, "tipo": "PERSONA"},  # Carla Della Vedova
            {"start": 69, "end": 85, "tipo": "DATA"},  # 22 novembre 2026
            {"start": 109, "end": 115, "tipo": "LUOGO"},  # Verona
        ],
    },
    {
        "id": "frase_74",
        "categoria": "cliente",
        "testo": (
            "Il preventivo richiesto da Cooperativa Muratori SNC è stato validato dal "
            "geom. Pietro Dell'Acqua e trasmesso via PEC questa mattina."
        ),
        "entita": [
            {"start": 27, "end": 51, "tipo": "ORG"},  # Cooperativa Muratori SNC
            {"start": 79, "end": 96, "tipo": "PERSONA"},  # Pietro Dell'Acqua
        ],
    },
    {
        "id": "frase_75",
        "categoria": "cliente",
        "testo": (
            "La segnalazione è stata protocollata da ASST Papa Giovanni XXIII e "
            "girata al referente tecnico, ing. Francesca Colombo."
        ),
        "entita": [
            {"start": 40, "end": 64, "tipo": "ORG"},  # ASST Papa Giovanni XXIII
            {"start": 101, "end": 118, "tipo": "PERSONA"},  # Francesca Colombo
        ],
    },
    {
        "id": "frase_76",
        "categoria": "cliente",
        "testo": (
            "Restiamo in attesa del riscontro del sig. LUCA BIANCO, amministratore "
            "unico di FRATELLI FUMAGALLI & C. SAS, partita IVA 07711223342."
        ),
        "entita": [
            {"start": 42, "end": 53, "tipo": "PERSONA"},  # LUCA BIANCO
            {"start": 79, "end": 106, "tipo": "ORG"},  # FRATELLI FUMAGALLI & C. SAS
            {"start": 120, "end": 131, "tipo": "PIVA"},  # 07711223342
        ],
    },
]
