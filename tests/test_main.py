"""
Tests for the /api/cluster endpoint.

We mock fcsparser.parse for the "valid FCS file" test cases rather than
shipping a real binary .fcs fixture — this keeps the suite fast, deterministic,
and free of a binary test asset to maintain. The "invalid file" tests use a
genuinely bogus file, since that logic must reject the upload BEFORE ever
calling fcsparser.parse, and mocking would hide a regression there.
"""

import io
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def make_fake_fcs_dataframe(n_events: int = 100, seed: int = 0) -> pd.DataFrame:
    """Build a small synthetic dataframe shaped like real FCS channel data."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "FSC-A": rng.uniform(0, 250000, n_events),
        "SSC-A": rng.uniform(0, 250000, n_events),
        "FL1-A": rng.uniform(-500, 100000, n_events),  # negative values are
        "FL2-A": rng.uniform(-500, 100000, n_events),  # normal post-compensation
    })


def fake_meta_data_pair(n_events: int = 100, seed: int = 0):
    """Mimics fcsparser.parse's (meta, data) return signature."""
    return {"$TOT": str(n_events)}, make_fake_fcs_dataframe(n_events, seed)


# ---------------------------------------------------------------------------
# Invalid file type — should be rejected before touching fcsparser at all
# ---------------------------------------------------------------------------

def test_rejects_non_fcs_extension():
    fake_file = io.BytesIO(b"just,some,csv,data\n1,2,3,4")
    response = client.post(
        "/api/cluster",
        files={"file": ("sample.csv", fake_file, "text/csv")},
        data={"markers": "FSC-A,SSC-A"},
    )
    assert response.status_code == 200  # endpoint returns 200 with an error payload
    body = response.json()
    assert "error" in body
    assert "sample.csv" in body["error"]
    assert ".fcs" in body["error"].lower()


def test_rejects_filename_with_no_extension():
    fake_file = io.BytesIO(b"data")
    response = client.post(
        "/api/cluster",
        files={"file": ("sample_no_extension", fake_file, "application/octet-stream")},
        data={"markers": "FSC-A,SSC-A"},
    )
    body = response.json()
    assert "error" in body
    assert "sample_no_extension" in body["error"]


def test_rejects_txt_disguised_with_fcs_like_name_but_wrong_suffix():
    fake_file = io.BytesIO(b"not real fcs data")
    response = client.post(
        "/api/cluster",
        files={"file": ("results.txt", fake_file, "text/plain")},
        data={"markers": "FSC-A,SSC-A"},
    )
    body = response.json()
    assert "error" in body
    assert "results.txt" in body["error"]


# ---------------------------------------------------------------------------
# Unparseable .fcs file — correct extension, but garbage/corrupted contents
# ---------------------------------------------------------------------------

