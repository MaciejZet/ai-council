from fastapi.testclient import TestClient

import main as api_main


def test_main_installs_decision_memory_routes_and_state():
    assert getattr(api_main.app.state, "decision_memory_installed", False) is True
    paths = {route.path for route in api_main.app.routes}
    assert "/api/decision-memory" in paths
    assert "/api/decision-memory/calibration" in paths
    assert "/api/decision-memory/{decision_id}" in paths
    assert "/api/decision-memory/{decision_id}/outcome" in paths
    assert "/api/decision-memory" in api_main.CORE_CONTRACT_PATH_PREFIXES


def test_main_decision_memory_validation_uses_core_error_contract():
    client = TestClient(api_main.app)
    response = client.get("/api/decision-memory", params={"limit": 0})

    assert response.status_code == 422
    payload = response.json()
    assert payload["ok"] is False
    assert payload["error"]["code"] == "validation_error"
