"""KYC application + document endpoints."""

from __future__ import annotations

from datetime import datetime
import logging
import mimetypes
from pathlib import Path
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from app.api.deps.auth import get_current_user, get_optional_user
from app.api.deps.db import get_db
from app.core.config import get_settings
from app.models.application import DocumentArtifact, KycApplication
from app.models.audit import AuditAction
from app.models.enums import ApplicationStatus, DocumentStatus, DocumentType
from app.models.risk import RiskDecision
from app.schemas.application import (
    ApplicationCreate,
    ApplicationRead,
    ApplicationSummary,
    DocumentPreviewResponse,
    DocumentRead,
)
from app.schemas.risk import RiskAssessmentRequest, RiskDecisionRead, RiskStatusResponse
from app.schemas.workflow import (
    ApplicationTimeline,
    NotificationCreate,
    NotificationRead,
    ReviewCreate,
    ReviewRead,
)
from app.services.audit import AuditLogger
from app.services.document_pipeline import DocumentPipeline
from app.services.guidance import GuidanceEngine
from app.services.notification import NotificationService
from app.services.risk_catalog import derive_risk_category, risk_reasons_for
from app.services.risk_engine import RiskEngine
from app.services.timeline import TimelineBuilder
from app.models.workflow import NotificationEvent, ReviewTask
from app.models.user import User
from app.db.session import get_session

router = APIRouter(prefix="/kyc", tags=["kyc"])
pipeline = DocumentPipeline()
risk_engine = RiskEngine()
guidance_engine = GuidanceEngine()
notification_service = NotificationService()
timeline_builder = TimelineBuilder()
audit_logger = AuditLogger()
settings = get_settings()
logger = logging.getLogger(__name__)

MAX_DOCUMENTS = 5

_DOC_TYPE_ALIASES = {
    "application/pdf": DocumentType.PDF,
    "image/jpeg": DocumentType.JPEG,
    "image/jpg": DocumentType.JPG,
    "image/png": DocumentType.PNG,
    "jpeg": DocumentType.JPEG,
    "jpg": DocumentType.JPG,
    "png": DocumentType.PNG,
    "pdf": DocumentType.PDF,
}


def _parse_doc_type(raw_value: str | None) -> DocumentType:
    if not raw_value:
        return DocumentType.OTHER
    normalized = raw_value.strip().lower()
    try:
        return DocumentType(normalized)
    except ValueError:
        return _DOC_TYPE_ALIASES.get(normalized, DocumentType.OTHER)


def _assert_application_access(application: KycApplication, user: User | None) -> None:
    if user is None:
        return
    if user.is_admin:
        return
    if application.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to modify this application")


