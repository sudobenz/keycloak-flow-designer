#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -e .env ]]; then echo ".env existe déjà — aucun fichier modifié."; exit 1; fi
command -v python3 >/dev/null || { echo "Python 3 est requis pour générer les secrets." >&2; exit 1; }
cp .env.example .env
SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
ENCRYPTION_KEY="$(python3 -c 'import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())')"
ADMIN_PASSWORD="$(python3 -c 'import secrets; print(secrets.token_urlsafe(18))')"
python3 - "$SECRET_KEY" "$ENCRYPTION_KEY" "$ADMIN_PASSWORD" <<'PY'
from pathlib import Path
import sys
p=Path('.env')
s=p.read_text()
s=s.replace('REPLACE_WITH_RANDOM_SECRET_AT_LEAST_32_CHARS', sys.argv[1])
s=s.replace('REPLACE_WITH_GENERATED_FERNET_KEY', sys.argv[2])
s=s.replace('ChangeThis-Immediately-123!', sys.argv[3])
p.write_text(s)
PY
chmod 600 .env || true
echo "Fichier .env créé. Identifiant initial : admin"
echo "Mot de passe initial : $ADMIN_PASSWORD"
echo "Conservez ce mot de passe et les clés du fichier .env dans un coffre sécurisé."
