import pytest


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
    from app.database import async_session_factory
    from app.models.tool_module import ToolModule, RoleToolPermission
    from sqlalchemy import select

    # Use the monkey-patched factory so middleware sees the data
    # Use unique names to avoid conflicts with model tests
    async with async_session_factory() as db:
        tool = ToolModule(name="ping", display_name_key="t.ping", description_key="d.ping",
                          enabled=True, version="1.0")
        db.add(tool)
        await db.flush()
        db.add(RoleToolPermission(role="visitor", tool_id=tool.id, allowed=True))
        await db.commit()

    try:
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
    finally:
        # Clean up to avoid polluting other tests
        async with async_session_factory() as db:
            from sqlalchemy import delete
            await db.execute(delete(RoleToolPermission).where(RoleToolPermission.tool_id == tool.id))
            await db.execute(delete(ToolModule).where(ToolModule.id == tool.id))
            await db.commit()


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
