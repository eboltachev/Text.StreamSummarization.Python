from stream_summarization.domain.report import ReportTemplate
from stream_summarization.domain.session import Session
from stream_summarization.domain.user import User
from stream_summarization.services.config import Session as DB

from .base import IRepository


class UserRepository(IRepository):
    def __init__(self, db: DB):
        self.db = db

    def add(self, data: User) -> None:
        self.db.add(data)

    def get(self, object_id: str):
        return self.db.query(User).filter_by(user_id=object_id).first()

    def delete(self, user_id: str) -> None:
        user = self.db.query(User).filter_by(user_id=user_id).first()
        if user:
            self.db.delete(user)

    def list(self):
        return self.db.query(User).all()


class SessionRepository(IRepository):
    def __init__(self, db: DB):
        self.db = db

    def add(self, data: Session) -> None:
        self.db.add(data)

    def get(self, object_id: str):
        return self.db.query(Session).filter_by(session_id=object_id).first()

    def list_for_user(self, user_id: str):
        return self.db.query(Session).filter_by(user_id=user_id).all()


class ReportTemplateRepository(IRepository):
    def __init__(self, db: DB):
        self.db = db

    def add(self, data: ReportTemplate) -> None:
        self.db.add(data)

    def get(self, object_id: str):
        return self.db.query(ReportTemplate).filter_by(template_id=object_id).first()

    def list(self):
        return self.db.query(ReportTemplate).all()

    def list_by_report_types(self, report_index: int):
        return (
            self.db.query(ReportTemplate)
            .filter_by(report_index=report_index)
            .all()
        )
