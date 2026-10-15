"""
Настройка централизованного логгера приложения.
Включает ротацию файлов логов, форматирование и перехват критических необработанных исключений.
"""
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logger(app_name: str = "MusicFormator") -> logging.Logger:
    """Инициализирует и возвращает настроенный глобальный логгер."""
    # Каталог logs создается рядом со скриптом запуска
    log_dir = Path(__file__).resolve().parents[2] / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "app.log"

    logger = logging.getLogger(app_name)
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        logger.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(module)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Вывод в консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Ротация файлов (до 3 файлов по 5 МБ)
    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        logger.critical("Необработанное исключение (CRASH):", exc_info=(exc_type, exc_value, exc_traceback))

    sys.excepthook = handle_uncaught_exception
    return logger