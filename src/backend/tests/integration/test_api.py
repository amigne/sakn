import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_endpoint(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "database" in data["checks"]
    assert "redis" in data["checks"]


@pytest.mark.asyncio
async def test_list_tools(client):
    response = await client.get("/api/v1/tools")
    assert response.status_code == 200
    data = response.json()
    assert "tools" in data
    tools = data["tools"]
    assert isinstance(tools, list)
    ping_tools = [t for t in tools if t["name"] == "ping"]
    assert len(ping_tools) == 1
    ping = ping_tools[0]
    assert ping["category"] == "network"
    assert len(ping["parameters"]) > 0


@pytest.mark.asyncio
async def test_execute_unknown_tool(client):
    response = await client.post("/api/v1/tools/nonexistent/execute", json={})
    assert response.status_code == 200
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"


@pytest.mark.asyncio
async def test_health_database_check(client):
    response = await client.get("/health")
    data = response.json()
    assert data["checks"]["database"] in ("ok", "unavailable")
