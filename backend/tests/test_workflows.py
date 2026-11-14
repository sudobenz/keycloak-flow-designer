from app.workflows import validate_project, diff_nodes

def base(nodes):
    return {"project":{"id":"x"},"flow":{"alias":"browser-test","providerId":"basic-flow","nodes":nodes}}

def test_valid_empty_flow_warns():
    result=validate_project(base([]))
    assert result["valid"] is True and result["warnings"]

def test_duplicate_node_ids_are_rejected():
    n={"nodeId":"same","type":"execution","providerId":"auth-cookie","requirement":"ALTERNATIVE"}
    result=validate_project(base([n,n.copy()]))
    assert result["valid"] is False
    assert any("dupliqué" in x for x in result["errors"])

def test_invalid_requirement_is_rejected():
    n={"nodeId":"n1","type":"execution","providerId":"auth-cookie","requirement":"MAYBE"}
    assert not validate_project(base([n]))["valid"]

def test_builtin_flow_is_protected():
    p=base([]); p["flow"]["builtIn"]=True
    assert not validate_project(p)["valid"]

def test_diff_detects_new_node():
    local=[{"nodeId":"n1","type":"execution","providerId":"auth-cookie","displayName":"Cookie","requirement":"ALTERNATIVE","config":{}}]
    assert diff_nodes(local,[])[0]["action"]=="create"


def test_flow_type_normalization():
    import asyncio
    from app.workflows import import_flow_tree
    class KC:
        async def flows(self, realm):
            return [{"alias":"root","providerId":"basic-flow"},{"alias":"forms","providerId":"form-flow"}]
        async def executions(self, realm, alias):
            if alias == "root":
                return [{"id":"e1","authenticationFlow":True,"alias":"forms","flowId":"f1","requirement":"ALTERNATIVE","priority":10}]
            return []
        async def flow(self, realm, flow_id):
            return {"alias":flow_id,"providerId":"form-flow"}
    nodes=asyncio.run(import_flow_tree(KC(),"demo",{"alias":"root"}))
    assert nodes[0]["flowType"] == "form"


def test_conditional_requirement_is_limited_to_subflows():
    n={"nodeId":"n1","type":"execution","providerId":"auth-cookie","requirement":"CONDITIONAL"}
    result=validate_project(base([n]))
    assert not result["valid"]
    assert any("CONDITIONAL" in x for x in result["errors"])


def test_shipped_templates_pass_structural_validation():
    import json
    from pathlib import Path
    base_dir=Path(__file__).resolve().parents[2]
    for template_name in ('browser-basic.example.json','browser-kerberos-mfa.example.json'):
        payload=json.loads((base_dir/'examples'/template_name).read_text(encoding='utf-8'))
        result=validate_project(payload)
        assert result['valid'], f"{template_name}: {result['errors']}"
