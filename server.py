"""
SISCA mock MCP server.

Espone un sistema ospedaliero finto: pazienti, reparti, vitali e note cliniche.
Trasporto: stdio. Pensato per essere consumato da un backend client MCP in fase di sviluppo.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

DATA_DIR = Path(__file__).parent / "data"
PATIENTS_FILE = DATA_DIR / "patients.json"
DEPARTMENTS_FILE = DATA_DIR / "departments.json"

VALID_STATUSES = {"stable", "critical", "observation", "recovering", "discharged"}

mcp = FastMCP("sisca-hospital")


def _load(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _save(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _find_patient(patients: list[dict], patient_id: str) -> dict:
    for p in patients:
        if p["id"] == patient_id:
            return p
    raise ValueError(f"Patient '{patient_id}' not found")


# ---------------------------------------------------------------------------
# Resources — read-only snapshots of the dataset (URI based)
# ---------------------------------------------------------------------------

@mcp.resource(
    "file:///patients.json",
    name="patients",
    description="Elenco completo dei pazienti ricoverati (JSON).",
    mime_type="application/json",
)
def patients_resource() -> str:
    return json.dumps(_load(PATIENTS_FILE), indent=2, ensure_ascii=False)


@mcp.resource(
    "file:///departments.json",
    name="departments",
    description="Elenco dei reparti ospedalieri con posti letto disponibili.",
    mime_type="application/json",
)
def departments_resource() -> str:
    return json.dumps(_load(DEPARTMENTS_FILE), indent=2, ensure_ascii=False)


@mcp.resource(
    "patient://{patient_id}",
    name="patient-detail",
    description="Cartella clinica completa di un singolo paziente per ID (es. P001).",
    mime_type="application/json",
)
def patient_resource(patient_id: str) -> str:
    patient = _find_patient(_load(PATIENTS_FILE), patient_id)
    return json.dumps(patient, indent=2, ensure_ascii=False)


@mcp.resource(
    "notes://{patient_id}",
    name="clinical-notes",
    description="Note cliniche di un paziente in ordine cronologico.",
    mime_type="application/json",
)
def notes_resource(patient_id: str) -> str:
    patient = _find_patient(_load(PATIENTS_FILE), patient_id)
    return json.dumps(patient.get("clinical_notes", []), indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tools — actions the LLM/backend can invoke
# ---------------------------------------------------------------------------

@mcp.tool()
def list_patients() -> list[dict]:
    """Ritorna un elenco compatto (id, nome, reparto, stato) di tutti i pazienti."""

    patients = []

    for p in _load(PATIENTS_FILE):
        patients.append({
            "id": p["id"],
            "name": p["name"],
            "department": p["department"],
            "status": p["status"],
            "room": p["room"],
        })

    return patients


@mcp.tool()
def get_patient(patient_id: str) -> dict:
    """Ritorna la cartella clinica completa per ID paziente (es. 'P001')."""
    return _find_patient(_load(PATIENTS_FILE), patient_id)


@mcp.tool()
def search_patients_by_name(name: str) -> list[dict]:
    """Cerca pazienti per nome (match case-insensitive parziale, es. 'rossi')."""
    query = name.strip().lower()
    if not query:
        return []
    return [p for p in _load(PATIENTS_FILE) if query in p["name"].lower()]


@mcp.tool()
def get_patients_by_department(department: str) -> list[dict]:
    """Lista i pazienti di un reparto. `department` è il codice (es. 'cardiology')."""
    return [p for p in _load(PATIENTS_FILE) if p["department"] == department]


@mcp.tool()
def get_patient_status(patient_id: str) -> dict:
    """Stato corrente del paziente: status clinico, reparto, diagnosi, ultimi vitali."""
    p = _find_patient(_load(PATIENTS_FILE), patient_id)
    return {
        "id": p["id"],
        "name": p["name"],
        "status": p["status"],
        "department": p["department"],
        "room": p["room"],
        "diagnosis": p["diagnosis"],
        "vital_signs": p["vital_signs"],
    }


@mcp.tool()
def update_vital_signs(
    patient_id: str,
    heart_rate: int | None = None,
    blood_pressure: str | None = None,
    temperature: float | None = None,
    oxygen_saturation: int | None = None,
) -> dict:
    """Aggiorna uno o più parametri vitali. I campi non passati restano invariati."""
    patients = _load(PATIENTS_FILE)
    p = _find_patient(patients, patient_id)
    v = p["vital_signs"]
    if heart_rate is not None:
        v["heart_rate"] = heart_rate
    if blood_pressure is not None:
        v["blood_pressure"] = blood_pressure
    if temperature is not None:
        v["temperature"] = temperature
    if oxygen_saturation is not None:
        v["oxygen_saturation"] = oxygen_saturation
    v["recorded_at"] = _now_iso()
    _save(PATIENTS_FILE, patients)
    return v


@mcp.tool()
def set_patient_status(patient_id: str, status: str) -> dict:
    """Imposta lo status clinico. Valori ammessi: stable, critical, observation, recovering, discharged."""
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of {sorted(VALID_STATUSES)}")
    patients = _load(PATIENTS_FILE)
    p = _find_patient(patients, patient_id)
    p["status"] = status
    _save(PATIENTS_FILE, patients)
    return {"id": p["id"], "status": p["status"]}


@mcp.tool()
def add_clinical_note(patient_id: str, author: str, text: str) -> dict:
    """Aggiunge una nota clinica (timestamp generato dal server) e la ritorna."""
    if not text.strip():
        raise ValueError("Note text cannot be empty")
    patients = _load(PATIENTS_FILE)
    p = _find_patient(patients, patient_id)
    note = {"date": _now_iso(), "author": author, "text": text}
    p.setdefault("clinical_notes", []).append(note)
    _save(PATIENTS_FILE, patients)
    return note


@mcp.tool()
def admit_patient(
    name: str,
    birth_date: str,
    gender: str,
    department: str,
    room: str,
    diagnosis: str,
    allergies: list[str] | None = None,
) -> dict:
    """Ricovera un nuovo paziente. Genera automaticamente l'ID (P###). `birth_date` in formato YYYY-MM-DD."""
    departments = {d["code"] for d in _load(DEPARTMENTS_FILE)}
    if department not in departments:
        raise ValueError(f"Unknown department '{department}'. Known: {sorted(departments)}")

    patients = _load(PATIENTS_FILE)
    next_num = max((int(p["id"][1:]) for p in patients), default=0) + 1
    new_id = f"P{next_num:03d}"

    record = {
        "id": new_id,
        "name": name,
        "birth_date": birth_date,
        "gender": gender,
        "department": department,
        "room": room,
        "admission_date": datetime.now(timezone.utc).date().isoformat(),
        "status": "observation",
        "diagnosis": diagnosis,
        "allergies": allergies or [],
        "vital_signs": {
            "heart_rate": None,
            "blood_pressure": None,
            "temperature": None,
            "oxygen_saturation": None,
            "recorded_at": None,
        },
        "clinical_notes": [],
    }
    patients.append(record)
    _save(PATIENTS_FILE, patients)
    return record


