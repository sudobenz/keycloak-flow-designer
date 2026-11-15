from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from pathlib import Path
from urllib.parse import quote
from datetime import datetime, timezone
import json, uuid, re, time
from contextlib import asynccontextmanager
import httpx
from .config import DATA_DIR, SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD, CORS_ORIGINS
from .storage import collection, read_json, write_json, new_id, audit
from .security import hash_password, verify_password, token_for, current_user, encrypt_secret, decrypt_secret, require_admin, require_editor
from .models import InstanceInput, LoginInput
from .keycloak import KeycloakClient
from .workflows import import_full_flow, validate_project, diff_nodes
from .deployment import deploy_project, validate_against_keycloak, DeploymentError
from .project_security import protect_project_secrets, restore_project_secrets

@asynccontextmanager
async def lifespan(app):
    init_admin()
    yield

app = FastAPI(title="Keycloak Flow Designer API", version="1.0.6", description="Conception, import, validation et déploiement contrôlé des Authentication Flows Keycloak.", docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=True, allow_methods=["GET","POST","PUT","PATCH","DELETE"], allow_headers=["Authorization","Content-Type"])
LOGIN_ATTEMPTS = {}
LOGIN_WINDOW_SECONDS = 600
LOGIN_MAX_ATTEMPTS = 5

class DeployRequest(BaseModel):
    instanceId: str
    realm: str
    mode: str = "create"
    alias: str = Field(min_length=1, max_length=100)
    allowDeletes: bool = False
    confirmation: str

class DuplicateRequest(BaseModel):
    newAlias: str = Field(min_length=1, max_length=100)

class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9._-]+$")
    password: str = Field(min_length=12, max_length=128)
    role: str = "editor"

class PasswordChange(BaseModel):
    currentPassword: str
    newPassword: str = Field(min_length=12, max_length=128)

class ProjectEnvelope(BaseModel):
    schemaVersion: str = "1.0"
    project: dict
    target: dict = Field(default_factory=dict)
    flow: dict

def init_admin():
    path = collection("users") / "users.json"
    users = read_json(path, {})
    if ADMIN_USERNAME not in users:
        users[ADMIN_USERNAME] = {"password_hash": hash_password(ADMIN_PASSWORD), "role": "admin", "disabled": False, "createdAt": datetime.now(timezone.utc).isoformat()}
        write_json(path, users)

def get_instance(instance_id: str):
    data = read_json(collection("instances") / "instances.json", {})
    if instance_id not in data: raise HTTPException(404, "Instance inconnue")
    item = data[instance_id].copy()
    item["client_secret"] = decrypt_secret(item["client_secret"])
    return item

def kc(instance_id: str):
    item = get_instance(instance_id)
    return KeycloakClient(item["base_url"], item["token_url"], item["client_id"], item["client_secret"], item.get("verify_tls", True))

def safe_project_path(project_id: str):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", project_id): raise HTTPException(400, "Identifiant projet invalide")
    return collection("projects") / f"{project_id}.json"

def project_get(project_id):
    path=safe_project_path(project_id)
    if not path.exists(): raise HTTPException(404,"Projet introuvable")
    return restore_project_secrets(read_json(path,{}))

@app.get("/health")
def health(): return {"status":"ok","version":"1.0.6"}

@app.post("/api/auth/login")
def login(data: LoginInput, request: Request):
    key=f"{request.client.host if request.client else 'unknown'}:{data.username.lower()}"
    now=time.monotonic()
    attempts=[stamp for stamp in LOGIN_ATTEMPTS.get(key,[]) if now-stamp<LOGIN_WINDOW_SECONDS]
    if len(attempts)>=LOGIN_MAX_ATTEMPTS:
        LOGIN_ATTEMPTS[key]=attempts
        raise HTTPException(429,"Trop de tentatives. Réessayer dans dix minutes.")
    users=read_json(collection("users")/"users.json",{})
    user=users.get(data.username)
    if not user or user.get("disabled") or not verify_password(data.password,user["password_hash"]):
        attempts.append(now); LOGIN_ATTEMPTS[key]=attempts
        raise HTTPException(401,"Identifiants incorrects")
    LOGIN_ATTEMPTS.pop(key,None)
    audit("login",data.username)
    return {"access_token":token_for(data.username,user.get("role","viewer")),"token_type":"bearer","username":data.username,"role":user.get("role","viewer")}

