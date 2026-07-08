"""Model registry — import all ORM models so ``Base.metadata`` discovers them."""

from app.models.chat_session_model import ChatSession
from app.models.file_record_model import FileRecord
from app.models.message_model import Message
from app.models.project_model import Project
from app.models.user_model import AppUser
from app.models.user_settings_model import UserSettings
