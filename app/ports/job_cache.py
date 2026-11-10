"""Persistence contract for job details."""

from abc import ABC, abstractmethod

from app.schemas.jobs import JobDetail


class JobCacheError(RuntimeError):
    """Indicates a storage failure, regardless of the adapter in use."""


class JobCache(ABC):
    """Defines asynchronous operations that are independent of the storage backend."""

    @abstractmethod
    async def get(self, job_id: str) -> JobDetail | None:
        """Retrieves job details or returns None when they are not stored."""

    @abstractmethod
    async def save(self, job: JobDetail) -> None:
        """Inserts or updates a job’s details."""

    @abstractmethod
    async def delete(self, job_id: str) -> None:
        """Removes the details associated with the given ID from storage."""
