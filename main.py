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
    markers: str = Form("FSC-A,SSC-A")
):
    temp_file_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".fcs") as tmp:
            content = await file.read()
            tmp.write(content)
            temp_file_path = tmp.name

        requested_markers = [m.strip().upper() for m in markers.split(',')]

        meta, data = fcsparser.parse(temp_file_path, reformat_meta=True)
        df_raw = pd.DataFrame(data)

        df_raw.columns = [str(c).strip().upper() for c in df_raw.columns]
        available_cols = list(df_raw.columns)

        print(f"\n========================================")
        print(f"INCOMING REQUEST MARKERS: {requested_markers}")
        print(f"AVAILABLE COLUMNS: {available_cols}")

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
            if req_clean in column_mapping:
                target = column_mapping[req_clean]
                if target in available_cols:
                    return target
            for col in available_cols:
                if req_clean in col or col in req_clean:
                    return col
            for col in available_cols:
                if req_clean.replace("-", "") in col.replace("-", ""):
                    return col
            return available_cols[0]

        x_col = resolve_column(requested_markers[0]) if len(requested_markers) > 0 else available_cols[0]
        y_col = resolve_column(requested_markers[1]) if len(requested_markers) > 1 else available_cols[min(1, len(available_cols)-1)]

        if x_col == y_col and len(available_cols) > 1:
            for col in available_cols:
                if col != x_col:
                    y_col = col
                    break

        print(f">>> FINAL RESOLVED X COLUMN: {x_col}")
        print(f">>> FINAL RESOLVED Y COLUMN: {y_col}")
        print(f"========================================")

        transformed = np.arcsinh(df_raw / 150)
        transformed.columns = available_cols

        kmeans = KMeans(n_clusters=3, random_state=42, n_init=5)
        cluster_features = transformed.select_dtypes(include=[np.number])
        cluster_labels = kmeans.fit_predict(cluster_features)

        result_df = pd.DataFrame({
            'x': transformed[x_col],
            'y': transformed[y_col],
            'cluster': cluster_labels
        })

        if len(result_df) > 3000:
            result_df = result_df.sample(n=3000, random_state=42)

        return {
            "columns": available_cols,
            "data": result_df.to_dict(orient="records"),
        }

    except Exception as e:
        print(f"CRITICAL BACKEND ERROR: {e}")
        return {"error": str(e)}
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)