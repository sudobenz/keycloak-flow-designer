import asyncio
from app.deployment import deploy_project, _sync_children, _configure, DeploymentError

class FakeKeycloak:
    def __init__(self):
        self.flow_list=[]
        self.executions_by_alias={}
        self.counter=0
        self.calls=[]
        self.form_subflow_provider_ids=[]
    async def flows(self, realm): return self.flow_list
    async def flow(self, realm, flow_id):
        return next((flow for flow in self.flow_list if flow.get("id") == flow_id), None)
    async def providers(self, realm):
        return [
            {"id":"auth-cookie"},
            {"id":"auth-username-password-form"},
        ]
    async def client_authenticator_providers(self, realm):
        return [{"id":"client-secret"},{"id":"client-jwt"}]
    async def form_action_providers(self, realm):
        return [{"id":"registration-user-creation"},{"id":"registration-profile-action"}]
    async def form_providers(self, realm):
        return [{"id":"registration-page-form"}]
    async def executions(self, realm, alias): return self.executions_by_alias.setdefault(alias, [])
    async def create_flow(self, realm, body):
        self.flow_list.append({**body,'id':f'flow-{len(self.flow_list)+1}'})
    async def create_execution(self, realm, parent_alias, provider_id):
        self.counter+=1
        self.executions_by_alias[parent_alias].append({'id':f'exec-{self.counter}','providerId':provider_id,'requirement':'REQUIRED','priority':len(self.executions_by_alias[parent_alias])*10})
    async def create_subflow(self, realm, parent_alias, alias, description, flow_type='basic', form_provider='registration-page-form'):
        if flow_type == 'form':
            self.form_subflow_provider_ids.append(form_provider)
        self.counter+=1
        self.executions_by_alias[parent_alias].append({'id':f'exec-{self.counter}','alias':alias,'authenticationFlow':True,'flowId':f'flow-child-{self.counter}','requirement':'REQUIRED','priority':len(self.executions_by_alias[parent_alias])*10})
        self.flow_list.append({'id':f'flow-child-{self.counter}','alias':alias,'providerId':'form-flow' if flow_type == 'form' else 'basic-flow','topLevel':False,'builtIn':False})
        self.executions_by_alias[alias]=[]
    async def set_requirement(self, realm, parent_alias, execution_id, requirement):
        for item in self.executions_by_alias[parent_alias]:
            if item['id']==execution_id: item['requirement']=requirement
    async def priority(self, realm, execution_id, direction):
        for items in self.executions_by_alias.values():
            index=next((i for i,x in enumerate(items) if x.get('id')==execution_id),None)
            if index is not None:
                target=index-1 if direction=='raise' else index+1
                if 0 <= target < len(items): items[index],items[target]=items[target],items[index]
                return
    async def set_execution_config(self, realm, execution_id, body): self.calls.append(('config',execution_id,body))
    async def delete_authenticator_config(self, realm, config_id): self.calls.append(('delete-config',config_id))
    async def delete_execution(self, realm, execution_id):
        self.calls.append(('delete-execution',execution_id))
        for items in self.executions_by_alias.values():
            items[:] = [x for x in items if x.get('id') != execution_id]
    async def request(self, method, path, **kwargs):
        self.calls.append((method,path,kwargs))
        if method == 'PUT' and '/authentication/flows/' in path:
            body = kwargs.get('json') or {}
            flow_id = path.rsplit('/', 1)[-1]
            target = next((flow for flow in self.flow_list if flow.get('id') == flow_id), None)
            if target:
                target.update(body)
        return None


def test_deploy_creates_root_execution_and_nested_subflow():
    kc=FakeKeycloak()
    project={
        'project':{'id':'p1','name':'Test'},
        'flow':{'alias':'browser-custom','description':'Test flow','providerId':'basic-flow','builtIn':False,'nodes':[
            {'nodeId':'a','type':'execution','displayName':'Cookie','providerId':'auth-cookie','requirement':'ALTERNATIVE','config':{}},
            {'nodeId':'b','type':'subflow','displayName':'Forms','alias':'forms-custom','flowType':'basic','requirement':'ALTERNATIVE','children':[
                {'nodeId':'c','type':'execution','displayName':'Password','providerId':'auth-username-password-form','requirement':'REQUIRED','config':{}}
            ]}
        ]}
    }
    result=asyncio.run(deploy_project(kc,'demo',project,'create','browser-custom',False))
    assert result['status']=='success'
    assert len(kc.executions_by_alias['browser-custom'])==2
    assert len(kc.executions_by_alias['forms-custom'])==1
    assert kc.executions_by_alias['browser-custom'][0]['requirement']=='ALTERNATIVE'


