from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from maxinator_bot.app.database.models import Patient
from maxinator_bot.app.domain.models import Page


class PatientRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, patient: Patient) -> Patient:
        self.session.add(patient)
        await self.session.flush()
        return patient

    async def get_by_id(
        self,
        patient_id: UUID,
        *,
        for_update: bool = False,
    ) -> Patient | None:
        statement = select(Patient).where(Patient.id == patient_id)
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def get_active_by_id(self, patient_id: UUID) -> Patient | None:
        statement = select(Patient).where(
            Patient.id == patient_id,
            Patient.is_archived.is_(False),
        )
        return await self.session.scalar(statement)

    async def get_active_by_code(self, public_code: str) -> Patient | None:
        statement = select(Patient).where(
            Patient.public_code == public_code,
            Patient.is_archived.is_(False),
        )
        return await self.session.scalar(statement)

    async def list_active(
        self,
        page: int,
        page_size: int = 10,
    ) -> Page[Patient]:
        page = max(0, page)
        filters = (Patient.is_archived.is_(False),)
        total = await self.session.scalar(
            select(func.count(Patient.id)).where(*filters),
        )
        statement = (
            select(Patient)
            .where(*filters)
            .order_by(Patient.created_at.desc(), Patient.id.desc())
            .offset(page * page_size)
            .limit(page_size)
        )
        patients = list((await self.session.scalars(statement)).all())
        return Page(
            items=patients,
            page=page,
            page_size=page_size,
            total=total or 0,
        )
