# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Filtri anti-rumore (GRUPPO B2 + B3).

Su un white paper tecnico l'app aveva prodotto oltre 60 sostituzioni
di cui una sola era un dato personale. Motivo: titoli in MAIUSCOLO,
nomi di file, codici tecnici, marchi pubblici, termini tecnici. Nessuna
di queste categorie è un dato personale, ma il motore neurale + i
recognizer tendevano a catturarli comunque.

Questo modulo espone ``e_rumore(valore, testo, start, end)``: True se
il valore va scartato indipendentemente dal tipo che il recognizer
gli ha assegnato.
"""

from __future__ import annotations

import re
from pathlib import Path

from .percorsi import cartella_liste

# ---------------------------------------------------------------------------
# B3 — Blacklist termini tecnici e marchi pubblici
# ---------------------------------------------------------------------------
#
# Case-insensitive. Match esatto della stringa (dopo strip) — non
# usiamo `in` per evitare che "Amazon Web Services" venga sbagliato
# quando l'utente vuole veramente "Amazon Rossi Srl" (poco probabile,
# ma la rubrica risolve).

_BLACKLIST_TECNICA: set[str] = {
    # ---- Metriche finanziarie / statistiche ----
    "var", "cvar", "nav", "beta", "alpha", "sharpe", "sortino",
    "drawdown", "volatility", "volatilità", "correlation",
    "monte carlo", "montecarlo",
    "msci", "s&p500", "s&p 500", "sp500", "ftse", "nasdaq", "dow jones",
    "vix", "bootstrap", "backtest", "rebalancing",
    "market cap", "eps", "p/e", "roe", "roi", "roic",
    # ---- Tecnologie / stack ----
    "sqlite", "wal", "json", "yaml", "toml", "xml", "csv",
    "api", "rest", "graphql", "grpc", "http", "https", "sql",
    "python", "javascript", "typescript", "rust", "golang",
    "telegram", "slack", "discord", "signal", "whatsapp",
    "launchd", "systemd", "cron", "crontab",
    "macos", "windows", "linux", "unix", "ios", "android",
    "docker", "kubernetes", "k8s", "aws", "gcp", "azure",
    "postgresql", "mysql", "mongodb", "redis",
    "fastapi", "django", "flask", "react", "vue", "angular",
    "numpy", "pandas", "pytorch", "tensorflow", "sklearn",
    "presidio", "spacy", "transformers", "gliner",
    "pyinstaller", "webview", "pywebview",
    # ---- Aziende e servizi pubblici (non sono dati personali) ----
    "yahoo", "yahoo finance",
    "stripe", "paypal",
    "tradegate", "trade republic", "traderepublic",
    "finnhub", "polygon", "coingecko", "coinmarketcap",
    "ecb", "bce", "fed",
    "google", "microsoft", "apple", "amazon", "meta", "facebook",
    "instagram", "twitter", "x", "linkedin", "github", "gitlab",
    "openai", "anthropic", "gemini", "deepmind",
    "netflix", "spotify", "tesla", "nvidia", "intel", "amd",
    "ibm", "oracle", "adobe", "salesforce",
    "huggingface", "hugging face",
    "istat", "eurostat", "world bank",
}


# ---------------------------------------------------------------------------
# B2 — Pattern anti-rumore
# ---------------------------------------------------------------------------

# Nome file: qualsiasi token con estensione riconoscibile.
_ESTENSIONI_FILE = {
    "py", "js", "ts", "tsx", "jsx", "json", "yaml", "yml", "toml",
    "xml", "csv", "tsv", "md", "markdown", "rst", "txt", "log",
    "html", "htm", "css", "scss", "sass", "less",
    "sh", "bash", "zsh", "fish", "ps1", "bat", "cmd",
    "sql", "db", "sqlite", "sqlite3",
    "png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "bmp",
    "pdf", "docx", "xlsx", "pptx", "odt", "ods", "odp",
    "rtf", "eml", "msg", "mbox",
    "zip", "tar", "gz", "bz2", "xz", "7z", "rar",
    "wav", "mp3", "flac", "ogg", "aac", "mp4", "mov", "avi", "mkv",
    "exe", "dll", "so", "dylib", "app", "dmg", "pkg", "deb", "rpm",
    "env", "cfg", "conf", "ini",
    "safetensors", "pt", "pth", "onnx", "gguf", "bin",
    "ipynb", "rb", "go", "rs", "java", "kt", "swift", "cs",
    "cpp", "cc", "c", "h", "hpp", "hxx",
}

_FILE_REGEX = re.compile(
    r"^[A-Za-z0-9_.\-/\\]+\.(?:" + "|".join(sorted(_ESTENSIONI_FILE)) + r")$",
    re.IGNORECASE,
)

# snake_case: token con un underscore in mezzo tra due lettere/cifre.
_SNAKE_CASE_REGEX = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)+$")

# CamelCase / PascalCase / mixed.
# Copre: "MyClass" ("y" min + "C" maj), "getUserById" (idem),
# "APIClient" ("APIC" acronimo + "lient" minusc.), "HTMLParser".
_CAMEL_CASE_REGEX = re.compile(
    r"^(?:"
    r"[a-zA-Z][a-zA-Z0-9]*[a-z][A-Z][a-zA-Z0-9]*"      # min→maj
    r"|[A-Z]{2,}[a-z][A-Za-z0-9]*"                       # ACRONIMO+word
    r")$"
)

# Codice alfanumerico breve stile "P0", "P5-URG", "T1", "A3-XY".
_CODICE_BREVE_REGEX = re.compile(
    r"^[A-Z][A-Z0-9]{0,3}(?:[-_.][A-Z0-9]{1,4})?$"
)

# Lettere singole separate da spazi: "C A S E   S T U D Y".
_LETTERE_SPAZIATE_REGEX = re.compile(
    r"^(?:[A-Z]\s+){2,}[A-Z]$"
)


def _sembra_nome_file(valore: str) -> bool:
    return bool(_FILE_REGEX.match(valore.strip()))


def _sembra_snake_case(valore: str) -> bool:
    return bool(_SNAKE_CASE_REGEX.match(valore.strip()))


def _sembra_camel_case(valore: str) -> bool:
    return bool(_CAMEL_CASE_REGEX.match(valore.strip()))


def _sembra_codice_breve(valore: str) -> bool:
    return bool(_CODICE_BREVE_REGEX.match(valore.strip()))


def _sembra_lettere_spaziate(valore: str) -> bool:
    return bool(_LETTERE_SPAZIATE_REGEX.match(valore.strip()))


def _in_blacklist_tecnica(valore: str) -> bool:
    """Case-insensitive, match esatto sulla stringa strip."""
    return valore.strip().lower() in _BLACKLIST_TECNICA


# ---------------------------------------------------------------------------
# Paesi e macroaree — collisione col dizionario nomi/cognomi
# ---------------------------------------------------------------------------
#
# Misurato su 91 nomi di stato/continente: 13 collidono col dizionario
# italiano (italia, francia, spagna, portogallo, india, corea, siria,
# marocco, brasile, argentina, africa, asia, inghilterra). Su documenti
# reali questo produce persone inesistenti — "in Francia, Guatemala o
# India?" diventava un elenco di individui.
#
# Alcuni sono anche nomi di battesimo veri e diffusi (Asia, India,
# Siria, Argentina): la lista NON li vieta, richiede che ci sia un
# innesco personale esplicito (titolo, "sono", "mi chiamo") — lo stesso
# che serve a qualunque altro nome fuori dizionario.

_PAESI_E_MACROAREE: set[str] = {
    # ---- Continenti e macroaree ----
    "africa", "america", "asia", "europa", "oceania", "antartide",
    "eurasia", "scandinavia", "balcani", "caucaso", "maghreb",
    "medio oriente", "estremo oriente", "sudamerica", "nordamerica",
    "centroamerica", "sudafrica",
    # ---- Europa ----
    "italia", "francia", "germania", "spagna", "portogallo", "grecia",
    "austria", "svizzera", "belgio", "olanda", "paesi bassi",
    "lussemburgo", "danimarca", "norvegia", "svezia", "finlandia",
    "islanda", "irlanda", "regno unito", "inghilterra", "scozia",
    "galles", "polonia", "ungheria", "romania", "bulgaria", "cechia",
    "repubblica ceca", "slovacchia", "slovenia", "croazia", "bosnia",
    "serbia", "montenegro", "macedonia", "kosovo", "albania",
    "estonia", "lettonia", "lituania", "bielorussia", "ucraina",
    "moldavia", "russia", "turchia", "cipro", "malta", "monaco",
    "andorra", "liechtenstein", "vaticano",
    # ---- Asia ----
    "cina", "india", "giappone", "corea", "corea del sud",
    "corea del nord", "vietnam", "thailandia", "cambogia", "laos",
    "birmania", "myanmar", "indonesia", "filippine", "malesia",
    "singapore", "pakistan", "bangladesh", "nepal", "bhutan",
    "sri lanka", "afghanistan", "iran", "iraq", "siria", "libano",
    "israele", "palestina", "giordania", "arabia saudita", "yemen",
    "oman", "qatar", "bahrein", "kuwait", "emirati arabi",
    "kazakistan", "uzbekistan", "turkmenistan", "kirghizistan",
    "tagikistan", "azerbaigian", "armenia", "georgia", "mongolia",
    "taiwan",
    # ---- Africa ----
    "egitto", "libia", "tunisia", "algeria", "marocco", "sudan",
    "etiopia", "eritrea", "somalia", "gibuti", "kenya", "uganda",
    "tanzania", "ruanda", "burundi", "congo", "camerun", "nigeria",
    "ghana", "costa d'avorio", "senegal", "mali", "niger", "ciad",
    "burkina faso", "guinea", "sierra leone", "liberia", "gambia",
    "mauritania", "angola", "zambia", "zimbabwe", "mozambico",
    "namibia", "botswana", "madagascar", "mauritius", "seychelles",
    # ---- Americhe ----
    "stati uniti", "canada", "messico", "guatemala", "honduras",
    "salvador", "nicaragua", "costa rica", "panama", "cuba",
    "giamaica", "haiti", "repubblica dominicana", "bahamas",
    "brasile", "argentina", "cile", "uruguay", "paraguay", "bolivia",
    "peru", "perù", "ecuador", "colombia", "venezuela", "guyana",
    "suriname",
    # ---- Oceania ----
    "australia", "nuova zelanda", "figi", "papua nuova guinea",
}


def e_paese_o_macroarea(valore: str) -> bool:
    """True se ``valore`` è il nome di uno stato, continente o macroarea."""
    return valore.strip().lower() in _PAESI_E_MACROAREE


# ---------------------------------------------------------------------------
# Dizionari di supporto (caricati una volta al modulo)
# ---------------------------------------------------------------------------

_LISTE_DIR = cartella_liste()


def _carica_lemmi(path: Path) -> set[str]:
    if not path.exists():
        return set()
    lemmi: set[str] = set()
    with path.open(encoding="utf-8") as fh:
        for riga in fh:
            w = riga.strip().lower()
            if w and w.isalpha():
                lemmi.add(w)
    return lemmi


_VOCAB_IT: set[str] = _carica_lemmi(_LISTE_DIR / "vocab_it_60k.txt")


def _carica_lista_nomi(path: Path) -> set[str]:
    """Ritorna solo la colonna nome (case-insensitive)."""
    out: set[str] = set()
    if not path.exists():
        return out
    with path.open(encoding="utf-8") as fh:
        for riga in fh:
            riga = riga.rstrip("\n")
            if not riga or riga.startswith("#"):
                continue
            parts = riga.split("\t")
            if parts:
                out.add(parts[0].strip().lower())
    return out


_NOMI: set[str] = _carica_lista_nomi(_LISTE_DIR / "nomi_italiani.tsv")
_COGNOMI: set[str] = _carica_lista_nomi(_LISTE_DIR / "cognomi_italiani.tsv")


def _lemma_comune_non_nome(valore: str) -> bool:
    """True se il valore (single-word) ha lemma nel vocabolario italiano
    e NON è nella lista nomi/cognomi.  Esempi:
      "APPRESA" → è "appresa" nel vocab, non è nome → True (scarta).
      "Mario"   → è "mario", ma è nome → False.
    """
    v = valore.strip().lower()
    # Solo per single-word puri alfa (non "Mario Rossi").
    if not v.isalpha():
        return False
    if v not in _VOCAB_IT:
        return False
    return v not in _NOMI and v not in _COGNOMI


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def e_rumore(valore: str, entity_type: str | None = None) -> bool:
    """True se ``valore`` va scartato perché è quasi certamente rumore
    (titolo maiuscolo, nome file, codice tecnico, marchio pubblico,
    parola comune non-nome).

    Non applichiamo il filtro alle entità con validatore aritmetico
    (IBAN, CF, PIVA, CARTA): quelle sono già certe. Ma i filtri sono
    tutti prudenti — anche applicati ad un IBAN dovrebbero produrre
    False (un IBAN reale non passa nessuno dei pattern rumore).
    """
    v = valore.strip()
    if not v:
        return True

    # Blacklist esplicita.
    if _in_blacklist_tecnica(v):
        return True

    # Tutto MAIUSCOLO: titoli, sigle di stampa. Eccezione: i lemmi che
    # compaiono nella lista nomi/cognomi italiani sono persone scritte
    # in caps (contratti, intestazioni formali, enfasi). "MARIO ROSSI",
    # "LUIGI DE LUCA", "PASQUALE", "GIOVANNI" restano; "TECNICO",
    # "SICUREZZA", "APPRESA", "SEZIONE 1" via.
    #
    # Il dizionario ha priorità sulla grafia: un nome è un nome anche
    # urlato. Prima la regola valeva solo da 2 token in su e i nomi
    # isolati in maiuscolo sparivano.
    lettere = [c for c in v if c.isalpha()]
    if len(lettere) >= 4 and all(c.isupper() for c in lettere):
        tokens_alpha = [t.lower() for t in re.split(r"[\s.\-']+", v) if t.isalpha()]
        # Se un token è nome o cognome noto, è una persona urlata, non rumore.
        return not any(t in _NOMI or t in _COGNOMI for t in tokens_alpha)

    # Lettere spaziate: "C A S E   S T U D Y".
    if _sembra_lettere_spaziate(v):
        return True

    # Nome file o path.
    if _sembra_nome_file(v):
        return True

    # snake_case / CamelCase (identificatori di codice).
    if _sembra_snake_case(v) or _sembra_camel_case(v):
        return True

    # Codice breve: "P0", "T1", "A3-URG".
    if _sembra_codice_breve(v):
        return True

    # Token 1-2 caratteri (senza contare punteggiatura).
    if len(v.replace(".", "").replace("-", "")) <= 2:
        return True

    # Parola singola con lemma nel vocabolario italiano E non nome/cognome.
    return _lemma_comune_non_nome(v)
