# PrivacyBridge — © 2026 Andrea Sforna — Licenza MIT
"""Configurazione condivisa per pytest.

- Isola ``PRIVACYBRIDGE_DATA_DIR`` in una directory temporanea prima
  di qualsiasi import di ``backend.*``: così le impostazioni
  persistenti (``impostazioni.json``, ``log.txt``, vault residuo)
  che potrebbero trovarsi nel profilo utente reale non contaminano
  i test.
"""

from __future__ import annotations

import os
import tempfile

# ``src`` finisce su sys.path via ``pythonpath`` in pyproject.toml.

if "PRIVACYBRIDGE_DATA_DIR" not in os.environ:
    _tmpdir = tempfile.mkdtemp(prefix="pb-tests-")
    os.environ["PRIVACYBRIDGE_DATA_DIR"] = _tmpdir
