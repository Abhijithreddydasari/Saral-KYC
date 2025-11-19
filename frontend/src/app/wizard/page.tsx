"use client";

import { useMemo, useState } from "react";

import { StatusIndicator } from "@/components/kyc/status-indicator";
import { UploadStep } from "@/components/wizard/upload-step";
import { StepWizard } from "@/components/wizard/step-wizard";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { DocumentRead } from "@/types/kyc";

const wizardSteps = [
  { id: "aadhaar", title: "Identity proof", description: "Upload Aadhaar front/back or national ID containing DOB", docType: "aadhaar" },
  { id: "selfie", title: "Selfie", description: "Capture a selfie for liveness/facial match", docType: "selfie" },
  { id: "signature", title: "Signature proof", description: "Upload a blank sheet signature or PAN card", docType: "signature" },
];

export default function WizardPage() {
  const [applicationId, setApplicationId] = useState<number>(1);
  const [activeStepId, setActiveStepId] = useState(wizardSteps[0].id);
  const [documents, setDocuments] = useState<Record<string, DocumentRead>>({});

  const currentStep = useMemo(() => wizardSteps.find((step) => step.id === activeStepId) ?? wizardSteps[0], [activeStepId]);

  const handleUploaded = (doc: DocumentRead) => {
    setDocuments((prev) => ({ ...prev, [doc.doc_type.toLowerCase()]: doc }));
    const currentIndex = wizardSteps.findIndex((step) => step.id === activeStepId);
    const nextStep = wizardSteps[currentIndex + 1];
    if (nextStep) {
      setActiveStepId(nextStep.id);
    }
  };

  return (
    <main className="mx-auto max-w-5xl space-y-6 px-6 py-10">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <Badge variant="secondary" className="mb-2">
            Applicant wizard
          </Badge>
          <h1 className="text-3xl font-semibold">Finish KYC in 3 quick steps</h1>
          <p className="text-sm text-muted-foreground">Use the reference ID from SMS/email to resume uploads any time.</p>
        </div>
        <div className="w-full max-w-xs">
          <label className="text-xs font-medium text-muted-foreground">Application ID</label>
          <Input
            type="number"
            min={1}
            value={applicationId}
            onChange={(event) => setApplicationId(Number(event.target.value) || 1)}
            className="mt-1"
          />
        </div>
      </div>

      <StepWizard steps={wizardSteps} activeStepId={activeStepId} />

      <UploadStep
        applicationId={applicationId}
        docType={currentStep.docType}
        label={currentStep.title}
        description={currentStep.description}
        onUploaded={handleUploaded}
      />

      <Card>
        <CardHeader>
          <CardTitle>Stage health</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-3">
          {wizardSteps.map((step) => (
            <StatusIndicator
              key={step.id}
              status={documents[step.id]?.status ?? "pending"}
              score={documents[step.id]?.authenticity_score}
              flags={documents[step.id]?.anomaly_flags}
            />
          ))}
        </CardContent>
      </Card>
    </main>
  );
}

