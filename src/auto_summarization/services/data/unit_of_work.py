from __future__ import annotations

import abc

from auto_summarization.adapters.repository import (
    AnalysisTemplateRepository,
    SessionRepository,
    UserRepository,
)


class IUoW(abc.ABC):
    def __enter__(self) -> IUoW:
        return self

    def __exit__(self, *args):
        self.rollback()

    @abc.abstractmethod
    def commit(self):
        raise NotImplementedError

    @abc.abstractmethod
    def rollback(self):
        raise NotImplementedError


class UserUoW(IUoW):
    def __enter__(self) -> UserUoW:
        self.users = UserRepository()
        self.sessions = SessionRepository()
        self.templates = AnalysisTemplateRepository()
        return super().__enter__()

    def commit(self):
        return None

    def rollback(self):
        return None


class AnalysisTemplateUoW(IUoW):
    def __enter__(self) -> AnalysisTemplateUoW:
        self.templates = AnalysisTemplateRepository()
        return super().__enter__()

    def commit(self):
        return None

    def rollback(self):
        return None
