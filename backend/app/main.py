from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import uuid, httpx
from .config import DATA_DIR, SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD, CORS_ORIGINS
from .storage import collection, read_json, write_json, new_id
from .security import hash_password, verify_password, token_for, current_user, encrypt_secret, decrypt_secret
from .models import InstanceInput, ProjectInput
from .keycloak import KeycloakClient

app = FastAPI(title="Keycloak Flow Designer API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

def init_admin():
    path = collection("users") / "users.json"
    users = read_json(path, {})
    if ADMIN_USERNAME not in users:
        users[ADMIN_USERNAME] = {"password_hash": hash_password(ADMIN_PASSWORD), "role": "admin"}
        write_json(path, users)

def get_instance(instance_id: str):
    data = read_json(collection("instances") / "instances.json", {})
    if instance_id not in data:
        raise HTTPException(404, "Instance inconnue")
    item = data[instance_id].copy()
    item["client_secret"] = decrypt_secret(item["client_secret"])
    return item

def kc(instance_id: str):
    item = get_instance(instance_id)
    return KeycloakClient(item["base_url"], item["token_url"], item["client_id"], item["client_secret"], item.get("verify_tls", True))

@app.on_event("startup")
def startup():
    init_admin()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/api/auth/login")
def login(data: OAuth2PasswordRequestForm = Depends()):
    users = read_json(collection("users") / "users.json", {})
    user = users.get(data.username)
    if not user or not verify_password(data.password, user["password_hash"]):
        raise HTTPException(401, "Identifiants incorrects")
    return {"access_token": token_for(data.username), "token_type": "bearer", "username": data.username}

@app.get("/api/auth/me")
def me(user=Depends(current_user)):
    return user

@app.get("/api/instances")
def list_instances(user=Depends(current_user)):
    data = read_json(collection("instances") / "instances.json", {})
    return [{"id": k, "name": v["name"], "base_url": v["base_url"], "verify_tls": v["verify_tls"]} for k,v in data.items()]

@app.post("/api/instances")
def add_instance(payload: InstanceInput, user=Depends(current_user)):
    data = read_json(collection("instances") / "instances.json", {})
    ident = new_id()
    data[ident] = {**payload.model_dump(exclude={"client_secret"}), "client_secret": encrypt_secret(payload.client_secret)}
    write_json(collection("instances") / "instances.json", data)
    return {"id": ident, "name": payload.name}

@app.delete("/api/instances/{instance_id}")
def delete_instance(instance_id: str, user=Depends(current_user)):
    data = read_json(collection("instances") / "instances.json", {})
    if instance_id not in data: raise HTTPException(404, "Instance inconnue")
    del data[instance_id]; write_json(collection("instances") / "instances.json", data)
    return {"deleted": True}

@app.post("/api/instances/{instance_id}/test")
async def test_instance(instance_id: str, user=Depends(current_user)):
    try:
        token = await kc(instance_id).token()
        return {"ok": True, "message": "Authentification client_credentials réussie"}
    except httpx.HTTPError as exc:
        raise HTTPException(502, f"Connexion Keycloak impossible : {exc}")

@app.get("/api/instances/{instance_id}/realms")
async def realms(instance_id: str, user=Depends(current_user)):
    try: return await kc(instance_id).realms()
    except httpx.HTTPError as exc: raise HTTPException(502, str(exc))

@app.get("/api/instances/{instance_id}/realms/{realm}/flows")
async def flows(instance_id: str, realm: str, user=Depends(current_user)):
    try: return await kc(instance_id).flows(realm)
    except httpx.HTTPError as exc: raise HTTPException(502, str(exc))

@app.get("/api/instances/{instance_id}/realms/{realm}/flows/{alias}/executions")
async def executions(instance_id: str, realm: str, alias: str, user=Depends(current_user)):
    try: return await kc(instance_id).executions(realm, alias)
    except httpx.HTTPError as exc: raise HTTPException(502, str(exc))

@app.get("/api/instances/{instance_id}/realms/{realm}/catalog")
async def catalog(instance_id: str, realm: str, user=Depends(current_user)):
    try:
        providers = await kc(instance_id).authenticator_providers(realm)
        return {"source": "keycloak", "providers": providers}
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return {"source": "fallback", "warning": "Endpoint de découverte non disponible sur cette version; catalogue de base fourni.", "providers": [
                {"id":"auth-cookie","displayName":"Cookie","category":"session"},
                {"id":"auth-spnego","displayName":"Kerberos","category":"federation"},
                {"id":"auth-username-password-form","displayName":"Username Password Form","category":"credentials"},
                {"id":"auth-otp-form","displayName":"OTP Form","category":"mfa"},
                {"id":"auth-webauthn","displayName":"WebAuthn Authenticator","category":"mfa"},
                {"id":"identity-provider-redirector","displayName":"Identity Provider Redirector","category":"federation"}
            ]}
        raise HTTPException(502, str(exc))
    except httpx.HTTPError as exc: raise HTTPException(502, str(exc))

@app.get("/api/projects")
def list_projects(user=Depends(current_user)):
    folder = collection("projects")
    result = []
    for path in folder.glob("*.json"):
        obj = read_json(path, {})
        result.append({"id": path.stem, "name": obj.get("project", {}).get("name", path.stem), "updatedAt": obj.get("updatedAt")})
    return result

@app.post("/api/projects")
def save_project(payload: ProjectInput, user=Depends(current_user)):
    ident = payload.project.get("id") or new_id()
    payload.project["id"] = ident
    from datetime import datetime, timezone
    obj = {**payload.model_dump(), "updatedAt": datetime.now(timezone.utc).isoformat()}
    write_json(collection("projects") / f"{ident}.json", obj)
    return obj

@app.get("/api/projects/{project_id}")
def get_project(project_id: str, user=Depends(current_user)):
    path = collection("projects") / f"{project_id}.json"
    if not path.exists(): raise HTTPException(404, "Projet introuvable")
    return read_json(path, {})

@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str, user=Depends(current_user)):
    path = collection("projects") / f"{project_id}.json"
    if not path.exists(): raise HTTPException(404, "Projet introuvable")
    path.unlink()
    return {"deleted": True}

