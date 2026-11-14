import asyncio
from app.deployment import deploy_project, _sync_children, _configure, DeploymentError

class FakeKeycloak:
    def __init__(self):
        self.flow_list=[]
        self.executions_by_alias={}
        self.counter=0
        self.calls=[]
    async def flows(self, realm): return self.flow_list
    async def providers(self, realm):
        return [
            {"id":"auth-cookie"},
            {"id":"auth-username-password-form"},
        ]
    async def executions(self, realm, alias): return self.executions_by_alias.setdefault(alias, [])
    async def create_flow(self, realm, body):
        self.flow_list.append({**body,'id':f'flow-{len(self.flow_list)+1}'})
    async def create_execution(self, realm, parent_alias, provider_id):
        self.counter+=1
        self.executions_by_alias[parent_alias].append({'id':f'exec-{self.counter}','providerId':provider_id,'requirement':'REQUIRED','priority':len(self.executions_by_alias[parent_alias])*10})
    async def create_subflow(self, realm, parent_alias, alias, description, flow_type='basic'):
        self.counter+=1
        self.executions_by_alias[parent_alias].append({'id':f'exec-{self.counter}','alias':alias,'authenticationFlow':True,'flowId':f'flow-child-{self.counter}','requirement':'REQUIRED','priority':len(self.executions_by_alias[parent_alias])*10})
        self.flow_list.append({'id':f'flow-child-{self.counter}','alias':alias,'providerId':'basic-flow','topLevel':False,'builtIn':False})
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
        self.calls.append((method,path))
        if method=='PUT': return None
        return None


def test_deploy_creates_root_execution_and_nested_subflow():
    kc=FakeKeycloak()
    project={
        'project':{'id':'p1','name':'Test'},
        'flow':{'alias':'browser-custom','description':'Test flow','providerId':'basic-flow','builtIn':False,'nodes':[
            {'nodeId':'a','type':'execution','displayName':'Cookie','providerId':'auth-cookie','requirement':'ALTERNATIVE','config':{}},
            {'nodeId':'b','type':'subflow','displayName':'Forms','alias':'forms-custom','flowType':'form','requirement':'REQUIRED','children':[
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
