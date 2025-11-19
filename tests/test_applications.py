import io
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api.v1.endpoints import applications as applications_router
from app.models.enums import DocumentStatus, DocumentType
from app.services.risk_engine import RiskAssessment


def test_create_application(client: TestClient) -> None:
    payload = {"full_name": "Test User", "email": "test@example.com", "phone_number": "1234567890"}
    response = client.post("/api/v1/kyc/applications", json=payload)
    assert response.status_code == 201
    body = response.json()
    assert body["full_name"] == payload["full_name"]
    assert body["status"] == "draft"


def test_upload_document_with_stubbed_pipeline(monkeypatch, client: TestClient) -> None:
    payload = {"full_name": "Doc User", "email": "doc@example.com"}
    create_resp = client.post("/api/v1/kyc/applications", json=payload)
    application_id = create_resp.json()["id"]

    async def fake_ingest(application, artifact, file):
        artifact.status = DocumentStatus.PROCESSED
        artifact.authenticity_score = 0.9
        artifact.liveness_score = 0.8
        artifact.extraction_payload = {"name": ["Doc User"]}
        artifact.anomaly_flags = []
        return artifact

    monkeypatch.setattr(applications_router.pipeline, "ingest_and_analyze", AsyncMock(side_effect=fake_ingest))

    files = {
        "file": ("aadhaar.png", io.BytesIO(b"fake-bytes"), "image/png"),
    }
    data = {"doc_type": DocumentType.AADHAAR.value}
    response = client.post(f"/api/v1/kyc/applications/{application_id}/documents", data=data, files=files)

    assert response.status_code == 201
    body = response.json()
    assert body["doc_type"] == DocumentType.AADHAAR.value


def test_risk_assessment_endpoint(monkeypatch, client: TestClient) -> None:
    payload = {"full_name": "Risk User"}
    create_resp = client.post("/api/v1/kyc/applications", json=payload)
    application_id = create_resp.json()["id"]

    async def fake_ingest(application, artifact, file):
        artifact.status = DocumentStatus.PROCESSED
        artifact.authenticity_score = 0.95
        artifact.liveness_score = 0.8
        artifact.extraction_payload = {"name": ["Risk User"]}
        artifact.anomaly_flags = []
        return artifact

    monkeypatch.setattr(applications_router.pipeline, "ingest_and_analyze", AsyncMock(side_effect=fake_ingest))

    files = {"file": ("pan.png", io.BytesIO(b"fake"), "image/png")}
    data = {"doc_type": DocumentType.PAN.value}
    client.post(f"/api/v1/kyc/applications/{application_id}/documents", data=data, files=files)

    mock_assessment = RiskAssessment(
        score=0.8,
        band="low",
        explanation={"factors": []},
        fairness_report={"language": "en"},
    )
    monkeypatch.setattr(applications_router.risk_engine, "assess", lambda *args, **kwargs: mock_assessment)

    response = client.post(
        f"/api/v1/kyc/applications/{application_id}/risk/assess",
        json={"customer_statement": "All documents submitted"},
    )
    assert response.status_code == 200
    assert response.json()["risk_band"] == "low"


def test_application_summary_endpoint(client: TestClient) -> None:
    payload = {"full_name": "Summary User"}
    create_resp = client.post("/api/v1/kyc/applications", json=payload)
    application_id = create_resp.json()["id"]

    response = client.get(f"/api/v1/kyc/applications/{application_id}/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["application"]["id"] == application_id
    assert body["timeline"]["application_id"] == application_id


def test_document_preview_endpoint(monkeypatch, client: TestClient, tmp_path) -> None:
    payload = {"full_name": "Preview User"}
    create_resp = client.post("/api/v1/kyc/applications", json=payload)
    application_id = create_resp.json()["id"]

    file_path = tmp_path / "preview.png"
    file_path.write_bytes(b"preview-bytes")

    async def fake_ingest(application, artifact, file):
        artifact.status = DocumentStatus.PROCESSED
        artifact.authenticity_score = 0.9
        artifact.liveness_score = 0.8
        artifact.storage_path = str(file_path)
        artifact.extraction_payload = {"name": ["Preview User"]}
        artifact.anomaly_flags = []
        return artifact

    monkeypatch.setattr(applications_router.pipeline, "ingest_and_analyze", AsyncMock(side_effect=fake_ingest))

    files = {"file": ("preview.png", io.BytesIO(b"fake"), "image/png")}
    data = {"doc_type": DocumentType.PAN.value}
    upload_resp = client.post(f"/api/v1/kyc/applications/{application_id}/documents", data=data, files=files)
    doc_id = upload_resp.json()["id"]

    preview_resp = client.get(f"/api/v1/kyc/applications/{application_id}/documents/{doc_id}/preview")
    assert preview_resp.status_code == 200
    preview_body = preview_resp.json()
    assert preview_body["document"]["id"] == doc_id
    assert preview_body["mime_type"] == "image/png"

    download_url = preview_body["download_url"]
    download_resp = client.get(download_url)
    assert download_resp.status_code == 200
    assert download_resp.content == b"preview-bytes"
