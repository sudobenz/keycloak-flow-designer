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
    alias = node.get("configAlias") or f"KFD - {node.get('displayName','Execution')} - {str(node.get('nodeId') or execution_id)[:8]}"
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
                flow_type = "form" if node.get("flowType") in ("form", "form-flow") else "basic"
                await kc.create_subflow(realm, parent_alias, sub_alias, node.get("description", ""), flow_type, node.get("formProviderId") or "registration-page-form")
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
                child_alias = item.get("alias") or item.get("displayName") or node.get("remoteAlias") or node.get("alias") or node.get("displayName")
                child_flow = None
                child_flow_id = node.get("remoteFlowId") or item.get("flowId")
                if child_flow_id:
                    try:
                        child_flow = await kc.flow(realm, str(child_flow_id))
                    except Exception:
                        child_flow = None
                if child_flow is None:
                    child_flow = next((f for f in await kc.flows(realm) if f.get("alias") == child_alias), None)
                if child_flow:
                    desired_type = "form-flow" if node.get("flowType") in ("form", "form-flow") else "basic-flow"
                    if child_flow.get("providerId") and child_flow.get("providerId") != desired_type:
                        raise DeploymentError(f"Le type du sous-flow {child_alias} ne peut pas être modifié en place. Recréez le sous-flow.")
                    if desired_type == "form-flow":
                        current_form_provider = item.get("providerId")
                        desired_form_provider = node.get("formProviderId") or "registration-page-form"
                        if current_form_provider and current_form_provider != desired_form_provider:
                            raise DeploymentError(f"Le FormAuthenticator du sous-flow {child_alias} ne peut pas être changé en place. Supprimez puis recréez le sous-flow.")
                    desired_alias = (node.get("alias") or child_alias or "").strip()
                    if desired_alias and desired_alias != child_alias:
                        all_flows = await kc.flows(realm)
                        conflict = next((flow for flow in all_flows if flow.get("alias") == desired_alias and flow.get("id") != child_flow.get("id")), None)
                        if conflict:
                            raise DeploymentError(f"Impossible de renommer le sous-flow : l'alias '{desired_alias}' existe déjà dans le Realm.")
                        await kc.request("PUT", f"/admin/realms/{quote(realm, safe='')}/authentication/flows/{quote(str(child_flow['id']), safe='')}", json={**child_flow, "alias": desired_alias, "description": node.get("description", ""), "topLevel": False, "builtIn": False})
                        child_alias = desired_alias
                    elif node.get("description", "") != child_flow.get("description", ""):
                        await kc.request("PUT", f"/admin/realms/{quote(realm, safe='')}/authentication/flows/{quote(str(child_flow['id']), safe='')}", json={**child_flow, "description": node.get("description", "")})
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
    """Valide chaque exécution contre le SPI correspondant à son flow parent.

    Basic flow -> AuthenticatorFactory ; Form flow -> FormActionFactory ;
    Client flow -> ClientAuthenticatorFactory. Les FormActionFactory exposent
    également ConfigurableAuthenticatorFactory, donc leur schéma peut être lu
    via config-description comme les authenticator classiques.
    """
    errors: list[str] = []
    warnings: list[str] = []
    catalog_cache: dict[str, dict[str, dict]] = {}

    async def provider_catalog(parent_flow_provider: str) -> dict[str, dict]:
        if parent_flow_provider not in catalog_cache:
            method_name = {
                "form-flow": "form_action_providers",
                "client-flow": "client_authenticator_providers",
            }.get(parent_flow_provider, "providers")
            method = getattr(kc, method_name, None)
            if not callable(method):
                catalog_cache[parent_flow_provider] = {}
            else:
                records = await method(realm) or []
                catalog_cache[parent_flow_provider] = {
                    str(item.get("id") or item.get("providerId")): item
                    for item in records
                    if item.get("id") or item.get("providerId")
                }
        return catalog_cache[parent_flow_provider]

    async def collect(current_nodes, path="root", parent_flow_provider=None):
        parent_flow_provider = parent_flow_provider or project.get("flow", {}).get("providerId", "basic-flow")
        for node in current_nodes or []:
            name = node.get("displayName", node.get("providerId", "component"))
            if node.get("type") == "execution":
                provider_id = str(node.get("providerId") or "").strip()
                if not provider_id:
                    errors.append(f"{path}/{name}: Provider ID absent.")
                    continue
                providers = await provider_catalog(parent_flow_provider)
                if not providers:
                    spi_label = {
                        "form-flow": "Form Action",
                        "client-flow": "Client Authenticator",
                    }.get(parent_flow_provider, "Authenticator")
                    errors.append(
                        f"{path}/{name}: Keycloak n'a retourné aucun provider {spi_label} ; "
                        "vérifiez le catalogue et les droits Admin REST."
                    )
                    continue
                if provider_id not in providers:
                    errors.append(
                        f"{path}/{name}: provider '{provider_id}' absent du catalogue "
                        f"{parent_flow_provider}."
                    )
                    continue
                config = node.get("config") or {}
                if not isinstance(config, dict):
                    errors.append(f"{path}/{name}: la configuration doit être un objet clé/valeur.")
                    continue
                try:
                    description = await kc.config_description(realm, provider_id)
                    properties = description.get("properties", []) if isinstance(description, dict) else []
                    missing = []
                    for prop in properties:
                        prop_name = prop.get("name")
                        required = prop.get("required") is True or str(prop.get("required", "")).lower() == "true"
                        if not prop_name or not required:
                            continue
                        value = config.get(prop_name, prop.get("defaultValue"))
                        if value is None or (isinstance(value, str) and not value.strip()):
                            missing.append(prop_name)
                    if missing:
                        errors.append(f"{path}/{name}: paramètres obligatoires manquants : {', '.join(missing)}.")
                except Exception as exc:
                    warnings.append(f"{path}/{name}: schéma de configuration non vérifié pour '{provider_id}' ({exc}).")
            elif node.get("type") == "subflow":
                if parent_flow_provider == "form-flow":
                    errors.append(f"{path}/{name}: un Form flow ne peut pas contenir un sous-flow ; ajoutez des Form Actions.")
                    continue
                child_provider = "form-flow" if node.get("flowType") in ("form", "form-flow") else "basic-flow"
                if child_provider == "form-flow":
                    form_catalog_method = getattr(kc, "form_providers", None)
                    form_provider_id = str(node.get("formProviderId") or "registration-page-form").strip()
                    if not callable(form_catalog_method):
                        errors.append(f"{path}/{name}: catalogue des FormAuthenticators indisponible.")
                    else:
                        try:
                            form_records = await form_catalog_method(realm) or []
                            form_ids = {str(item.get("id") or item.get("providerId")) for item in form_records if item.get("id") or item.get("providerId")}
                            if not form_ids:
                                errors.append(f"{path}/{name}: Keycloak n'a retourné aucun FormAuthenticator.")
                            elif form_provider_id not in form_ids:
                                errors.append(f"{path}/{name}: FormAuthenticator '{form_provider_id}' absent du catalogue form-providers.")
                        except Exception as exc:
                            errors.append(f"{path}/{name}: impossible de vérifier le FormAuthenticator '{form_provider_id}' ({exc}).")
                await collect(node.get("children", []), f"{path}/{name}", child_provider)

    nodes = project.get("flow", {}).get("nodes", [])
    await collect(nodes)
    if errors:
        raise DeploymentError("Validation Keycloak : " + " | ".join(errors))
    provider_count = sum(len(items) for items in catalog_cache.values())
    return {"providerCount": provider_count, "providerCatalogs": {key: len(value) for key, value in catalog_cache.items()}, "warnings": warnings}

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

