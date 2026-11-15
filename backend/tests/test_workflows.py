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


def test_client_flow_import_marks_client_authenticator_kind():
    import asyncio
    from app.workflows import import_flow_tree
    class KC:
        async def flows(self, realm): return [{"alias":"clients","providerId":"client-flow"}]
        async def executions(self, realm, alias):
            return [{"id":"e-client","providerId":"client-secret","requirement":"REQUIRED","priority":10}]
    nodes=asyncio.run(import_flow_tree(KC(),"demo",{"alias":"clients","providerId":"client-flow"},execution_kind="client-authenticator"))
    assert nodes[0]["executionKind"] == "client-authenticator"


def test_conditional_execution_must_live_under_conditional_subflow():
    conditional={"nodeId":"cond","type":"execution","providerId":"conditional-user-configured","requirement":"REQUIRED"}
    result=validate_project(base([conditional]))
    assert not result["valid"]
    assert any("CONDITIONAL" in x for x in result["errors"])


def test_conditional_execution_inside_conditional_subflow_is_valid():
    conditional={"nodeId":"cond","type":"execution","providerId":"conditional-user-configured","requirement":"REQUIRED"}
    subflow={"nodeId":"sf","type":"subflow","displayName":"2FA condition","requirement":"CONDITIONAL","flowType":"basic","children":[conditional]}
    result=validate_project(base([subflow]))
    assert result["valid"], result["errors"]


def test_basic_forms_subflow_accepts_alternative_requirement():
    subflow = {
        "nodeId": "forms", "type": "subflow", "displayName": "Forms",
        "flowType": "basic", "requirement": "ALTERNATIVE", "children": []
    }
    result = validate_project(base([subflow]))
    assert result["valid"], result["errors"]


def test_true_form_flow_rejects_alternative_requirement():
    subflow = {
        "nodeId": "forms", "type": "subflow", "displayName": "Registration Form",
        "flowType": "form", "requirement": "ALTERNATIVE", "children": []
    }
    result = validate_project(base([subflow]))
    assert not result["valid"]
    assert any("non autorisé" in error for error in result["errors"])


def test_form_subflow_rejects_conditional_when_not_offered_by_keycloak():
    subflow = {
        "nodeId": "forms", "type": "subflow", "displayName": "Forms",
        "flowType": "form", "requirement": "CONDITIONAL", "children": []
    }
    result = validate_project(base([subflow]))
    assert not result["valid"]
    assert any("CONDITIONAL" in error for error in result["errors"])


def test_form_action_only_valid_inside_form_flow():
    action = {"nodeId": "action", "type": "execution", "providerId": "registration-user-creation", "executionKind": "form-action", "requirement": "REQUIRED", "requirementChoices": ["REQUIRED", "DISABLED"]}
    subflow = {"nodeId": "form", "type": "subflow", "displayName": "Registration Form", "flowType": "form", "requirement": "REQUIRED", "children": [action]}
    assert validate_project(base([subflow]))["valid"]
    assert not validate_project(base([action]))["valid"]


def test_normal_authenticator_is_rejected_inside_form_flow():
    normal = {"nodeId": "cookie", "type": "execution", "providerId": "auth-cookie", "executionKind": "authenticator", "requirement": "REQUIRED"}
    subflow = {"nodeId": "form", "type": "subflow", "displayName": "Registration Form", "flowType": "form", "requirement": "REQUIRED", "children": [normal]}
    result = validate_project(base([subflow]))
    assert not result["valid"]
    assert any("form-action" in error for error in result["errors"])


def test_form_action_kind_is_rebuilt_during_import_of_nested_form_flow():
    import asyncio
    from app.workflows import import_flow_tree
    class KC:
        async def flows(self, realm): return [{"alias": "root", "providerId": "basic-flow"}]
        async def executions(self, realm, alias):
            if alias == "root":
                return [{"id": "flow-exec", "authenticationFlow": True, "displayName": "registration-form", "providerId": "registration-page-form", "flowId": "form-id", "requirement": "REQUIRED", "priority": 10}]
            return [{"id": "action-exec", "providerId": "registration-user-creation", "requirement": "REQUIRED", "requirementChoices": ["REQUIRED", "DISABLED"], "priority": 10}]
        async def flow(self, realm, flow_id): return {"id": flow_id, "alias": "registration-form", "providerId": "form-flow"}
        async def config_description(self, realm, provider_id): return {"properties": []}
    nodes = asyncio.run(import_flow_tree(KC(), "demo", {"alias": "root", "providerId": "basic-flow"}))
    assert nodes[0]["flowType"] == "form"
    assert nodes[0]["alias"] == "registration-form"
    assert nodes[0]["formProviderId"] == "registration-page-form"
    assert nodes[0]["remoteFlowId"] == "form-id"
    assert nodes[0]["children"][0]["executionKind"] == "form-action"
