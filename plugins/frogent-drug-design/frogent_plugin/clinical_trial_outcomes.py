"""Compact protocol outcome rendering for registry reader evidence."""

from typing import Mapping

PRIMARY_DESCRIPTION_LIMIT = 1200
_TRUNCATED = " [TRUNCATED: primary outcome description limit]"


def outcome_lines(nct_id: str, value: object, label: str,
                  include_description: bool = False) -> list[str]:
    outcomes = _objects(value)
    result = []
    for index, item in enumerate(outcomes, 1):
        line = (f"[REGISTRY {nct_id} {label} {index}] measure={_field(item, 'measure')}; "
                f"timeFrame={_field(item, 'timeFrame')}")
        description = item.get("description") if include_description else None
        if description not in (None, ""):
            line += "; description=" + _bounded(description)
        result.append(line)
    return result


def _objects(value: object) -> tuple[Mapping[str, object], ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, Mapping) for item in value):
        raise ValueError("registry outcomes must be a list of objects")
    return tuple(value)


def _field(values: Mapping[str, object], key: str) -> str:
    value = values.get(key)
    return _clean(value) if value not in (None, "") else "not_reported"


def _bounded(value: object) -> str:
    text = _clean(value)
    if len(text) <= PRIMARY_DESCRIPTION_LIMIT:
        return text
    return text[:PRIMARY_DESCRIPTION_LIMIT - len(_TRUNCATED)].rstrip() + _TRUNCATED


def _clean(value: object) -> str:
    return " ".join(str(value).split()).replace(";", ",")
