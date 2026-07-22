import numpy as np

# Apply numpy compatibility patches
if not hasattr(np, 'float'):
    np.float = float
if not hasattr(np, 'int'):
    np.int = int
if not hasattr(np, 'object'):
    np.object = object
if not hasattr(np, 'bool'):
    np.bool = bool
if not hasattr(np, 'complex'):
    np.complex = complex

from fastapi import FastAPI, Form, File, UploadFile
import fcsparser
import pandas as pd
from sklearn.cluster import KMeans
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import os

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/api/cluster")
async def get_clustered_data(
    file: UploadFile = File(...),
    markers: str = Form("FSC-A,SSC-A"),
    cluster_mode: str = Form("all"),  # "all" = cluster on every channel (default);
                                       # "selected" = cluster on just the two plotted axes
):
    temp_file_path = ""
    try:
        # Reject obviously-wrong file types up front with a clear message,
        # rather than letting fcsparser fail deep inside with a cryptic
        # binary-parsing error.
        if not file.filename or not file.filename.lower().endswith(".fcs"):
            return {"error": f"'{file.filename or 'this file'}' doesn't look like an .fcs file. Please upload a valid FCS file exported from your cytometer."}

        with tempfile.NamedTemporaryFile(delete=False, suffix=".fcs") as tmp:
            content = await file.read()
            tmp.write(content)
            temp_file_path = tmp.name

        requested_markers = [m.strip().upper() for m in markers.split(',')]

        try:
            meta, data = fcsparser.parse(temp_file_path, reformat_meta=True)
        except Exception:
            return {"error": "This file couldn't be read as a valid FCS file. It may be corrupted, or in an unsupported FCS version."}

        df_raw = pd.DataFrame(data)

        # Clean column headers
        df_raw.columns = [str(c).strip().upper() for c in df_raw.columns]
        available_cols = list(df_raw.columns)

        print(f"\n========================================")
        print(f"INCOMING REQUEST MARKERS: {requested_markers}")
        print(f"AVAILABLE COLUMNS: {available_cols}")

        # Precise column mapping dictionary for Accuri / standard FCS files
        column_mapping = {
            "FSC-A": "FSC-A",
            "SSC-A": "SSC-A",
            "B515-A": "FL1-A",
            "B515-A (FITC EQUIVALENT)": "FL1-A",
            "FITC": "FL1-A",
            "G560-A": "FL2-A",
            "G560-A (PE EQUIVALENT)": "FL2-A",
            "PE": "FL2-A",
            "V450-A": "FL3-A",
            "V450-A (VIOLET EQUIVALENT)": "FL3-A",
            "V500-A": "FL4-A",
            "FL1-A": "FL1-A",
            "FL2-A": "FL2-A",
            "FL3-A": "FL3-A",
            "FL4-A": "FL4-A",
            "FSC-H": "FSC-H",
            "SSC-H": "SSC-H",
            "WIDTH": "WIDTH",
            "TIME": "TIME"
        }

        def resolve_column(req):
            req_clean = req.upper().strip()
            # Direct dictionary check
            if req_clean in column_mapping:
                target = column_mapping[req_clean]
                if target in available_cols:
                    return target

            # Substring matching against available columns
            for col in available_cols:
                if req_clean in col or col in req_clean:
                    return col

            # Fallback index check
            for col in available_cols:
                if req_clean.replace("-", "") in col.replace("-", ""):
                    return col

            return available_cols[0]

        x_col = resolve_column(requested_markers[0]) if len(requested_markers) > 0 else available_cols[0]
        y_col = resolve_column(requested_markers[1]) if len(requested_markers) > 1 else available_cols[min(1, len(available_cols)-1)]

        # Prevent identical axes if requested unless dataset only has 1 column
        if x_col == y_col and len(available_cols) > 1:
            for col in available_cols:
                if col != x_col:
                    y_col = col
                    break

        print(f">>> FINAL RESOLVED X COLUMN: {x_col}")
        print(f">>> FINAL RESOLVED Y COLUMN: {y_col}")
        print(f"========================================")

        # Apply standard Arcsinh transformation
        transformed = np.arcsinh(df_raw / 150)
        transformed.columns = available_cols

        # Run KMeans clustering. "all" (default) clusters across every numeric
        # channel in the file, giving cluster assignments that reflect the
        # cell's full-dimensional identity — this is why the SAME cluster
        # colors can look cleanly separated on FSC-A/SSC-A but look scrambled
        # on other axis pairs that weren't as informative for the clustering
        # decision. "selected" instead clusters using only the two currently
        # plotted channels, which will always look visually clean on whatever
        # axes are shown, at the cost of the cluster identities changing
        # every time you switch axes (since it's a fresh 2D clustering each time).
        kmeans = KMeans(n_clusters=3, random_state=42, n_init=5)
        if cluster_mode == "selected":
            cluster_features = transformed[[x_col, y_col]]
        else:
            cluster_features = transformed.select_dtypes(include=[np.number])
        cluster_labels = kmeans.fit_predict(cluster_features)

        # Build result dataframe using resolved unique columns
        result_df = pd.DataFrame({
            'x': transformed[x_col],
            'y': transformed[y_col],
            'cluster': cluster_labels
        })

        # Downsample to 3,000 cells max for lightning-fast rendering and zero lag
        if len(result_df) > 3000:
            result_df = result_df.sample(n=3000, random_state=42)

        # Return the full column list alongside data so the frontend's
        # dropdowns populate with everything actually in this file, instead
        # of staying stuck on the initial FSC-A/SSC-A default.
        return {
            "columns": available_cols,
            "cluster_mode": cluster_mode,
            "data": result_df.to_dict(orient="records"),
        }

    except Exception as e:
        print(f"CRITICAL BACKEND ERROR: {e}")
        return {"error": str(e)}
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