@app.get("/api/auth/me")
def me(user=Depends(current_user)): return user

@app.post("/api/auth/password")
def change_password(data: PasswordChange, user=Depends(current_user)):
    users=read_json(collection("users")/"users.json",{}); entry=users[user["username"]]
    if not verify_password(data.currentPassword,entry["password_hash"]): raise HTTPException(400,"Mot de passe actuel incorrect")
    entry["password_hash"]=hash_password(data.newPassword); users[user["username"]]=entry; write_json(collection("users")/"users.json",users)
    audit("password_changed",user["username"])
    return {"changed":True}

@app.get("/api/users")
def list_users(user=Depends(require_admin)):
    users=read_json(collection("users")/"users.json",{})
    return [{"username":k,"role":v.get("role"),"disabled":v.get("disabled",False),"createdAt":v.get("createdAt")} for k,v in users.items()]

@app.post("/api/users")
def create_user(data: UserCreate, user=Depends(require_admin)):
    if data.role not in ("admin","editor","viewer"): raise HTTPException(400,"Rôle invalide")
    users=read_json(collection("users")/"users.json",{})
    if data.username in users: raise HTTPException(409,"Utilisateur déjà présent")
    users[data.username]={"password_hash":hash_password(data.password),"role":data.role,"disabled":False,"createdAt":datetime.now(timezone.utc).isoformat()}
    write_json(collection("users")/"users.json",users); audit("user_created",user["username"],{"username":data.username,"role":data.role})
    return {"username":data.username,"role":data.role}

@app.patch("/api/users/{username}/disabled")
def disable_user(username: str, disabled: bool, user=Depends(require_admin)):
    users=read_json(collection("users")/"users.json",{})
    if username not in users: raise HTTPException(404,"Utilisateur inconnu")
    if username==user["username"] and disabled: raise HTTPException(400,"Impossible de désactiver sa propre session")
    users[username]["disabled"]=disabled; write_json(collection("users")/"users.json",users); audit("user_disabled_changed",user["username"],{"username":username,"disabled":disabled})
    return {"username":username,"disabled":disabled}

@app.get("/api/instances")
def list_instances(user=Depends(current_user)):
    data=read_json(collection("instances")/"instances.json",{})
    return [{"id":k,"name":v["name"],"base_url":v["base_url"],"verify_tls":v["verify_tls"]} for k,v in data.items()]

@app.post("/api/instances")
def add_instance(payload: InstanceInput, user=Depends(require_admin)):
    if not payload.base_url.startswith(("https://","http://")) or not payload.token_url.startswith(("https://","http://")):
        raise HTTPException(400,"Les URL doivent commencer par http:// ou https://")
    data=read_json(collection("instances")/"instances.json",{}); ident=new_id()
    data[ident]={**payload.model_dump(exclude={"client_secret"}),"client_secret":encrypt_secret(payload.client_secret)}
    write_json(collection("instances")/"instances.json",data); audit("instance_created",user["username"],{"instanceId":ident,"name":payload.name})
    return {"id":ident,"name":payload.name}

@app.delete("/api/instances/{instance_id}")
def delete_instance(instance_id: str, user=Depends(require_admin)):
    data=read_json(collection("instances")/"instances.json",{})
    if instance_id not in data: raise HTTPException(404,"Instance inconnue")
    del data[instance_id]; write_json(collection("instances")/"instances.json",data); audit("instance_deleted",user["username"],{"instanceId":instance_id})
    return {"deleted":True}

