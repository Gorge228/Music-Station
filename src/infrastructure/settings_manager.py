# infrastructure/settings_manager.py
"""
Менеджер сохранения и загрузки конфигураций в текстовый файл settings.txt.
Хранит состояние панелей (видимость, порядок, активная вкладка)
и параметры колонок треклиста в человекочитаемом формате.
"""
from pathlib import Path
import configparser
import logging

logger = logging.getLogger("MusicFormator")


class SettingsManager:
    SETTINGS_FILE = Path("settings.txt")

    @classmethod
    def _get_config(cls) -> configparser.ConfigParser:
        config = configparser.ConfigParser()
        if cls.SETTINGS_FILE.exists():
            try:
                config.read(cls.SETTINGS_FILE, encoding="utf-8")
            except Exception as e:
                logger.warning(f"Не удалось прочитать {cls.SETTINGS_FILE}: {e}")
        return config

    @classmethod
    def _save_config(cls, config: configparser.ConfigParser) -> None:
        try:
            with open(cls.SETTINGS_FILE, "w", encoding="utf-8") as f:
                config.write(f)
        except Exception as e:
            logger.error(f"Ошибка сохранения настроек в {cls.SETTINGS_FILE}: {e}")

    # --- Настройки панелей инспектора ---

    @classmethod
    def save_panels_config(cls, order: list[str], visible: list[str], active: str) -> None:
        config = cls._get_config()
        if not config.has_section("PANELS"):
            config.add_section("PANELS")
        config.set("PANELS", "order", ",".join(order))
        config.set("PANELS", "visible", ",".join(visible))
        config.set("PANELS", "active", active)
        cls._save_config(config)

    @classmethod
    def load_panels_config(cls, default_order: list[str]) -> dict:
        config = cls._get_config()
        if not config.has_section("PANELS"):
            return {
                "order": default_order,
                "visible": default_order,
                "active": default_order[0] if default_order else ""
            }

        order_raw = config.get("PANELS", "order", fallback=",".join(default_order))
        visible_raw = config.get("PANELS", "visible", fallback=",".join(default_order))
        active = config.get("PANELS", "active", fallback=default_order[0] if default_order else "")

        order = [x.strip() for x in order_raw.split(",") if x.strip()]
        # Добавляем новые панели, если они появились в коде
        for p in default_order:
            if p not in order:
                order.append(p)

        visible = [x.strip() for x in visible_raw.split(",") if x.strip()]
        return {
            "order": order,
            "visible": visible,
            "active": active
        }

    # --- Настройки колонок треклиста ---

    @classmethod
    def save_tracklist_columns(cls, col_widths: dict[int, int], col_hidden: dict[int, bool], sort_col: int, sort_order: int) -> None:
        config = cls._get_config()
        if not config.has_section("TRACKLIST"):
            config.add_section("TRACKLIST")

        config.set("TRACKLIST", "sort_col", str(sort_col))
        config.set("TRACKLIST", "sort_order", str(sort_order))

        for col_idx, width in col_widths.items():
            config.set("TRACKLIST", f"col_{col_idx}_width", str(width))
        for col_idx, hidden in col_hidden.items():
            config.set("TRACKLIST", f"col_{col_idx}_hidden", str(hidden))

        cls._save_config(config)

    @classmethod
    def load_tracklist_columns(cls) -> dict:
        config = cls._get_config()
        if not config.has_section("TRACKLIST"):
            return {}

        data = {
            "sort_col": config.getint("TRACKLIST", "sort_col", fallback=1),
            "sort_order": config.getint("TRACKLIST", "sort_order", fallback=0),
            "widths": {},
            "hidden": {}
        }

        for key, val in config.items("TRACKLIST"):
            if key.startswith("col_") and key.endswith("_width"):
                try:
                    c_idx = int(key.split("_")[1])
                    data["widths"][c_idx] = int(val)
                except ValueError:
                    pass
            elif key.startswith("col_") and key.endswith("_hidden"):
                try:
                    c_idx = int(key.split("_")[1])
                    data["hidden"][c_idx] = val.lower() in ("true", "1", "yes")
                except ValueError:
                    pass

        return data

    @classmethod
    def save_last_export_path(cls, path_str: str) -> None:
        config = cls._get_config()
        if not config.has_section("EXPORT"):
            config.add_section("EXPORT")
        config.set("EXPORT", "last_path", path_str)
        cls._save_config(config)

    @classmethod
    def load_last_export_path(cls) -> str:
        config = cls._get_config()
        if config.has_section("EXPORT"):
            return config.get("EXPORT", "last_path", fallback="")
        return ""