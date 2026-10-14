"""Persistence: in-memory for local runs, Azure Cosmos DB (serverless) in the cloud."""

from __future__ import annotations

import logging
from typing import Protocol

log = logging.getLogger("lasso.store")


class Store(Protocol):
    async def get_user(self, user_id: str) -> dict | None: ...
    async def put_user(self, user: dict) -> None: ...
    async def list_users(self) -> list[dict]: ...
    async def put_call(self, call: dict) -> None: ...
    async def calls_for_market(self, market_id: str) -> list[dict]: ...
    async def calls_for_user(self, user_id: str) -> list[dict]: ...
    async def get_league(self, code: str) -> dict | None: ...
    async def put_league(self, league: dict) -> None: ...


class MemoryStore:
    def __init__(self) -> None:
        self.users: dict[str, dict] = {}
        self.calls: dict[str, dict] = {}
        self.leagues: dict[str, dict] = {}

    async def get_user(self, user_id: str) -> dict | None:
        return self.users.get(user_id)

    async def put_user(self, user: dict) -> None:
        self.users[user["id"]] = user

    async def list_users(self) -> list[dict]:
        return list(self.users.values())

    async def put_call(self, call: dict) -> None:
        self.calls[call["id"]] = call

    async def calls_for_market(self, market_id: str) -> list[dict]:
        return [c for c in self.calls.values() if c["market_id"] == market_id]

    async def calls_for_user(self, user_id: str) -> list[dict]:
        return sorted((c for c in self.calls.values() if c["user_id"] == user_id),
                      key=lambda c: c["placed_at"], reverse=True)

    async def get_league(self, code: str) -> dict | None:
        return self.leagues.get(code)

    async def put_league(self, league: dict) -> None:
        self.leagues[league["code"]] = league


class CosmosStore:
    """Cosmos DB for NoSQL with Entra ID auth (managed identity in Azure)."""

    def __init__(self, endpoint: str, database: str, client_id: str = "") -> None:
        from azure.cosmos.aio import CosmosClient
        from azure.identity.aio import DefaultAzureCredential

        cred = DefaultAzureCredential(managed_identity_client_id=client_id or None)
        self._client = CosmosClient(endpoint, credential=cred)
        db = self._client.get_database_client(database)
        self.users = db.get_container_client("users")
        self.calls = db.get_container_client("calls")
        self.leagues = db.get_container_client("leagues")

    async def get_user(self, user_id: str) -> dict | None:
        from azure.cosmos.exceptions import CosmosResourceNotFoundError
        try:
            return await self.users.read_item(user_id, partition_key=user_id)
        except CosmosResourceNotFoundError:
            return None

    async def put_user(self, user: dict) -> None:
        await self.users.upsert_item(user)

    async def list_users(self) -> list[dict]:
        return [u async for u in self.users.query_items(
            "SELECT TOP 200 * FROM u ORDER BY u.biscuits DESC")]

    async def put_call(self, call: dict) -> None:
        await self.calls.upsert_item(call)

    async def calls_for_market(self, market_id: str) -> list[dict]:
        return [c async for c in self.calls.query_items(
            "SELECT * FROM c WHERE c.market_id = @m", parameters=[{"name": "@m", "value": market_id}])]

    async def calls_for_user(self, user_id: str) -> list[dict]:
        return [c async for c in self.calls.query_items(
            "SELECT TOP 50 * FROM c WHERE c.user_id = @u ORDER BY c.placed_at DESC",
            parameters=[{"name": "@u", "value": user_id}], partition_key=user_id)]

    async def get_league(self, code: str) -> dict | None:
        from azure.cosmos.exceptions import CosmosResourceNotFoundError
        try:
            return await self.leagues.read_item(code, partition_key=code)
        except CosmosResourceNotFoundError:
            return None

    async def put_league(self, league: dict) -> None:
        await self.leagues.upsert_item({**league, "id": league["code"]})


def make_store(endpoint: str, database: str, client_id: str = "") -> Store:
    if endpoint:
        log.info("using Cosmos DB at %s", endpoint)
        return CosmosStore(endpoint, database, client_id)
    log.info("using in-memory store")
    return MemoryStore()
