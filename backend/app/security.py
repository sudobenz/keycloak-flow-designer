from datetime import datetime, timedelta, timezone
from hashlib import scrypt
from hmac import compare_digest
import jwt
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from .config import SECRET_KEY, ENCRYPTION_KEY
from .storage import collection, read_json, write_json

ALGORITHM = "HS256"
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    if len(password) < 12:
        raise ValueError("Le mot de passe doit contenir au moins 12 caractères.")
    salt = __import__('secrets').token_bytes(16)
    digest = scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = encoded.split("$", 2)
        if scheme != "scrypt":
            return False
        expected = bytes.fromhex(digest_hex)
        actual = scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1, dklen=len(expected))
        return compare_digest(actual, expected)
    except Exception:
        return False


def token_for(username: str, role: str):
    exp = datetime.now(timezone.utc) + timedelta(hours=8)
    return jwt.encode({"sub": username, "role": role, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)


def current_user(token: str = Depends(oauth2)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise ValueError()
    except (jwt.InvalidTokenError, ValueError):
        raise HTTPException(status_code=401, detail="Session invalide ou expirée")
    users = read_json(collection("users") / "users.json", {})
    entry = users.get(username)
    if not entry or entry.get("disabled"):
        raise HTTPException(status_code=401, detail="Utilisateur inconnu ou désactivé")
    return {"username": username, "role": entry.get("role", "viewer")}


def require_editor(user=Depends(current_user)):
    if user["role"] not in ("admin", "editor"):
        raise HTTPException(status_code=403, detail="Droits éditeur requis")
    return user


def require_admin(user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Droits administrateur requis")
    return user


def cipher():
    if not ENCRYPTION_KEY:
        raise RuntimeError("ENCRYPTION_KEY non définie. Générer une clé Fernet.")
    try:
        return Fernet(ENCRYPTION_KEY.encode())
    except Exception as exc:
        raise RuntimeError("ENCRYPTION_KEY invalide : générer une clé Fernet.") from exc


def encrypt_secret(value: str):
    return cipher().encrypt(value.encode()).decode()


def decrypt_secret(value: str):
    try:
        return cipher().decrypt(value.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("Impossible de déchiffrer le secret enregistré. Vérifier ENCRYPTION_KEY.") from exc