@app.post("/api/instances/{instance_id}/test")
async def test_instance(instance_id: str, user=Depends(require_editor)):
    client=kc(instance_id)
    try:
        await client.token(); info=await client.server_info()
        return {"ok":True,"message":"Authentification client_credentials réussie","version":(info or {}).get("systemInfo",{}).get("version") or (info or {}).get("version"),"serverInfo":info}
    except httpx.HTTPError as exc: raise HTTPException(502,f"Connexion Keycloak impossible : {exc}")

@app.get("/api/instances/{instance_id}/info")
async def instance_info(instance_id: str, user=Depends(require_editor)):
    try: return await kc(instance_id).server_info()
    except httpx.HTTPError as exc: raise HTTPException(502,str(exc))

@app.get("/api/instances/{instance_id}/realms")
async def realms(instance_id: str, user=Depends(require_editor)):
    try: return await kc(instance_id).realms()
    except httpx.HTTPError as exc: raise HTTPException(502,str(exc))

@app.get("/api/instances/{instance_id}/realms/{realm}/flows")
async def flows(instance_id: str, realm: str, user=Depends(require_editor)):
    try: return await kc(instance_id).flows(realm)
    except httpx.HTTPError as exc: raise HTTPException(502,str(exc))

@app.get("/api/instances/{instance_id}/realms/{realm}/flows/{alias}/executions")
async def executions(instance_id: str, realm: str, alias: str, user=Depends(require_editor)):
    try: return await kc(instance_id).executions(realm,alias)
    except httpx.HTTPError as exc: raise HTTPException(502,str(exc))

@app.get("/api/instances/{instance_id}/realms/{realm}/flows/{alias}/import")
async def import_flow(instance_id: str, realm: str, alias: str, user=Depends(require_editor)):
    try:
        project=await import_full_flow(kc(instance_id),realm,alias)
        info=await kc(instance_id).server_info()
        project["target"]["instanceId"]=instance_id
        project["target"]["keycloakVersion"]=(info or {}).get("systemInfo",{}).get("version")
        audit("flow_imported",user["username"],{"instanceId":instance_id,"realm":realm,"alias":alias})
        return project
    except KeyError as exc: raise HTTPException(404,str(exc))
    except httpx.HTTPError as exc: raise HTTPException(502,str(exc))

@app.post("/api/instances/{instance_id}/realms/{realm}/flows/{alias}/duplicate")
async def duplicate_flow(instance_id: str, realm: str, alias: str, payload: DuplicateRequest, user=Depends(require_editor)):
    try:
        await kc(instance_id).copy_flow(realm,alias,payload.newAlias)
        imported=await import_full_flow(kc(instance_id),realm,payload.newAlias)
        imported["target"]["instanceId"]=instance_id
        audit("flow_duplicated",user["username"],{"realm":realm,"source":alias,"newAlias":payload.newAlias})
        return imported
    except httpx.HTTPError as exc: raise HTTPException(502,str(exc))

@app.get("/api/instances/{instance_id}/realms/{realm}/catalog")
async def catalog(instance_id: str, realm: str, user=Depends(require_editor)):
    client=kc(instance_id)
    try:
        providers=await client.providers(realm)
        result=[]
        for provider in providers or []:
            provider_id=provider.get("id") or provider.get("providerId")
            item={**provider,"id":provider_id,"configDescription":None}
            if provider_id:
                try: item["configDescription"]=await client.config_description(realm,provider_id)
                except httpx.HTTPStatusError as exc:
                    item["configDescriptionError"]=f"HTTP {exc.response.status_code}"
            result.append(item)
        form_actions=[]; form_providers=[]
        try: form_actions=await client.form_action_providers(realm)
        except httpx.HTTPError: pass
        try: form_providers=await client.form_providers(realm)
        except httpx.HTTPError: pass
        return {"source":"keycloak","providers":result,"formActionProviders":form_actions,"formProviders":form_providers}
    except httpx.HTTPStatusError as exc:
        raise HTTPException(exc.response.status_code,f"Découverte des providers impossible : {exc.response.text[:1000]}")
    except httpx.HTTPError as exc: raise HTTPException(502,str(exc))

