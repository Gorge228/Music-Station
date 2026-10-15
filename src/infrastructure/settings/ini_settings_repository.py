"""
Репозиторий настроек приложения.
Сохраняет и читает конфигурацию напрямую из текстового файла settings.txt в корне программы.
"""
import configparser
import logging
import base64
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from core.interfaces.settings_repository import ISettingsRepository

logger = logging.getLogger("MusicFormator")


class IniSettingsRepository(ISettingsRepository):
    """Файловая реализация настроек на базе settings.txt."""

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is not None:
            self._path = config_path
        else:
            cwd_file = Path("settings.txt").resolve()
            if cwd_file.exists():
                self._path = cwd_file
            else:
                candidate = Path(__file__).resolve()
                found_root = None
                for parent in candidate.parents:
                    if (parent / "settings.txt").exists() or (parent / "main.py").exists() or (parent / "run.py").exists():
                        found_root = parent
                        break
                self._path = (found_root / "settings.txt") if found_root else cwd_file

        logger.info(f"Используется файл конфигурации: {self._path}")

    def _read_config(self) -> configparser.ConfigParser:
        config = configparser.ConfigParser()
        if self._path.exists():
            try:
                config.read(str(self._path), encoding="utf-8")
            except Exception as e:
                logger.warning(f"Не удалось прочитать настройки из {self._path}: {e}")
        return config

    def _write_config(self, config: configparser.ConfigParser) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "w", encoding="utf-8") as f:
                config.write(f)
        except Exception as e:
            logger.error(f"Ошибка сохранения настроек в {self._path}: {e}")

    def save_panels_config(self, order: List[str], visible: List[str], active: str) -> None:
        config = self._read_config()
        if not config.has_section("PANELS"):
            config.add_section("PANELS")
        config.set("PANELS", "order", ",".join(order))
        config.set("PANELS", "visible", ",".join(visible))
        config.set("PANELS", "active", active)
        self._write_config(config)

    def load_panels_config(self, default_order: List[str]) -> Dict[str, Any]:
        config = self._read_config()
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
        for panel_key in default_order:
            if panel_key not in order:
                order.append(panel_key)

        visible = [x.strip() for x in visible_raw.split(",") if x.strip()]
        return {"order": order, "visible": visible, "active": active}

    def save_tracklist_columns(
        self, col_widths: Dict[int, int], col_hidden: Dict[int, bool], sort_col: int, sort_order: int
    ) -> None:
        config = self._read_config()
        if not config.has_section("TRACKLIST"):
            config.add_section("TRACKLIST")

        config.set("TRACKLIST", "sort_col", str(sort_col))
        config.set("TRACKLIST", "sort_order", str(sort_order))

        for col_idx, width in col_widths.items():
            config.set("TRACKLIST", f"col_{col_idx}_width", str(width))
        for col_idx, hidden in col_hidden.items():
            config.set("TRACKLIST", f"col_{col_idx}_hidden", str(hidden))

        self._write_config(config)

    def load_tracklist_columns(self) -> Dict[str, Any]:
        config = self._read_config()
        if not config.has_section("TRACKLIST"):
            return {}

        data: Dict[str, Any] = {
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

    def save_last_export_path(self, path_str: str) -> None:
        config = self._read_config()
        if not config.has_section("EXPORT"):
            config.add_section("EXPORT")
        config.set("EXPORT", "last_path", path_str)
        self._write_config(config)

    def load_last_export_path(self) -> str:
        config = self._read_config()
        if config.has_section("EXPORT"):
            return config.get("EXPORT", "last_path", fallback="")
        return ""

    def save_custom_templates(self, track_templates: List[str], album_templates: List[str]) -> None:
        config = self._read_config()
        if not config.has_section("TEMPLATES"):
            config.add_section("TEMPLATES")
        config.set("TEMPLATES", "track_templates", ";;".join(track_templates))
        config.set("TEMPLATES", "album_templates", ";;".join(album_templates))
        self._write_config(config)

    def load_custom_templates(self) -> Tuple[List[str], List[str]]:
        config = self._read_config()
        if not config.has_section("TEMPLATES"):
            return [], []
        tr_raw = config.get("TEMPLATES", "track_templates", fallback="")
        alb_raw = config.get("TEMPLATES", "album_templates", fallback="")
        tr_list = [x.strip() for x in tr_raw.split(";;") if x.strip()]
        alb_list = [x.strip() for x in alb_raw.split(";;") if x.strip()]
        return tr_list, alb_list

    def save_window_state(self, geometry: bytes, splitter_state: bytes) -> None:
        config = self._read_config()
        if not config.has_section("WINDOW"):
            config.add_section("WINDOW")
        config.set("WINDOW", "geometry", base64.b64encode(geometry).decode("ascii"))
        config.set("WINDOW", "splitter", base64.b64encode(splitter_state).decode("ascii"))
        self._write_config(config)

    def load_window_state(self) -> Tuple[Optional[bytes], Optional[bytes]]:
        config = self._read_config()
        if not config.has_section("WINDOW"):
            return None, None
        geo_b64 = config.get("WINDOW", "geometry", fallback="")
        spl_b64 = config.get("WINDOW", "splitter", fallback="")
        geo = base64.b64decode(geo_b64) if geo_b64 else None
        spl = base64.b64decode(spl_b64) if spl_b64 else None
        return geo, spl