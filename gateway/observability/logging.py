from __future__ import annotations
import logging, sys
import structlog
from contextvars import ContextVar

run_id_var: ContextVar[str | None] = ContextVar("run_id", default=None)

def configure_logging(level: str = "INFO", json_logs: bool = True) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        stream=sys.stdout,
        format="%(message)s",
    )

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )

def get_logger(name: str = "agw"):
    return structlog.get_logger(name)

def bind_run_id(run_id: str | None):
    structlog.contextvars.bind_contextvars(run_id=run_id or "-")