@app.get("/api/projects")
def list_projects(user=Depends(current_user)):
    result=[]
    for path in collection("projects").glob("*.json"):
        obj=read_json(path,{})
        result.append({"id":path.stem,"name":obj.get("project",{}).get("name",path.stem),"updatedAt":obj.get("updatedAt"),"realm":obj.get("target",{}).get("realm")})
    return sorted(result,key=lambda x:x.get("updatedAt") or "",reverse=True)

@app.post("/api/projects")
def save_project(payload: ProjectEnvelope, user=Depends(require_editor)):
    ident=payload.project.get("id") or new_id()
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}",ident): raise HTTPException(400,"Identifiant de projet invalide")
    payload.project["id"]=ident
    path=safe_project_path(ident)
    if path.exists():
        previous=read_json(path,{})
        incoming=payload.model_dump()
        previous_core={key:previous.get(key) for key in ("schemaVersion","project","target","flow")}
        if previous_core != incoming:
            history_id=new_id()
            history_dir=collection("history")/ident
            write_json(history_dir/f"{history_id}.json",{"versionId":history_id,"projectId":ident,"createdAt":datetime.now(timezone.utc).isoformat(),"snapshot":previous})
            versions=sorted(history_dir.glob("*.json"),key=lambda x:x.stat().st_mtime,reverse=True)
            for obsolete in versions[50:]: obsolete.unlink(missing_ok=True)
    obj={**payload.model_dump(),"updatedAt":datetime.now(timezone.utc).isoformat(),"updatedBy":user["username"]}
    write_json(path,protect_project_secrets(obj)); audit("project_saved",user["username"],{"projectId":ident})
    return obj

@app.get("/api/projects/{project_id}")
def get_project(project_id: str, user=Depends(current_user)): return project_get(project_id)

@app.get("/api/projects/{project_id}/history")
def project_history(project_id: str, user=Depends(current_user)):
    safe_project_path(project_id)
    folder=collection("history")/project_id
    if not folder.exists(): return []
    items=[]
    for path in folder.glob("*.json"):
        obj=read_json(path,{})
        snapshot=obj.get("snapshot",{})
        items.append({"versionId":obj.get("versionId",path.stem),"createdAt":obj.get("createdAt"),"name":snapshot.get("project",{}).get("name",project_id),"updatedAt":snapshot.get("updatedAt"),"updatedBy":snapshot.get("updatedBy")})
    return sorted(items,key=lambda x:x.get("createdAt") or "",reverse=True)

@app.post("/api/projects/{project_id}/history/{version_id}/restore")
def restore_project_version(project_id: str, version_id: str, user=Depends(require_admin)):
    safe_project_path(project_id)
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}",version_id): raise HTTPException(400,"Identifiant de version invalide")
    version_path=collection("history")/project_id/f"{version_id}.json"
    if not version_path.exists(): raise HTTPException(404,"Version introuvable")
    record=read_json(version_path,{})
    snapshot=restore_project_secrets(record.get("snapshot",{}))
    if not isinstance(snapshot,dict) or snapshot.get("project",{}).get("id")!=project_id:
        raise HTTPException(400,"Snapshot non valide pour ce projet")
    restored=save_project(ProjectEnvelope(**snapshot),user)
    audit("project_version_restored",user["username"],{"projectId":project_id,"versionId":version_id})
    return restored

@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str, user=Depends(require_editor)):
    path=safe_project_path(project_id)
    if not path.exists(): raise HTTPException(404,"Projet introuvable")
    path.unlink(); audit("project_deleted",user["username"],{"projectId":project_id}); return {"deleted":True}

@app.post("/api/projects/{project_id}/validate")
def validate(project_id: str, user=Depends(current_user)):
    return validate_project(project_get(project_id))

