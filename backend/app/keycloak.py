from urllib.parse import quote
import httpx

class KeycloakClient:
    def __init__(self, base_url: str, token_url: str, client_id: str, client_secret: str, verify_tls: bool = True):
        self.base_url = base_url.rstrip("/")
        self.token_url = token_url
        self.client_id, self.client_secret = client_id, client_secret
        self.verify_tls = verify_tls
        self._token = None

    async def token(self):
        if self._token: return self._token
        async with httpx.AsyncClient(verify=self.verify_tls, timeout=20) as client:
            response = await client.post(self.token_url, data={"grant_type":"client_credentials", "client_id":self.client_id, "client_secret":self.client_secret})
            response.raise_for_status()
            self._token = response.json()["access_token"]
            return self._token

    async def request(self, method: str, path: str, **kwargs):
        for attempt in range(2):
            token = await self.token()
            async with httpx.AsyncClient(verify=self.verify_tls, timeout=40) as client:
                response = await client.request(method, f"{self.base_url}{path}", headers={"Authorization":f"Bearer {token}", "Accept":"application/json"}, **kwargs)
            if response.status_code == 401 and attempt == 0:
                self._token = None
                continue
            if response.status_code >= 400:
                detail = response.text[:1500]
                raise httpx.HTTPStatusError(f"Keycloak {response.status_code}: {detail}", request=response.request, response=response)
            if response.status_code == 204 or not response.content: return None
            try: return response.json()
            except ValueError: return response.text
        raise RuntimeError("Échec du renouvellement du jeton Keycloak.")

    async def server_info(self):
        try: return await self.request("GET", "/admin/serverinfo")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403, 404): return {"version": None, "warning": "Informations serveur non accessibles"}
            raise

    async def realms(self): return await self.request("GET", "/admin/realms?briefRepresentation=true")
    async def flows(self, realm): return await self.request("GET", f"/admin/realms/{quote(realm,safe='')}/authentication/flows")
    async def flow(self, realm, flow_id): return await self.request("GET", f"/admin/realms/{quote(realm,safe='')}/authentication/flows/{quote(flow_id,safe='')}")
    async def executions(self, realm, alias): return await self.request("GET", f"/admin/realms/{quote(realm,safe='')}/authentication/flows/{quote(alias,safe='')}/executions")
    async def providers(self, realm): return await self.request("GET", f"/admin/realms/{quote(realm,safe='')}/authentication/authenticator-providers")
    async def config_description(self, realm, provider_id): return await self.request("GET", f"/admin/realms/{quote(realm,safe='')}/authentication/config-description/{quote(provider_id,safe='')}")
    async def form_action_providers(self, realm): return await self.request("GET", f"/admin/realms/{quote(realm,safe='')}/authentication/form-action-providers")
    async def form_providers(self, realm): return await self.request("GET", f"/admin/realms/{quote(realm,safe='')}/authentication/form-providers")

    async def create_flow(self, realm, body):
        return await self.request("POST", f"/admin/realms/{quote(realm,safe='')}/authentication/flows", json=body)
    async def create_execution(self, realm, parent_alias, provider_id):
        return await self.request("POST", f"/admin/realms/{quote(realm,safe='')}/authentication/flows/{quote(parent_alias,safe='')}/executions/execution", json={"provider":provider_id})
    async def create_subflow(self, realm, parent_alias, alias, description, flow_type="basic"):
        return await self.request("POST", f"/admin/realms/{quote(realm,safe='')}/authentication/flows/{quote(parent_alias,safe='')}/executions/flow", json={"alias":alias,"description":description,"provider":"basic-flow","type":flow_type})
    async def set_requirement(self, realm, parent_alias, execution_id, requirement):
        return await self.request("PUT", f"/admin/realms/{quote(realm,safe='')}/authentication/flows/{quote(parent_alias,safe='')}/executions", json={"id":execution_id,"requirement":requirement})
    async def delete_execution(self, realm, execution_id):
        return await self.request("DELETE", f"/admin/realms/{quote(realm,safe='')}/authentication/executions/{quote(execution_id,safe='')}")
    async def priority(self, realm, execution_id, direction):
        return await self.request("POST", f"/admin/realms/{quote(realm,safe='')}/authentication/executions/{quote(execution_id,safe='')}/{direction}-priority")
    async def get_auth_config(self, realm, config_id):
        return await self.request("GET", f"/admin/realms/{quote(realm,safe='')}/authentication/config/{quote(config_id,safe='')}")
    async def set_execution_config(self, realm, execution_id, body):
        return await self.request("POST", f"/admin/realms/{quote(realm,safe='')}/authentication/executions/{quote(execution_id,safe='')}/config", json=body)
    async def update_authenticator_config(self, realm, config_id, body):
        return await self.request("PUT", f"/admin/realms/{quote(realm,safe='')}/authentication/config/{quote(config_id,safe='')}", json=body)
    async def delete_authenticator_config(self, realm, config_id):
        return await self.request("DELETE", f"/admin/realms/{quote(realm,safe='')}/authentication/config/{quote(config_id,safe='')}")
    async def copy_flow(self, realm, source_alias, new_alias):
        return await self.request("POST", f"/admin/realms/{quote(realm,safe='')}/authentication/flows/{quote(source_alias,safe='')}/copy", json={"newName":new_alias})
