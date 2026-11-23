"use client";

import * as React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  FileText,
  Presentation,
  FileCode,
  Calendar,
  Layers,
  ArrowRight,
  Sparkles,
  Trash2,
  AlertTriangle,
  Loader2,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Document } from "@/types";
import { formatDate, formatFileSize, getStatusColor } from "@/lib/utils";
import { api } from "@/lib/api";
import { toast } from "sonner";

interface DocumentCardProps {
  document: Document;
  onDeleted?: (id: string) => void;
}

export function DocumentCard({ document: doc, onDeleted }: DocumentCardProps) {
  const router = useRouter();
  const [isDeleting, setIsDeleting] = React.useState(false);
  const statusInfo = getStatusColor(doc.status);

  // File type icon
  const getFileIcon = (fileType: string) => {
    switch (fileType.toLowerCase()) {
      case "pdf":
        return <FileText className="h-5 w-5 text-rose-500" />;
      case "pptx":
        return <Presentation className="h-5 w-5 text-amber-500" />;
      case "txt":
      default:
        return <FileCode className="h-5 w-5 text-blue-500" />;
    }
  };

  const isProcessing = [
    "parsing",
    "chunking",
    "extracting_concepts",
    "generating_summary",
    "generating_questions",
    "evaluating",
    "retrying",
  ].includes(doc.status);

  const handleDelete = async (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (!confirm(`Are you sure you want to delete "${doc.filename}"?`)) {
      return;
    }

    try {
      setIsDeleting(true);
      await api.deleteDocument(doc.id);
      toast.success("Document deleted");
      onDeleted?.(doc.id);
      router.refresh();
    } catch (err: any) {
      toast.error("Failed to delete document", {
        description: err.message,
      });
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <Card className="group relative overflow-hidden transition-all duration-200 hover:border-primary/40 hover:shadow-md">
      <CardContent className="p-5 flex flex-col justify-between h-full">
        <div>
          {/* Header Row: Icon + Type + Status Badge */}
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-muted/60 transition-colors group-hover:bg-primary/10">
                {getFileIcon(doc.file_type)}
              </div>
              <div>
                <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                  {doc.file_type}
                </span>
                <p className="text-xs text-muted-foreground">
                  {formatFileSize(doc.file_size)}
                </p>
              </div>
            </div>

            <div
              className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${statusInfo.badge}`}
            >
              <span className={`h-1.5 w-1.5 rounded-full ${statusInfo.dot}`} />
              <span>{statusInfo.label}</span>
            </div>
          </div>

          {/* Filename */}
          <Link
            href={`/documents/${doc.id}`}
            className="mt-3 block font-semibold text-foreground line-clamp-1 group-hover:text-primary transition-colors text-base"
            title={doc.filename}
          >
            {doc.filename}
          </Link>

          {/* Document metadata (pages, chunks, upload date) */}
          <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            <div className="flex items-center gap-1">
              <Calendar className="h-3.5 w-3.5" />
              <span>{formatDate(doc.created_at)}</span>
            </div>

            {doc.page_count !== null && doc.page_count !== undefined && (
              <div className="flex items-center gap-1">
                <Layers className="h-3.5 w-3.5" />
                <span>
                  {doc.page_count}{" "}
                  {doc.file_type === "pptx" ? "slides" : "pages"}
                </span>
              </div>
            )}
          </div>

          {/* Processing Progress Bar */}
          {isProcessing && (
            <div className="mt-3 space-y-1">
              <div className="flex justify-between text-[11px] font-medium text-muted-foreground">
                <span className="flex items-center gap-1 text-primary">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Processing pipeline...
                </span>
              </div>
              <Progress value={65} className="h-1.5" />
            </div>
          )}

          {/* Error Message if Failed */}
          {doc.status === "failed" && doc.error_message && (
            <div className="mt-2.5 flex items-center gap-1.5 rounded-md bg-destructive/10 p-2 text-xs text-destructive">
              <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
              <span className="line-clamp-1">{doc.error_message}</span>
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="mt-4 flex items-center justify-between border-t pt-3">
          <Link
            href={`/documents/${doc.id}`}
            className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline"
          >
            <span>View Details</span>
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>

          <div className="flex items-center gap-1">
            {doc.has_study_pack && (
              <Link href={`/study-packs/${doc.id}`}>
                <Button
                  size="sm"
                  variant="secondary"
                  className="h-7 text-xs gap-1"
                >
                  <Sparkles className="h-3 w-3 text-primary" />
                  <span>Study Pack</span>
                </Button>
              </Link>
            )}

            <button
              onClick={handleDelete}
              disabled={isDeleting}
              className="p-1.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-md transition-colors"
              title="Delete document"
            >
              {isDeleting ? (
                <Loader2 className="h-4 w-4 animate-spin text-destructive" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
            </button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