@app.post("/api/projects/{project_id}/diff")
async def preview_diff(project_id: str, instanceId: str, realm: str, alias: str, user=Depends(require_editor)):
    obj=project_get(project_id); remote=await import_full_flow(kc(instanceId),realm,alias)
    local_nodes=obj.get("flow",{}).get("nodes",[]); remote_nodes=remote.get("flow",{}).get("nodes",[])
    actions=diff_nodes(local_nodes,remote_nodes)
    return {"source":"Keycloak","targetAlias":alias,"actions":actions,"counts":{a:sum(1 for x in actions if x["action"]==a) for a in ("create","modify","delete")},"note":"La comparaison utilise les identifiants distants présents dans le projet et les propriétés normalisées."}

@app.post("/api/projects/{project_id}/deploy/preview")
async def deploy_preview(project_id: str, payload: DeployRequest, user=Depends(require_editor)):
    obj=project_get(project_id); val=validate_project(obj)
    actions=[]
    exists=False
    if payload.mode not in ("create", "update"):
        val["errors"].append("Mode de déploiement invalide."); val["valid"]=False
    try:
        target_client=kc(payload.instanceId)
        await validate_against_keycloak(target_client,payload.realm,obj)
        remote_flows=await target_client.flows(payload.realm)
        existing=next((f for f in remote_flows if f.get("alias")==payload.alias),None)
        exists=bool(existing)
        if payload.mode=="create" and exists:
            val["errors"].append(f"Un flow nommé '{payload.alias}' existe déjà."); val["valid"]=False
        if payload.mode=="update":
            if not existing: val["errors"].append(f"Flow cible '{payload.alias}' introuvable."); val["valid"]=False
            elif not obj.get("target", {}).get("sourceFlowId"):
                val["errors"].append("Importer d'abord le flow cible avant de demander sa mise à jour."); val["valid"]=False
            elif obj.get("target", {}).get("instanceId") == payload.instanceId and obj.get("target", {}).get("realm") == payload.realm and obj.get("target", {}).get("sourceFlowId") != existing.get("id"):
                val["errors"].append("Le projet ne provient pas de ce flow cible. Réimporter le bon flow avant la mise à jour."); val["valid"]=False
            elif existing.get("builtIn"): val["errors"].append("Un flow natif ne peut pas être modifié directement."); val["valid"]=False
            elif existing.get("providerId") and existing.get("providerId") != obj.get("flow", {}).get("providerId", "basic-flow"):
                val["errors"].append("Le type du flow racine ne peut pas être changé lors d'une mise à jour."); val["valid"]=False
            else:
                remote=await import_full_flow(kc(payload.instanceId),payload.realm,payload.alias)
                actions=diff_nodes(obj.get("flow",{}).get("nodes",[]),remote.get("flow",{}).get("nodes",[]))
    except DeploymentError as exc:
        val["errors"].append(str(exc)); val["valid"]=False
    except httpx.HTTPError as exc:
        val["warnings"].append(f"Contrôle distant indisponible : {exc}")
        val["errors"].append("Prévisualisation impossible sans connexion valide à Keycloak.")
        val["valid"]=False
    return {"valid":val["valid"],"errors":val["errors"],"warnings":val["warnings"],"mode":payload.mode,"targetAlias":payload.alias,"targetExists":exists,"deletesEnabled":payload.allowDeletes,"actions":actions,"counts":{a:sum(1 for x in actions if x["action"]==a) for a in ("create","modify","delete")},"requiresConfirmation":True,"confirmationText":payload.alias,"summary":"Le déploiement modifie le Realm cible. Une sauvegarde sera créée avant modification."}

