"""
Structured Logging Module for Trivox AI Models

Provides consistent logging across the application with support for
structured JSON logging, log rotation, and context tracking.
"""

import logging
import logging.handlers
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from functools import wraps
import traceback


class StructuredLogFormatter(logging.Formatter):
    """Custom formatter that outputs JSON structured logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info),
            }

        # Add extra fields
        if hasattr(record, "context"):
            log_data["context"] = record.context

        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms

        if hasattr(record, "pipeline_stage"):
            log_data["pipeline_stage"] = record.pipeline_stage

        return json.dumps(log_data, default=str)


class Logger:
    """
    Application logger with structured logging support.

    Usage:
        from core.logger import get_logger

        logger = get_logger(__name__)
        logger.info("Processing started", context={"image": "path/to/img.jpg"})

        # With timing
        with logger.timed("pipeline"):
            run_pipeline()
    """

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)
        self._setup_handlers()

    def _setup_handlers(self):
        """Setup log handlers if not already configured."""
        if self._logger.handlers:
            return

        # Create logs directory in user's AppData (writable location)
        import os

        app_data = (
            os.environ.get("LOCALAPPDATA")
            or os.environ.get("APPDATA")
            or str(Path.home())
        )
        log_dir = Path(app_data) / "Trivox AI Models" / "logs"
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # Fallback to temp directory if AppData is not writable
            log_dir = (
                Path(os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp")
                / "Trivox AI Models"
                / "logs"
            )
            log_dir.mkdir(parents=True, exist_ok=True)

        # Console handler with simple format for development
        console_handler = logging.StreamHandler(sys.stdout)
        console_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(console_format)
        console_handler.setLevel(logging.INFO)

        # File handler with JSON format for structured logging
        file_handler = logging.handlers.RotatingFileHandler(
            log_dir / "app.log",
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(StructuredLogFormatter())
        file_handler.setLevel(logging.DEBUG)

        self._logger.addHandler(console_handler)
        self._logger.addHandler(file_handler)
        self._logger.setLevel(logging.DEBUG)

    def _log(self, level: int, message: str, **kwargs):
        """Internal log method with extra context."""
        extra = {}

        if "context" in kwargs:
            extra["context"] = kwargs["context"]
        if "duration_ms" in kwargs:
            extra["duration_ms"] = kwargs["duration_ms"]
        if "pipeline_stage" in kwargs:
            extra["pipeline_stage"] = kwargs["pipeline_stage"]

        self._logger.log(level, message, extra=extra)

    def debug(self, message: str, **kwargs):
        """Log debug message."""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        """Log info message."""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        """Log warning message."""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        """Log error message."""
        self._log(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        """Log critical message."""
        self._log(logging.CRITICAL, message, **kwargs)

    def exception(self, message: str, **kwargs):
        """Log exception with traceback."""
        self._logger.exception(message, extra=kwargs)

    def timed(self, stage_name: str):
        """Context manager for timing operations."""
        return TimedContext(self, stage_name)


class TimedContext:
    """Context manager for timing operations."""

    def __init__(self, logger: Logger, stage_name: str):
        self.logger = logger
        self.stage_name = stage_name
        self.start_time: Optional[datetime] = None

    def __enter__(self):
        self.start_time = datetime.utcnow()
        self.logger.debug(f"Started: {self.stage_name}", pipeline_stage=self.stage_name)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = (datetime.utcnow() - self.start_time).total_seconds() * 1000

            if exc_type:
                self.logger.error(
                    f"Failed: {self.stage_name}",
                    duration_ms=duration,
                    pipeline_stage=self.stage_name,
                    context={"error": str(exc_val)},
                )
            else:
                self.logger.info(
                    f"Completed: {self.stage_name}",
                    duration_ms=duration,
                    pipeline_stage=self.stage_name,
                )


# Global logger cache
_loggers: Dict[str, Logger] = {}


def get_logger(name: str) -> Logger:
    """Get or create logger for a module."""
    if name not in _loggers:
        _loggers[name] = Logger(name)
    return _loggers[name]


def log_exception(func):
    """Decorator to log exceptions with context."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(
                f"Exception in {func.__name__}",
                context={
                    "function": func.__name__,
                    "args": str(args),
                    "kwargs": str(kwargs),
                    "error": str(e),
                },
            )
            raise

    return wrapper


class PipelineStageLogger:
    """
    Helper class for logging pipeline stages with timing.

    Usage:
        stage_logger = PipelineStageLogger(logger, "image_processing")

        with stage_logger.stage("load_image"):
            image = load_image(path)

        with stage_logger.stage("inference"):
            result = run_inference(image)
    """

    def __init__(self, logger: Logger, pipeline_name: str):
        self.logger = logger
        self.pipeline_name = pipeline_name
        self.stage_times: Dict[str, float] = {}

    def stage(self, stage_name: str):
        """Context manager for a pipeline stage."""
        full_name = f"{self.pipeline_name}.{stage_name}"
        return TimedContext(self.logger, full_name)

    def summary(self):
        """Log summary of all stages."""
        total_time = sum(self.stage_times.values())
        self.logger.info(
            f"Pipeline '{self.pipeline_name}' summary",
            context={
                "total_time_ms": total_time,
                "stages": self.stage_times,
            },
        )


__all__ = [
    "get_logger",
    "Logger",
    "log_exception",
    "PipelineStageLogger",
    "TimedContext",
]
