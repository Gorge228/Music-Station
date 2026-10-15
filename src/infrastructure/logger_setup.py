# infrastructure/logger_setup.py
"""Конфигурация потокобезопасного логгера с ротацией файлов и перехватом крашей."""
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(app_name: str = "MusicFormator") -> logging.Logger:
    """Инициализирует глобальный логгер приложения."""
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "app.log"

    logger = logging.getLogger(app_name)
    logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)-8s | %(module)s:%(lineno)d | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    if logger.hasHandlers():
        logger.handlers.clear()

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical("Необработанное исключение (КРАШ):", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_exception
    return logger