from __future__ import annotations

from typing import List, Optional

from auto_summarization.domain.analysis import AnalysisTemplate
from auto_summarization.domain.session import Session
from auto_summarization.domain.user import User
from auto_summarization.services.config import database

from .base import IRepository


class UserRepository(IRepository):
    def add(self, data: User) -> None:
        database.users[data.user_id] = data

    def get(self, object_id: str) -> Optional[User]:
        return database.users.get(object_id)

    def delete(self, user_id: str) -> None:
        database.users.pop(user_id, None)

    def list(self) -> List[User]:
        return list(database.users.values())


class SessionRepository(IRepository):
    def add(self, data: Session) -> None:
        owner = database.users.get(getattr(data, "user_id", ""))
        if owner:
            owner.sessions.append(data)

    def get(self, object_id: str) -> Optional[Session]:
        for user in database.users.values():
            for session in user.sessions:
                if session.session_id == object_id:
                    return session
        return None

    def list_for_user(self, user_id: str) -> List[Session]:
        user = database.users.get(user_id)
        return list(user.sessions) if user else []


class AnalysisTemplateRepository(IRepository):
    def add(self, data: AnalysisTemplate) -> None:
        database.templates[data.category_index] = data

    def get(self, object_id: str) -> Optional[AnalysisTemplate]:
        for template in database.templates.values():
            if template.template_id == object_id:
                return template
        return None

    def list(self) -> List[AnalysisTemplate]:
        return list(sorted(database.templates.values(), key=lambda item: item.category_index))

    def list_by_category(self, category_index: int) -> List[AnalysisTemplate]:
        template = database.templates.get(category_index)
        return [template] if template else []

    def get_by_category(self, category_index: int) -> AnalysisTemplate | None:
        return database.templates.get(category_index)
