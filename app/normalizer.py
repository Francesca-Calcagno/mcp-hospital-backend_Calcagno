"""Mappa termini italiani ai valori canonici accettati dal MCP server."""

from typing import Any

DEPARTMENT_ALIASES = {
    "cardiologia": "cardiology",
    "cardiologico": "cardiology",
    "cardio": "cardiology",
    "neurologia": "neurology",
    "neurologico": "neurology",
    "neuro": "neurology",
    "oncologia": "oncology",
    "oncologico": "oncology",
    "onco": "oncology",
    "pediatria": "pediatrics",
    "pediatrico": "pediatrics",
    "pediatrica": "pediatrics",
    "pronto soccorso": "emergency",
    "ps": "emergency",
    "emergenza": "emergency",
    "urgenze": "emergency",
}

STATUS_ALIASES = {
    "stabile": "stable",
    "critico": "critical",
    "critica": "critical",
    "osservazione": "observation",
    "in osservazione": "observation",
    "in recupero": "recovering",
    "recupero": "recovering",
    "dimesso": "discharged",
    "dimessa": "discharged",
}


def _coerce(value: Any, mapping: dict[str, str]) -> Any:
    if not isinstance(value, str):
        return value
    return mapping.get(value.strip().lower(), value)


def normalize_arguments(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Applica i mapping IT→EN ai campi noti senza alterare gli altri."""
    out = dict(arguments)
    if "department" in out:
        out["department"] = _coerce(out["department"], DEPARTMENT_ALIASES)
    if "status" in out:
        out["status"] = _coerce(out["status"], STATUS_ALIASES)
    return out
