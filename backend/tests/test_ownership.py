"""Unit tests for workspace ownership boundaries and anti-existence-probing 404 responses."""

import uuid
import pytest
from fastapi import HTTPException
from api.dependencies import require_workspace_access
from db.models import User, Workspace
from db.session import session_scope


def test_workspace_ownership_authorization():
    """User who owns a workspace should successfully pass authorization."""
    owner_id = uuid.uuid4()
    ws_id = uuid.uuid4()

    owner_user = User(
        id=owner_id,
        email="owner@nexus.ai",
        name="Owner User",
        role="analyst",
        is_active=True,
    )

    with session_scope() as session:
        ws = Workspace(id=ws_id, name="Confidential Diligence Room", owner_id=owner_id)
        session.add(ws)
        session.flush()

        class DummyRequest:
            state = type("State", (), {})()

        req = DummyRequest()
        authed_ws = require_workspace_access(str(ws_id), req, current_user=owner_user)
        assert authed_ws.id == ws_id


def test_workspace_isolation_unauthorized_user_gets_404():
    """Unauthorized user attempting to access another user's workspace must receive a 404, not 403.
    
    This prevents enumeration and existence probing of confidential client data rooms.
    """
    owner_id = uuid.uuid4()
    other_user_id = uuid.uuid4()
    ws_id = uuid.uuid4()

    other_user = User(
        id=other_user_id,
        email="other@nexus.ai",
        name="Other Analyst",
        role="analyst",
        is_active=True,
    )

    with session_scope() as session:
        ws = Workspace(id=ws_id, name="Private M&A Deal Room", owner_id=owner_id)
        session.add(ws)
        session.flush()

        class DummyRequest:
            state = type("State", (), {})()

        req = DummyRequest()
        with pytest.raises(HTTPException) as exc_info:
            require_workspace_access(str(ws_id), req, current_user=other_user)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Workspace not found"
