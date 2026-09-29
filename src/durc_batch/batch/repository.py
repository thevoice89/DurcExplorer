"""Persistenza dello stato delle richieste (idempotenza + ripresa batch)."""
from collections.abc import Iterable
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from durc_batch.core.logging_conf import get_logger
from durc_batch.models import DurcRequest, RequestStatus

logger = get_logger(__name__)


class _Base(DeclarativeBase):
    """Base declarative SQLAlchemy."""


class _DurcRequestRow(_Base):
    """Riga di persistenza dello stato di una richiesta DURC."""
    __tablename__ = "durc_requests"

    codice_fiscale: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, index=True)
    request_id: Mapped[str | None] = mapped_column(String, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class StateRepository:
    """Repository (SQLAlchemy/SQLite) per lo stato di ogni DurcRequest."""

    def __init__(self, db_url: str) -> None:
        """Inizializza engine/sessione e crea lo schema se assente."""
        self._engine = create_engine(db_url, future=True)
        _Base.metadata.create_all(self._engine)

    def upsert(self, request: DurcRequest) -> None:
        """Inserisce o aggiorna lo stato di una richiesta (chiave: codice_fiscale)."""
        with Session(self._engine) as session:
            row = session.get(_DurcRequestRow, request.codice_fiscale)
            if row is None:
                row = _DurcRequestRow(codice_fiscale=request.codice_fiscale)
                session.add(row)
            row.status = request.status.value
            row.request_id = request.request_id
            row.attempts = request.attempts
            row.last_error = request.last_error
            row.updated_at = datetime.now(timezone.utc)
            session.commit()

    def get_by_status(self, status: RequestStatus) -> Iterable[DurcRequest]:
        """Ritorna tutte le richieste in un dato stato (per il polling/retry)."""
        with Session(self._engine) as session:
            rows = session.execute(
                select(_DurcRequestRow).where(_DurcRequestRow.status == status.value)
            ).scalars().all()
            return [self._to_model(row) for row in rows]

    @staticmethod
    def _to_model(row: _DurcRequestRow) -> DurcRequest:
        """Converte una riga ORM nel DTO di dominio."""
        return DurcRequest(
            codice_fiscale=row.codice_fiscale,
            status=RequestStatus(row.status),
            request_id=row.request_id,
            attempts=row.attempts,
            last_error=row.last_error,
            updated_at=row.updated_at,
        )
