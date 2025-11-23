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
    PASSPORT = "passport"
    VOTER_ID = "voter_id"
    DRIVERS_LICENSE = "drivers_license"
    BANK_STATEMENT = "bank_statement"
    ITR = "itr"
    SALARY_SLIPS = "salary_slips"
    SELFIE = "selfie"
    UTILITY_BILL = "utility_bill"
    ID_CARD = "id_card"
    ADDRESS = "address"
    PDF = "pdf"
    JPG = "jpg"
    JPEG = "jpeg"
    PNG = "png"
    OTHER = "other"