@app.post("/api/projects/{project_id}/validate")
def validate_project(project_id: str, user=Depends(current_user)):
    path = collection("projects") / f"{project_id}.json"
    if not path.exists(): raise HTTPException(404, "Projet introuvable")
    obj = read_json(path, {})
    errors, warnings = [], []
    flow = obj.get("flow", {})
    if not flow.get("alias"): errors.append("L'alias du flow est obligatoire.")
    if not flow.get("providerId"): errors.append("Le providerId du flow est obligatoire.")
    def walk(nodes, parent="root"):
        for node in nodes:
            if node.get("type") not in ("execution", "subflow"): errors.append(f"Type de nœud inconnu : {node.get('type')}")
            if node.get("type") == "execution" and not node.get("providerId"): errors.append(f"Provider absent pour {node.get('displayName','composant')}")
            if node.get("requirement") not in ("REQUIRED","ALTERNATIVE","CONDITIONAL","DISABLED"): errors.append(f"Requirement invalide pour {node.get('displayName','composant')}")
            if node.get("type") == "subflow": walk(node.get("children", []), node.get("nodeId"))
    walk(flow.get("nodes", []))
    if not flow.get("nodes"): warnings.append("Le flow ne contient aucune exécution.")
    return {"valid": not errors, "errors": errors, "warnings": warnings}

@app.post("/api/projects/{project_id}/deploy/preview")
def deploy_preview(project_id: str, user=Depends(current_user)):
    path = collection("projects") / f"{project_id}.json"
    if not path.exists(): raise HTTPException(404, "Projet introuvable")
    return {"status":"not_implemented", "message":"Le moteur de déploiement transactionnel doit être activé après qualification sur la version Keycloak cible.", "requiresConfirmation":False, "project":read_json(path,{})["project"]["name"]}
