# Clinical Cytometry Dashboard

An interactive web dashboard for exploring flow cytometry data. Upload an `.fcs` file, pick any two markers to plot against each other, and view automated K-Means gating with a live-updating scatter plot, color-coded clusters, and per-population statistics.

![Dashboard Screenshot](./docs/screenshot.png)
*(Replace this with a real screenshot of the running dashboard — upload a sample `.fcs` file and capture the scatter plot + legend panel.)*

## Features

- **Drag-and-drop `.fcs` upload** with clear validation (rejects non-FCS files with a helpful error instead of failing silently)
- **Configurable X/Y axes** — choose any two channels detected in the uploaded file (forward/side scatter, fluorescence channels, etc.)
- **Automated gating** via K-Means clustering (scikit-learn), with clusters mapped to common leukocyte populations (lymphocytes, monocytes, granulocytes)
- **Arcsinh-transformed** channel data, the standard transformation for flow cytometry visualization
- **Live statistics panel** showing per-cluster event counts and percentages
- **Downsampling** to 3,000 events for smooth rendering on high-event clinical files

## Architecture

```
┌─────────────────────┐        POST /api/cluster        ┌──────────────────────┐
│   Frontend (React)  │ ───────────────────────────────▶ │   Backend (FastAPI)  │
│   Vite + TypeScript │                                   │   Python 3.11        │
│   Recharts          │ ◀─────────────────────────────── │   fcsparser + sklearn │
│   served by nginx    │        { columns, data }         │   uvicorn             │
└─────────────────────┘                                   └──────────────────────┘
      localhost:5173                                             localhost:8000
```

- **Frontend**: React + TypeScript, built with Vite, charted with Recharts, served in production as a static build behind nginx.
- **Backend**: FastAPI service that accepts an uploaded `.fcs` file plus the two requested marker names, parses it with `fcsparser`, applies an arcsinh transform, runs K-Means clustering (`k=3`) across all numeric channels, and returns the resolved column list plus a downsampled set of `{x, y, cluster}` points as JSON.
- Both services run as separate Docker containers, orchestrated with Docker Compose, communicating over HTTP on the host network (`localhost:8000`).

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose

### Run with Docker Compose

```bash
git clone <your-repo-url>
cd cytometry-pipeline
docker compose up --build
```

This builds and starts both services:
- Frontend: [http://localhost:5173](http://localhost:5173)
- Backend API docs (Swagger UI): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Once both are running, open the frontend, upload a `.fcs` file, and select your X/Y markers.

To stop everything:
```bash
docker compose down
```

To rebuild after making code changes:
```bash
docker compose down
docker compose up --build -d
```

### Running locally without Docker (alternative)

If you'd rather run each service directly on your machine for faster iteration during development:

**Backend:**
```bash
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
uvicorn main:app --reload
```

**Frontend** (in a separate terminal, from the `frontend/` directory):
```bash
cd frontend
npm install
npm run dev
```

The frontend expects the backend at `http://localhost:8000` — make sure both are running for the upload flow to work.

## Project Structure

```
cytometry-pipeline/
├── main.py                 # FastAPI backend — clustering, FCS parsing
├── requirements.txt        # Python dependencies
├── Dockerfile               # Backend container definition
├── docker-compose.yml      # Orchestrates frontend + backend
└── frontend/
    ├── src/
    │   └── App.tsx          # Main dashboard component
    ├── Dockerfile            # Frontend container definition (multi-stage: Node build → nginx serve)
    └── package.json
```

## API

### `POST /api/cluster`

Accepts a multipart form with:
- `file`: the `.fcs` file to analyze
- `markers`: comma-separated marker names to plot, e.g. `"FSC-A,SSC-A"`

Returns:
```json
{
  "columns": ["FSC-A", "SSC-A", "FL1-A", "..."],
  "data": [
    { "x": 6.53, "y": 3.28, "cluster": 0 },
    ...
  ]
}
```

On invalid input (wrong file type, unparseable FCS file), returns:
```json
{ "error": "Human-readable explanation of what went wrong." }
```

## Notes on Clustering

Cluster assignment is computed via unsupervised K-Means (`k=3`) across **all** numeric channels in the file, not just the two currently plotted on X/Y. This means the color-coded populations represent the overall cellular subpopulations in the sample, and stay consistent as you switch which two channels you're viewing — but it also means the cluster boundaries won't align with a 2D decision boundary on any single axis pair.

---

Built as part of a hands-on data engineering / full-stack crash course covering FastAPI, React, Docker, and applied clustering on real clinical instrument data.