@mcp.tool()
def discharge_patient(patient_id: str, summary: str) -> dict:
    """Dimette il paziente: imposta status='discharged' e registra una sintesi di dimissione."""
    patients = _load(PATIENTS_FILE)
    p = _find_patient(patients, patient_id)
    p["status"] = "discharged"
    p["discharge_date"] = datetime.now(timezone.utc).date().isoformat()
    p["discharge_summary"] = summary
    _save(PATIENTS_FILE, patients)
    return {
        "id": p["id"],
        "name": p["name"],
        "status": p["status"],
        "discharge_date": p["discharge_date"],
    }


@mcp.tool()
def list_departments() -> list[dict]:
    """Elenco reparti con posti letto disponibili e primario."""
    return _load(DEPARTMENTS_FILE)


@mcp.tool()
def get_department_occupancy(department: str) -> dict:
    """Occupazione del reparto: pazienti attivi, posti totali e disponibili."""
    departments = {d["code"]: d for d in _load(DEPARTMENTS_FILE)}
    if department not in departments:
        raise ValueError(f"Unknown department '{department}'")
    d = departments[department]
    active = [
        p for p in _load(PATIENTS_FILE)
        if p["department"] == department and p["status"] != "discharged"
    ]
    return {
        "department": department,
        "name": d["name"],
        "beds_total": d["beds_total"],
        "beds_available": d["beds_available"],
        "active_patients": len(active),
        "patient_ids": [p["id"] for p in active],
    }


if __name__ == "__main__":
    mcp.run()
