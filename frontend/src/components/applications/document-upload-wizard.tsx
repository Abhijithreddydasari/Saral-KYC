"use client";

import { useState, useRef } from "react";
import { Upload, FileText, CheckCircle2, AlertCircle, Loader2, File as FileIcon, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { apiClient } from "@/lib/api-client";
import type { DocumentRead } from "@/types/kyc";

const DOCUMENT_OPTIONS = [
  { value: "aadhaar", label: "National ID / Aadhaar (India)" },
  { value: "pan", label: "PAN Card" },
  { value: "passport", label: "Passport" },
  { value: "voter_id", label: "Voter ID" },
  { value: "drivers_license", label: "Driver's License" },
  { value: "bank_statement", label: "Bank statement / passbook" },
  { value: "itr", label: "ITR" },
  { value: "salary_slips", label: "Salary Slips" },
];

interface DocumentUploadWizardProps {
  applicationId: number;
  onUploadComplete?: (document: DocumentRead) => void;
}

type UploadState = "idle" | "uploading" | "processing" | "success" | "error";

export function DocumentUploadWizard({ applicationId, onUploadComplete }: DocumentUploadWizardProps) {
  const [docType, setDocType] = useState<string>(DOCUMENT_OPTIONS[0]?.value ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [uploadState, setUploadState] = useState<UploadState>("idle");
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState<DocumentRead | null>(null);
  const [error, setError] = useState<string | null>(null);
  
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError(null);
      setUploadState("idle");
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
      setError(null);
      setUploadState("idle");
    }
  };

  const triggerFileSelect = () => {
    inputRef.current?.click();
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploadState("uploading");
    setProgress(0);
    setError(null);

    const formData = new FormData();
    formData.append("doc_type", docType);
    formData.append("file", file);

    // Simulated progress for UX
    const progressInterval = setInterval(() => {
      setProgress((prev) => {
        if (prev >= 90) return prev;
        return prev + 5; // Faster upload simulation
      });
    }, 100);

    try {
      // Step 1: Upload & Analyze
      // The backend pipeline runs synchronously for now, so this request might take a few seconds
      const { data } = await apiClient.post<DocumentRead>(
        `/kyc/applications/${applicationId}/documents`, 
        formData
      );
      
      clearInterval(progressInterval);
      setProgress(100);
      setResult(data);
      setUploadState("success");
      onUploadComplete?.(data);
      
      // Haptic feedback if available
      if (navigator.vibrate) {
        navigator.vibrate(50); 
      }

    } catch (err: any) {
      clearInterval(progressInterval);
      setUploadState("error");
      setError(err.response?.data?.detail || "Failed to upload and analyze document.");
    }
  };

  const resetWizard = () => {
    setFile(null);
    setResult(null);
    setUploadState("idle");
    setProgress(0);
    if (inputRef.current) inputRef.current.value = "";
  };

  return (
    <Card className="w-full max-w-2xl mx-auto border-2">
      <CardHeader>
        <CardTitle>Upload Document</CardTitle>
        <CardDescription>
          Select the document type and upload a clear image or PDF.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        
        {/* Step 1: Document Type Selection */}
        <div className="space-y-2">
          <label className="text-sm font-medium">Document Type</label>
          <Select
            value={docType}
            onValueChange={setDocType}
            disabled={uploadState === "uploading" || uploadState === "processing"}
          >
            <SelectTrigger>
              <SelectValue placeholder="Select document type" />
            </SelectTrigger>
            <SelectContent>
              {DOCUMENT_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Step 2: Upload Area */}
        {!result && (
          <div 
            className={cn(
              "border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer relative",
              uploadState === "error" ? "border-destructive/50 bg-destructive/5" : "border-muted-foreground/25 hover:border-primary/50 hover:bg-muted/50",
              "flex flex-col items-center justify-center gap-4"
            )}
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            onClick={triggerFileSelect}
          >
            <input 
              type="file" 
              ref={inputRef}
              className="hidden" 
              accept="image/*,application/pdf"
              onChange={handleFileSelect}
            />
            
            {file ? (
              <div className="flex flex-col items-center gap-2 animate-in fade-in zoom-in duration-300">
                <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center">
                  <FileText className="h-8 w-8 text-primary" />
                </div>
                <div className="text-sm font-medium">{file.name}</div>
                <div className="text-xs text-muted-foreground">{(file.size / 1024 / 1024).toFixed(2)} MB</div>
                <Button variant="ghost" size="sm" className="mt-2 h-8 text-xs" onClick={(e) => { e.stopPropagation(); setFile(null); }}>
                  Change File
                </Button>
              </div>
            ) : (
              <>
                <div className="h-12 w-12 rounded-full bg-muted flex items-center justify-center mb-2">
                  <Upload className="h-6 w-6 text-muted-foreground" />
                </div>
                <div className="space-y-1">
                  <p className="text-sm font-medium">Click to upload or drag and drop</p>
                  <p className="text-xs text-muted-foreground">SVG, PNG, JPG or PDF (max. 10MB)</p>
                </div>
                {/* Tactile Button for "Choose File" */}
                <Button variant="secondary" className="mt-4 shadow-sm active:scale-95 transition-transform">
                  Choose File
                </Button>
              </>
            )}
          </div>
        )}

        {/* Step 3: Progress State */}
        {(uploadState === "uploading" || uploadState === "processing") && (
          <div className="space-y-2 animate-in fade-in slide-in-from-bottom-4">
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>{progress < 100 ? "Uploading & Analyzing..." : "Finalizing analysis..."}</span>
              <span>{progress}%</span>
            </div>
            <Progress value={progress} className="h-2" />
            <p className="text-xs text-muted-foreground text-center pt-2">
              Our AI models are verifying authenticity, reading text, and checking for forgery. This may take a moment.
            </p>
          </div>
        )}

        {/* Step 4: Results Display */}
        {result && uploadState === "success" && (
          <div className="rounded-lg border bg-card text-card-foreground shadow-sm animate-in fade-in slide-in-from-bottom-8">
            <div className="p-6 space-y-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="h-5 w-5 text-green-500" />
                  <h3 className="font-semibold">Analysis Complete</h3>
                </div>
                <div className={cn(
                  "px-2.5 py-0.5 rounded-full text-xs font-medium",
                  (result.authenticity_score || 0) > 0.8 ? "bg-green-100 text-green-800" : 
                  (result.authenticity_score || 0) > 0.5 ? "bg-yellow-100 text-yellow-800" : "bg-red-100 text-red-800"
                )}>
                  Trust Score: {Math.round((result.authenticity_score || 0) * 100)}%
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div className="space-y-1">
                  <p className="text-muted-foreground">Document ID</p>
                  <p className="font-mono">{result.id}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-muted-foreground">Status</p>
                  <p className="capitalize">{result.status}</p>
                </div>
              </div>

              {result.anomaly_flags && result.anomaly_flags.length > 0 && (
                <Alert variant="destructive">
                  <AlertCircle className="h-4 w-4" />
                  <AlertTitle>Anomalies Detected</AlertTitle>
                  <AlertDescription>
                    <ul className="list-disc list-inside text-xs mt-1">
                      {result.anomaly_flags.map((flag, i) => (
                        <li key={i}>{flag.replace(/_/g, " ")}</li>
                      ))}
                    </ul>
                  </AlertDescription>
                </Alert>
              )}

              <div className="pt-4 flex justify-end gap-2">
                <Button variant="outline" onClick={resetWizard}>Upload Another</Button>
              </div>
            </div>
          </div>
        )}

        {uploadState === "error" && error && (
          <Alert variant="destructive" className="animate-in fade-in">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>Upload Failed</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

      </CardContent>
      
      {!result && (
        <CardFooter className="justify-between border-t bg-muted/10 p-6">
          <Button variant="ghost" onClick={() => setFile(null)} disabled={!file || uploadState === "uploading"}>
            Clear
          </Button>
          <Button onClick={handleUpload} disabled={!file || uploadState === "uploading"}>
            {uploadState === "uploading" ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Processing
              </>
            ) : (
              "Upload & Analyze"
            )}
          </Button>
        </CardFooter>
      )}
    </Card>
  );
}

