from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

from jsonschema import ValidationError, validate

REPO_COL = "repo_name"
TIMESTAMP_COL = "TIMESTAMP"
LAST_PUSH_COL = "github.last_push"
LAST_PUSH_PARSE_FORMAT = "%Y-%m-%d %H:%M:%S"

MISSING_COLUMNS: set[str] = set()
CONFIG_VALIDATION_ERRORS: dict[str, str] = {}


def parse_snapshot_date(value: object) -> date | None:
	"""Parse the snapshot date (YYYY-MM-DD) into a date object."""
	if value is None:
		return None
	text = str(value).strip()
	if not text:
		return None
	try:
		return date.fromisoformat(text)
	except ValueError:
		return None


def parse_last_push_utc(value: object) -> datetime | None:
	"""Parse github.last_push as naive UTC timestamp."""
	if value is None:
		return None
	text = str(value).strip()
	if not text:
		return None
	try:
		dt = datetime.strptime(text, LAST_PUSH_PARSE_FORMAT)
		return dt.replace(tzinfo=timezone.utc)
	except ValueError:
		return None


def soft_assert_columns(columns: Iterable[str], expected: Iterable[str]) -> list[str]:
	"""Track missing expected columns and return the missing list."""
	present = set(columns)
	missing = [column for column in expected if column not in present]
	MISSING_COLUMNS.update(missing)
	return missing


def schema_path_for(config_name: str) -> Path:
	root = Path(__file__).resolve().parents[1]
	return root / "config" / "schemas" / f"{config_name}.schema.json"


def validate_config_data(config_name: str, payload: dict, strict: bool = False) -> bool:
	"""Validate configuration payload against its JSON schema.

	When strict is False, errors are recorded and the function returns False.
	When strict is True, validation errors are raised.
	"""
	schema_path = schema_path_for(config_name)
	if not schema_path.exists():
		CONFIG_VALIDATION_ERRORS[config_name] = f"missing schema: {schema_path}"
		if strict:
			raise FileNotFoundError(CONFIG_VALIDATION_ERRORS[config_name])
		return False

	with schema_path.open("r", encoding="utf-8") as stream:
		schema = json.load(stream)

	try:
		validate(instance=payload, schema=schema)
		CONFIG_VALIDATION_ERRORS.pop(config_name, None)
		return True
	except ValidationError as exc:
		CONFIG_VALIDATION_ERRORS[config_name] = str(exc)
		if strict:
			raise
		return False