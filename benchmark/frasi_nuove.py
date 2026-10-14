# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Venti frasi di dominio diverso, scritte per misurare senza barare.

Non derivano dal corpus su cui il motore è stato messo a punto: se le
regole fossero cucite addosso ai casi di sviluppo, è qui che si vede.
Domini: email commerciali, verbali di riunione, comunicazioni
condominiali.
"""

FRASI_NUOVE = [
    # -- EMAIL COMMERCIALI (7) --
    {
        "id": "nuova_1",
        "dominio": "email_commerciale",
        "testo": (
            "Gentile Dott. Luigi Bianchi, in risposta alla sua richiesta del "
            "15/03/2026, le confermiamo che la fattura n. 2026-0041 di € 12.450,00 "
            "sarà saldata entro il 30/04/2026 tramite bonifico bancario sul conto "
            "IT60X0542811101000012345678. Per chiarimenti contatti l'ufficio "
            "contabilità all'indirizzo contabilita@edilservice.it o al numero "
            "02 48712345. Distinti saluti, Amministrazione Edilservice S.p.A."
        ),
        "entita": [
            {"start": 14, "end": 27, "tipo": "PERSON"},        # Luigi Bianchi
            {"start": 64, "end": 74, "tipo": "DATE_TIME"},     # 15/03/2026
            {"start": 109, "end": 118, "tipo": "NUMERO_FATTURA"}, # 2026-0041
            {"start": 124, "end": 133, "tipo": "IT_IMPORTO"},   # 12.450,00
            {"start": 156, "end": 166, "tipo": "DATE_TIME"},    # 30/04/2026
            {"start": 203, "end": 210, "tipo": "IT_IBAN"},      # IT60...
            {"start": 293, "end": 319, "tipo": "EMAIL_ADDRESS"}, # contabilita@edilservice.it
            {"start": 332, "end": 343, "tipo": "PHONE_NUMBER"},  # 02 48712345
            {"start": 378, "end": 396, "tipo": "ORGANIZATION"},  # Edilservice S.p.A.
        ],
    },
    {
        "id": "nuova_2",
        "dominio": "email_commerciale",
        "testo": (
            "Buongiorno, con la presente trasmettiamo il DDT n. 4789 del "
            "22/02/2026 relativo alla fornitura di n. 50 PC portatili modello "
            "ThinkPad X1 Carbon ordinati dal Sig. Marco Verdi (CF: "
            "VRDMRC85M01H501Z, P.IVA: 01234560157). Merce consegnata presso "
            "la sede di Via Cavour 123, 20121 Milano. Il trasportatore "
            "è stato Bartolini (spedizione n. 1Z9R8A4B6C7D8E9F)."
        ),
        "entita": [
            {"start": 162, "end": 173, "tipo": "PERSON"},       # Marco Verdi
            {"start": 179, "end": 195, "tipo": "IT_CODICE_FISCALE"}, # VRDMRC85M01H501Z
            {"start": 204, "end": 215, "tipo": "IT_PARTITA_IVA"}, # 01234560157
            {"start": 253, "end": 267, "tipo": "LOCATION"},     # Via Cavour 123
            {"start": 269, "end": 274, "tipo": "IT_CAP"},       # 20121
            {"start": 275, "end": 281, "tipo": "LOCATION"},     # Milano
            {"start": 308, "end": 317, "tipo": "ORGANIZATION"}, # Bartolini
            {"start": 333, "end": 349, "tipo": "NUMERO_SPEDIZIONE"}, # 1Z9R8A4B6C7D8E9F
        ],
    },
    {
        "id": "nuova_3",
        "dominio": "email_commerciale",
        "testo": (
            "Alla cortese attenzione della Dott.ssa Anna Neri, le scriviamo "
            "per sollecitare il pagamento della fattura n. 2026-0087 scaduta "
            "il 10/01/2026 per un importo di € 3.780,00. In caso di mancato "
            "pagamento entro 15 giorni, provvederemo all'invio dell'estratto "
            "conto alla sua email personale a.neri@consultingpartners.com. "
            "Cordiali saluti, Ufficio Crediti Recupero S.r.l. - Via Nazionale "
            "55, 50123 Firenze - tel. 055 2468135."
        ),
        "entita": [
            {"start": 39, "end": 48, "tipo": "PERSON"},         # Anna Neri
            {"start": 109, "end": 118, "tipo": "NUMERO_FATTURA"}, # 2026-0087
            {"start": 130, "end": 140, "tipo": "DATE_TIME"},    # 10/01/2026
            {"start": 161, "end": 169, "tipo": "IT_IMPORTO"},   # 3.780,00
            {"start": 285, "end": 314, "tipo": "EMAIL_ADDRESS"}, # a.neri@consultingpartners.com
            {"start": 349, "end": 364, "tipo": "ORGANIZATION"}, # Recupero S.r.l.
            {"start": 367, "end": 383, "tipo": "LOCATION"},     # Via Nazionale 55
            {"start": 385, "end": 390, "tipo": "IT_CAP"},       # 50123
            {"start": 391, "end": 398, "tipo": "LOCATION"},     # Firenze
            {"start": 406, "end": 417, "tipo": "PHONE_NUMBER"}, # 055 2468135
        ],
    },
    {
        "id": "nuova_4",
        "dominio": "email_commerciale",
        "testo": (
            "Conferma d'ordine n. ORD-2026-3342 del 05/04/2026 per il "
            "Cliente: Beta Impianti S.n.c. di Rossi e Gialli, Via Dante "
            "Alighieri 78, 40121 Bologna. Articoli ordinati: n. 3 pompe "
            "idrauliche Mod. HP-300, n. 10 valvole a sfera DN50. Totale "
            "€ 8.920,00 IVA inclusa. Pagamento: bonifico su IBAN "
            "IT40P1234512345123456789012. Spedizione prevista per il "
            "12/04/2026. Referente: Ing. Giuseppe Gialli, tel. "
            "+39 335 7890123."
        ),
        "entita": [
            {"start": 66, "end": 86, "tipo": "ORGANIZATION"},   # Beta Impianti S.n.c.
            {"start": 90, "end": 104, "tipo": "PERSON"},        # Rossi e Gialli
            {"start": 106, "end": 128, "tipo": "LOCATION"},     # Via Dante Alighieri 78
            {"start": 130, "end": 135, "tipo": "IT_CAP"},       # 40121
            {"start": 136, "end": 143, "tipo": "LOCATION"},     # Bologna
            {"start": 236, "end": 244, "tipo": "IT_IMPORTO"},   # 8.920,00
            {"start": 286, "end": 295, "tipo": "IT_IBAN"},      # IT40P1...
            {"start": 342, "end": 352, "tipo": "DATE_TIME"},    # 12/04/2026
            {"start": 370, "end": 385, "tipo": "PERSON"},       # Giuseppe Gialli
            {"start": 392, "end": 407, "tipo": "PHONE_NUMBER"}, # +39 335 7890123
        ],
    },
    {
        "id": "nuova_5",
        "dominio": "email_commerciale",
        "testo": (
            "Rinnovo contratto di assistenza annuale per il Dott. Francesco "
            "Verdi, CF: VRDFRC70T15G273Q, residente in Viale dei Giusti 33, "
            "80125 Napoli. Il nuovo contratto decorre dal 01/07/2026 con "
            "scadenza 30/06/2027. Canone annuo € 1.250,00. Modalità di "
            "pagamento: RID bancario su IBAN IT04M1234512345123456012345. "
            "Per disdetta scrivere a assistenza@assicurazionigenerali.com "
            "entro 30 giorni dalla scadenza."
        ),
        "entita": [
            {"start": 53, "end": 68, "tipo": "PERSON"},         # Francesco Verdi
            {"start": 74, "end": 90, "tipo": "IT_CODICE_FISCALE"}, # VRDFRC70T15G273Q
            {"start": 105, "end": 124, "tipo": "LOCATION"},      # Viale dei Giusti 33
            {"start": 126, "end": 131, "tipo": "IT_CAP"},       # 80125
            {"start": 132, "end": 138, "tipo": "LOCATION"},     # Napoli
            {"start": 171, "end": 181, "tipo": "DATE_TIME"},    # 01/07/2026
            {"start": 195, "end": 205, "tipo": "DATE_TIME"},    # 30/06/2027
            {"start": 222, "end": 230, "tipo": "IT_IMPORTO"},   # 1.250,00
            {"start": 276, "end": 285, "tipo": "IT_IBAN"},      # IT04M1...
            {"start": 329, "end": 343, "tipo": "EMAIL_ADDRESS"}, # assistenza@...
        ],
    },
    {
        "id": "nuova_6",
        "dominio": "email_commerciale",
        "testo": (
            "Si comunica che la merce ordinata dalla Ditta Tecnologie "
            "Avanzate S.p.A., P.IVA 02123450158, è stata spedita in data "
            "08/05/2026 con corriere GLS (tracking: GLSIT987654321). "
            "Destinatario: Sig. Tommaso Romano, Via Merulana 220, 00185 "
            "Roma. Peso complessivo kg 145. Il pagamento di € 5.670,00 "
            "è già stato registrato il 06/05/2026 (fatt. n. 2026-0112)."
        ),
        "entita": [
            {"start": 46, "end": 72, "tipo": "ORGANIZATION"},   # Tecnologie Avanzate S.p.A.
            {"start": 80, "end": 91, "tipo": "IT_PARTITA_IVA"}, # 02123450158
            {"start": 117, "end": 127, "tipo": "DATE_TIME"},    # 08/05/2026
            {"start": 141, "end": 144, "tipo": "ORGANIZATION"}, # GLS
            {"start": 156, "end": 170, "tipo": "NUMERO_SPEDIZIONE"}, # GLSIT987654321
            {"start": 192, "end": 206, "tipo": "PERSON"},       # Tommaso Romano
            {"start": 208, "end": 224, "tipo": "LOCATION"},     # Via Merulana 220
            {"start": 226, "end": 231, "tipo": "IT_CAP"},       # 00185
            {"start": 200, "end": 204, "tipo": "LOCATION"},     # Roma
            {"start": 281, "end": 289, "tipo": "IT_IMPORTO"},   # 5.670,00
            {"start": 316, "end": 326, "tipo": "DATE_TIME"},    # 06/05/2026
        ],
    },
    {
        "id": "nuova_7",
        "dominio": "email_commerciale",
        "testo": (
            "Gentile Prof. Alessandro Conti, in qualità di Presidente del "
            "Consiglio di Amministrazione di Holostudio S.p.A., la invitiamo "
            "all'Assemblea Ordinaria dei Soci del 20/06/2026 presso la sede "
            "di Corso Italia 17, 20122 Milano. All'ordine del giorno: "
            "approvazione bilancio 2025, nomina nuovo Collegio Sindacale, "
            "conferimento incarico revisione alla Dott.ssa Maria Fumagalli "
            "(CF: FMGMRN75H41F205W)."
        ),
        "entita": [
            {"start": 14, "end": 30, "tipo": "PERSON"},         # Alessandro Conti
            {"start": 93, "end": 110, "tipo": "ORGANIZATION"}, # Holostudio S.p.A.
            {"start": 162, "end": 172, "tipo": "DATE_TIME"},    # 20/06/2026
            {"start": 191, "end": 206, "tipo": "LOCATION"},     # Corso Italia 17
            {"start": 208, "end": 213, "tipo": "IT_CAP"},       # 20122
            {"start": 214, "end": 220, "tipo": "LOCATION"},     # Milano
            {"start": 352, "end": 367, "tipo": "PERSON"},       # Maria Fumagalli
            {"start": 373, "end": 389, "tipo": "IT_CODICE_FISCALE"}, # FMGMRN75H41F205W
        ],
    },
    # -- VERBALI DI RIUNIONE (6) --
    {
        "id": "nuova_8",
        "dominio": "verbale_riunione",
        "testo": (
            "Verbale della riunione del Comitato Tecnico del 12/02/2026. "
            "Presenti: Ing. Carlo Ferrara (Resp. Produzione), Dott. Luca "
            "Bianco (CFO), Sig.ra Elena Russo (Resp. HR). Ordine del giorno: "
            "1) Aggiornamento progetto NEPTUNE; 2) Budget 2026; 3) Assunzioni "
            "previste. Decisioni: approvato budget di € 250.000 per la nuova "
            "linea di produzione da realizzare presso lo stabilimento di Via "
            "dell'Industria 88, 30020 Noventa di Piave (VE). Prossima "
            "riunione: 10/03/2026 ore 14:30."
        ),
        "entita": [
            {"start": 48, "end": 58, "tipo": "DATE_TIME"},      # 12/02/2026
            {"start": 75, "end": 88, "tipo": "PERSON"},         # Carlo Ferrara
            {"start": 115, "end": 126, "tipo": "PERSON"},       # Luca Bianco
            {"start": 141, "end": 152, "tipo": "PERSON"},       # Elena Russo
            {"start": 292, "end": 299, "tipo": "IT_IMPORTO"},   # 250.000
            {"start": 373, "end": 394, "tipo": "LOCATION"},     # Via dell'Industria 88
            {"start": 396, "end": 401, "tipo": "IT_CAP"},       # 30020
            {"start": 402, "end": 423, "tipo": "LOCATION"},     # Noventa di Piave (VE)
            {"start": 444, "end": 454, "tipo": "DATE_TIME"},    # 10/03/2026
        ],
    },
    {
        "id": "nuova_9",
        "dominio": "verbale_riunione",
        "testo": (
            "Riunione del Team Sviluppo del 28/04/2026 convocata dal "
            "responsabile Arch. Marco Sala. Partecipanti: Dott. Giuseppe "
            "Trevisan (Backend), Ing. Sofia Colombo (Frontend), Dott.ssa "
            "Martina Ferrari (UX). Temi trattati: rilasci previsti per "
            "la versione 3.2 (15/05/2026), criticità sul modulo di "
            "pagamento (contattare assistenza@bancopassione.it), decisione "
            "di adottare AWS per il deployment. Prossimo sprint review: "
            "05/05/2026. Redatto da: Ing. Marco Sala."
        ),
        "entita": [
            {"start": 75, "end": 85, "tipo": "PERSON"},         # Marco Sala
            {"start": 107, "end": 124, "tipo": "PERSON"},        # Giuseppe Trevisan
            {"start": 141, "end": 154, "tipo": "PERSON"},       # Sofia Colombo
            {"start": 176, "end": 191, "tipo": "PERSON"},       # Martina Ferrari
            {"start": 251, "end": 261, "tipo": "DATE_TIME"},    # 15/05/2026
            {"start": 310, "end": 324, "tipo": "EMAIL_ADDRESS"}, # assistenza@...
            {"start": 362, "end": 365, "tipo": "ORGANIZATION"}, # AWS
            {"start": 409, "end": 419, "tipo": "DATE_TIME"},    # 05/05/2026
        ],
    },
    {
        "id": "nuova_10",
        "dominio": "verbale_riunione",
        "testo": (
            "Consiglio di Amministrazione del 03/03/2026. Presenti: "
            "Avv. Giovanni Nardi (Presidente), Dott. Alberto Sassi "
            "(Amministratore Delegato), Prof.ssa Laura Moretti (Consigliere), "
            "Sig. Roberto Testa (Consigliere). All'unanimità è stato "
            "deliberato l'acquisto del ramo d'azienda di Logicomp S.r.l. "
            "(P.IVA 03456720156) per un corrispettivo di € 1.450.000. "
            "L'operazione sarà finanziata tramite mutuo con Banca Sella "
            "di € 1.200.000. Segretario verbalizzante: Dott. Paolo Gori."
        ),
        "entita": [
            {"start": 33, "end": 43, "tipo": "DATE_TIME"},      # 03/03/2026
            {"start": 60, "end": 74, "tipo": "PERSON"},         # Giovanni Nardi
            {"start": 95, "end": 108, "tipo": "PERSON"},        # Alberto Sassi
            {"start": 145, "end": 158, "tipo": "PERSON"},       # Laura Moretti
            {"start": 179, "end": 192, "tipo": "PERSON"},       # Roberto Testa
            {"start": 274, "end": 289, "tipo": "ORGANIZATION"}, # Logicomp S.r.l.
            {"start": 297, "end": 308, "tipo": "IT_PARTITA_IVA"}, # 03456720156
            {"start": 336, "end": 345, "tipo": "IT_IMPORTO"},   # 1.450.000
            {"start": 394, "end": 405, "tipo": "ORGANIZATION"}, # Banca Sella
            {"start": 411, "end": 420, "tipo": "IT_IMPORTO"},   # 1.200.000
            {"start": 454, "end": 464, "tipo": "PERSON"},       # Paolo Gori
        ],
    },
    {
        "id": "nuova_11",
        "dominio": "verbale_riunione",
        "testo": (
            "Riunione del Gruppo Qualità del 18/01/2026 ore 10:00. "
            "Partecipanti: Dott.ssa Giulia Riva (QM), Ing. Davide "
            "Monti (Produzione), Sig. Antonio Villa (Logistica). "
            "Risultati audit interno ISO 9001:2025. Rilevate 3 non "
            "conformità (NC-2026-001, NC-2026-002, NC-2026-003) "
            "presso il reparto di Via Leonardo Da Vinci 5, 20090 "
            "Settimo Milanese (MI). Azioni correttive entro il "
            "15/02/2026. Prossimo audit: 20/03/2026."
        ),
        "entita": [
            {"start": 32, "end": 42, "tipo": "DATE_TIME"},      # 18/01/2026
            {"start": 77, "end": 88, "tipo": "PERSON"},         # Giulia Riva
            {"start": 100, "end": 112, "tipo": "PERSON"},       # Davide Monti
            {"start": 132, "end": 145, "tipo": "PERSON"},       # Antonio Villa
            {"start": 183, "end": 191, "tipo": "ORGANIZATION"}, # ISO 9001
            {"start": 285, "end": 308, "tipo": "LOCATION"},     # Via Leonardo Da Vinci 5
            {"start": 310, "end": 315, "tipo": "IT_CAP"},       # 20090
            {"start": 316, "end": 337, "tipo": "LOCATION"},     # Settimo Milanese (MI)
            {"start": 366, "end": 376, "tipo": "DATE_TIME"},    # 15/02/2026
            {"start": 394, "end": 404, "tipo": "DATE_TIME"},    # 20/03/2026
        ],
    },
    {
        "id": "nuova_12",
        "dominio": "verbale_riunione",
        "testo": (
            "Comitato Investimenti del 08/02/2026. Hanno partecipato: "
            "Avv. Stefano Galli, Dott.ssa Chiara Neri (Direttore "
            "Finanziario), Prof. Fabio Rizzo, Sig. Luca Sala. "
            "Analizzato il prospetto della proposta di acquisto del "
            "fondo immobiliare 'Residenze Venete' (€ 3.200.000) "
            "localizzato in Viale della Repubblica 45, 35131 Padova. "
            "Cofinanziamento richiesto a Intesa Sanpaolo. Decisione "
            "rinviata al 22/02/2026 per approfondimenti fiscali."
        ),
        "entita": [
            {"start": 26, "end": 36, "tipo": "DATE_TIME"},      # 08/02/2026
            {"start": 62, "end": 75, "tipo": "PERSON"},         # Stefano Galli
            {"start": 86, "end": 97, "tipo": "PERSON"},        # Chiara Neri
            {"start": 129, "end": 140, "tipo": "PERSON"},       # Fabio Rizzo
            {"start": 147, "end": 156, "tipo": "PERSON"},       # Luca Sala
            {"start": 253, "end": 262, "tipo": "IT_IMPORTO"},   # 3.200.000
            {"start": 279, "end": 304, "tipo": "LOCATION"},     # Viale della Repubblica 45
            {"start": 306, "end": 311, "tipo": "IT_CAP"},       # 35131
            {"start": 312, "end": 318, "tipo": "LOCATION"},     # Padova
            {"start": 348, "end": 363, "tipo": "ORGANIZATION"}, # Intesa Sanpaolo
            {"start": 387, "end": 397, "tipo": "DATE_TIME"},    # 22/02/2026
        ],
    },
    {
        "id": "nuova_13",
        "dominio": "verbale_riunione",
        "testo": (
            "Incontro del personale del reparto IT del 25/11/2026. "
            "Tema: transizione a nuovo CRM. Presenti: Ing. Tommaso "
            "Ferrari (CIO), Dott.ssa Alice Monti (IT), Sig. Enrico "
            "Bianchi (Sviluppo), Sig.ra Sara Fontana (Helpdesk). "
            "Il passaggio avverrà il 01/12/2026. Le credenziali di "
            "accesso saranno inviate via email istituzionale "
            "(@aziendagroup.com). Il fornitore Zucchetti S.p.A. ha "
            "garantito assistenza h24. Firma contratto: 30/11/2026."
        ),
        "entita": [
            {"start": 42, "end": 52, "tipo": "DATE_TIME"},      # 25/11/2026
            {"start": 100, "end": 115, "tipo": "PERSON"},        # Tommaso Ferrari
            {"start": 132, "end": 143, "tipo": "PERSON"},       # Alice Monti
            {"start": 155, "end": 169, "tipo": "PERSON"},       # Enrico Bianchi
            {"start": 189, "end": 201, "tipo": "PERSON"},       # Sara Fontana
            {"start": 238, "end": 248, "tipo": "DATE_TIME"},    # 01/12/2026
            {"start": 350, "end": 366, "tipo": "ORGANIZATION"}, # Zucchetti S.p.A.
            {"start": 413, "end": 423, "tipo": "DATE_TIME"},    # 30/11/2026
        ],
    },
    # -- COMUNICAZIONI CONDOMINIALI (7) --
    {
        "id": "nuova_14",
        "dominio": "condominio",
        "testo": (
            "CONVOCAZIONE ASSEMBLEA ORDINARIA. Il Condominio di Via "
            "Monte Bianco 12, 20159 Milano è convocato in prima "
            "convocazione il 14/06/2026 alle ore 08:00 e in seconda "
            "il 16/06/2026 alle ore 18:30 presso il Bar Centrale in "
            "Piazza della Repubblica 3. All'ordine del giorno: "
            "approvazione consuntivo 2025 (€ 52.340,00), ripartizione "
            "spese straordinarie per rifacimento facciata (€ 128.000,00, "
            "quota media per unità € 4.266,00), nomina nuovo "
            "amministratore. L'Amministratore Dott. Oscar Bello."
        ),
        "entita": [
            {"start": 51, "end": 70, "tipo": "LOCATION"},       # Via Monte Bianco 12
            {"start": 72, "end": 77, "tipo": "IT_CAP"},         # 20159
            {"start": 78, "end": 84, "tipo": "LOCATION"},       # Milano
            {"start": 122, "end": 132, "tipo": "DATE_TIME"},    # 14/06/2026
            {"start": 164, "end": 174, "tipo": "DATE_TIME"},    # 16/06/2026
            {"start": 216, "end": 241, "tipo": "LOCATION"},     # Piazza della Repubblica 3
            {"start": 298, "end": 307, "tipo": "IT_IMPORTO"},   # 52.340,00
            {"start": 371, "end": 381, "tipo": "IT_IMPORTO"},   # 128.000,00
            {"start": 407, "end": 415, "tipo": "IT_IMPORTO"},   # 4.266,00
            {"start": 470, "end": 481, "tipo": "PERSON"},       # Oscar Bello
        ],
    },
    {
        "id": "nuova_15",
        "dominio": "condominio",
        "testo": (
            "AVVISO AI CONDOMINI. L'impresa Edilnova S.r.l. (P.IVA "
            "04123450154) inizierà i lavori di rifacimento del tetto "
            "a partire dal 05/09/2026. L'area di cantiere sarà "
            "delimitata in Via Roma 23 e Via Trento 12. I lavori "
            "dureranno circa 45 giorni. Per urgenze contattare il "
            "direttore lavori Ing. Paolo Verdi al numero "
            "+39 333 1234567 o via email direttore@edilnovasrl.com. "
            "I millesimi approvati sono visibili presso lo studio "
            "dell'amministratore in Via Manzoni 5, 20123 Milano."
        ),
        "entita": [
            {"start": 31, "end": 46, "tipo": "ORGANIZATION"},   # Edilnova S.r.l.
            {"start": 54, "end": 65, "tipo": "IT_PARTITA_IVA"}, # 04123450154
            {"start": 124, "end": 134, "tipo": "DATE_TIME"},    # 05/09/2026
            {"start": 174, "end": 185, "tipo": "LOCATION"},     # Via Roma 23
            {"start": 188, "end": 201, "tipo": "LOCATION"},     # Via Trento 12
            {"start": 287, "end": 298, "tipo": "PERSON"},       # Paolo Verdi
            {"start": 309, "end": 324, "tipo": "PHONE_NUMBER"}, # +39 333 1234567
            {"start": 337, "end": 362, "tipo": "EMAIL_ADDRESS"}, # direttore@edilnovasrl.com
            {"start": 440, "end": 453, "tipo": "LOCATION"},     # Via Manzoni 5
            {"start": 455, "end": 460, "tipo": "IT_CAP"},       # 20123
            {"start": 461, "end": 467, "tipo": "LOCATION"},     # Milano
        ],
    },
    {
        "id": "nuova_16",
        "dominio": "condominio",
        "testo": (
            "RENDICONTO STRAORDINARIO 2026. Cari condomini, come "
            "comunicato nell'assemblea del 20/03/2026, si rende "
            "necessario un conguaglio di € 180,00 per unità per "
            "far fronte all'aumento delle tariffe Acea per la "
            "fornitura di gas metano. Il saldo dovrà essere "
            "versato entro il 15/05/2026 tramite bonifico su IBAN "
            "IT92Z0123456789012345678901 intestato al Condominio "
            "di Via Fiume 8, 00198 Roma (codice fiscale condominio: "
            "80012330584). In caso di ritardo applicheremo interessi "
            "di mora al tasso annuo del 5,50%."
        ),
        "entita": [
            {"start": 82, "end": 92, "tipo": "DATE_TIME"},      # 20/03/2026
            {"start": 133, "end": 139, "tipo": "IT_IMPORTO"},   # 180,00
            {"start": 131, "end": 139, "tipo": "IT_IMPORTO"},   # € 180,00
            {"start": 267, "end": 277, "tipo": "DATE_TIME"},    # 15/05/2026
            {"start": 303, "end": 311, "tipo": "IT_IBAN"},      # IT92Z...
            {"start": 358, "end": 369, "tipo": "LOCATION"},     # Via Fiume 8
            {"start": 371, "end": 376, "tipo": "IT_CAP"},       # 00198
            {"start": 377, "end": 381, "tipo": "LOCATION"},     # Roma
            {"start": 410, "end": 421, "tipo": "IT_CODICE_FISCALE"}, # 80012330584
        ],
    },
    {
        "id": "nuova_17",
        "dominio": "condominio",
        "testo": (
            "SOLECITO PAGAMENTO. Il Sig. Mauro Gialli, proprietario "
            "dell'appartamento in Via Garibaldi 45, scala B, int. 8, "
            "20154 Milano, risulta moroso per l'importo di € 3.890,00 "
            "relativo alle quote condominiali dei mesi di ottobre, "
            "novembre e dicembre 2025. Si invita al pagamento entro "
            "e non oltre il 10/02/2026 tramite bonifico su IBAN "
            "IT40P1234512345678901234567. In caso di ulteriore "
            "inadempimento si procederà al pignoramento presso il "
            "Tribunale Ordinario di Milano."
        ),
        "entita": [
            {"start": 28, "end": 40, "tipo": "PERSON"},         # Mauro Gialli
            {"start": 76, "end": 92, "tipo": "LOCATION"},       # Via Garibaldi 45
            {"start": 111, "end": 116, "tipo": "IT_CAP"},       # 20154
            {"start": 117, "end": 123, "tipo": "LOCATION"},     # Milano
            {"start": 159, "end": 167, "tipo": "IT_IMPORTO"},   # 3.890,00
            {"start": 292, "end": 302, "tipo": "DATE_TIME"},    # 10/02/2026
            {"start": 328, "end": 337, "tipo": "IT_IBAN"},      # IT40P1...
        ],
    },
    {
        "id": "nuova_18",
        "dominio": "condominio",
        "testo": (
            "COMUNICAZIONE SINDACO. Il Condominio 'Residenza "
            "Sempione' di Corso Sempione 78, 20145 Milano, è "
            "convocato per l'assemblea straordinaria del "
            "08/07/2026 alle ore 21:00. Tema: installazione "
            "impianto fotovoltaico condominiale del costo di "
            "€ 45.000,00 (di cui € 23.000,00 coperti da "
            "detrazione fiscale 50%). L'installatore EnergyGreen "
            "S.p.A. (P.IVA 05123450153) seguirà i lavori. Per "
            "ogni chiarimento rivolgersi all'amministratore "
            "Rag. Davide Forte (cell. +39 348 9876543)."
        ),
        "entita": [
            {"start": 61, "end": 78, "tipo": "LOCATION"},       # Corso Sempione 78
            {"start": 80, "end": 85, "tipo": "IT_CAP"},         # 20145
            {"start": 86, "end": 92, "tipo": "LOCATION"},       # Milano
            {"start": 140, "end": 150, "tipo": "DATE_TIME"},    # 08/07/2026
            {"start": 237, "end": 246, "tipo": "IT_IMPORTO"},   # 45.000,00
            {"start": 257, "end": 266, "tipo": "IT_IMPORTO"},   # 23.000,00
            {"start": 318, "end": 336, "tipo": "ORGANIZATION"}, # EnergyGreen S.p.A.
            {"start": 344, "end": 355, "tipo": "IT_PARTITA_IVA"}, # 05123450153
            {"start": 431, "end": 443, "tipo": "PERSON"},       # Davide Forte
            {"start": 451, "end": 466, "tipo": "PHONE_NUMBER"}, # +39 348 9876543
        ],
    },
    {
        "id": "nuova_19",
        "dominio": "condominio",
        "testo": (
            "REVISIONE TABELLE MILLESIMALI. Si informano i "
            "condomini di Via Dante 33, 37121 Verona, che lo studio "
            "tecnico dell'Ing. Riccardo Marchetti ha completato la "
            "revisione delle tabelle millesimali. Il nuovo "
            "prospetto è disponibile presso lo studio in Corso "
            "Cavour 10, 37122 Verona, previo appuntamento "
            "(tel. 045 8123456). Le nuove tabelle saranno "
            "approvate nell'assemblea del 15/12/2026. Eventuali "
            "contestazioni vanno inviate a PEC "
            "amministrazione@pec-condominiverona.it entro 30 "
            "giorni dalla pubblicazione."
        ),
        "entita": [
            {"start": 59, "end": 71, "tipo": "LOCATION"},       # Via Dante 33
            {"start": 73, "end": 78, "tipo": "IT_CAP"},         # 37121
            {"start": 79, "end": 85, "tipo": "LOCATION"},       # Verona
            {"start": 119, "end": 137, "tipo": "PERSON"},       # Riccardo Marchetti
            {"start": 245, "end": 260, "tipo": "LOCATION"},     # Corso Cavour 10
            {"start": 262, "end": 267, "tipo": "IT_CAP"},       # 37122
            {"start": 79, "end": 85, "tipo": "LOCATION"},     # Verona
            {"start": 302, "end": 313, "tipo": "PHONE_NUMBER"}, # 045 8123456
            {"start": 370, "end": 380, "tipo": "DATE_TIME"},    # 15/12/2026
            {"start": 426, "end": 445, "tipo": "EMAIL_ADDRESS"}, # amministrazione@...
        ],
    },
    {
        "id": "nuova_20",
        "dominio": "condominio",
        "testo": (
            "SOSTITUZIONE CALDAIA CENTRALIZZATA. Il Condominio di "
            "Via Piacenza 7, 20900 Monza (MB) comunica che la ditta "
            "TermoService 2000 S.n.c. (P.IVA 06543210158) è stata "
            "incaricata della sostituzione della caldaia centrale "
            "per un costo complessivo di € 78.500,00. I lavori "
            "inizieranno il 07/11/2026. Il pagamento sarà rateizzato "
            "in 6 rate mensili da € 13.083,33 con addebito su conto "
            "corrente intestato al condominio (IBAN "
            "IT23P1234567890123456789012). Per informazioni "
            "rivolgersi all'amministratore Sig.ra Rosa Gialli "
            "(tel. 039 2345678)."
        ),
        "entita": [
            {"start": 53, "end": 67, "tipo": "LOCATION"},       # Via Piacenza 7
            {"start": 69, "end": 74, "tipo": "IT_CAP"},         # 20900
            {"start": 75, "end": 85, "tipo": "LOCATION"},       # Monza (MB)
            {"start": 108, "end": 132, "tipo": "ORGANIZATION"}, # TermoService 2000 S.n.c.
            {"start": 140, "end": 151, "tipo": "IT_PARTITA_IVA"}, # 06543210158
            {"start": 244, "end": 253, "tipo": "IT_IMPORTO"},   # 78.500,00
            {"start": 279, "end": 289, "tipo": "DATE_TIME"},    # 07/11/2026
            {"start": 343, "end": 352, "tipo": "IT_IMPORTO"},   # 13.083,33
            {"start": 414, "end": 423, "tipo": "IT_IBAN"},      # IT23P1...
            {"start": 498, "end": 509, "tipo": "PERSON"},       # Rosa Gialli
            {"start": 516, "end": 527, "tipo": "PHONE_NUMBER"}, # 039 2345678
        ],
    },
]
