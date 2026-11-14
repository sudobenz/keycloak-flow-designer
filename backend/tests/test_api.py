from fastapi.testclient import TestClient
from app.main import app


def test_auth_and_project_lifecycle():
    with TestClient(app) as client:
        login=client.post('/api/auth/login',json={'username':'admin','password':'Admin-Test-Password-2026!'})
        assert login.status_code==200
        token=login.json()['access_token']
        headers={'Authorization':f'Bearer {token}'}
        project={'schemaVersion':'1.0','project':{'id':'api-test','name':'API Test'},'target':{},'flow':{'alias':'browser-test','providerId':'basic-flow','topLevel':True,'nodes':[]}}
        saved=client.post('/api/projects',json=project,headers=headers)
        assert saved.status_code==200
        assert saved.json()['project']['id']=='api-test'
        check=client.post('/api/projects/api-test/validate',headers=headers)
        assert check.status_code==200 and check.json()['valid'] is True
        exported=client.get('/api/projects/api-test/export.json',headers=headers)
        assert exported.status_code==200 and 'browser-test' in exported.text
        yaml=client.get('/api/projects/api-test/export.yaml',headers=headers)
        assert yaml.status_code==200 and 'AuthenticationFlowProject' in yaml.text
        assert client.get('/api/users',headers=headers).status_code==200


def test_project_secret_is_encrypted_at_rest_and_restored():
    from app.project_security import protect_project_secrets, restore_project_secrets
    project={"flow":{"nodes":[{"type":"execution","secretConfigKeys":["bindCredential"],"config":{"bindCredential":"SuperSecret-123"}}]}}
    protected=protect_project_secrets(project)
    stored_value=protected["flow"]["nodes"][0]["config"]["bindCredential"]
    assert stored_value != "SuperSecret-123"
    assert stored_value.startswith("kfdenc:v1:")
    assert restore_project_secrets(protected)==project


def test_nested_snapshot_provider_secrets_are_encrypted_and_restored():
    from app.project_security import protect_project_secrets, restore_project_secrets

    imported_project = {
        "flow": {
            "nodes": [
                {
                    "type": "subflow",
                    "children": [
                        {
                            "type": "execution",
                            "secretConfigKeys": ["clientSecret"],
                            "config": {"clientSecret": "Nested-Secret-456"},
                        }
                    ],
                }
            ]
        }
    }
    backup = {"snapshot": imported_project, "alias": "browser-custom"}
    protected = protect_project_secrets(backup)
    encrypted_value = protected["snapshot"]["flow"]["nodes"][0]["children"][0]["config"]["clientSecret"]
    assert encrypted_value.startswith("kfdenc:v1:")
    assert "Nested-Secret-456" not in str(protected)
    assert restore_project_secrets(protected) == backup


def test_project_history_and_admin_restore():
    with TestClient(app) as client:
        login=client.post('/api/auth/login',json={'username':'admin','password':'Admin-Test-Password-2026!'})
        headers={'Authorization':f"Bearer {login.json()['access_token']}"}
        base={'schemaVersion':'1.0','project':{'id':'history-test','name':'Version 1'},'target':{},'flow':{'alias':'browser-history','providerId':'basic-flow','topLevel':True,'nodes':[]}}
        assert client.post('/api/projects',json=base,headers=headers).status_code==200
        changed={**base,'project':{'id':'history-test','name':'Version 2'}}
        assert client.post('/api/projects',json=changed,headers=headers).status_code==200
        versions=client.get('/api/projects/history-test/history',headers=headers)
        assert versions.status_code==200 and len(versions.json())==1
        version_id=versions.json()[0]['versionId']
        restored=client.post(f'/api/projects/history-test/history/{version_id}/restore',headers=headers)
        assert restored.status_code==200
        assert restored.json()['project']['name']=='Version 1'


def test_backup_list_and_export_are_admin_only(tmp_path, monkeypatch):
    from app.storage import collection, write_json, new_id
    from app.config import DATA_DIR
    with TestClient(app) as client:
        login=client.post('/api/auth/login',json={'username':'admin','password':'Admin-Test-Password-2026!'})
        headers={'Authorization':f"Bearer {login.json()['access_token']}"}
        backup_id=new_id()
        write_json(collection('backups')/f'{backup_id}.json',{'createdAt':'2026-11-14T12:00:00Z','instanceId':'inst-1','realm':'demo','alias':'browser-custom','snapshot':{'schemaVersion':'1.0','project':{'id':'snapshot-1','name':'Backup'},'target':{'realm':'demo'},'flow':{'alias':'browser-custom','providerId':'basic-flow','nodes':[]}}})
        items=client.get('/api/backups',headers=headers)
        assert items.status_code==200 and any(x['id']==backup_id for x in items.json())
        exported=client.get(f'/api/backups/{backup_id}/export.json',headers=headers)
        assert exported.status_code==200 and 'browser-custom' in exported.text
