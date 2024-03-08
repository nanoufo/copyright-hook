import datetime
from pathlib import PurePath, Path
from typing import Optional, Any, Callable, Dict

import yaml

from copyrighthook.years_pattern import YearsPattern


class CopyrightConfig:
    license_file: PurePath
    ignore_commits_before: Optional[datetime.datetime]
    pattern: YearsPattern

    def __init__(self, config: Dict[str, object]) -> None:
        self._raw = config
        self.ignore_commits_before = self._get(
            "ignore_commits_before", parser=self._parse_datetime, default=None
        )
        self.pattern = self._get("pattern", parser=YearsPattern, types=str)
        self.license_file = self._get("license_file", parser=PurePath, default=PurePath("LICENSE"), types=str)

    def _get(
        self, key: str, *, types: Any = None, parser: Optional[Callable[[Any], Any]] = None, **kwargs: Any
    ) -> Any:
        if key not in self._raw:
            if "default" not in kwargs:
                raise ValueError(f"missing `{key}` in config")
            return kwargs["default"]
        value = self._raw[key]
        if types is not None and not isinstance(value, types):
            raise ValueError(f"`{key}`={value} has wrong type, expected {types}")
        return parser(value) if parser else value

    @staticmethod
    def _parse_datetime(value: object) -> Optional[datetime.datetime]:
        if value is None:
            return None
        if isinstance(value, datetime.datetime):
            if value.tzinfo:
                return value
            return value.replace(tzinfo=datetime.timezone.utc)
        if isinstance(value, datetime.date):
            return datetime.datetime.combine(value, datetime.time.min, tzinfo=datetime.timezone.utc)
        raise ValueError(f"expected timestamp or null, found {value}")

    @staticmethod
    def load_from_file(path: Path) -> "CopyrightConfig":
        with path.open(encoding="utf-8") as config_file:
            config = CopyrightConfig(yaml.load(config_file, Loader=yaml.SafeLoader))
            return config
