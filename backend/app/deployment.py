from copy import deepcopy
from .workflows import import_full_flow, validate_project
from .storage import collection, write_json, new_id
from .project_security import protect_project_secrets
from datetime import datetime, timezone
from urllib.parse import quote

class DeploymentError(RuntimeError): pass

async def _list_exec(kc, realm, alias):
    return await kc.executions(realm, alias) or []

async def _find_created(kc, realm, parent_alias, before_ids, provider_id=None, flow_alias=None):
    after = await _list_exec(kc, realm, parent_alias)
    new_items = [x for x in after if x.get("id") not in before_ids]
    if flow_alias:
        found = next((x for x in new_items if x.get("alias") == flow_alias or x.get("displayName") == flow_alias), None)
    else:
        found = next((x for x in new_items if x.get("providerId") == provider_id), None)
    if not found and len(new_items) == 1: found = new_items[0]
    if not found or not found.get("id"):
        raise DeploymentError(f"Keycloak a accepté l'ajout, mais l'exécution créée n'a pas pu être retrouvée dans {parent_alias}.")
    return found

async def _configure(kc, realm, execution_id, node, existing_execution=True):
    if node.get("configReadWarning"):
        raise DeploymentError(f"Configuration distante de {node.get('displayName')} non lisible ; déploiement bloqué pour éviter une perte de paramètres.")
    cfg = node.get("config") or {}
    config_id = node.get("remoteConfigId") if existing_execution else None
    if not cfg:
        if config_id:
            await kc.delete_authenticator_config(realm, config_id)
        return
    alias = node.get("configAlias") or f"KFD - {node.get('displayName','Execution')}"
    body = {"alias": alias, "config": {str(k): str(v) for k,v in cfg.items()}}
    if config_id:
        try:
            await kc.update_authenticator_config(realm, config_id, {**body, "id": config_id})
            return
        except Exception as exc:
            # Projet importé depuis un autre Realm : l'identifiant de config peut ne pas exister sur la cible.
            response = getattr(exc, "response", None)
            if response is None or response.status_code != 404:
                raise
    await kc.set_execution_config(realm, execution_id, body)

async def _move_execution(kc, realm, parent_alias, execution_id, target_index):
    # L'API Keycloak expose raise/lower-priority ; on réordonne à partir de l'état relu.
    for _ in range(100):
        items = await _list_exec(kc, realm, parent_alias)
        current = next((i for i,x in enumerate(items) if x.get("id") == execution_id), None)
        if current is None: return
        if current == target_index: return
        direction = "raise" if current > target_index else "lower"
        await kc.priority(realm, execution_id, direction)
    raise DeploymentError(f"Impossible de positionner l'exécution {execution_id} dans {parent_alias}.")

