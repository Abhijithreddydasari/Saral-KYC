"\"\"\"Shared enums for application + document status.\"\"\""

from enum import Enum


class ApplicationStatus(str, Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    MANUAL_REVIEW = "manual_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class DocumentType(str, Enum):
    AADHAAR = "aadhaar"
    PAN = "pan"
    ADDRESS = "address"
    SELFIE = "selfie"
    BANK_STATEMENT = "bank_statement"
    OTHER = "other"

