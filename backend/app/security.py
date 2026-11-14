from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from passlib.context import CryptContext
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from .config import SECRET_KEY, ENCRYPTION_KEY
from .storage import collection, read_json, write_json

ALGORITHM = "HS256"
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def hash_password(value: str):
    return pwd.hash(value)

def verify_password(value: str, hashed: str):
    return pwd.verify(value, hashed)

def token_for(username: str):
    exp = datetime.now(timezone.utc) + timedelta(hours=8)
    return jwt.encode({"sub": username, "exp": exp}, SECRET_KEY, algorithm=ALGORITHM)

def current_user(token: str = Depends(oauth2)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise ValueError()
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Session invalide ou expirée")
    users = read_json(collection("users") / "users.json", {})
    if username not in users:
        raise HTTPException(status_code=401, detail="Utilisateur inconnu")
    return {"username": username, "role": users[username].get("role", "admin")}

def cipher():
    if not ENCRYPTION_KEY:
        raise RuntimeError("ENCRYPTION_KEY doit être définie pour stocker les secrets.")
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
        raise RuntimeError("Impossible de déchiffrer le secret enregistré.") from exc