def test_new_execution_with_same_provider_is_not_silently_reused():
    kc=FakeKeycloak()
    kc.executions_by_alias['browser']=[{'id':'existing','providerId':'auth-cookie','requirement':'ALTERNATIVE','priority':10}]
    node={'nodeId':'new','type':'execution','displayName':'Cookie bis','providerId':'auth-cookie','requirement':'REQUIRED','config':{}}
    asyncio.run(_sync_children(kc,'demo','browser',[node],allow_deletes=False,created=[]))
    assert len(kc.executions_by_alias['browser']) == 2

def test_empty_config_removes_existing_remote_config():
    kc=FakeKeycloak()
    node={'displayName':'Cookie','remoteConfigId':'cfg-1','config':{}}
    asyncio.run(_configure(kc,'demo','exec-1',node,existing_execution=True))
    assert ('delete-config','cfg-1') in kc.calls


def test_update_requires_source_flow_to_prevent_duplicate_executions():
    kc=FakeKeycloak()
    kc.flow_list=[{'id':'flow-1','alias':'browser-custom','providerId':'basic-flow','builtIn':False}]
    kc.executions_by_alias['browser-custom']=[]
    project={
        'project':{'id':'p-update','name':'Update'},
        'flow':{'alias':'browser-custom','providerId':'basic-flow','builtIn':False,'nodes':[]}
    }
    try:
        asyncio.run(deploy_project(kc,'demo',project,'update','browser-custom',False,'instance-1'))
    except DeploymentError as exc:
        assert "importer d'abord" in str(exc)
    else:
        raise AssertionError('La mise à jour doit exiger la provenance du flow importé.')


def test_client_flow_validates_against_client_authenticator_catalog():
    from app.deployment import validate_against_keycloak
    kc=FakeKeycloak()
    project={"flow":{"providerId":"client-flow","nodes":[
        {"type":"execution","providerId":"client-secret","displayName":"Client Secret"}
    ]}}
    result=asyncio.run(validate_against_keycloak(kc,"demo",project))
    assert result["providerCount"] == 2


def test_client_flow_rejects_standard_authenticator_provider():
    from app.deployment import validate_against_keycloak
    kc=FakeKeycloak()
    project={"flow":{"providerId":"client-flow","nodes":[
        {"type":"execution","providerId":"auth-cookie","displayName":"Cookie"}
    ]}}
    try:
        asyncio.run(validate_against_keycloak(kc,"demo",project))
    except DeploymentError as exc:
        assert "absent du catalogue client-flow" in str(exc)
    else:
        raise AssertionError("Un authenticator standard ne doit pas être accepté dans un flow client.")


def test_empty_project_does_not_require_provider_catalog():
    from app.deployment import validate_against_keycloak

    class EmptyCatalog(FakeKeycloak):
        async def providers(self, realm): return []

    result = asyncio.run(validate_against_keycloak(EmptyCatalog(), "demo", {"flow": {"providerId": "basic-flow", "nodes": []}}))
    assert result["providerCount"] == 0


def test_provider_catalog_is_required_when_execution_exists():
    from app.deployment import validate_against_keycloak

    class EmptyCatalog(FakeKeycloak):
        async def providers(self, realm): return []

    project = {"flow": {"providerId": "basic-flow", "nodes": [{"type": "execution", "providerId": "auth-cookie", "displayName": "Cookie"}]}}
    try:
        asyncio.run(validate_against_keycloak(EmptyCatalog(), "demo", project))
    except DeploymentError as exc:
        assert "aucun provider Authenticator" in str(exc)
    else:
        raise AssertionError("Une exécution doit être validée contre un catalogue distant non vide.")


def test_required_provider_configuration_is_checked_even_when_empty():
    from app.deployment import validate_against_keycloak

    class ConfigurableKeycloak(FakeKeycloak):
        async def config_description(self, realm, provider_id):
            return {"properties": [{"name": "mandatoryValue", "required": True}]}

    project = {"flow": {"providerId": "basic-flow", "nodes": [{
        "type": "execution", "providerId": "auth-cookie", "displayName": "Provider configuré", "config": {}
    }]}}
    try:
        asyncio.run(validate_against_keycloak(ConfigurableKeycloak(), "demo", project))
    except DeploymentError as exc:
        assert "mandatoryValue" in str(exc)
    else:
        raise AssertionError("Une propriété requise doit être détectée même si la configuration est vide.")




