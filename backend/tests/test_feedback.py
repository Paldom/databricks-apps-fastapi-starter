"""Feedback endpoint: links human assessments to MLflow traces."""

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

import app.main as app_main


def _post_feedback(payload):
    with patch("mlflow.log_feedback") as log_feedback:
        log_feedback.return_value = MagicMock(assessment_id="a-123")
        with TestClient(app_main.app) as client:
            response = client.post(
                "/api/agents/feedback",
                json=payload,
                headers={"X-Forwarded-User": "test-user"},
            )
    return response, log_feedback


def test_records_feedback_with_human_source():
    response, log_feedback = _post_feedback(
        {"trace_id": "tr-1", "value": True, "rationale": "helpful"}
    )
    assert response.status_code == 201
    assert response.json() == {"assessment_id": "a-123"}
    kwargs = log_feedback.call_args.kwargs
    assert kwargs["trace_id"] == "tr-1"
    assert kwargs["value"] is True
    assert kwargs["source"].source_id  # local dev fallback user


def test_rejects_missing_trace_id():
    response, _ = _post_feedback({"value": True})
    assert response.status_code == 422


def test_maps_mlflow_failure_to_502():
    with (
        patch("mlflow.log_feedback", side_effect=RuntimeError("boom")),
        TestClient(app_main.app) as client,
    ):
        response = client.post(
            "/api/agents/feedback",
            json={"trace_id": "tr-1", "value": False},
            headers={"X-Forwarded-User": "test-user"},
        )
    assert response.status_code == 502
