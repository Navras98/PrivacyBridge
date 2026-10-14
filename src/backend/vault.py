# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Vault SQLite per la persistenza delle entità anonimizzate.

Ogni sessione contiene una mappatura bidirezionale placeholder <-> valore_reale.
Il file di default è quello indicato da ``percorsi.percorso_vault()``: la
cartella dati dell'utente, non il bundle dell'app.

I valori originali sono in chiaro — è ciò che rende possibile il
ripristino — quindi il file è ristretto al solo proprietario (0600).
"""

from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Self

from .percorsi import percorso_vault

DEFAULT_DB_PATH = str(percorso_vault())

# Cifratura at-rest opzionale (vault_crypto.py).  Se cryptography non è
# disponibile o la chiave non è recuperabile, i metodi encrypt/decrypt
# diventano no-op — l'app non si blocca mai per la cifratura.
try:
    from .vault_crypto import decrypt_valore, encrypt_valore  # noqa: F401
    _HAS_CRYPTO = True
except ImportError:
    _HAS_CRYPTO = False

    def encrypt_valore(v: str, data_dir=None) -> str:  # type: ignore[no-redef]
        return v

    def decrypt_valore(v: str, data_dir=None) -> str:  # type: ignore[no-redef]
        return v


def _restringi_al_proprietario(db_path: str) -> None:
    """Rende il vault leggibile solo dall'utente che lo possiede.

    Il default del filesystem è 0644: su una macchina condivisa — un PC
    aziendale con più account — qualunque altro utente potrebbe leggere
    i valori originali, che qui stanno in chiaro. WAL e SHM contengono
    le stesse righe e vanno ristretti insieme al database.
    """
    for p in (db_path, db_path + "-wal", db_path + "-shm"):
        try:
            os.chmod(p, 0o600)
        except OSError:
            # Sidecar non ancora creato, oppure filesystem senza
            # permessi POSIX (una condivisione di rete): non è un
            # motivo per rifiutarsi di aprire il vault.
            pass


_SCHEMA_TABELLE = """
CREATE TABLE IF NOT EXISTS entita (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    sessione_id   TEXT    NOT NULL,
    placeholder   TEXT    NOT NULL,
    valore_reale  TEXT    NOT NULL,
    valore_hash   TEXT,
    tipo          TEXT    NOT NULL,
    chiave_norm   TEXT,
    created_at    TEXT    NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ent_ph
    ON entita (sessione_id, placeholder);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ent_val
    ON entita (sessione_id, valore_reale);

CREATE INDEX IF NOT EXISTS idx_ent_tipo
    ON entita (sessione_id, tipo);
"""

_SCHEMA_RUBRICA = """
-- Rubrica personale (FASE 2.3): termini che l'utente ha marcato come
-- "sempre da anonimizzare" (nomi di clienti, aziende ricorrenti, ecc.).
-- Il match è deterministico ed ha priorità sopra ogni recognizer.
-- I dati NON escono mai dalla macchina (come tutto il resto).
CREATE TABLE IF NOT EXISTS rubrica (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    testo         TEXT    NOT NULL,
    tipo          TEXT    NOT NULL,
    created_at    TEXT    NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_rub_testo
    ON rubrica (testo);

CREATE INDEX IF NOT EXISTS idx_rub_tipo
    ON rubrica (tipo);
"""

# Indici che dipendono da colonne aggiunte via ALTER TABLE: vanno
# creati DOPO la migrazione, non insieme al CREATE TABLE.
_SCHEMA_INDICI_MIGRATI = """
CREATE INDEX IF NOT EXISTS idx_ent_chiave
    ON entita (sessione_id, tipo, chiave_norm);
CREATE UNIQUE INDEX IF NOT EXISTS idx_ent_valore_hash
    ON entita (sessione_id, valore_hash);
"""


class Vault:
    """Wrapper attorno al database SQLite del vault.

    In ``batch_mode=True`` (single-thread) tutte le lookup usano un dict in
    memoria e le INSERT vengono accumulate in una coda flushata in un'unica
    transazione SQLite da ``flush()`` / ``close()``.  Non usa RLock perché
    l'accesso è mono-thread.
    """

    def __init__(
        self,
        db_path: str | None = None,
        *,
        batch_mode: bool = False,
    ) -> None:
        self.db_path = db_path or DEFAULT_DB_PATH
        self._batch_mode = batch_mode
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        # Ordine: (1) tabelle base + indici non-migrati, (2) migrazione
        # ALTER TABLE per DB pre-GRUPPO A, (3) indici che dipendono
        # dalla colonna migrata, (4) rubrica.
        self._conn.executescript(_SCHEMA_TABELLE)
        try:
            cols = [r[1] for r in self._conn.execute("PRAGMA table_info(entita)")]
            if "chiave_norm" not in cols:
                self._conn.execute("ALTER TABLE entita ADD COLUMN chiave_norm TEXT")
            if "valore_hash" not in cols:
                self._conn.execute("ALTER TABLE entita ADD COLUMN valore_hash TEXT")
                # Backfill hash per le righe legacy (valore in chiaro).
                try:
                    import hashlib
                    for row in self._conn.execute("SELECT id, valore_reale FROM entita WHERE valore_hash IS NULL"):
                        h = hashlib.sha256(row[1].encode("utf-8")).hexdigest()
                        self._conn.execute("UPDATE entita SET valore_hash=? WHERE id=?", (h, row[0]))
                except Exception:
                    pass
        except sqlite3.Error:
            pass
        self._conn.executescript(_SCHEMA_INDICI_MIGRATI)
        self._conn.executescript(_SCHEMA_RUBRICA)
        # Dopo gli executescript: WAL e SHM esistono solo da qui in poi.
        _restringi_al_proprietario(self.db_path)

        if not batch_mode:
            self._lock: threading.RLock | None = threading.RLock()
        else:
            self._lock = None

        # Cache in memoria (batch_mode only).
        self._cache_by_valore: dict[tuple[str, str], sqlite3.Row] = {}
        self._cache_by_placeholder: dict[tuple[str, str], sqlite3.Row] = {}
        self._counters: dict[tuple[str, str], int] = {}
        self._pending: list[tuple[str, str, str, str, str]] = []

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def close(self) -> None:
        if self._batch_mode:
            self.flush()
        try:
            self._conn.close()
        except sqlite3.Error:
            pass

    def rollback(self) -> None:
        """Scarta INSERT pendenti senza scriverli su DB (batch_mode).

        Da chiamare in caso di eccezione per garantire che nessuna entità
        parziale rimanga in memoria o venga scritta sul DB.
        """
        if self._batch_mode:
            self._pending.clear()
            self._cache_by_valore.clear()
            self._cache_by_placeholder.clear()
            self._counters.clear()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Preload (batch_mode only)
    # ------------------------------------------------------------------

    def preload_session(self, sessione_id: str) -> None:
        """Carica in memoria le entità già presenti in DB per la sessione.

        Va chiamato prima di usare il vault in batch_mode su sessioni
        che potrebbero avere dati precedenti su SQLite.
        """
        cur = self._conn.execute(
            "SELECT * FROM entita WHERE sessione_id=? ORDER BY id ASC",
            (sessione_id,),
        )
        for raw in cur.fetchall():
            row = dict(raw)
            # Decifra valore_reale se cifrato (migrazione trasparente).
            vr_enc = row["valore_reale"]
            vr = decrypt_valore(vr_enc) if _HAS_CRYPTO else vr_enc
            if vr != vr_enc:
                row["valore_reale"] = vr
            ph = row["placeholder"]
            tp = row["tipo"]
            self._cache_by_valore[(sessione_id, vr)] = row
            self._cache_by_placeholder[(sessione_id, ph)] = row
            key = (sessione_id, tp)
            self._counters[key] = self._counters.get(key, 0) + 1

    # ------------------------------------------------------------------
    # Flush (batch_mode only)
    # ------------------------------------------------------------------

    def flush(self) -> None:
        """Scrive in SQLite tutti gli INSERT accumulati in un'unica transazione."""
        if not self._pending:
            return
        self._conn.execute("BEGIN")
        try:
            # _pending contiene già valore_reale cifrato + valore_hash
            # se _HAS_CRYPTO, altrimenti plaintext senza hash.
            has_hash = self._pending and len(self._pending[0]) == 7
            if has_hash:
                self._conn.executemany(
                    "INSERT OR IGNORE INTO entita "
                    "(sessione_id, placeholder, valore_reale, valore_hash, tipo, chiave_norm, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    self._pending,
                )
            else:
                self._conn.executemany(
                    "INSERT OR IGNORE INTO entita "
                    "(sessione_id, placeholder, valore_reale, tipo, chiave_norm, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    self._pending,
                )
            self._conn.execute("COMMIT")
        except Exception:
            self._conn.execute("ROLLBACK")
            raise
        self._pending.clear()

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------

    def get_by_valore(
        self, sessione_id: str, valore_reale: str
    ) -> sqlite3.Row | None:
        if self._batch_mode:
            return self._cache_by_valore.get((sessione_id, valore_reale))
        # Lookup via hash deterministico (Fernet è non-deterministico,
        # quindi non possiamo cercare per valore_reale cifrato).
        if _HAS_CRYPTO:
            import hashlib
            h = hashlib.sha256(valore_reale.encode("utf-8")).hexdigest()
            with self._lock:
                cur = self._conn.execute(
                    "SELECT * FROM entita WHERE sessione_id=? AND valore_hash=?",
                    (sessione_id, h),
                )
                row = cur.fetchone()
                if row is not None:
                    return self._decrypt_row(row)
                # Fallback legacy: righe senza hash (pre-migrazione)
                cur = self._conn.execute(
                    "SELECT * FROM entita WHERE sessione_id=? AND valore_reale=?",
                    (sessione_id, valore_reale),
                )
                row = cur.fetchone()
                if row is not None:
                    return row
                return None
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM entita WHERE sessione_id=? AND valore_reale=?",
                (sessione_id, valore_reale),
            )
            return cur.fetchone()

    def _decrypt_row(self, row: sqlite3.Row) -> dict:
        """Decifra valore_reale di una riga SQLite e ritorna un dict."""
        d = dict(row)
        d["valore_reale"] = decrypt_valore(d["valore_reale"])
        return d

    def get_by_placeholder(
        self, sessione_id: str, placeholder: str
    ) -> sqlite3.Row | None:
        if self._batch_mode:
            return self._cache_by_placeholder.get((sessione_id, placeholder))
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM entita WHERE sessione_id=? AND placeholder=?",
                (sessione_id, placeholder),
            )
            row = cur.fetchone()
            if row is None:
                return None
            if _HAS_CRYPTO:
                return self._decrypt_row(row)
            return row

    def next_index(self, sessione_id: str, tipo: str) -> int:
        """Restituisce il prossimo numero progressivo per un dato tipo."""
        if self._batch_mode:
            key = (sessione_id, tipo)
            self._counters[key] = self._counters.get(key, 0) + 1
            return self._counters[key]
        with self._lock:
            cur = self._conn.execute(
                "SELECT COUNT(*) AS c FROM entita WHERE sessione_id=? AND tipo=?",
                (sessione_id, tipo),
            )
            row = cur.fetchone()
            return int(row["c"]) + 1

    def add(
        self,
        sessione_id: str,
        placeholder: str,
        valore_reale: str,
        tipo: str,
        chiave_norm: str | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        # Cifra valore_reale per la persistenza; la cache resta in chiaro
        # per le lookup veloci (chiave = plaintext).
        if _HAS_CRYPTO:
            import hashlib
            valore_enc = encrypt_valore(valore_reale)
            valore_hash = hashlib.sha256(valore_reale.encode("utf-8")).hexdigest()
        else:
            valore_enc = valore_reale
            valore_hash = None
        if self._batch_mode:
            row: dict = {
                "sessione_id": sessione_id,
                "placeholder": placeholder,
                "valore_reale": valore_reale,
                "valore_hash": valore_hash,
                "tipo": tipo,
                "chiave_norm": chiave_norm,
                "created_at": now,
            }
            self._cache_by_valore[(sessione_id, valore_reale)] = row
            self._cache_by_placeholder[(sessione_id, placeholder)] = row
            if _HAS_CRYPTO:
                self._pending.append(
                    (sessione_id, placeholder, valore_enc, valore_hash, tipo, chiave_norm, now)
                )
            else:
                self._pending.append(
                    (sessione_id, placeholder, valore_enc, tipo, chiave_norm, now)
                )
            return
        with self._lock:
            if _HAS_CRYPTO:
                self._conn.execute(
                    "INSERT OR IGNORE INTO entita "
                    "(sessione_id, placeholder, valore_reale, valore_hash, tipo, chiave_norm, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (sessione_id, placeholder, valore_enc, valore_hash, tipo, chiave_norm, now),
                )
            else:
                self._conn.execute(
                    "INSERT OR IGNORE INTO entita "
                    "(sessione_id, placeholder, valore_reale, tipo, chiave_norm, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (sessione_id, placeholder, valore_reale, tipo, chiave_norm, now),
                )

    def all_for_session(self, sessione_id: str) -> Iterable[sqlite3.Row]:
        if self._batch_mode:
            return [v for k, v in self._cache_by_valore.items() if k[0] == sessione_id]
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM entita WHERE sessione_id=? ORDER BY id ASC",
                (sessione_id,),
            )
            rows = cur.fetchall()
            if _HAS_CRYPTO:
                return [self._decrypt_row(r) for r in rows]
            return rows

    def all_sessions(self) -> list[sqlite3.Row]:
        sql = (
            "SELECT sessione_id, COUNT(*) AS entita, MAX(created_at) AS ultimo "
            "FROM entita GROUP BY sessione_id ORDER BY ultimo DESC"
        )
        if self._lock:
            with self._lock:
                return self._conn.execute(sql).fetchall()
        return self._conn.execute(sql).fetchall()

    # ------------------------------------------------------------------
    # Rubrica personale (FASE 2.3)
    # ------------------------------------------------------------------
    #
    # Metodi separati dalla tabella entità perché la rubrica NON è
    # sessione-scoped: è globale per l'installazione, condivisa fra
    # tutte le anonimizzazioni. Ha priorità sopra ogni recognizer.

    def rubrica_add(self, testo: str, tipo: str) -> None:
        """Aggiunge un termine alla rubrica. Se già presente, aggiorna
        il tipo. Idempotente."""
        now = datetime.now(UTC).isoformat()
        testo = (testo or "").strip()
        tipo = (tipo or "ALTRO").strip().upper() or "ALTRO"
        if not testo:
            return
        if self._lock:
            with self._lock:
                self._conn.execute(
                    "INSERT INTO rubrica (testo, tipo, created_at) VALUES (?,?,?) "
                    "ON CONFLICT(testo) DO UPDATE SET tipo=excluded.tipo",
                    (testo, tipo, now),
                )
        else:
            self._conn.execute(
                "INSERT INTO rubrica (testo, tipo, created_at) VALUES (?,?,?) "
                "ON CONFLICT(testo) DO UPDATE SET tipo=excluded.tipo",
                (testo, tipo, now),
            )

    def rubrica_remove(self, testo: str) -> None:
        testo = (testo or "").strip()
        if not testo:
            return
        if self._lock:
            with self._lock:
                self._conn.execute("DELETE FROM rubrica WHERE testo=?", (testo,))
        else:
            self._conn.execute("DELETE FROM rubrica WHERE testo=?", (testo,))

    def rubrica_all(self) -> list[sqlite3.Row]:
        sql = "SELECT id, testo, tipo, created_at FROM rubrica ORDER BY testo COLLATE NOCASE"
        if self._lock:
            with self._lock:
                return self._conn.execute(sql).fetchall()
        return self._conn.execute(sql).fetchall()

    def rubrica_count(self) -> int:
        if self._lock:
            with self._lock:
                return int(self._conn.execute("SELECT COUNT(*) FROM rubrica").fetchone()[0])
        return int(self._conn.execute("SELECT COUNT(*) FROM rubrica").fetchone()[0])

    def clear_session(self, sessione_id: str) -> None:
        if self._batch_mode:
            keys_to_del = [k for k in self._cache_by_valore if k[0] == sessione_id]
            for k in keys_to_del:
                del self._cache_by_valore[k]
            keys_to_del = [k for k in self._cache_by_placeholder if k[0] == sessione_id]
            for k in keys_to_del:
                del self._cache_by_placeholder[k]
            keys_to_del = [k for k in self._counters if k[0] == sessione_id]
            for k in keys_to_del:
                del self._counters[k]
            self._pending = [p for p in self._pending if p[0] != sessione_id]
        if self._lock:
            with self._lock:
                self._conn.execute(
                    "DELETE FROM entita WHERE sessione_id=?",
                    (sessione_id,),
                )
        else:
            self._conn.execute(
                "DELETE FROM entita WHERE sessione_id=?",
                (sessione_id,),
            )
