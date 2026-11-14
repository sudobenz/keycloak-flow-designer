from copy import deepcopy
from typing import Any
from .storage import new_id

REQS = {"REQUIRED", "ALTERNATIVE", "CONDITIONAL", "DISABLED"}

async def import_flow_tree(kc, realm: str, flow: dict, flow_index: dict | None = None, depth: int = 0):
    if depth > 12: raise ValueError("Profondeur maximale de sous-flux dépassée")
    index = flow_index or {f.get("alias"):f for f in await kc.flows(realm)}
    alias = flow.get("alias")
    items = await kc.executions(realm, alias)
    nodes = []
    schema_cache = {}
    for item in sorted(items or [], key=lambda x: (x.get("index", 0), x.get("priority", 0))):
        is_sub = bool(item.get("authenticationFlow"))
        node = {
            "nodeId": new_id(), "type": "subflow" if is_sub else "execution",
            "displayName": item.get("displayName") or item.get("alias") or item.get("providerId") or "Execution",
            "providerId": item.get("providerId"), "requirement": item.get("requirement") or "DISABLED",
            "priority": item.get("priority", 0), "config": {}, "configAlias": None,
            "remoteExecutionId": item.get("id"), "remoteFlowId": item.get("flowId"),
            "remoteAlias": item.get("alias"), "alias": item.get("alias") if is_sub else None, "remoteConfigId": item.get("authenticationConfig"),
            "requirementChoices": item.get("requirementChoices") or [],
            "configurable": item.get("configurable", False), "remote": deepcopy(item)
        }
        if is_sub:
            child_alias = item.get("alias")
            child_flow = index.get(child_alias)
            if child_flow is None and child_alias:
                try:
                    child_flow = await kc.flow(realm, child_alias)
                except Exception:
                    child_flow = None
            child_flow = child_flow or {"alias": child_alias, "providerId":"basic-flow", "topLevel":False}
            node["flowType"] = "form" if child_flow.get("providerId") in ("form-flow", "form") else "basic"
            node["description"] = child_flow.get("description", "")
            node["children"] = await import_flow_tree(kc, realm, child_flow, index, depth + 1)
        else:
            provider_id = item.get("providerId")
            if provider_id:
                if provider_id not in schema_cache:
                    try:
                        schema_cache[provider_id] = await kc.config_description(realm, provider_id)
                    except Exception:
                        schema_cache[provider_id] = {}
                properties = schema_cache[provider_id].get("properties", []) if isinstance(schema_cache[provider_id], dict) else []
                node["secretConfigKeys"] = [p.get("name") for p in properties if p.get("name") and str(p.get("secret", False)).lower() == "true"]
            cfg_id = item.get("authenticationConfig")
            if cfg_id:
                try:
                    config = await kc.get_auth_config(realm, cfg_id)
                    node["config"] = config.get("config", {})
                    node["configAlias"] = config.get("alias")
                except Exception as exc:
                    node["configReadWarning"] = str(exc)
        nodes.append(node)
    return nodes

async def import_full_flow(kc, realm: str, alias: str):
    flows = await kc.flows(realm)
    flow = next((f for f in flows if f.get("alias") == alias), None)
    if not flow: raise KeyError(f"Flow inconnu : {alias}")
    nodes = await import_flow_tree(kc, realm, flow, {f.get("alias"): f for f in flows})
    return {
        "schemaVersion":"1.0",
        "project":{"id":new_id(),"name":flow.get("alias"),"description":flow.get("description") or ""},
        "target":{"realm":realm,"sourceAlias":alias,"sourceFlowId":flow.get("id"),"keycloakVersion":None},
        "flow":{"alias":alias,"description":flow.get("description") or "","topLevel":flow.get("topLevel",True),"providerId":flow.get("providerId","basic-flow"),"builtIn":flow.get("builtIn",False),"remoteFlowId":flow.get("id"),"nodes":nodes}
    }

