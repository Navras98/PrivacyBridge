# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Cifratura trasparente del vault (valore_reale at-rest).

Obiettivo: i valori originali (nomi, IBAN, CF…) non restano in chiaro
su disco.  La cifratura è trasparente al chiamante — ``vault.add`` e
``vault.get_*`` lavorano con plaintext, la conversione avviene qui.

Design
------
* Algoritmo: Fernet (AES-128-CBC + HMAC-SHA256, cryptography 48+).
* Chiave: 32 byte casuali, 44 char base64.  Conservata nel Portachiavi
  di sistema (macOS Keychain via ``security`` CLI, Windows Credential
  Manager in futuro) con fallback su file ``.vault.key`` a 0600 nella
  cartella dati.  Se la chiave non esiste viene generata al primo
  utilizzo.
* Formato su disco: ``enc:v1:<fernet-token>``.  Le righe legacy in chiaro
  restano leggibili e vengono migrate al prossimo ``add`` / ``flush``.
* Fallback: se ``cryptography`` non è importabile o la chiave non è
  recuperabile, ``encrypt``/``decrypt`` diventano no-op con warning —
  l'app non si blocca mai per la cifratura.

Perché non SQLCipher
--------------------
SQLCipher cifra l'intero file SQLite ma richiede un'estensione nativa
compilata per ogni piattaforma e un bootloader custom in PyInstaller.
Fernet cifra solo la colonna sensibile, è puro Python + cryptography
(già dipendenza transitiva di questo progetto) e non cambia il formato
del file — un vault esistente resta leggibile senza migrazione.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger("privacybridge.vault_crypto")

_ENC_PREFIX = "enc:v1:"
_KEYCHAIN_SERVICE = "com.andreasforna.privacybridge"
_KEYCHAIN_ACCOUNT = "vault-key"

# Cache del Fernet già istanziato (evita di rileggere il portachiavi
# ad ogni riga del vault).
_fernet_cache: object | None = None
_no_crypto_warned = False


# ---------------------------------------------------------------------------
# Rilevamento disponibilità
# ---------------------------------------------------------------------------

def _try_import_fernet():
    try:
        from cryptography.fernet import Fernet as _F  # noqa: F401

        return _F
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Gestione chiave
# ---------------------------------------------------------------------------

def _key_file_path(data_dir: Path | None = None) -> Path:
    """Percorso del file di fallback della chiave."""
    if data_dir is not None:
        return Path(data_dir) / ".vault.key"
    # Risolto lazy per rispettare PRIVACYBRIDGE_DATA_DIR nei test.
    from .percorsi import cartella_dati

    try:
        d = cartella_dati()
    except Exception:
        d = Path.home() / ".config" / "PrivacyBridge"
        d.mkdir(parents=True, exist_ok=True)
    return d / ".vault.key"


def _keychain_get() -> str | None:
    """Legge la chiave dal Portachiavi di sistema.  Ritorna None se assente."""
    if sys.platform == "darwin":
        try:
            r = subprocess.run(
                ["security", "find-generic-password",
                 "-a", _KEYCHAIN_ACCOUNT, "-s", _KEYCHAIN_SERVICE, "-w"],
                capture_output=True, text=True, timeout=5,
            )
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            pass
    return None


def _keychain_set(key_b64: str) -> bool:
    """Scrive la chiave nel Portachiavi.  Ritorna True se riuscito."""
    if sys.platform == "darwin":
        try:
            # -U = update se esiste già
            r = subprocess.run(
                ["security", "add-generic-password",
                 "-a", _KEYCHAIN_ACCOUNT, "-s", _KEYCHAIN_SERVICE,
                 "-w", key_b64, "-U"],
                capture_output=True, text=True, timeout=5,
            )
            return r.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            pass
    return False