def test_form_flow_accepts_and_deploys_form_action_provider():
    kc = FakeKeycloak()
    project = {
        "project": {"id": "form-project", "name": "Registration"},
        "flow": {"alias": "registration-custom", "providerId": "basic-flow", "builtIn": False, "nodes": [
            {"nodeId": "form-node", "type": "subflow", "displayName": "Registration Form", "alias": "registration-form-custom", "flowType": "form", "requirement": "REQUIRED", "children": [
                {"nodeId": "action-node", "type": "execution", "displayName": "User Creation", "providerId": "registration-user-creation", "executionKind": "form-action", "requirement": "REQUIRED", "requirementChoices": ["REQUIRED", "DISABLED"], "config": {}}
            ]}
        ]}
    }
    result = asyncio.run(deploy_project(kc, "demo", project, "create", "registration-custom", False))
    assert result["status"] == "success"
    assert len(kc.executions_by_alias["registration-form-custom"]) == 1
    assert kc.executions_by_alias["registration-form-custom"][0]["providerId"] == "registration-user-creation"
    assert kc.form_subflow_provider_ids == ["registration-page-form"]


def test_form_flow_provider_is_validated_against_form_action_catalog():
    from app.deployment import validate_against_keycloak
    kc = FakeKeycloak()
    project = {"flow": {"providerId": "basic-flow", "nodes": [
        {"nodeId": "sf", "type": "subflow", "displayName": "Registration Form", "flowType": "form", "requirement": "REQUIRED", "children": [
            {"nodeId": "action", "type": "execution", "displayName": "User Creation", "providerId": "registration-user-creation", "executionKind": "form-action", "requirement": "REQUIRED", "requirementChoices": ["REQUIRED", "DISABLED"], "config": {}}
        ]}
    ]}}
    result = asyncio.run(validate_against_keycloak(kc, "demo", project))
    assert result["providerCatalogs"]["form-flow"] == 2


def test_form_flow_rejects_provider_not_in_form_action_catalog():
    from app.deployment import validate_against_keycloak
    kc = FakeKeycloak()
    project = {"flow": {"providerId": "basic-flow", "nodes": [
        {"nodeId": "sf", "type": "subflow", "displayName": "Registration Form", "flowType": "form", "requirement": "REQUIRED", "children": [
            {"nodeId": "action", "type": "execution", "displayName": "Cookie", "providerId": "auth-cookie", "executionKind": "form-action", "requirement": "REQUIRED", "requirementChoices": ["REQUIRED", "DISABLED"], "config": {}}
        ]}
    ]}}
    try:
        asyncio.run(validate_against_keycloak(kc, "demo", project))
    except DeploymentError as exc:
        assert "absent du catalogue form-flow" in str(exc)
    else:
        raise AssertionError("Un authenticator ne doit pas être accepté comme Form Action.")


def test_form_flow_rejects_unknown_form_authenticator_provider():
    from app.deployment import validate_against_keycloak

    class UnknownFormProvider(FakeKeycloak):
        async def form_providers(self, realm):
            return [{"id": "registration-page-form"}]

    project = {"flow": {"providerId": "basic-flow", "nodes": [
        {"nodeId": "sf", "type": "subflow", "displayName": "Form", "flowType": "form", "formProviderId": "missing-form-renderer", "requirement": "REQUIRED", "children": [
            {"nodeId": "action", "type": "execution", "displayName": "User Creation", "providerId": "registration-user-creation", "executionKind": "form-action", "requirement": "REQUIRED", "config": {}}
        ]}
    ]}}
    try:
        asyncio.run(validate_against_keycloak(UnknownFormProvider(), "demo", project))
    except DeploymentError as exc:
        assert "absent du catalogue form-providers" in str(exc)
    else:
        raise AssertionError("Un FormAuthenticator non présent dans le Realm ne doit pas être accepté.")


def test_update_subflow_reads_child_by_flow_id_and_updates_alias():
    kc = FakeKeycloak()
    kc.flow_list = [{"id": "flow-child-1", "alias": "old-subflow", "providerId": "basic-flow", "description": "Old", "topLevel": False, "builtIn": False}]
    kc.executions_by_alias["parent"] = [{"id": "exec-sub-1", "authenticationFlow": True, "flowId": "flow-child-1", "displayName": "old-subflow", "requirement": "REQUIRED", "priority": 10}]
    kc.executions_by_alias["old-subflow"] = []
    node = {"nodeId": "sub", "type": "subflow", "displayName": "new-subflow", "alias": "new-subflow", "remoteAlias": "old-subflow", "remoteExecutionId": "exec-sub-1", "remoteFlowId": "flow-child-1", "flowType": "basic", "description": "Updated", "requirement": "REQUIRED", "children": []}
    asyncio.run(_sync_children(kc, "demo", "parent", [node], allow_deletes=False, created=[]))
    updated = next(flow for flow in kc.flow_list if flow["id"] == "flow-child-1")
    assert updated["alias"] == "new-subflow"
    assert updated["description"] == "Updated"
    assert any(call[0] == "PUT" and "flow-child-1" in call[1] and call[2]["json"]["alias"] == "new-subflow" for call in kc.calls)
