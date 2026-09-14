# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Auto-collaudo avversariale (PARTE 3).

I casi sono GENERATI in modo sistematico incrociando i tipi della
tassonomia (TASSONOMIA_PII.md) con le dimensioni della matrice input
(MATRICE_INPUT.md): grafia × posizione × contesto × formato, più le
coppie insidiose e i controcasi (testi che NON devono produrre
sostituzioni).

Regola del progetto: questi casi servono a TROVARE difetti, non a
dimostrare che non ce ne sono — il recall dichiarato viene dai
documenti reali (`benchmark/documenti_utente/`). Ogni caso che
fallisce va corretto alla CLASSE, non all'esemplare.
"""

from __future__ import annotations

import uuid

import pytest

from backend.motore import anonimizza


@pytest.fixture(scope="module")
def db(tmp_path_factory):
    return str(tmp_path_factory.mktemp("avv") / "vault.db")


def _anon(testo: str, db: str, **kw):
    return anonimizza(testo, str(uuid.uuid4()), db_path=db, **kw)


# ===========================================================================
# 1. DETERMINISTICI — ogni formato ammesso × ogni posizione
# ===========================================================================

# (etichetta, valore come scritto nel testo)
_VALORI_DETERMINISTICI = [
    # Codice fiscale: persona (maiuscolo/minuscolo), ente con keyword.
    ("cf", "RSSMRA85T10A944I"),
    ("cf-minuscolo", "rssmra85t10a944i"),
    # Partita IVA (nel contesto c'è sempre almeno la parola generica).
    ("piva", "P.IVA 01234567890"),
    ("piva-spazi", "partita IVA 01234 56789 0"),
    # IBAN: attaccato, a gruppi di 4, minuscolo, estero.
    ("iban", "IT60X0542811101000000123456"),
    ("iban-gruppi", "IT60 X054 2811 1010 0000 0123 456"),
    ("iban-minuscolo", "it60x0542811101000000123456"),
    ("iban-de", "DE89370400440532013000"),
    ("iban-fr", "FR7630006000011234567890189"),
    ("iban-es", "ES9121000418450200051332"),
    ("iban-ch", "CH9300762011623852957"),
    ("iban-nl", "NL91ABNA0417164300"),
    # Carta di pagamento (Luhn).
    ("carta", "4111 1111 1111 1111"),
    # Telefoni: mobile nudo, +39, 0039, con trattini, fisso.
    ("tel-mobile", "3391234567"),
    ("tel-mobile-spazi", "339 123 4567"),
    ("tel-prefisso", "+39 333 1234567"),
    ("tel-0039", "0039 333 1234567"),
    ("tel-trattini", "333-123-4567"),
    ("tel-fisso", "06 4890123"),
    # Email (anche maiuscola = PEC-like).
    ("email", "m.rossi@studio.it"),
    ("email-maiuscola", "MARIO.ROSSI@PEC.STUDIO.IT"),
    # Targa: attaccata, con spazi, con trattini, minuscola.
    ("targa", "FG771XD"),
    ("targa-spazi", "FG 771 XD"),
    ("targa-trattini", "FG-771-XD"),
    ("targa-minuscola", "fg771xd"),
    # VIN con keyword.
    ("vin", "telaio ZFA1234567B123456"),
    # Documenti con keyword.
    ("doc-ci", "carta d'identità AB 1234567"),
    ("doc-passaporto", "passaporto YA1234567"),
    ("doc-patente", "patente n. AB1234567C"),
    # Pratiche/procedimenti.
    ("rg", "R.G. 1234/2023"),
    ("sentenza", "sentenza n. 89/2021"),
    ("protocollo", "prot. n. 45210"),
    ("fattura", "fattura n. 2024/151"),
    ("polizza", "polizza n. 998877-K"),
    ("matricola", "matricola INPS 1234567890"),
    # Social.
    ("social", "@mario.rossi_88"),
    ("social-underscore", "@ma_ri_2024"),
    # Indirizzi.
    ("indirizzo", "Via Roma 12"),
    ("indirizzo-corso", "Corso Vittorio Emanuele 118"),
    ("casella-postale", "C.P. 123"),
    # CF ente (11 cifre + keyword nel template o nel valore).
    ("cf-ente", "codice fiscale 80012330584"),
    # Targhe con keyword (moto/storica).
    ("targa-moto", "moto targata BA12345"),
    ("targa-storica", "veicolo storico targa MI 123456"),
    # Documenti aggiuntivi.
    ("doc-cie", "CIE n. CA00000AA"),
    ("doc-team", "tessera sanitaria 80380500123456789012"),
    # Pratiche aggiuntive.
    ("decreto", "decreto n. 771/2024"),
    ("ordinanza", "ordinanza n. 15/2025"),
    ("verbale", "verbale n. 12/2024"),
    ("repertorio", "atto rep. 12345"),
    ("albo", "iscrizione albo n. A12345"),
    ("inail", "posizione INAIL n. 87654321"),
    ("codice-contratto", "codice identificativo contratto T4H88KLM2P"),
]

# La parte del valore che DEVE sparire dal testo anonimizzato (per i
# valori con etichetta inclusa — "P.IVA 01234567890" — sparisce il numero).
_ATTESO_ASSENTE = {
    "piva": "01234567890",
    "piva-spazi": "01234 56789 0",
    "vin": "ZFA1234567B123456",
    "doc-ci": "AB 1234567",
    "doc-passaporto": "YA1234567",
    "doc-patente": "AB1234567C",
    "rg": "1234/2023",
    "sentenza": "89/2021",
    "protocollo": "45210",
    "fattura": "2024/151",
    "polizza": "998877-K",
    "matricola": "1234567890",
    "cf-ente": "80012330584",
    "targa-moto": "BA12345",
    "targa-storica": "MI 123456",
    "doc-cie": "CA00000AA",
    "doc-team": "80380500123456789012",
    "decreto": "771/2024",
    "ordinanza": "15/2025",
    "verbale": "12/2024",
    "repertorio": "12345",
    "albo": "A12345",
    "inail": "87654321",
    "codice-contratto": "T4H88KLM2P",
}

_POSIZIONI = [
    ("inizio", "{v} risulta essere il riferimento indicato."),
    ("meta", "Il riferimento indicato, {v}, risulta corretto."),
    ("fine", "Il riferimento corretto della pratica è {v}"),
    ("tabella", "Campo\tValore\nRiferimento\t{v}\nStato\tverificato"),
    ("titolo", "OGGETTO: VERIFICA {v}\n\nSi conferma la ricezione del documento."),
]


@pytest.mark.parametrize("etichetta,valore", _VALORI_DETERMINISTICI,
                         ids=[e for e, _ in _VALORI_DETERMINISTICI])
@pytest.mark.parametrize("pos,template", _POSIZIONI,
                         ids=[p for p, _ in _POSIZIONI])
def test_deterministico_formato_x_posizione(etichetta, valore, pos, template, db):
    testo = template.format(v=valore)
    out, _ = _anon(testo, db)
    assente = _ATTESO_ASSENTE.get(etichetta, valore)
    assert assente not in out, f"[{etichetta}/{pos}] fuga: {assente!r} in {out!r}"


# ===========================================================================
# 2. PERSONA — nome × contesto × grafia
# ===========================================================================

_NOMI = ["andrea", "giuseppe", "matteo", "giovanni", "francesco",
         "alessandro", "federica", "martina", "simone", "giacomo"]

# (id, template sul nome minuscolo, il nome deve sparire)
_CONTESTI_PERSONA = [
    ("presentazione", "ciao sono {n}, ci vediamo domani"),
    ("mi-chiamo", "buongiorno, mi chiamo {n} e chiamo per il preventivo"),
    ("titolo-sig", "il sig. {N} ha firmato il contratto"),
    ("verbo-viene", "sicuramente viene {n} con noi alla riunione"),
    ("da-personale", "ci vediamo da {n} alle otto"),
    ("apertura", "Gentile {N},\nle scrivo per un preventivo"),
    ("firma", "Cordiali saluti,\n{N}"),
    ("isolato-maiuscolo", "Ho parlato con {N} riguardo al progetto"),
    ("nome-cognome", "{N} Rossi ha inviato il documento richiesto"),
    ("caps-lock", "IL SOTTOSCRITTO {NN} ROSSI CHIEDE QUANTO SEGUE"),
    ("verbo-avvisa", "per favore avvisa {n} del cambio orario"),
    ("elenco", "- referente: {N}\n- stato: confermato"),
]


@pytest.mark.parametrize("nome", _NOMI)
@pytest.mark.parametrize("ctx,template", _CONTESTI_PERSONA,
                         ids=[c for c, _ in _CONTESTI_PERSONA])
def test_persona_contesto_x_grafia(nome, ctx, template, db):
    testo = template.format(n=nome, N=nome.title(), NN=nome.upper())
    out, _ents = _anon(testo, db)
    # Il nome (in qualunque grafia sia stato scritto) deve sparire.
    for forma in (nome, nome.title(), nome.upper()):
        if forma in testo:
            assert forma not in out, (
                f"[{ctx}] {forma!r} ancora presente in {out!r}"
            )


# Nome + cognome con particella nobiliare, per grafia.
_PARTICELLE_CASI = [
    "Anna Della Valle ha confermato l'appuntamento",
    "scrivi a luca lo bianco per il preventivo",
    "Stefania De Giovanni parteciperà alla riunione",
    "il documento di Marco Dal Pozzo è pronto",
]


@pytest.mark.parametrize("testo", _PARTICELLE_CASI)
def test_persona_particelle_nobiliari(testo, db):
    out, ents = _anon(testo, db)
    attivi = [e for e in ents if not e.get("suggerito") and e["tipo"] == "PERSONA"]
    assert attivi, f"nessuna PERSONA attiva in {out!r}"


# ===========================================================================
# 3. DATE DI NASCITA — sei formati
# ===========================================================================

_DATE_NASCITA = [
    "27/03/2004", "27-03-2004", "27.03.2004", "2004-03-27",
    "27 marzo 2004", "27 mar 2004",
]


@pytest.mark.parametrize("data", _DATE_NASCITA)
def test_data_nascita_formati(data, db):
    out, _ = _anon(f"Il richiedente è nato il {data} a Perugia.", db)
    assert data not in out


# ===========================================================================
# 4. COPPIE INSIDIOSE — il dato accanto a una parola che gli somiglia
# ===========================================================================

# (testo, deve_sparire, deve_restare)
_COPPIE = [
    ("l'auto targata FG771XD e il codice interno XFG771XD9",
     "FG771XD", "XFG771XD9"),
    ("il CF RSSMRA85T10A944I e la sigla RSSMRA del progetto",
     "RSSMRA85T10A944I", "sigla RSSMRA"),
    ("chiama Matteo e poi marca la casella",
     "Matteo", "marca la casella"),
    ("il cellulare 3391234567 e il progressivo 1234567",
     "3391234567", "progressivo 1234567"),
    ("abita in Via Roma 12, vicino alla via romana antica",
     "Via Roma 12", "via romana antica"),
    ("sentenza n. 89/2021 e rapporto di conformità 90/2021",
     "89/2021", "rapporto di conformità 90/2021"),
    ("il profilo @mario.rossi_88 e il prezzo @ 88 euro",
     "@mario.rossi_88", "prezzo @ 88 euro"),
    ("l'IBAN IT60X0542811101000000123456 e il codice ITX99 del listino",
     "IT60X0542811101000000123456", "codice ITX99"),
    ("scrive m.rossi@studio.it citando il file m.rossi.txt",
     "m.rossi@studio.it", "m.rossi.txt"),
    ("patente n. AB1234567C e modello AB12 del catalogo",
     "AB1234567C", "modello AB12"),
    ("è nato il 27/03/2004; la versione 27.3 del software resta",
     "27/03/2004", "versione 27.3"),
    ("arriva Giovanni da Parma con il prosciutto di Parma",
     "Giovanni", "prosciutto di Parma"),
]


@pytest.mark.parametrize("testo,sparisce,resta", _COPPIE,
                         ids=[c[1][:18] for c in _COPPIE])
def test_coppie_insidiose(testo, sparisce, resta, db):
    import re as _re
    out, _ = _anon(testo, db)
    # Confine alfanumerico: "FG771XD" dentro "XFG771XD9" (che DEVE
    # restare) non è una fuga.
    standalone = _re.search(
        rf"(?<![A-Za-z0-9]){_re.escape(sparisce)}(?![A-Za-z0-9])", out
    )
    assert not standalone, f"fuga: {sparisce!r} in {out!r}"
    assert resta in out, f"falso positivo: {resta!r} sparito da {out!r}"


# ===========================================================================
# 5. CONTROCASI — testi che NON devono produrre sostituzioni
# ===========================================================================

_CONTROCASI = [
    # --- parole comuni che coincidono con nomi (uso comune, minuscolo) ---
    "ho comprato una rosa rossa dal fioraio",
    "si muove con grazia sorprendente",
    "un fiore all'occhiello per l'azienda",
    "il cielo celeste di primavera",
    "il tempo è sereno su tutta la regione",
    "un angelo custode veglia su di noi",
    "la vittoria della squadra è meritata",
    "l'aurora boreale è visibile stanotte",
    "la gioia dei bambini in cortile",
    "una margherita nel prato",
    "la stella polare indica il nord",
    "una perla rara in collezione",
    "la palma da datteri cresce al sud",
    "una speranza concreta di ripresa",
    "la luce del tramonto sul mare",
    # --- verbi coniugati identici a nomi propri ---
    "io marco le presenze ogni mattina",
    "sforna il pane alle sette in punto",
    "conta i giorni che mancano alla scadenza",
    "salvo il documento e chiudo il programma",
    "io guido la macchina fino in ufficio",
    "porto il pane a casa ogni sera",
    "spero che il progetto vada in porto",
    "dora l'arrosto nel forno a legna",
    "lino il cassetto con la carta",
    # --- termini tecnici e marchi pubblici ---
    "la simulazione Monte Carlo converge in fretta",
    "il backend è scritto in Python con FastAPI",
    "il container Docker gira su Kubernetes",
    "l'indice S&P500 ha chiuso in rialzo",
    "il repository è su GitHub da ieri",
    "il profilo aziendale su LinkedIn cresce",
    "il VaR del portafoglio resta contenuto",
    "il backtest della strategia è promettente",
    "il modello è pubblicato su Hugging Face",
    "compila il foglio in Excel e salvalo",
    "la certificazione ISO 9001 è stata rinnovata",
    "acciaio conforme alla UNI EN 10025",
    # --- nomi di file, percorsi, comandi, codici ---
    "apri il file backend/motore.py e controlla",
    "la configurazione è in config.yaml come sempre",
    "lancia lo script run_test.sh dalla radice",
    "esegui git commit -m e poi push",
    "il ticket P0 va gestito subito",
    "il task T1-URG scade oggi",
    "la variabile snake_case_var non è usata",
    "la classe CamelCaseClass va rinominata",
    "il log è in data/log.txt sul server",
    "scarica il pacchetto model.safetensors dal mirror",
    # --- toponimi in contesti non personali ---
    "la scuola romana di pittura del Seicento",
    "il prosciutto di Parma è una DOP",
    "la pizza napoletana è patrimonio UNESCO",
    "un caffè alla romana per tutti",
    "l'insalata di riso alla milanese",
    "il derby della capitale finisce pari",
    # --- leggi e norme (non sono pratiche personali) ---
    "come previsto dalla legge n. 194 del 1978",
    "ai sensi del d.lgs. 196/2003 sulla privacy",
    "il decreto legislativo n. 231/2001 si applica",
    "come da art. 5 del codice di procedura",
    "la legge 241/1990 sul procedimento amministrativo",
    # --- unità, metriche, numeri non personali ---
    "il file pesa 199 KB dopo la compressione",
    "le tariffe sono 0,14 e 0,28 euro",
    "le metriche riportano 0.987 e 0.990",
    "il manoscritto risale al 1689",
    "lo sconto è del 15% fino a domenica",
    "la potenza del motore è 90 CV",
    "lo schermo ha 400 HZ di refresh",
    "sono 45 KM di strada panoramica",
    # --- usi temporali/idiomatici dei nomi-collisione ---
    "ci vediamo domenica prossima al mercato",
    "a natale torniamo tutti a casa",
    "partiamo all'alba per evitare il traffico",
    "il sole splende sulla vallata",
    "salvo imprevisti arriviamo alle nove",
    "arriva domenica mattina con il treno",
    "il massimo del punteggio è cento",
    "abbi fede nel progetto",
    "la fede nuziale è d'oro",
    # --- titoli e struttura documentale ---
    "RELAZIONE TECNICA FINALE",
    "INDICE DEI CONTENUTI",
    "C A S E   S T U D Y",
    "CAPITOLO PRIMO: INTRODUZIONE",
    "ALLEGATO TECNICO B",
    # --- frasi di lavoro comuni (nessun dato personale) ---
    "la riunione è rimandata a data da destinarsi",
    "il preventivo sarà pronto entro fine mese",
    "si prega di confermare la ricezione",
    "il documento allegato annulla il precedente",
    "restiamo a disposizione per chiarimenti",
    "l'impianto è conforme alle normative vigenti",
    "il collaudo è previsto per la prossima settimana",
    "i lavori procedono secondo il cronoprogramma",
    # --- mesi, giorni, colori, saluti (mai persone) ---
    "a marzo ricominciano i corsi serali",
    "il lunedì è sempre il giorno più pieno",
    "ad agosto l'ufficio resta chiuso",
    "la parete è dipinta di verde salvia",
    "una tovaglia bianca e blu",
    "buongiorno a tutti e buon lavoro",
    "grazie mille e a presto",
    "in bocca al lupo per l'esame",
    # --- inglese tecnico dentro testo italiano ---
    "il deploy in production è schedulato stanotte",
    "serve una code review prima del merge",
    "il team ha fatto il refactoring del modulo",
    "la roadmap prevede due release quest'anno",
    # --- testo rovinato da OCR (nessun dato reale) ---
    "il s0ttoscritt0 chiede c0me da m0dul0 allegat0",
    "la c0pia c0nf0rme all 0riginale e dep0sitata",
    "ii presente d0cument0 c0nsta di n0ve pagine",
    # --- numeri civili/quantità in contesti non personali ---
    "il lotto 12 della particella non catastale",
    "sono previsti 123 posti a sedere",
    "l'aula 06081 non esiste in questo edificio",
    "il modello 730 va presentato a luglio",
    "il volo AZ 610 è in orario",
    "la linea 64 passa ogni dieci minuti",
    # --- sigle istituzionali (non identificativi personali) ---
    "l'INPS ha aggiornato il portale",
    "la sede INAIL è chiusa il venerdì",
    "il CUP dell'ospedale risponde al mattino",
    "l'ISEE va rinnovato ogni anno",
]


@pytest.mark.parametrize("testo", _CONTROCASI, ids=[t[:28] for t in _CONTROCASI])
def test_controcaso_nessuna_sostituzione(testo, db):
    out, ents = _anon(testo, db)
    assert out == testo, (
        f"controcaso modificato: {out!r} — entità: "
        f"{[(e['tipo'], e['valore_reale']) for e in ents if not e.get('suggerito')]}"
    )


# ===========================================================================
# 6. CATEGORIE OPT-IN — di default NON sostituite
# ===========================================================================

_OPT_IN = [
    ("ip", "il server risponde da 192.168.1.10 in locale", "192.168.1.10"),
    ("url", "vedi https://esempio.com/pagina per i dettagli",
     "https://esempio.com/pagina"),
    ("importo", "il canone è di 1.250,00 euro mensili", "1.250,00"),
    ("luogo", "il convegno si terrà a Perugia in autunno", "Perugia"),
    ("data-generica", "la riunione è fissata per il 15/09/2026", "15/09/2026"),
    ("catasto", "immobile censito al foglio 12 particella 345 sub 6",
     "foglio 12 particella 345 sub 6"),
]


@pytest.mark.parametrize("nome,testo,resta", _OPT_IN, ids=[c[0] for c in _OPT_IN])
def test_categoria_opt_in_non_sostituita_di_default(nome, testo, resta, db):
    out, _ = _anon(testo, db)
    assert resta in out, f"[{nome}] {resta!r} sostituito ma la categoria è opt-in"


# ===========================================================================
# 7. CASO "MARCO" (briefing) + modalità diagnostica
# ===========================================================================

def test_caso_briefing_marco_completo(db):
    testo = ("ciao sono andrea, devo andare a Pescara, sicuramente viene "
             "marco con me, prendiamo un auto targata FG771XD")
    out, ents = _anon(testo, db)
    assert "andrea" not in out
    assert "marco" not in out.replace("«", "").replace("»", "") or "marco" not in out
    assert "FG771XD" not in out
    tipi = {e["tipo"] for e in ents if not e.get("suggerito")}
    assert "PERSONA" in tipi and "TARGA" in tipi
    persone = [e for e in ents if e["tipo"] == "PERSONA" and not e.get("suggerito")]
    assert len(persone) == 2, f"attese 2 persone (andrea, marco): {persone}"


# ===========================================================================
# 8. NOMI PERSI SUL CAMPO — casi raccolti dall'utente in uso reale
# ===========================================================================
#
# Ogni riga qui sotto è un testo che l'utente ha davvero incollato
# nell'app e su cui il motore aveva perso almeno un nome. Il formato è
# (testo, nomi che DEVONO sparire).

_NOMI_PERSI_SUL_CAMPO = [
    ("Ciao sono Andrea, sono con marco, giovanni, maria, luisa e fiorella",
     ["Andrea", "marco", "giovanni", "maria", "luisa", "fiorella"]),
    ("ciao sono con giovanni, marco e maria",
     ["giovanni", "marco", "maria"]),
    (("Ciao mi trovo in via perugia 18 con marco, sto andando a casa di di "
      "giovanni, penso che questa sera farò tardi andrò da, marco! "
      "PENSO che luca, o PASQUALE"),
     ["marco", "giovanni", "luca", "PASQUALE"]),
    ("Ciao sono Delfo", ["Delfo"]),
    ("Ciao sono delfo berretti", ["delfo", "berretti"]),
]


@pytest.mark.parametrize("testo,nomi", _NOMI_PERSI_SUL_CAMPO,
                         ids=[t[0][:30] for t in _NOMI_PERSI_SUL_CAMPO])
def test_nome_perso_sul_campo(testo, nomi, db):
    out, _ = _anon(testo, db)
    persi = [n for n in nomi if n in out]
    assert not persi, f"nomi non sostituiti: {persi} — uscita: {out!r}"


def test_nessun_suggerimento_su_testo_gia_sostituito(db):
    """Fix E: "via perugia 18" diventa «INDIRIZZO_1»; proporre "perugia"
    come persona è un doppione su testo che non esiste più."""
    testo = "Ciao mi trovo in via perugia 18 con marco"
    _, ents = _anon(testo, db)
    for e in ents:
        if not e.get("suggerito"):
            continue
        assert e["valore_reale"].lower() not in "via perugia 18", (
            f"suggerimento {e['valore_reale']!r} su testo già sostituito"
        )


# --- ogni nome in ogni posizione × ogni grafia -----------------------------

_GRAFIE = ["Marco", "marco", "MARCO", "Pasquale", "pasquale", "PASQUALE"]

_POSIZIONI_NOME = [
    "sono con {n}, andiamo insieme",
    "{n}, giovanni e luisa arrivano dopo",
    "vengono giovanni, luisa e {n}",
    "ho parlato con giovanni e con {n}",
]


@pytest.mark.parametrize("grafia", _GRAFIE)
@pytest.mark.parametrize("modello", _POSIZIONI_NOME,
                         ids=[m[:16] for m in _POSIZIONI_NOME])
def test_nome_in_ogni_posizione_e_grafia(grafia, modello, db):
    testo = modello.format(n=grafia)
    out, _ = _anon(testo, db)
    assert grafia not in out, f"{grafia!r} non sostituito in {out!r}"


# --- nomi rari e stranieri dopo contesto forte -----------------------------
#
# Nessuno di questi è nel dizionario italiano: devono passare per il
# contesto, non per la lista. È la garanzia che il motore non sia solo
# un cercatore di stringhe note.

_NOMI_FUORI_DIZIONARIO = [
    "Delfo", "Ndiaye", "Oleksandr", "Aigerim", "Thanawat",
    "Bogdan", "Ruxandra", "Yevheniia", "Chiwetel", "Sanjeev",
]

_CONTESTI_FORTI = [
    "Ciao sono {n}",
    "Mi chiamo {n}",
    "Il signor {n} ha firmato",
    "Gentile {n}, la contatto per",
]


@pytest.mark.parametrize("nome", _NOMI_FUORI_DIZIONARIO)
@pytest.mark.parametrize("contesto", _CONTESTI_FORTI,
                         ids=[c[:14] for c in _CONTESTI_FORTI])
def test_nome_fuori_dizionario_con_contesto_forte(nome, contesto, db):
    testo = contesto.format(n=nome) + "."
    out, _ = _anon(testo, db)
    assert nome not in out, (
        f"{nome!r} fuori dizionario perso nonostante il contesto: {out!r}"
    )


# --- controcasi del contesto forte ----------------------------------------
#
# "sono" e "mi chiamo" aprono la porta ai nomi fuori dizionario: la
# porta non deve lasciar passare verbi, aggettivi e orari.

_CONTROCASI_CONTESTO_FORTE = [
    "sono felice di questa notizia",
    "sono andato a Roma in treno",
    "sono le otto passate da un pezzo",
    "sono stanco ma soddisfatto",
    "sono previsti ritardi sulla linea",
    "mi chiamo fuori da questa storia",
    "sono sicuro che funzionerà",
    "sono d'accordo con la proposta",
]


@pytest.mark.parametrize("testo", _CONTROCASI_CONTESTO_FORTE,
                         ids=[t[:26] for t in _CONTROCASI_CONTESTO_FORTE])
def test_contesto_forte_non_promuove_parole_comuni(testo, db):
    _out, ents = _anon(testo, db)
    persone = [e["valore_reale"] for e in ents
               if e["tipo"] == "PERSONA" and not e.get("suggerito")]
    assert not persone, f"falsa persona in {testo!r}: {persone}"


# --- toponimi: uno stato non è una persona --------------------------------

_TOPONIMI_NON_PERSONA = [
    "Vuoi inviare un messaggio in Francia, Guatemala o India?",
    "L'Italia e la Spagna hanno firmato l'accordo con il Brasile",
    "le filiali sono in Argentina, Corea e Marocco",
    "il volume esportato verso Asia e Africa è cresciuto",
]


@pytest.mark.parametrize("testo", _TOPONIMI_NON_PERSONA,
                         ids=[t[:26] for t in _TOPONIMI_NON_PERSONA])
def test_stato_non_diventa_persona(testo, db):
    _out, ents = _anon(testo, db)
    persone = [e["valore_reale"] for e in ents
               if e["tipo"] == "PERSONA" and not e.get("suggerito")]
    assert not persone, f"stato scambiato per persona in {testo!r}: {persone}"


def test_nome_che_coincide_con_stato_resta_se_persona(db):
    """La regola sugli stati non deve cancellare le persone che si
    chiamano davvero Asia o India."""
    out, _ = _anon("Ciao sono Asia, ti presento mia sorella.", db)
    assert "Asia" not in out
    out2, _ = _anon("La signora India Rossi ha firmato il contratto.", db)
    assert "India" not in out2


def test_diagnosi_traccia_percorso(db):
    from backend.diagnosi import ultima_diagnosi
    testo = "RELAZIONE TECNICA: contattare Mario Rossi al 3391234567."
    _out, _ = _anon(testo, db, diagnosi=True)
    eventi = ultima_diagnosi()
    fasi = {e["fase"] for e in eventi}
    assert any(f == "rilevato" for f in fasi), "nessun evento 'rilevato'"
    assert any(f == "accettato" for f in fasi), "nessun evento 'accettato'"
    assert any(f.startswith("scartato") for f in fasi), (
        "nessun evento 'scartato' — il titolo maiuscolo doveva produrne"
    )
    # Ogni evento accettato riporta placeholder e tipo.
    for e in eventi:
        if e["fase"] == "accettato":
            assert "«" in e["dettaglio"] and e["tipo"]


def test_diagnosi_spiega_token_persi(db):
    """Il caso-firma della diagnostica: un nome noto minuscolo senza
    contesto deve comparire fra i token spiegati, con il motivo."""
    from backend.diagnosi import ultima_diagnosi
    # "grazia" senza alcun trigger: non sostituito, ma la diagnosi
    # deve dire perché.
    _out, _ = _anon("porta grazia nel modo di fare, dicono tutti", db,
                   diagnosi=True)
    eventi = ultima_diagnosi()
    persi = [e for e in eventi if e["fase"] == "token perso"]
    # o è stato scartato con motivo, o è nei token persi: mai silenzio.
    scartati = [e for e in eventi if e["fase"].startswith("scartato")]
    assert persi or scartati