def _load_or_create_key(data_dir: Path | None = None) -> bytes | None:
    """Carica la chiave esistente o ne genera una nuova.

    Ordine: Portachiavi → file fallback → genera e salva.
    Ritorna i byte della chiave Fernet (44 char base64) o None se
    cryptography non è disponibile.
    """
    Fernet = _try_import_fernet()
    if Fernet is None:
        return None

    # 1. Portachiavi
    kc = _keychain_get()
    if kc:
        try:
            # Valida che sia una Fernet key
            Fernet(kc.encode())
            return kc.encode()
        except Exception:
            logger.warning("Chiave nel Portachiavi non valida, rigenero")

    # 2. File fallback
    kf = _key_file_path(data_dir)
    if kf.exists():
        try:
            raw = kf.read_text(encoding="utf-8").strip()
            Fernet(raw.encode())
            # Promuovi al Portachiavi se ora disponibile
            _keychain_set(raw)
            return raw.encode()
        except Exception:
            logger.warning("Chiave su file non valida: %s", kf)

    # 3. Genera nuova
    new_key = Fernet.generate_key()
    saved = _keychain_set(new_key.decode())
    if not saved:
        # Fallback su file
        try:
            kf.parent.mkdir(parents=True, exist_ok=True)
            kf.write_text(new_key.decode(), encoding="utf-8")
            try:
                os.chmod(kf, 0o600)
            except OSError:
                pass
        except OSError as e:
            logger.warning("Impossibile salvare la chiave di cifratura: %s", e)
            # Ritorna comunque la chiave per la sessione corrente
    return new_key


def _get_fernet(data_dir: Path | None = None):
    """Ritorna l'istanza Fernet (cached) o None se non disponibile."""
    global _fernet_cache, _no_crypto_warned
    if _fernet_cache is not None:
        return _fernet_cache

    Fernet = _try_import_fernet()
    if Fernet is None:
        if not _no_crypto_warned:
            logger.warning("cryptography non disponibile — vault in chiaro")
            _no_crypto_warned = True
        return None

    key = _load_or_create_key(data_dir)
    if key is None:
        return None
    try:
        _fernet_cache = Fernet(key)
        return _fernet_cache
    except Exception as e:
        logger.warning("Impossibile inizializzare Fernet: %s", e)
        return None


def reset_crypto_cache() -> None:
    """Azzera la cache (per test)."""
    global _fernet_cache, _no_crypto_warned
    _fernet_cache = None
    _no_crypto_warned = False


# ---------------------------------------------------------------------------
# API pubblica
# ---------------------------------------------------------------------------

def encrypt_valore(plaintext: str, data_dir: Path | None = None) -> str:
    """Cifra ``plaintext``.  Ritorna ``enc:v1:<token>`` o il plaintext
    se la cifratura non è disponibile (fallback trasparente)."""
    if not plaintext or plaintext.startswith(_ENC_PREFIX):
        return plaintext
    f = _get_fernet(data_dir)
    if f is None:
        return plaintext
    try:
        token = f.encrypt(plaintext.encode("utf-8")).decode("utf-8")
        return _ENC_PREFIX + token
    except Exception as e:
        logger.warning("Cifratura fallita, salvo in chiaro: %s", e)
        return plaintext


def decrypt_valore(stored: str, data_dir: Path | None = None) -> str:
    """Decifra ``stored`` se cifrato, altrimenti lo ritorna com'è (legacy)."""
    if not stored or not stored.startswith(_ENC_PREFIX):
        return stored
    f = _get_fernet(data_dir)
    if f is None:
        logger.warning("Vault cifrato ma cryptography non disponibile — "
                        "impossibile decifrare, ritorno placeholder")
        return stored
    token = stored[len(_ENC_PREFIX):]
    try:
        return f.decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception as e:
        logger.warning("Decifratura fallita: %s", e)
        return stored


def is_encrypted(stored: str) -> bool:
    """True se ``stored`` è in formato cifrato."""
    return bool(stored and stored.startswith(_ENC_PREFIX))


def vault_is_encrypted(db_path: str | None = None) -> bool:
    """True se almeno una riga del vault è cifrata."""
    import sqlite3

    from .percorsi import percorso_vault

    path = db_path or str(percorso_vault())
    if not Path(path).exists():
        return False
    try:
        conn = sqlite3.connect(path)
        cur = conn.execute(
            "SELECT valore_reale FROM entita WHERE valore_reale LIKE 'enc:v1:%' LIMIT 1"
        )
        return cur.fetchone() is not None
    except Exception:
        return False
    finally:
        try:
            conn.close()
        except Exception:
            pass
