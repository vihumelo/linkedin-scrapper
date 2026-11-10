"""Configuração de logs estruturados e contexto de requisição."""

import json
import logging
import logging.config
import re
import uuid
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

REQUEST_ID_CONTEXT: ContextVar[str | None] = ContextVar("request_id", default=None)
_LOGGING_CONFIGURED = False
_STANDARD_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__)


class JSONLogFormatter(logging.Formatter):
    """Serializa eventos de log como JSON com correlação de requisição."""

    def format(self, record: logging.LogRecord) -> str:
        """Formata evento, contexto e campos extras sem registrar dados da requisição."""

        event: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None) or REQUEST_ID_CONTEXT.get()
        if request_id:
            event["request_id"] = request_id

        for field, value in record.__dict__.items():
            if field not in _STANDARD_RECORD_FIELDS and field not in {"message", "asctime"}:
                event[field] = value

        if record.exc_info:
            event["exception"] = self.formatException(record.exc_info)
        return json.dumps(event, ensure_ascii=False, default=str)


def configure_logging() -> None:
    """Configura uma saída JSON única para os logs da aplicação e do Uvicorn."""

    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {"()": "app.core.observability.JSONLogFormatter"},
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                    "formatter": "json",
                },
            },
            "root": {"level": "INFO", "handlers": ["console"]},
            "loggers": {
                "uvicorn": {"level": "INFO", "handlers": ["console"], "propagate": False},
                "uvicorn.error": {
                    "level": "INFO",
                    "handlers": ["console"],
                    "propagate": False,
                },
                "uvicorn.access": {"level": "WARNING", "handlers": [], "propagate": False},
                "httpx": {"level": "WARNING", "propagate": True},
                "httpx2": {"level": "WARNING", "propagate": True},
            },
        }
    )
    _LOGGING_CONFIGURED = True


def choose_request_id(candidate: str | None) -> str:
    """Valida o ID recebido ou gera um novo para evitar conteúdo inseguro nos logs."""

    if candidate and len(candidate) <= 64 and re.fullmatch(r"[A-Za-z0-9._-]+", candidate):
        return candidate
    return uuid.uuid4().hex
