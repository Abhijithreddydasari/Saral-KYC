from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.db.session import engine
from app.models.audit import AuditEvent


def test_escalate_application(client: TestClient) -> None:
    payload = {"full_name": "Escalation User"}
    create_resp = client.post("/api/v1/kyc/applications", json=payload)
    application_id = create_resp.json()["id"]

    escalate_resp = client.post(
        f"/api/v1/kyc/applications/{application_id}/escalate",
        json={"issue_type": "missing_pan"},
    )
    assert escalate_resp.status_code == 201
    assert escalate_resp.json()["issue_type"] == "missing_pan"


def test_audit_event_created_on_application_create(client: TestClient) -> None:
    response = client.post("/api/v1/kyc/applications", json={"full_name": "Audit User"})
    assert response.status_code == 201

    with Session(engine) as session:
        events = session.exec(select(AuditEvent)).all()
        assert any(event.action.value == "application_created" for event in events)

