import asyncio
from app.keycloak import KeycloakClient


def test_create_basic_subflow_uses_keycloak_flow_provider_id():
    client = KeycloakClient("https://kc", "https://kc/token", "kfd", "secret")
    calls = []

    async def fake_request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {"ok": True}

    client.request = fake_request
    asyncio.run(client.create_subflow("demo", "browser-custom", "sub-basic", "Basic subflow", "basic"))
    body = calls[0][2]["json"]
    assert body["type"] == "basic-flow"
    assert "provider" not in body


def test_create_form_subflow_uses_form_flow_and_selected_renderer():
    client = KeycloakClient("https://kc", "https://kc/token", "kfd", "secret")
    calls = []

    async def fake_request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return {"ok": True}

    client.request = fake_request
    asyncio.run(client.create_subflow("demo", "registration-custom", "registration-form", "Registration", "form", "registration-page-form"))
    body = calls[0][2]["json"]
    assert body["type"] == "form-flow"
    assert body["provider"] == "registration-page-form"
