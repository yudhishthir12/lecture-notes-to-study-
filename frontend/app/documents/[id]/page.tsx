"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  FileText,
  Presentation,
  FileCode,
  Calendar,
  Layers,
  Sparkles,
  RefreshCw,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  ArrowLeft,
  Loader2,
  Trash2,
  Clock,
  ShieldCheck,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { Document, DocumentStatusResponse } from "@/types";
import { api } from "@/lib/api";
import { formatDate, formatFileSize, getStatusColor } from "@/lib/utils";
import { toast } from "sonner";

export default function DocumentDetailPage() {
  const params = useParams();
  const router = useRouter();
  const documentId = params?.id as string;

  const [document, setDocument] = React.useState<Document | null>(null);
  const [statusResponse, setStatusResponse] =
    React.useState<DocumentStatusResponse | null>(null);
  const [isLoading, setIsLoading] = React.useState(true);
  const [isGenerating, setIsGenerating] = React.useState(false);
  const [isDeleting, setIsDeleting] = React.useState(false);
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null);

  // Load document data
  const loadDoc = React.useCallback(async () => {
    if (!documentId) return;
    try {
      const doc = await api.getDocument(documentId);
      setDocument(doc);
      setErrorMsg(null);
    } catch (err: any) {
      console.error("Failed to load document details:", err);
      setErrorMsg(err.message || "Could not load document.");
    } finally {
      setIsLoading(false);
    }
  }, [documentId]);

  // Poll status while processing
  React.useEffect(() => {
    loadDoc();
  }, [loadDoc]);

  React.useEffect(() => {
    if (!documentId) return;

    let interval: NodeJS.Timeout;
    const isProcessing =
      document &&
      [
        "uploaded",
        "parsing",
        "chunking",
        "extracting_concepts",
        "generating_summary",
        "generating_questions",
        "evaluating",
        "retrying",
      ].includes(document.status);

    if (isProcessing) {
      interval = setInterval(async () => {
        try {
          const statusRes = await api.getDocumentStatus(documentId);
          setStatusResponse(statusRes);
          if (statusRes.status !== document?.status) {
            setDocument((prev) =>
              prev ? { ...prev, status: statusRes.status } : null,
            );
          }
          if (
            statusRes.status === "completed" ||
            statusRes.status === "failed"
          ) {
            loadDoc();
            clearInterval(interval);
          }
        } catch (e) {
          // ignore status poll errors
        }
      }, 1500);
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [document?.status, documentId, loadDoc]);

  // Handle generation trigger
  const handleGenerate = async () => {
    if (!documentId) return;
    try {
      setIsGenerating(true);
      setErrorMsg(null);
      const res = await api.generateStudyPack(documentId);
      setStatusResponse(res);
      toast.success("Study pack generation started!", {
        description: "The AI pipeline is parsing and generating materials.",
      });
      loadDoc();
    } catch (err: any) {
      console.error("Failed to trigger study pack generation:", err);
      const detail = err.detail || err.message;
      setErrorMsg(detail);
      toast.error("Generation failed to start", { description: detail });
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDelete = async () => {
    if (!confirm(`Are you sure you want to delete "${document?.filename}"?`))
      return;
    try {
      setIsDeleting(true);
      await api.deleteDocument(documentId);
      toast.success("Document deleted");
      router.push("/");
    } catch (err: any) {
      toast.error("Failed to delete document", { description: err.message });
      setIsDeleting(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-44 w-full rounded-xl" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  if (errorMsg && !document) {
    return (
      <div className="rounded-xl border border-destructive/20 bg-destructive/10 p-8 text-center space-y-4">
        <AlertTriangle className="h-10 w-10 text-destructive mx-auto" />
        <h3 className="text-lg font-bold text-destructive">
          Failed to Load Document
        </h3>
        <p className="text-sm text-muted-foreground">{errorMsg}</p>
        <div className="flex justify-center gap-3">
          <Button variant="outline" onClick={() => router.push("/")}>
            Back to Dashboard
          </Button>
          <Button onClick={loadDoc}>Retry</Button>
        </div>
      </div>
    );
  }

  if (!document) return null;

  const statusInfo = getStatusColor(document.status);
  const isPipelineActive = [
    "parsing",
    "chunking",
    "extracting_concepts",
    "generating_summary",
    "generating_questions",
    "evaluating",
    "retrying",
  ].includes(document.status);

  // Stepper stages
  const pipelineStages = [
    { key: "uploaded", label: "Uploaded" },
    { key: "parsing", label: "Parsing" },
    { key: "chunking", label: "Chunking" },
    { key: "extracting_concepts", label: "Concepts" },
    { key: "generating_summary", label: "Summary" },
    { key: "generating_questions", label: "Questions" },
    { key: "evaluating", label: "Audit" },
    { key: "completed", label: "Ready" },
  ];

  const currentStageIndex = pipelineStages.findIndex(
    (s) => s.key === document.status,
  );

  return (
    <div className="space-y-6">
      {/* Top Navigation */}
      <div className="flex items-center justify-between">
        <Link
          href="/"
          className="inline-flex items-center gap-1.5 text-xs font-semibold text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          <span>Back to Dashboard</span>
        </Link>

        <div className="flex items-center gap-2">
          {document.has_study_pack && (
            <Link href={`/study-packs/${document.study_pack_id || document.id}`}>
              <Button size="sm" className="gap-1.5">
                <Sparkles className="h-4 w-4" />
                <span>View Study Pack</span>
              </Button>
            </Link>
          )}

          <Button
            variant="outline"
            size="sm"
            onClick={handleDelete}
            disabled={isDeleting}
            className="text-destructive hover:bg-destructive/10 hover:text-destructive h-8 px-2.5"
            title="Delete document"
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Main Document Details Card */}
      <Card>
        <CardContent className="p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="space-y-2">
              <div className="flex items-center gap-2">
                <span className="text-xs uppercase font-bold text-muted-foreground bg-muted px-2 py-0.5 rounded">
                  {document.file_type}
                </span>
                <div
                  className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${statusInfo.badge}`}
                >
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${statusInfo.dot}`}
                  />
                  <span>{statusInfo.label}</span>
                </div>
              </div>

              <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-foreground">
                {document.filename}
              </h1>

              <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
                <div className="flex items-center gap-1">
                  <Calendar className="h-3.5 w-3.5" />
                  <span>Uploaded {formatDate(document.created_at)}</span>
                </div>
                <span>•</span>
                <span>Size: {formatFileSize(document.file_size)}</span>
                {document.page_count && (
                  <>
                    <span>•</span>
                    <div className="flex items-center gap-1">
                      <Layers className="h-3.5 w-3.5" />
                      <span>{document.page_count} pages / slides</span>
                    </div>
                  </>
                )}
                {document.chunks_count ? (
                  <>
                    <span>•</span>
                    <span>{document.chunks_count} text chunks</span>
                  </>
                ) : null}
              </div>
            </div>

            {/* Primary Action Button */}
            <div className="flex flex-col sm:items-end gap-2">
              {document.has_study_pack ? (
                <Link href={`/study-packs/${document.study_pack_id || document.id}`}>
                  <Button className="gap-2 shadow-sm">
                    <Sparkles className="h-4 w-4" />
                    <span>Open Study Pack</span>
                    <ArrowRight className="h-4 w-4" />
                  </Button>
                </Link>
              ) : (
                <Button
                  onClick={handleGenerate}
                  disabled={isPipelineActive || isGenerating}
                  className="gap-2 shadow-sm"
                >
                  {isPipelineActive || isGenerating ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Processing Study Pack...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4" />
                      <span>Generate Study Pack</span>
                    </>
                  )}
                </Button>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Progress Stepper & Real-time Status Card */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <Clock className="h-4 w-4 text-primary" />
              Pipeline Execution Status
            </CardTitle>
            <Button
              variant="ghost"
              size="sm"
              onClick={loadDoc}
              className="h-7 text-xs gap-1"
            >
              <RefreshCw className="h-3 w-3" />
              <span>Refresh</span>
            </Button>
          </div>
          <CardDescription>
            {statusResponse?.current_stage ||
              (document.status === "completed"
                ? "Generation completed successfully"
                : document.status === "uploaded"
                  ? "Document uploaded and awaiting study pack generation"
                  : `Current status: ${statusInfo.label}`)}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-6">
          {/* Progress bar */}
          <div className="space-y-1.5">
            <div className="flex justify-between text-xs font-semibold text-muted-foreground">
              <span>Overall Progress</span>
              <span>
                {statusResponse?.progress_percentage ??
                  (document.status === "completed"
                    ? 100
                    : document.status === "uploaded"
                      ? 10
                      : 60)}
                %
              </span>
            </div>
            <Progress
              value={
                statusResponse?.progress_percentage ??
                (document.status === "completed"
                  ? 100
                  : document.status === "uploaded"
                    ? 10
                    : 60)
              }
            />
          </div>

          {/* Stepper bubbles */}
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8 text-center text-xs">
            {pipelineStages.map((stage, idx) => {
              const isPassed =
                document.status === "completed" ||
                (currentStageIndex !== -1 && idx <= currentStageIndex);
              const isCurrent = stage.key === document.status;

              return (
                <div
                  key={stage.key}
                  className={`rounded-lg border p-2.5 transition-all ${
                    isCurrent
                      ? "border-primary bg-primary/10 text-primary font-bold shadow-xs"
                      : isPassed
                        ? "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-400 font-medium"
                        : "border-muted bg-muted/30 text-muted-foreground"
                  }`}
                >
                  <div className="flex items-center justify-center mb-1">
                    {isCurrent ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />
                    ) : isPassed ? (
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
                    ) : (
                      <span className="h-2 w-2 rounded-full bg-muted-foreground/40" />
                    )}
                  </div>
                  <span className="truncate block">{stage.label}</span>
                </div>
              );
            })}
          </div>

          {/* Error notice if failed */}
          {(document.status === "failed" || errorMsg) && (
            <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-xs text-destructive flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 shrink-0" />
              <div className="space-y-1">
                <p className="font-semibold">Pipeline encountered an issue</p>
                <p>
                  {document.error_message ||
                    errorMsg ||
                    "An error occurred during processing."}
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleGenerate}
                  className="mt-2 text-xs h-7"
                >
                  Retry Study Pack Generation
                </Button>
              </div>
            </div>
          )}

          {/* Ready notification banner */}
          {document.has_study_pack && (
            <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-4 text-xs text-emerald-900 dark:text-emerald-300 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <ShieldCheck className="h-5 w-5 text-emerald-600 shrink-0" />
                <div>
                  <p className="font-semibold">Study Pack is Ready!</p>
                  <p className="text-muted-foreground">
                    Includes summary, concepts, glossary, formulas, and verified
                    questions.
                  </p>
                </div>
              </div>
              <Link href={`/study-packs/${document.study_pack_id || document.id}`}>
                <Button
                  size="sm"
                  variant="success"
                  className="gap-1 h-8 text-xs"
                >
                  <span>Open Viewer</span>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
              </Link>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Extracted Text Preview Card */}
      {document.extracted_text && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <FileText className="h-4 w-4 text-primary" />
              Extracted Text Preview
            </CardTitle>
            <CardDescription>
              Raw extracted content parsed from your lecture file.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <pre className="max-h-72 overflow-y-auto rounded-lg bg-muted/40 p-4 text-xs font-mono text-muted-foreground whitespace-pre-wrap leading-relaxed border">
              {document.extracted_text}
            </pre>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