def test_handles_corrupted_fcs_file_gracefully():
    fake_file = io.BytesIO(b"this is not a real FCS binary structure")
    response = client.post(
        "/api/cluster",
        files={"file": ("corrupted.fcs", fake_file, "application/octet-stream")},
        data={"markers": "FSC-A,SSC-A"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "error" in body
    assert "couldn't be read" in body["error"].lower() or "corrupted" in body["error"].lower()


# ---------------------------------------------------------------------------
# Valid file, mocked parser — the "happy path"
# ---------------------------------------------------------------------------

@patch("main.fcsparser.parse")
def test_valid_file_returns_columns_and_data(mock_parse):
    mock_parse.return_value = fake_meta_data_pair(n_events=200)

    fake_file = io.BytesIO(b"pretend this is fcs bytes")
    response = client.post(
        "/api/cluster",
        files={"file": ("sample.fcs", fake_file, "application/octet-stream")},
        data={"markers": "FSC-A,SSC-A"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "error" not in body
    assert "columns" in body
    assert "data" in body
    assert set(["FSC-A", "SSC-A", "FL1-A", "FL2-A"]).issubset(set(body["columns"]))
    assert len(body["data"]) == 200
    for point in body["data"]:
        assert set(point.keys()) == {"x", "y", "cluster"}
        assert point["cluster"] in (0, 1, 2)


@patch("main.fcsparser.parse")
def test_axis_selection_changes_which_columns_are_plotted(mock_parse):
    """
    Regression test for the exact bug we hit tonight: selecting different
    markers must actually change which columns end up as x/y in the response.
    """
    mock_parse.return_value = fake_meta_data_pair(n_events=50)

    fake_file_1 = io.BytesIO(b"fcs bytes")
    response_1 = client.post(
        "/api/cluster",
        files={"file": ("sample.fcs", fake_file_1, "application/octet-stream")},
        data={"markers": "FSC-A,SSC-A"},
    )
    data_1 = response_1.json()["data"]

    fake_file_2 = io.BytesIO(b"fcs bytes")
    response_2 = client.post(
        "/api/cluster",
        files={"file": ("sample.fcs", fake_file_2, "application/octet-stream")},
        data={"markers": "FL1-A,FL2-A"},
    )
    data_2 = response_2.json()["data"]

    # Different marker pairs on the same underlying data should produce
    # different x/y values point-for-point (extremely unlikely to coincide
    # across 50 random events if the right columns were actually used).
    xs_1 = [round(p["x"], 6) for p in data_1]
    xs_2 = [round(p["x"], 6) for p in data_2]
    assert xs_1 != xs_2


@patch("main.fcsparser.parse")
def test_duplicate_axis_request_falls_back_to_a_different_column(mock_parse):
    mock_parse.return_value = fake_meta_data_pair(n_events=50)

    fake_file = io.BytesIO(b"fcs bytes")
    response = client.post(
        "/api/cluster",
        files={"file": ("sample.fcs", fake_file, "application/octet-stream")},
        data={"markers": "FSC-A,FSC-A"},  # same marker requested for both axes
    )
    body = response.json()
    assert "error" not in body
    # x and y should not end up identical for every point — some other
    # column should have been substituted for y per the dedup logic.
    data = body["data"]
    assert any(p["x"] != p["y"] for p in data)


@patch("main.fcsparser.parse")
def test_downsamples_large_event_counts_to_3000(mock_parse):
    mock_parse.return_value = fake_meta_data_pair(n_events=10_000)

    fake_file = io.BytesIO(b"fcs bytes")
    response = client.post(
        "/api/cluster",
        files={"file": ("large_sample.fcs", fake_file, "application/octet-stream")},
        data={"markers": "FSC-A,SSC-A"},
    )
    body = response.json()
    assert len(body["data"]) == 3000


@patch("main.fcsparser.parse")
def test_small_event_count_is_not_downsampled(mock_parse):
    mock_parse.return_value = fake_meta_data_pair(n_events=50)

    fake_file = io.BytesIO(b"fcs bytes")
    response = client.post(
        "/api/cluster",
        files={"file": ("small_sample.fcs", fake_file, "application/octet-stream")},
        data={"markers": "FSC-A,SSC-A"},
    )
    body = response.json()
    assert len(body["data"]) == 50


@patch("main.fcsparser.parse")
def test_default_cluster_mode_is_all_channels(mock_parse):
    mock_parse.return_value = fake_meta_data_pair(n_events=50)

    fake_file = io.BytesIO(b"fcs bytes")
    response = client.post(
        "/api/cluster",
        files={"file": ("sample.fcs", fake_file, "application/octet-stream")},
        data={"markers": "FSC-A,SSC-A"},  # cluster_mode omitted
    )
    body = response.json()
    assert body["cluster_mode"] == "all"


@patch("main.fcsparser.parse")
def test_selected_cluster_mode_is_echoed_back(mock_parse):
    mock_parse.return_value = fake_meta_data_pair(n_events=50)

    fake_file = io.BytesIO(b"fcs bytes")
    response = client.post(
        "/api/cluster",
        files={"file": ("sample.fcs", fake_file, "application/octet-stream")},
        data={"markers": "FSC-A,SSC-A", "cluster_mode": "selected"},
    )
    body = response.json()
    assert body["cluster_mode"] == "selected"


@patch("main.fcsparser.parse")
def test_selected_mode_clusters_differently_than_all_mode(mock_parse):
    """
    The two modes should generally produce different cluster label
    assignments, since "selected" only looks at 2 of the 4 channels while
    "all" looks at all 4. We don't assert exact labels (K-Means label
    numbering is arbitrary), just that the assignments aren't identical.
    """
    mock_parse.return_value = fake_meta_data_pair(n_events=100, seed=42)

    fake_file_1 = io.BytesIO(b"fcs bytes")
    response_all = client.post(
        "/api/cluster",
        files={"file": ("sample.fcs", fake_file_1, "application/octet-stream")},
        data={"markers": "FSC-A,SSC-A", "cluster_mode": "all"},
    )
    clusters_all = [p["cluster"] for p in response_all.json()["data"]]

    fake_file_2 = io.BytesIO(b"fcs bytes")
    response_selected = client.post(
        "/api/cluster",
        files={"file": ("sample.fcs", fake_file_2, "application/octet-stream")},
        data={"markers": "FSC-A,SSC-A", "cluster_mode": "selected"},
    )
    clusters_selected = [p["cluster"] for p in response_selected.json()["data"]]

    assert clusters_all != clusters_selected


@patch("main.fcsparser.parse")
def test_unrecognized_marker_name_falls_back_gracefully(mock_parse):
    """
    resolve_column() should fall back to a sensible default (first available
    column) rather than raising a KeyError when asked for a marker that
    doesn't exist in this file.
    """
    mock_parse.return_value = fake_meta_data_pair(n_events=20)

    fake_file = io.BytesIO(b"fcs bytes")
    response = client.post(
        "/api/cluster",
        files={"file": ("sample.fcs", fake_file, "application/octet-stream")},
        data={"markers": "NOT-A-REAL-MARKER,ALSO-FAKE"},
    )
    assert response.status_code == 200
    body = response.json()
    assert "error" not in body
    assert len(body["data"]) == 20
