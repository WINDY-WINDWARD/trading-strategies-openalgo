from fastapi.testclient import TestClient

from data_warehouse.api.api import create_app


def test_add_stock_returns_accepted_with_job_metadata():
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/data-warehouse/stocks/add",
        json={
            "ticker": "RELIANCE",
            "timeframe": "1d",
            "range": {"start_epoch": 1700000000, "end_epoch": 1700086400},
        },
    )

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"


def test_get_stock_returns_data_payload():
    app = create_app()
    client = TestClient(app)

    add_resp = client.post(
        "/api/data-warehouse/stocks/add",
        json={
            "ticker": "RELIANCE",
            "timeframe": "1d",
            "range": {"start_epoch": 1700000000, "end_epoch": 1700000000},
        },
    )
    assert add_resp.status_code == 202
    job_id = add_resp.json()["job_id"]
    job_resp = client.get(f"/api/data-warehouse/jobs/{job_id}")
    assert job_resp.status_code == 200

    response = client.post(
        "/api/data-warehouse/stocks/get",
        json={
            "ticker": "RELIANCE",
            "timeframe": "1d",
            "range": {"start_epoch": 1700000000, "end_epoch": 1700000000},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "RELIANCE"
    assert data["timeframe"] == "1d"
    assert isinstance(data["candles"], list)


def test_delete_stock_returns_job_metadata():
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/data-warehouse/stocks/delete",
        json={"ticker": "RELIANCE", "timeframe": "1d"},
    )

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"


def test_bulk_add_returns_accepted_with_job_metadata():
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/data-warehouse/stocks/add-bulk",
        json={
            "rows": [
                {
                    "ticker": "RELIANCE",
                    "timeframe": "1d",
                    "range": {"start_epoch": 1700000000, "end_epoch": 1700000000},
                }
            ]
        },
    )

    assert response.status_code == 202
    data = response.json()
    assert "job_id" in data
    assert data["status"] == "queued"


def test_search_symbols_returns_results_payload():
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/data-warehouse/stocks/search",
        json={"query": "reliance", "exchange": "nse"},
    )

    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert isinstance(data["results"], list)

    index_response = client.post(
        "/api/data-warehouse/stocks/search",
        json={"query": "nifty", "is_index": True},
    )
    assert index_response.status_code == 200