async def _sync_children(kc, realm, parent_alias, nodes, allow_deletes=False, created=None, match_untracked=False):
    created = created if created is not None else []
    current = await _list_exec(kc, realm, parent_alias)
    used_ids = set()
    for index, node in enumerate(nodes or []):
        typ = node.get("type")
        remote_id = node.get("remoteExecutionId")
        item = next((x for x in current if remote_id and x.get("id") == remote_id), None)
        existing_execution = item is not None
        if item is None and match_untracked:
            # Pour une migration inter-Realms/instances, les IDs distants ne sont pas portables.
            # La correspondance heuristique n'est autorisée que dans ce cas : jamais pour un nouveau nœud local.
            if typ == "execution":
                item = next((x for x in current if x.get("providerId") == node.get("providerId") and x.get("id") not in used_ids), None)
            else:
                expected_alias = node.get("alias") or node.get("remoteAlias") or _safe_alias(node.get("displayName", "subflow"), node.get("nodeId"))
                item = next((x for x in current if x.get("authenticationFlow") and x.get("alias") == expected_alias and x.get("id") not in used_ids), None)
        if item is None:
            before = {x.get("id") for x in await _list_exec(kc, realm, parent_alias)}
            if typ == "subflow":
                sub_alias = node.get("alias") or node.get("remoteAlias") or _safe_alias(node.get("displayName", "subflow"), node.get("nodeId"))
                await kc.create_subflow(realm, parent_alias, sub_alias, node.get("description", ""), "form" if node.get("flowType") in ("form", "form-flow") else "basic")
                item = await _find_created(kc, realm, parent_alias, before, flow_alias=sub_alias)
                created.append({"kind":"execution","id":item["id"]})
                child_alias = item.get("alias") or sub_alias
                child_nodes = node.get("children", [])
                await _sync_children(kc, realm, child_alias, child_nodes, allow_deletes, created, match_untracked)
            else:
                await kc.create_execution(realm, parent_alias, node.get("providerId"))
                item = await _find_created(kc, realm, parent_alias, before, provider_id=node.get("providerId"))
                created.append({"kind":"execution","id":item["id"]})
        else:
            if typ == "execution" and item.get("providerId") and item.get("providerId") != node.get("providerId"):
                raise DeploymentError(f"Le provider de {node.get('displayName')} a changé. Supprimer puis recréer explicitement cette exécution.")
            if typ == "subflow" and item.get("authenticationFlow"):
                child_alias = item.get("alias") or node.get("remoteAlias")
                child_flow = next((f for f in await kc.flows(realm) if f.get("alias") == child_alias), None)
                if child_flow:
                    desired_type = "form-flow" if node.get("flowType") in ("form", "form-flow") else "basic-flow"
                    if child_flow.get("providerId") and child_flow.get("providerId") != desired_type:
                        raise DeploymentError(f"Le type du sous-flow {child_alias} ne peut pas être modifié en place. Recréez le sous-flow.")
                    if node.get("alias") and node.get("alias") != child_alias:
                        raise DeploymentError(f"Le renommage du sous-flow {child_alias} n'est pas pris en charge en mise à jour. Recréez-le avec son nouvel alias.")
                    if node.get("description", "") != child_flow.get("description", ""):
                        await kc.request("PUT", f"/admin/realms/{realm}/authentication/flows/{child_flow['id']}", json={**child_flow, "description": node.get("description", "")})
                await _sync_children(kc, realm, child_alias, node.get("children", []), allow_deletes, created, match_untracked)
        if not item or not item.get("id"):
            raise DeploymentError(f"Élément non résolu : {node.get('displayName')}")
        used_ids.add(item["id"])
        requirement = node.get("requirement", "REQUIRED")
        if item.get("requirement") != requirement:
            await kc.set_requirement(realm, parent_alias, item["id"], requirement)
        if typ == "execution":
            # Mettre à jour, créer ou retirer une configuration d'authenticator si nécessaire.
            if node.get("config") or node.get("remoteConfigId") or node.get("configReadWarning"):
                await _configure(kc, realm, item["id"], node, existing_execution=existing_execution and not match_untracked)
        await _move_execution(kc, realm, parent_alias, item["id"], index)
        current = await _list_exec(kc, realm, parent_alias)
    if allow_deletes:
        desired_ids = used_ids
        for item in current:
            if item.get("id") not in desired_ids:
                if item.get("authenticationConfig"):
                    await kc.delete_authenticator_config(realm, item["authenticationConfig"])
                await kc.delete_execution(realm, item["id"])
                created.append({"kind":"deleted-execution","id":item["id"]})
                if item.get("authenticationFlow") and item.get("flowId"):
                    try:
                        await kc.request("DELETE", f"/admin/realms/{quote(realm, safe='')}/authentication/flows/{quote(str(item['flowId']), safe='')}")
                        created.append({"kind":"deleted-subflow","id":item["flowId"]})
                    except Exception:
                        # La suppression du flow orphelin n'empêche pas le reste de la synchronisation.
                        pass


def _safe_alias(label: str, node_id: str | None):
    import re
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", label.strip()).strip("-").lower() or "subflow"
    return f"{slug[:35]}-{(node_id or new_id())[:8]}"


async def validate_against_keycloak(kc, realm: str, project: dict):
    providers = await kc.providers(realm)
    provider_ids = {p.get("id") or p.get("providerId") for p in (providers or [])}
    errors = []

    def collect(nodes, path="root"):
        for node in nodes or []:
            name = node.get("displayName", node.get("providerId", "component"))
            if node.get("type") == "execution":
                provider_id = node.get("providerId")
                if provider_id and provider_ids and provider_id not in provider_ids:
                    errors.append(f"{path}/{name}: provider '{provider_id}' absent de l'instance cible.")
            elif node.get("type") == "subflow":
                collect(node.get("children", []), f"{path}/{name}")

    collect(project.get("flow", {}).get("nodes", []))
    if errors:
        raise DeploymentError("Providers incompatibles : " + " | ".join(errors))
    return {"providerCount": len(provider_ids)}

