"use client";

import { useMemo } from "react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface Step {
  id: string;
  title: string;
  description: string;
}

interface StepWizardProps {
  steps: Step[];
  activeStepId: string;
}

export function StepWizard({ steps, activeStepId }: StepWizardProps) {
  const activeIndex = useMemo(() => steps.findIndex((step) => step.id === activeStepId), [steps, activeStepId]);

  return (
    <Card>
      <CardContent className="flex flex-col gap-4 py-6">
        {steps.map((step, index) => {
          const isActive = index === activeIndex;
          const isDone = index < activeIndex;
          return (
            <div key={step.id} className={cn("flex items-start gap-3 rounded-lg border p-3", isActive ? "border-primary/50 bg-primary/5" : "border-muted")}>
              <Badge variant={isDone ? "secondary" : isActive ? "default" : "outline"} className="shrink-0">
                {index + 1}
              </Badge>
              <div>
                <p className="font-medium">{step.title}</p>
                <p className="text-sm text-muted-foreground">{step.description}</p>
              </div>
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
}

