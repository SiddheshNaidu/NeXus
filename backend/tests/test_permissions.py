"""Sprint 1 acceptance tests — Workspace, Identity, Permissions.

Acceptance criteria from PRD §54:
  ✓ Viewer / Contributor / Admin permissions enforce correct access levels.
  ✓ User A cannot access User B's workspace.
  ✓ Permission checks are fully decoupled and reusable (tested via service layer directly).
"""
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.workspaces import WorkspaceMember
from app.services.permissions import Role, require_workspace_role, role_at_least

# Import fixtures from the sprint-1 conftest
pytest_plugins = ("tests.conftest_sprint1",)


# ===========================================================================
# Unit tests — permission service in isolation (no HTTP, no routes)
# ===========================================================================


class TestRoleHierarchy:
    """role_at_least() correctly implements the viewer < contributor < admin order."""

    def test_viewer_satisfies_viewer(self):
        assert role_at_least("viewer", Role.VIEWER) is True

    def test_viewer_fails_contributor(self):
        assert role_at_least("viewer", Role.CONTRIBUTOR) is False

    def test_viewer_fails_admin(self):
        assert role_at_least("viewer", Role.ADMIN) is False

    def test_contributor_satisfies_viewer(self):
        assert role_at_least("contributor", Role.VIEWER) is True

    def test_contributor_satisfies_contributor(self):
        assert role_at_least("contributor", Role.CONTRIBUTOR) is True

    def test_contributor_fails_admin(self):
        assert role_at_least("contributor", Role.ADMIN) is False

    def test_admin_satisfies_all(self):
        assert role_at_least("admin", Role.VIEWER) is True
        assert role_at_least("admin", Role.CONTRIBUTOR) is True
        assert role_at_least("admin", Role.ADMIN) is True

    def test_unknown_role_fails(self):
        assert role_at_least("superuser", Role.VIEWER) is False


# ===========================================================================
# Service-layer tests — require_workspace_role called directly (reusability proof)
# ===========================================================================


@pytest.mark.asyncio
async def test_service_admin_can_access_own_workspace(db_session: AsyncSession, seed):
    """Admin calling the service directly must succeed."""
    membership = await require_workspace_role(
        db_session, seed.user_a, seed.workspace_a.id, Role.ADMIN
    )
    assert isinstance(membership, WorkspaceMember)
    assert membership.role == "admin"


@pytest.mark.asyncio
async def test_service_viewer_satisfies_viewer_requirement(db_session: AsyncSession, seed):
    """user_a is VIEWER of workspace_b — should pass a viewer check."""
    membership = await require_workspace_role(
        db_session, seed.user_a, seed.workspace_b.id, Role.VIEWER
    )
    assert membership.role == "viewer"


@pytest.mark.asyncio
async def test_service_viewer_blocked_for_contributor(db_session: AsyncSession, seed):
    """user_a is VIEWER of workspace_b — must be blocked when CONTRIBUTOR is required."""
    from app.core.errors import ForbiddenError
    with pytest.raises(ForbiddenError):
        await require_workspace_role(
            db_session, seed.user_a, seed.workspace_b.id, Role.CONTRIBUTOR
        )


@pytest.mark.asyncio
async def test_service_non_member_blocked(db_session: AsyncSession, seed):
    """user_b has NO membership in workspace_a — must raise ForbiddenError."""
    from app.core.errors import ForbiddenError
    with pytest.raises(ForbiddenError):
        await require_workspace_role(
            db_session, seed.user_b, seed.workspace_a.id, Role.VIEWER
        )


@pytest.mark.asyncio
async def test_service_nonexistent_workspace_raises_404(db_session: AsyncSession, seed):
    """A workspace UUID that does not exist must raise NotFoundError."""
    from app.core.errors import NotFoundError
    with pytest.raises(NotFoundError):
        await require_workspace_role(
            db_session, seed.user_a, uuid.uuid4(), Role.VIEWER
        )


