import pytest
from unittest.mock import AsyncMock, MagicMock

import main
from modules.todo.services import TodoService
from modules.todo.controllers import get_service
from modules.todo.repositories import TodoRepository
from core.auth import UserInfo


@pytest.fixture
def mock_repo():
    repo = MagicMock(spec=TodoRepository)
    repo.list = AsyncMock()
    repo.get = AsyncMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.delete = AsyncMock()
    return repo


@pytest.fixture
def mock_user():
    return UserInfo(user_id="user123", email="test@example.com")


@pytest.fixture
def mock_todo_service(mock_repo, mock_user):
    service = TodoService(mock_repo, mock_user, MagicMock())
    main.app.dependency_overrides[get_service] = lambda: service
    yield service
    main.app.dependency_overrides.clear()