@router.post("/applications", response_model=ApplicationRead, status_code=status.HTTP_201_CREATED)
def create_application(
    payload: ApplicationCreate,
    session: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> ApplicationRead:
    application = KycApplication(**payload.dict(), user_id=current_user.id if current_user else None)
    session.add(application)
    session.flush()
    audit_logger.record(
        session,
        AuditAction.APPLICATION_CREATED,
        "kyc_application",
        str(application.id),
        {"reference_id": application.reference_id},
    )
    session.commit()
    session.refresh(application)
    application.documents = []
    return application


@router.get("/applications", response_model=List[ApplicationRead])
def list_applications(session: Session = Depends(get_db)) -> List[ApplicationRead]:
    applications = session.exec(select(KycApplication)).all()
    for app_obj in applications:
        docs = session.exec(select(DocumentArtifact).where(DocumentArtifact.application_id == app_obj.id)).all()
        app_obj.documents = docs
    return applications


@router.get("/applications/mine", response_model=List[ApplicationRead])
def list_my_applications(
    session: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[ApplicationRead]:
    applications = session.exec(select(KycApplication).where(KycApplication.user_id == current_user.id)).all()
    for app_obj in applications:
        docs = session.exec(select(DocumentArtifact).where(DocumentArtifact.application_id == app_obj.id)).all()
        app_obj.documents = docs
    return applications


@router.get("/applications/{application_id}", response_model=ApplicationRead)
def get_application(application_id: int, session: Session = Depends(get_db)) -> ApplicationRead:
    application = session.get(KycApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    documents = session.exec(select(DocumentArtifact).where(DocumentArtifact.application_id == application_id)).all()
    application.documents = documents
    return application


@router.post(
    "/applications/{application_id}/documents",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_document(
    application_id: int,
    background_tasks: BackgroundTasks,
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> DocumentRead:
    application = session.get(KycApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    _assert_application_access(application, current_user)

    resolved_doc_type = _parse_doc_type(doc_type)
    if resolved_doc_type != DocumentType.SELFIE:
        existing_docs = session.exec(
            select(DocumentArtifact)
            .where(DocumentArtifact.application_id == application_id)
            .where(DocumentArtifact.doc_type != DocumentType.SELFIE)
        ).all()
        if len(existing_docs) >= MAX_DOCUMENTS:
            raise HTTPException(status_code=400, detail="Maximum document uploads reached")

    artifact = DocumentArtifact(application_id=application_id, doc_type=resolved_doc_type, status=DocumentStatus.UPLOADED)
    session.add(artifact)
    session.flush()

    if settings.doc_enable_async_processing:
        pipeline.store_document_file(application, artifact, file)
        artifact.status = DocumentStatus.PROCESSING
        audit_logger.record(
            session,
            AuditAction.DOCUMENT_UPLOADED,
            "document_artifact",
            str(artifact.id),
            {"doc_type": artifact.doc_type.value},
        )
        session.add(artifact)
        session.commit()
        session.refresh(artifact)
        background_tasks.add_task(_process_document_task, application.id, artifact.id)
        return artifact

    application.documents = session.exec(select(DocumentArtifact).where(DocumentArtifact.application_id == application_id)).all()
    artifact = await pipeline.ingest_and_analyze(application, artifact, file)
    audit_logger.record(
        session,
        AuditAction.DOCUMENT_UPLOADED,
        "document_artifact",
        str(artifact.id),
        {"doc_type": artifact.doc_type.value},
    )
    session.add(artifact)
    session.commit()
    session.refresh(artifact)
    return artifact


@router.post(
    "/applications/{application_id}/liveness",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_liveness_check(
    application_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> DocumentRead:
    application = session.get(KycApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    _assert_application_access(application, current_user)

    existing_selfie = session.exec(
        select(DocumentArtifact)
        .where(DocumentArtifact.application_id == application_id)
        .where(DocumentArtifact.doc_type == DocumentType.SELFIE)
    ).first()
    if existing_selfie:
        raise HTTPException(status_code=400, detail="Selfie already uploaded")

    artifact = DocumentArtifact(application_id=application_id, doc_type=DocumentType.SELFIE, status=DocumentStatus.UPLOADED)
    session.add(artifact)
    session.flush()

    if settings.doc_enable_async_processing:
        pipeline.store_document_file(application, artifact, file)
        artifact.status = DocumentStatus.PROCESSING
        audit_logger.record(
            session,
            AuditAction.DOCUMENT_UPLOADED,
            "document_artifact",
            str(artifact.id),
            {"doc_type": artifact.doc_type.value},
        )
        session.add(artifact)
        session.commit()
        session.refresh(artifact)
        background_tasks.add_task(_process_document_task, application.id, artifact.id)
        return artifact

    application.documents = session.exec(select(DocumentArtifact).where(DocumentArtifact.application_id == application_id)).all()
    artifact = await pipeline.ingest_and_analyze(application, artifact, file)
    audit_logger.record(
        session,
        AuditAction.DOCUMENT_UPLOADED,
        "document_artifact",
        str(artifact.id),
        {"doc_type": artifact.doc_type.value},
    )
    session.add(artifact)
    session.commit()
    session.refresh(artifact)
    return artifact


@router.post(
    "/applications/{application_id}/escalate",
    response_model=ReviewRead,
    status_code=status.HTTP_201_CREATED,
)
def escalate_application(
    application_id: int,
    payload: ReviewCreate,
    session: Session = Depends(get_db),
) -> ReviewRead:
    application = session.get(KycApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    documents = session.exec(select(DocumentArtifact).where(DocumentArtifact.application_id == application_id)).all()
    summary = payload.ai_summary or guidance_engine.build_escalation_summary(documents)

    review = ReviewTask(application_id=application_id, issue_type=payload.issue_type, ai_summary=summary)
    application.status = ApplicationStatus.MANUAL_REVIEW

    session.add(review)
    session.add(application)
    session.flush()
    audit_logger.record(
        session,
        AuditAction.ESCALATED,
        "review_task",
        str(review.id),
        {"issue_type": payload.issue_type},
    )
    session.commit()
    session.refresh(review)
    return review


@router.post(
    "/applications/{application_id}/complete",
    response_model=ApplicationRead,
)
def complete_application(
    application_id: int,
    session: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> ApplicationRead:
    application = session.get(KycApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    _assert_application_access(application, current_user)

    now = datetime.utcnow()
    application.status = ApplicationStatus.PENDING_REVIEW
    application.submitted_at = now
    application.completed_at = now

    session.add(application)
    session.commit()
    session.refresh(application)
    application.documents = session.exec(select(DocumentArtifact).where(DocumentArtifact.application_id == application_id)).all()
    return application


@router.post(
    "/applications/{application_id}/nudges",
    response_model=NotificationRead,
    status_code=status.HTTP_201_CREATED,
)
def send_nudge(
    application_id: int,
    payload: NotificationCreate,
    session: Session = Depends(get_db),
) -> NotificationRead:
    application = session.get(KycApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    notification = NotificationEvent(
        application_id=application_id,
        channel=payload.channel,
        message=payload.message,
        metadata_payload=payload.metadata,
    )

    notification_service.send(payload.channel, application.email or application.phone_number, payload.message, payload.metadata)

    session.add(notification)
    session.flush()
    audit_logger.record(
        session,
        AuditAction.NUDGE_SENT,
        "notification_event",
        str(notification.id),
        {"channel": payload.channel.value},
    )
    session.commit()
    session.refresh(notification)
    return notification


@router.get(
    "/applications/{application_id}/timeline",
    response_model=ApplicationTimeline,
)
def get_timeline(application_id: int, session: Session = Depends(get_db)) -> ApplicationTimeline:
    application = session.get(KycApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    application.documents = session.exec(select(DocumentArtifact).where(DocumentArtifact.application_id == application_id)).all()
    application.risk_decisions = session.exec(select(RiskDecision).where(RiskDecision.application_id == application_id)).all()
    application.review_tasks = session.exec(select(ReviewTask).where(ReviewTask.application_id == application_id)).all()
    application.notifications = session.exec(select(NotificationEvent).where(NotificationEvent.application_id == application_id)).all()

    return timeline_builder.build(application)


@router.get(
    "/applications/{application_id}/summary",
    response_model=ApplicationSummary,
)
def get_application_summary(application_id: int, session: Session = Depends(get_db)) -> ApplicationSummary:
    application = session.get(KycApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    documents = session.exec(select(DocumentArtifact).where(DocumentArtifact.application_id == application_id)).all()
    application.documents = documents
    application.risk_decisions = session.exec(
        select(RiskDecision).where(RiskDecision.application_id == application_id).order_by(RiskDecision.created_at.desc())
    ).all()
    application.review_tasks = session.exec(select(ReviewTask).where(ReviewTask.application_id == application_id)).all()
    application.notifications = session.exec(select(NotificationEvent).where(NotificationEvent.application_id == application_id)).all()
    timeline = timeline_builder.build(application)

    latest_risk = session.exec(
        select(RiskDecision)
        .where(RiskDecision.application_id == application_id)
        .order_by(RiskDecision.created_at.desc())
    ).first()

    return ApplicationSummary(application=application, latest_risk=latest_risk, timeline=timeline)


@router.get(
    "/applications/{application_id}/documents/{document_id}/preview",
    response_model=DocumentPreviewResponse,
)
def get_document_preview(
    application_id: int,
    document_id: int,
    session: Session = Depends(get_db),
) -> DocumentPreviewResponse:
    document = session.get(DocumentArtifact, document_id)
    if not document or document.application_id != application_id:
        raise HTTPException(status_code=404, detail="Document not found")

    download_url = f"/api/v1/kyc/documents/{document_id}/download"
    mime_type, _ = mimetypes.guess_type(document.storage_path or "")
    available_actions = ["download", "share"]
    return DocumentPreviewResponse(
        document=document,
        download_url=download_url,
        mime_type=mime_type,
        available_actions=available_actions,
    )


@router.get("/documents/{document_id}/download")
def download_document(document_id: int, session: Session = Depends(get_db)) -> FileResponse:
    document = session.get(DocumentArtifact, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    if not document.storage_path:
        raise HTTPException(status_code=404, detail="Document storage unavailable")

    file_path = Path(document.storage_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Document file missing")

    media_type, _ = mimetypes.guess_type(file_path.name)
    return FileResponse(
        path=file_path,
        media_type=media_type or "application/octet-stream",
        filename=file_path.name,
    )


@router.post(
    "/applications/{application_id}/risk/assess",
    response_model=RiskDecisionRead,
)
def assess_risk(
    application_id: int,
    payload: RiskAssessmentRequest,
    session: Session = Depends(get_db),
) -> RiskDecisionRead:
    application = session.get(KycApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    documents = session.exec(select(DocumentArtifact).where(DocumentArtifact.application_id == application_id)).all()
    assessment = risk_engine.assess(application, documents, payload.customer_statement)

    decision = RiskDecision(
        application_id=application_id,
        risk_score=assessment.score,
        risk_band=assessment.band,
        rule_version=assessment.rule_version,
        explanation=assessment.explanation,
        fairness_report=assessment.fairness_report,
    )

    application.risk_score = assessment.score
    application.risk_reason = assessment.band

    session.add(decision)
    session.add(application)
    session.flush()
    audit_logger.record(
        session,
        AuditAction.RISK_ASSESSED,
        "kyc_application",
        str(application_id),
        {"score": assessment.score, "band": assessment.band},
    )
    session.commit()
    session.refresh(decision)
    return decision


def _process_document_task(application_id: int, document_id: int) -> None:
    with get_session() as session:
        application = session.get(KycApplication, application_id)
        document = session.get(DocumentArtifact, document_id)
        if not application or not document:
            logger.warning("Background doc processing aborted app_id=%s doc_id=%s missing data", application_id, document_id)
            return
        application.documents = session.exec(select(DocumentArtifact).where(DocumentArtifact.application_id == application_id)).all()
        try:
            pipeline.analyze_stored_document(application, document)
            session.add(document)
            session.commit()
        except Exception as exc:  # pragma: no cover - background failures logged
            logger.exception("Failed to process document in background doc_id=%s error=%s", document_id, exc)


@router.get(
    "/applications/{application_id}/risk/status",
    response_model=RiskStatusResponse,
)
def get_risk_status(
    application_id: int,
    session: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> RiskStatusResponse:
    application = session.get(KycApplication, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    _assert_application_access(application, current_user)

    category, normalized = derive_risk_category(application.risk_score, application.reference_id)
    reasons = risk_reasons_for(category)
    return RiskStatusResponse(category=category, score=normalized, reasons=reasons, generated_at=datetime.utcnow())