async def deploy_project(kc, realm: str, project: dict, mode: str, alias: str, allow_deletes: bool, target_instance_id: str | None = None):
    validation = validate_project(deepcopy(project))
    if not validation["valid"]:
        raise DeploymentError("Validation bloquante : " + " | ".join(validation["errors"]))
    await validate_against_keycloak(kc, realm, project)
    flow = project["flow"]
    flows = await kc.flows(realm)
    existing = next((x for x in flows if x.get("alias") == alias), None)
    created = []
    backup = None
    backup_id = None
    root_alias = alias
    source = project.get("target", {})
    has_source_flow = bool(source.get("sourceFlowId"))
    same_source_target = (
        source.get("instanceId") == target_instance_id
        and source.get("realm") == realm
    )
    match_untracked = has_source_flow and not same_source_target

    if mode == "create" and existing:
        raise DeploymentError(f"Un flow nommé '{alias}' existe déjà. Choisir un alias différent ou le mode mise à jour.")
    if mode == "update" and not existing:
        raise DeploymentError(f"Flow cible '{alias}' introuvable.")
    if mode == "update" and not has_source_flow:
        raise DeploymentError("Pour mettre à jour un flow, importer d'abord le flow cible dans le projet afin de conserver ses identifiants d'exécution.")
    if mode == "update" and same_source_target and source.get("sourceFlowId") != existing.get("id"):
        raise DeploymentError("Le projet n'a pas été importé depuis ce flow cible. Réimporter le bon flow avant la mise à jour.")
    if mode == "update" and existing.get("builtIn"):
        raise DeploymentError("Impossible de modifier directement un flow natif. Dupliquez-le d'abord.")
    if mode == "update" and existing.get("providerId") and existing.get("providerId") != flow.get("providerId", "basic-flow"):
        raise DeploymentError("Le type du flow racine ne peut pas être changé lors d'une mise à jour.")
    if mode not in ("create", "update"):
        raise DeploymentError("Mode de déploiement inconnu.")

    try:
        if mode == "create":
            body = {"alias":alias,"description":flow.get("description", ""),"providerId":flow.get("providerId", "basic-flow"),"topLevel":True,"builtIn":False}
            await kc.create_flow(realm, body)
            flows = await kc.flows(realm)
            created_flow = next((x for x in flows if x.get("alias") == alias), None)
            if not created_flow:
                raise DeploymentError("Flow créé mais introuvable lors de la vérification.")
            created.append({"kind":"flow","id":created_flow.get("id")})
        else:
            backup = await import_full_flow(kc, realm, alias)
            backup_id = new_id()
            backup_record = {
                "createdAt":datetime.now(timezone.utc).isoformat(),
                "instanceId":target_instance_id,
                "realm":realm,"alias":alias,"snapshot":backup
            }
            write_json(collection("backups") / f"{backup_id}.json", protect_project_secrets(backup_record))
            await kc.request("PUT", f"/admin/realms/{quote(realm, safe='')}/authentication/flows/{quote(str(existing['id']), safe='')}", json={
                "id":existing["id"],"alias":alias,"description":flow.get("description", ""),
                "providerId":flow.get("providerId", "basic-flow"),"topLevel":True,"builtIn":False
            })

        await _sync_children(kc, realm, root_alias, flow.get("nodes", []), allow_deletes=allow_deletes, created=created, match_untracked=match_untracked)
        final_flows = await kc.flows(realm)
        final_flow = next((x for x in final_flows if x.get("alias") == root_alias), None)
        final_nodes = await _list_exec(kc, realm, root_alias)
        refreshed = await import_full_flow(kc, realm, root_alias)
        refreshed["project"] = deepcopy(project.get("project", refreshed["project"]))
        refreshed["target"] = {**deepcopy(project.get("target", {})), "realm":realm, "sourceAlias":root_alias, "sourceFlowId":final_flow.get("id") if final_flow else None}
        return {
            "status":"success","alias":root_alias,"flowId":final_flow.get("id") if final_flow else None,
            "executions":len(final_nodes),"backupId":backup_id,"operations":created,
            "updatedProject":refreshed,"message":"Le flow a été déployé et relu depuis Keycloak."
        }
    except Exception as exc:
        rollback = {"attempted":True,"success":False,"detail":""}
        if mode == "create":
            try:
                f = next((x for x in await kc.flows(realm) if x.get("alias")==root_alias), None)
                if f:
                    await kc.request("DELETE", f"/admin/realms/{quote(realm, safe='')}/authentication/flows/{quote(str(f['id']), safe='')}")
                rollback.update(success=True, detail="Flow créé supprimé après échec.")
            except Exception as rb:
                rollback["detail"] = str(rb)
        elif backup:
            try:
                current_root = next((f for f in await kc.flows(realm) if f.get("alias") == root_alias), None)
                if current_root:
                    snapshot_flow = backup.get("flow", {})
                    await kc.request("PUT", f"/admin/realms/{quote(realm, safe='')}/authentication/flows/{quote(str(current_root['id']), safe='')}", json={
                        "id":current_root["id"], "alias":root_alias,
                        "description":snapshot_flow.get("description", ""),
                        "providerId":snapshot_flow.get("providerId", "basic-flow"),
                        "topLevel":True, "builtIn":False
                    })
                await _sync_children(kc, realm, root_alias, backup["flow"].get("nodes", []), allow_deletes=True, created=[])
                rollback.update(success=True, detail="Tentative de restauration du snapshot (métadonnées et exécutions) terminée.")
            except Exception as rb:
                rollback["detail"] = str(rb)
        raise DeploymentError(f"Déploiement interrompu : {exc}. Rollback : {rollback}") from exc

