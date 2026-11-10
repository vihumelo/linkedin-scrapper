"""Contrato de persistência para detalhes de vagas."""

from abc import ABC, abstractmethod

from app.schemas.jobs import JobDetail


class JobCacheError(RuntimeError):
    """Indica uma falha de armazenamento independente do adapter utilizado."""


class JobCache(ABC):
    """Define operações assíncronas independentes do armazenamento utilizado."""

    @abstractmethod
    async def get(self, job_id: str) -> JobDetail | None:
        """Recupera os detalhes da vaga ou retorna nulo quando não estão armazenados."""

    @abstractmethod
    async def save(self, job: JobDetail) -> None:
        """Insere ou atualiza os detalhes de uma vaga."""

    @abstractmethod
    async def delete(self, job_id: str) -> None:
        """Remove do armazenamento os detalhes associados ao ID informado."""
