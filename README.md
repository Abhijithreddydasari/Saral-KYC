# **Saral-KYC: Simple. Secure. Seamless.**

## **Concept Overview**

**Saral-KYC** reimagines KYC as an _AI-first, compliance-aware orchestration system_ that automates end-to-end onboarding while preserving transparency, fairness, and auditability. It unifies **multimodal AI**, **large language models (LLMs)**, and **risk intelligence graphs** to deliver a _trustworthy, scalable, and explainable KYC pipeline_ for banks and financial institutions.

----------

## **Core System Architecture & Automation Design**

The Saral-KYC architecture operates as a **multi-layered AI orchestration pipeline** combining document intelligence, entity analytics, and compliance reasoning — optimized for both _accuracy_ and _regulatory transparency_.

1.  **Document Intelligence & Data Extraction:**  
    Incoming documents (Aadhar, PAN, utility bills, etc.) pass through a _multimodal preprocessing pipeline_ that detects type, orientation, and authenticity before extraction.
    
    -   **Vision Transformers (Donut / DocFormer):** Perform layout-aware parsing of IDs, extracting key-value pairs directly from images.
        
    -   **OCR + NER Hybrid Layer:** Handles non-standard document layouts using OCR text fed to a transformer-based _Named Entity Recognition_ model fine-tuned for Indian KYC fields.
        
    -   **Forgery & Liveness Verification:** CNNs detect tampering (compression artifacts, edge mismatches) while 3D face depth estimation confirms selfie liveness and cross-matches with document photos.
        
    -   **Cross-Document Validation:** Sentence-BERT embeddings compare extracted entities across documents, identifying inconsistencies in names, addresses, or ID details.
        
2.  **AI-driven Risk & Anomaly Detection:**  
    Verified entities feed into a _Risk Intelligence Graph_, mapping relationships between users, addresses, and connected accounts.
    
    -   **Graph Neural Networks (GNNs):** Detect relational anomalies such as synthetic identities or fraud clusters.
        
    -   **LLM-based Behavior Understanding:** Analyzes free-text statements or user chats to infer intent, cooperation, and risk sentiment.
        
    -   **Dynamic Risk Scoring Engine:** Combines document authenticity, entity consistency, and behavioral trust into a composite _KYC Risk Index_, aligned with FATF/AML guidelines. Scoring rules are version-controlled for audit readiness.
        
3.  **Explainability, Governance & Compliance Integration:**  
    Each model decision generates an _XAI metadata packet_ containing SHAP explanations, decision rationale, and applied regulatory rule IDs.
    
    -   A _Regulatory Logic Engine_ dynamically aligns actions with RBI/AML policies via rule-sync APIs.
        
    -   Continuous _model monitoring_ tracks fairness, accuracy, and drift — auto-triggering retraining pipelines when thresholds are breached.
        
    -   An _immutable audit ledger_ logs every decision, ensuring end-to-end traceability.
        
4.  **Human Oversight & Feedback Loop:**  
    Ambiguous cases are escalated with AI-generated rationale summaries for manual verification. Human verdicts reinforce retraining datasets, enabling a _self-improving governance framework_.
    

----------

## **Innovation**

-   **Conversational LLM Orchestrator:** Guides customers contextually, providing multilingual clarifications and dynamic document assistance.
    
-   **Adaptive Fairness Checks:** Differential performance monitoring ensures unbiased decisions across user segments.
    
-   **Real-time Reg-Tech Sync:** Policy updates auto-reflect in decision logic through modular rule APIs.
    

----------

## **Impact**

-   **Efficiency:** 70% reduction in manual verification time and near-instant approval for low-risk profiles.
    
-   **Compliance:** Full explainability and auditable decisions reduce regulatory risk.
    
-   **Scalability:** Cloud-native microservices integrate easily with legacy banking systems.

----------

## Backend quickstart

```bash
uvicorn app.main:app --reload
```

- Configuration lives in `app/core/config.py`. Document weights, metadata thresholds, and similarity cutoffs are now tunable without touching code.
- New ML telemetry (metadata, layout, language, entity overlap) is surfaced in `DocumentArtifact.model_trace` and consumed by the enriched risk engine (`FeatureVector` + fairness counters).
- Key API additions for the frontend bridge:
  - `GET /api/v1/kyc/applications/{id}/summary`
  - `GET /api/v1/kyc/applications/{id}/documents/{doc_id}/preview`
  - `GET /api/v1/kyc/documents/{doc_id}/download`
  - `GET /api/v1/assist/session/bootstrap`

Run the test suite any time with:

```bash
pytest
```

----------

## Frontend (Next.js + Tailwind + shadcn/ui)

The repository now ships with a `/frontend` workspace that consumes the FastAPI hooks for both the applicant wizard and the operator console.

1. Install Node.js 18+ (e.g., via [https://nodejs.org](https://nodejs.org)) – required for Next.js packages.
2. Configure the API base URL:

   ```bash
   cd frontend
   cp env.example .env.local  # update NEXT_PUBLIC_API_BASE_URL if needed
   ```

3. Install dependencies and start the dev server (once Node is available):

   ```bash
   npm install
   npm run dev
   ```

What’s included out of the box:

- `src/app/wizard` — drag/drop upload stepper with live status indicators for applicants.
- `src/app/ops` — staff dashboard showing application list, risk SHAP factors, document previews, timeline, and the multilingual assistant drawer.
- `src/lib/api-client.ts` — typed fetch wrapper that respects `NEXT_PUBLIC_API_BASE_URL`.
- shadcn/ui primitives (`components/ui/*`) plus design tokens via Tailwind for quick feature work.