# ===========================================================================
# HTTP integration tests — routes enforce auth end-to-end
# ===========================================================================


@pytest.mark.asyncio
async def test_me_returns_200_with_valid_user(client: AsyncClient, seed):
    resp = await client.get("/api/v1/me", headers={"X-Dev-User-ID": str(seed.user_a.id)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == seed.user_a.email
    # user_a is in workspace_a (admin) and workspace_b (viewer)
    ws_ids = {w["id"] for w in body["workspaces"]}
    assert str(seed.workspace_a.id) in ws_ids
    assert str(seed.workspace_b.id) in ws_ids


@pytest.mark.asyncio
async def test_me_returns_401_without_header(client: AsyncClient):
    resp = await client.get("/api/v1/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_me_returns_401_unknown_user(client: AsyncClient):
    resp = await client.get("/api/v1/me", headers={"X-Dev-User-ID": str(uuid.uuid4())})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_workspace_viewer_allowed(client: AsyncClient, seed):
    """user_a (VIEWER of workspace_b) can GET workspace_b."""
    resp = await client.get(
        f"/api/v1/workspaces/{seed.workspace_b.id}",
        headers={"X-Dev-User-ID": str(seed.user_a.id)},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "viewer"


@pytest.mark.asyncio
async def test_get_workspace_non_member_forbidden(client: AsyncClient, seed):
    """Critical isolation: user_b must be blocked from workspace_a (403)."""
    resp = await client.get(
        f"/api/v1/workspaces/{seed.workspace_a.id}",
        headers={"X-Dev-User-ID": str(seed.user_b.id)},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.asyncio
async def test_list_workspaces_only_own(client: AsyncClient, seed):
    """user_b must only see workspace_b, not workspace_a."""
    resp = await client.get(
        "/api/v1/workspaces",
        headers={"X-Dev-User-ID": str(seed.user_b.id)},
    )
    assert resp.status_code == 200
    ids = {w["id"] for w in resp.json()}
    assert str(seed.workspace_b.id) in ids
    assert str(seed.workspace_a.id) not in ids


@pytest.mark.asyncio
async def test_collections_requires_membership(client: AsyncClient, seed):
    """user_b cannot list collections from workspace_a."""
    resp = await client.get(
        f"/api/v1/workspaces/{seed.workspace_a.id}/collections",
        headers={"X-Dev-User-ID": str(seed.user_b.id)},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_collections_viewer_can_list(client: AsyncClient, seed, db_session: AsyncSession):
    """user_a (VIEWER of workspace_b) can list collections in workspace_b."""
    from app.db.models.workspaces import Collection
    col = Collection(id=uuid.uuid4(), workspace_id=seed.workspace_b.id, name="Test Col")
    db_session.add(col)
    await db_session.commit()

    resp = await client.get(
        f"/api/v1/workspaces/{seed.workspace_b.id}/collections",
        headers={"X-Dev-User-ID": str(seed.user_a.id)},
    )
    assert resp.status_code == 200
    names = [c["name"] for c in resp.json()]
    assert "Test Col" in names


@pytest.mark.asyncio
async def test_role_in_me_response_matches_membership(client: AsyncClient, seed):
    """Roles surfaced in /me must match the actual membership rows."""
    resp = await client.get("/api/v1/me", headers={"X-Dev-User-ID": str(seed.user_a.id)})
    workspaces = {w["id"]: w["role"] for w in resp.json()["workspaces"]}
    assert workspaces[str(seed.workspace_a.id)] == "admin"
    assert workspaces[str(seed.workspace_b.id)] == "viewer"


@pytest.mark.asyncio
async def test_admin_sees_own_workspace_as_admin(client: AsyncClient, seed):
    """user_b is ADMIN of workspace_b — role must surface correctly."""
    resp = await client.get(
        f"/api/v1/workspaces/{seed.workspace_b.id}",
        headers={"X-Dev-User-ID": str(seed.user_b.id)},
    )
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"
