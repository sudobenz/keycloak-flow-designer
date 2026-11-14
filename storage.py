"""Chiffrement au repos des propriétés marquées `secret` par les métadonnées Keycloak."""
from copy import deepcopy
import json
from .security import encrypt_secret, decrypt_secret

PREFIX = "kfdenc:v1:"


def _walk(nodes):
    for node in nodes or []:
        yield node
        if node.get("type") == "subflow":
            yield from _walk(node.get("children", []))


def protect_project_secrets(project: dict) -> dict:
    result = deepcopy(project)
    if isinstance(result.get("snapshot"), dict):
        result["snapshot"] = protect_project_secrets(result["snapshot"])
    nodes = result.get("flow", {}).get("nodes", [])
    for node in _walk(nodes):
        if node.get("type") != "execution":
            continue
        config = node.get("config") or {}
        for key in node.get("secretConfigKeys", []) or []:
            if key not in config or config[key] is None:
                continue
            value = config[key]
            if isinstance(value, str) and value.startswith(PREFIX):
                continue
            serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
            config[key] = PREFIX + encrypt_secret(serialized)
        node["config"] = config
    return result


def restore_project_secrets(project: dict) -> dict:
    result = deepcopy(project)
    if isinstance(result.get("snapshot"), dict):
        result["snapshot"] = restore_project_secrets(result["snapshot"])
    nodes = result.get("flow", {}).get("nodes", [])
    for node in _walk(nodes):
        if node.get("type") != "execution":
            continue
        config = node.get("config") or {}
        for key, value in list(config.items()):
            if isinstance(value, str) and value.startswith(PREFIX):
                try:
                    config[key] = json.loads(decrypt_secret(value[len(PREFIX):]))
                except Exception as exc:
                    raise RuntimeError(f"Impossible de déchiffrer la propriété secrète '{key}'. Vérifier ENCRYPTION_KEY.") from exc
        node["config"] = config
    return result
