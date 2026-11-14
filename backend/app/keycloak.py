import httpx
from urllib.parse import quote
from typing import Any

class KeycloakClient:
    def __init__(self, base_url: str, token_url: str, client_id: str, client_secret: str, verify_tls: bool = True):
        self.base_url = base_url.rstrip("/")
        self.token_url = token_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.verify_tls = verify_tls

    async def token(self):
        async with httpx.AsyncClient(verify=self.verify_tls, timeout=20) as client:
            response = await client.post(self.token_url, data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret
            })
            response.raise_for_status()
            return response.json()["access_token"]

    async def request(self, method: str, path: str, **kwargs):
        token = await self.token()
        async with httpx.AsyncClient(verify=self.verify_tls, timeout=30) as client:
            response = await client.request(method, f"{self.base_url}{path}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                **kwargs)
            response.raise_for_status()
            if response.status_code == 204 or not response.content:
                return None
            return response.json()

    async def discover(self):
        async with httpx.AsyncClient(verify=self.verify_tls, timeout=15) as client:
            response = await client.get(f"{self.base_url}/")
            response.raise_for_status()
            info = await client.get(f"{self.base_url}/")
        return {"reachable": True}

    async def realms(self):
        return await self.request("GET", "/admin/realms")

    async def flows(self, realm: str):
        return await self.request("GET", f"/admin/realms/{quote(realm, safe='')}/authentication/flows")

    async def executions(self, realm: str, alias: str):
        return await self.request("GET", f"/admin/realms/{quote(realm, safe='')}/authentication/flows/{quote(alias, safe='')}/executions")

    async def authenticator_providers(self, realm: str):
        # Endpoint exposé par l'API d'administration Keycloak sur les versions qui le supportent.
        return await self.request("GET", f"/admin/realms/{quote(realm, safe='')}/authentication/authenticator-providers")