def validate_project(project: dict[str, Any]):
    errors, warnings = [], []
    flow = project.get("flow") or {}
    if not flow.get("alias"): errors.append("L'alias du flow est obligatoire.")
    if not flow.get("providerId"): errors.append("Le providerId du flow est obligatoire.")
    if flow.get("builtIn"): errors.append("Un flow natif Keycloak ne peut pas être modifié directement. Dupliquez-le vers un flow personnalisé.")
    seen = set()
    def walk(nodes, path="root", depth=0):
        if depth > 12: errors.append(f"Profondeur excessive dans {path}."); return
        for pos, node in enumerate(nodes or []):
            name = node.get("displayName", "Composant sans nom")
            node_id = node.get("nodeId")
            if not node_id: errors.append(f"{name}: nodeId absent.")
            elif node_id in seen: errors.append(f"{name}: nodeId dupliqué ({node_id}).")
            else: seen.add(node_id)
            typ = node.get("type")
            if typ not in ("execution", "subflow"): errors.append(f"{name}: type de nœud inconnu.")
            if node.get("requirement") not in REQS: errors.append(f"{name}: requirement invalide.")
            allowed_choices = node.get("requirementChoices") or (
                ["REQUIRED", "ALTERNATIVE", "CONDITIONAL", "DISABLED"] if typ == "subflow"
                else ["REQUIRED", "ALTERNATIVE", "DISABLED"]
            )
            if node.get("requirement") in REQS and node.get("requirement") not in allowed_choices:
                errors.append(f"{name}: requirement {node.get('requirement')} non autorisé par le provider.")
            if typ == "execution" and node.get("requirement") == "CONDITIONAL":
                errors.append(f"{name}: CONDITIONAL est une exigence de sous-flow, pas d'exécution authenticator.")
            if typ == "execution" and not node.get("providerId"): errors.append(f"{name}: providerId absent.")
            if typ == "subflow":
                if not node.get("flowType"): node["flowType"] = "basic-flow"
                if not node.get("alias") and not node.get("remoteAlias"): warnings.append(f"{name}: alias Keycloak sera généré au déploiement.")
                walk(node.get("children", []), f"{path}/{name}", depth+1)
            if node.get("config") and not isinstance(node["config"], dict): errors.append(f"{name}: la configuration doit être un objet clé/valeur.")
    walk(flow.get("nodes", []))
    if not flow.get("nodes"): warnings.append("Le flow ne contient aucune exécution.")
    return {"valid":not errors,"errors":errors,"warnings":warnings}

def normalize_for_compare(node):
    return {k:node.get(k) for k in ("type","providerId","displayName","requirement","config","flowType","priority","description")}

def diff_nodes(local_nodes, remote_nodes):
    actions=[]
    remote_by_id={n.get("remoteExecutionId"):n for n in remote_nodes if n.get("remoteExecutionId")}
    remote_by_key={(n.get("type"),n.get("providerId"),n.get("remoteAlias")):n for n in remote_nodes}
    used=set()
    for local in local_nodes:
        remote=remote_by_id.get(local.get("remoteExecutionId"))
        if not remote:
            key=(local.get("type"),local.get("providerId"),local.get("remoteAlias"))
            remote=remote_by_key.get(key)
        if remote:
            used.add(remote.get("remoteExecutionId"))
            if normalize_for_compare(local)!=normalize_for_compare(remote): actions.append({"action":"modify","name":local.get("displayName"),"nodeId":local.get("nodeId")})
            if local.get("type")=="subflow": actions.extend(diff_nodes(local.get("children",[]),remote.get("children",[])))
        else: actions.append({"action":"create","name":local.get("displayName"),"nodeId":local.get("nodeId")})
    for remote in remote_nodes:
        if remote.get("remoteExecutionId") not in used:
            actions.append({"action":"delete","name":remote.get("displayName"),"remoteExecutionId":remote.get("remoteExecutionId")})
    return actions