@app.post("/api/projects/{project_id}/deploy")
async def deploy(project_id: str, payload: DeployRequest, user=Depends(require_admin)):
    if payload.confirmation != payload.alias: raise HTTPException(400,"Confirmation invalide : saisir exactement l'alias cible.")
    obj=project_get(project_id)
    try:
        result=await deploy_project(kc(payload.instanceId),payload.realm,obj,payload.mode,payload.alias,payload.allowDeletes,payload.instanceId)
        audit("flow_deployed",user["username"],{"projectId":project_id,"instanceId":payload.instanceId,"realm":payload.realm,"alias":payload.alias,"result":result.get("status")})
        return result
    except DeploymentError as exc:
        audit("flow_deploy_failed",user["username"],{"projectId":project_id,"alias":payload.alias,"error":str(exc)})
        raise HTTPException(502,str(exc))
    except httpx.HTTPError as exc:
        audit("flow_deploy_failed",user["username"],{"projectId":project_id,"alias":payload.alias,"error":str(exc)})
        raise HTTPException(502,f"Erreur REST Keycloak : {exc}")

@app.get("/api/projects/{project_id}/export.json")
def export_json(project_id: str, user=Depends(current_user)):
    obj=project_get(project_id)
    return Response(content=json.dumps(obj,ensure_ascii=False,indent=2),media_type="application/json",headers={"Content-Disposition":f'attachment; filename="{project_id}.json"'})

@app.get("/api/projects/{project_id}/export.yaml")
def export_yaml(project_id: str, user=Depends(current_user)):
    import yaml
    obj=project_get(project_id)
    manifest={"apiVersion":"kfd.keycloak-flow-designer/v1","kind":"AuthenticationFlowProject","metadata":obj.get("project",{}),"target":obj.get("target",{}),"flow":obj.get("flow",{})}
    return Response(content=yaml.safe_dump(manifest,allow_unicode=True,sort_keys=False),media_type="application/yaml",headers={"Content-Disposition":f'attachment; filename="{project_id}.yaml"'})

@app.post("/api/projects/import")
async def import_project_file(file: UploadFile=File(...), user=Depends(require_editor)):
    if not file.filename or not file.filename.lower().endswith(".json"): raise HTTPException(400,"Fichier JSON attendu")
    if file.size and file.size > 2_000_000: raise HTTPException(413,"Fichier trop volumineux (2 Mo maximum)")
    try: obj=json.loads((await file.read()).decode("utf-8"))
    except Exception: raise HTTPException(400,"JSON invalide")
    if not isinstance(obj,dict) or not isinstance(obj.get("flow"),dict) or not isinstance(obj.get("project"),dict): raise HTTPException(400,"Structure de projet non reconnue")
    obj.setdefault("schemaVersion","1.0"); obj["project"]["id"]=new_id()
    saved=save_project(ProjectEnvelope(**obj),user)
    return saved

@app.get("/api/backups")
def list_backups(user=Depends(require_admin)):
    items=[]
    for path in collection("backups").glob("*.json"):
        obj=read_json(path,{})
        items.append({"id":path.stem,"createdAt":obj.get("createdAt"),"instanceId":obj.get("instanceId"),"realm":obj.get("realm"),"alias":obj.get("alias")})
    return sorted(items,key=lambda x:x.get("createdAt") or "",reverse=True)

@app.get("/api/backups/{backup_id}/export.json")
def export_backup(backup_id: str, user=Depends(require_admin)):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}",backup_id): raise HTTPException(400,"Identifiant de sauvegarde invalide")
    path=collection("backups")/f"{backup_id}.json"
    if not path.exists(): raise HTTPException(404,"Sauvegarde introuvable")
    record=read_json(path,{})
    snapshot=record.get("snapshot")
    if not isinstance(snapshot,dict): raise HTTPException(400,"Snapshot de sauvegarde invalide")
    snapshot=restore_project_secrets(snapshot)
    return Response(content=json.dumps(snapshot,ensure_ascii=False,indent=2),media_type="application/json",headers={"Content-Disposition":f'attachment; filename="keycloak-backup-{backup_id}.json"'})

@app.get("/api/audit")
def get_audit(limit: int=100, user=Depends(require_admin)):
    path=collection("audit")/"events.jsonl"
    if not path.exists(): return []
    rows=[]
    for line in path.read_text(encoding="utf-8").splitlines()[-max(1,min(limit,500)):]:
        try: rows.append(json.loads(line))
        except ValueError: pass
    return list(reversed(rows))
