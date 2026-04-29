# SISCA — Backend conversazionale + Mock MCP Server

Due componenti in un unico repo:

1. **MCP server mock** (`server.py`) — simula il sistema ospedaliero (pazienti, reparti, vitali, note cliniche). Sostituibile col server reale quando disponibile.
2. **Backend FastAPI** (`app/`) — espone `/query`, riceve domande in linguaggio naturale dai medici, le instrada via Claude Haiku + tool use al MCP server, e restituisce una risposta conversazionale.

Pipeline a 6 step (in `app/pipeline.py`):

```
Domanda medico
    ↓ (1) FastAPI POST /query
    ↓ (2) parsing LLM        → Claude Haiku sceglie tool e parametri
    ↓ (3) validazione        → tool esiste? campi obbligatori?
    ↓ (4) normalizzazione    → "cardiologia" → "cardiology"
    ↓ (5) tool execution     → chiamata MCP via stdio
    ↓ (6) output             → Claude Haiku formula la risposta in italiano
Risposta JSON al frontend
```

---

## Requisiti

- Python **>=3.10**
- `pip` (o `uv`)
- Una `ANTHROPIC_API_KEY`

---

# Setup

```bash
cd "C:\Users\franc\Desktop\TIROCINIO\sisca-be"

# venv + dipendenze
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# configura la API key Anthropic
cp .env.example .env
# modifica .env e inserisci la tua ANTHROPIC_API_KEY
```

---

## Avvio

### Backend FastAPI (la cosa principale)

```bash
uvicorn app.main:app --reload --port 8000
```

Lo startup:
1. Spawna `server.py` come subprocess MCP via stdio
2. Inizializza la sessione MCP, recupera la lista dei tool
3. Apre Claude client async
4. Espone l'API REST su `http://localhost:8000`

Endpoint disponibili:

| Metodo | Path | Cosa fa |
|---|---|---|
| `POST` | `/query` | Body: `{"question": "..."}` → risposta naturale + log tool calls |
| `GET` | `/health` | Status + lista dei tool MCP caricati |
| `GET` | `/docs` | Swagger UI auto-generata |

### Esempio chiamata

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "Come sta Mario Rossi oggi?"}'
```
## Qualità, confidenza e valutazione

Questo progetto ora include una valutazione automatica della qualità della risposta:
- `confidence` stima la sicurezza del backend su una scala da `0.0` a `1.0`
- `quality_checks` riporta note sul flusso di elaborazione (tool usati, errori, iterazioni)
- la pipeline è stata resa più modulare in `app/evaluator.py` e `app/agent.py`

Il risultato JSON restituito da `/query` ora contiene anche questi campi.
Risposta:

```json
{
  "answer": "Mario Rossi (P001) è ricoverato in cardiologia, stanza 204, in stato stabile. Ultimi vitali: FC 72, PA 130/85, T° 36.8, SpO₂ 98%.",
  "tool_calls": [
    {
      "name": "search_patients_by_name",
      "arguments": {"name": "Mario Rossi"},
      "result": "[...]"
    },
    {
      "name": "get_patient_status",
      "arguments": {"patient_id": "P001"},
      "result": "[...]"
    }
  ],
  "iterations": 3,
  "model": "claude-haiku-4-5-20251001",
  "confidence": 0.82,
  "quality_checks": [
    "Nessuna anomalia di qualità rilevata."
  ]
}
```

Altri esempi di domande:

- `"Chi c'è in cardiologia?"`
- `"Aggiungi una nota a Lucia Ferrari: TAC programmata per domani, autore Dr. Conti"`
- `"Aggiorna i vitali di P003: FC 110, T° 38.6"`
- `"Quanti posti liberi ci sono in oncologia?"`
- `"Dimetti Carla Romano con summary: paziente stabile, terapia domiciliare programmata"`

### Solo MCP server (debug)

Per testare il MCP server isolato senza FastAPI:

```bash
mcp dev server.py            # MCP Inspector — UI in browser
python server.py             # stdio server (in attesa di un client)
```

## Test e qualità del codice

Il progetto include una suite di test unitari per verificare i componenti principali del backend.

```bash
python -m unittest discover tests
```

I test coprono:
- la normalizzazione dei parametri in `app/normalizer.py`
- il calcolo della confidenza e i controlli qualitativi in `app/evaluator.py`
- gli schemi di risposta API in `app/schemas.py`

---

## Struttura del progetto

```
sisca-be/
├── server.py              # MCP server (FastMCP) ─┐
├── data/                                          │
│   ├── patients.json      # 8 pazienti mock      │ MCP server
│   └── departments.json   # 5 reparti            │
│                                                  ┘
├── app/                                           ┐
│   ├── main.py            # FastAPI app + lifespan│
│   ├── mcp_client.py      # client stdio MCP     │
│   ├── pipeline.py        # 6-step pipeline      │ Backend
│   ├── agent.py           # tool / risultato modello│
│   ├── evaluator.py       # confidenza e qualità  │
│   ├── normalizer.py      # IT→EN dictionary     │
│   └── schemas.py         # Pydantic models      │
│                                                  ┘
├── pyproject.toml
├── requirements.txt
├── .env.example
└── README.md
```

---

## MCP — Tools esposti

| Tool | Cosa fa |
|---|---|
| `list_patients` | Elenco compatto di tutti i pazienti |
| `get_patient` | Cartella completa per ID (`P001`…) |
| `search_patients_by_name` | Match parziale case-insensitive sul nome |
| `get_patients_by_department` | Filtra per codice reparto |
| `get_patient_status` | Status + ultimi vitali del paziente |
| `update_vital_signs` | Aggiorna FC/PA/T°/SpO₂ (parziale, server-timestamped) |
| `set_patient_status` | Cambia status (`stable`/`critical`/`observation`/`recovering`/`discharged`) |
| `add_clinical_note` | Aggiunge nota clinica con autore + timestamp |
| `admit_patient` | Ricovera nuovo paziente, genera `P###` |
| `discharge_patient` | Dimissione + summary |
| `list_departments` | Lista reparti |
| `get_department_occupancy` | Occupazione (totali/disponibili/attivi) |

## MCP — Resources (URI)

| URI | Contenuto |
|---|---|
| `file:///patients.json` | Tutti i pazienti |
| `file:///departments.json` | Tutti i reparti |
| `patient://{patient_id}` | Cartella singolo paziente (es. `patient://P001`) |
| `notes://{patient_id}` | Solo note cliniche di un paziente |

---

## Note tecniche

- **Modello**: Claude `claude-opus-4-7` con native tool use. Il modello sceglie autonomamente i tool MCP da chiamare e ne estrae i parametri.
- **Prompt caching**: il system prompt e la lista dei tool sono cached con TTL ephemeral (5 min) → riduce costo e latenza nelle chiamate ripetute del loop agentico.
- **Loop agentico**: max 10 iterazioni per query. Il modello può concatenare più tool call (es. cerca per nome → preleva status).
- **Reset dati**: le mutazioni vanno su `data/*.json`. Per ripristinare lo stato iniziale, rigenera o ripristina i file da git/backup.
- **Migrazione al MCP reale**: cambia solo la connection string in `app/mcp_client.py` (es. da stdio a HTTP/SSE). Il resto del backend resta invariato.
