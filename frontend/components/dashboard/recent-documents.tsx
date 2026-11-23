"use client";

import * as React from "react";
import { FileText, Search, RefreshCw, FolderOpen, Filter } from "lucide-react";
import { DocumentCard } from "@/components/dashboard/document-card";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Document } from "@/types";
import { api } from "@/lib/api";

interface RecentDocumentsProps {
  initialDocuments?: Document[];
  onUploadClick?: () => void;
}

export function RecentDocuments({
  initialDocuments = [],
  onUploadClick,
}: RecentDocumentsProps) {
  const [documents, setDocuments] =
    React.useState<Document[]>(initialDocuments);
  const [isLoading, setIsLoading] = React.useState(false);
  const [searchQuery, setSearchQuery] = React.useState("");
  const [statusFilter, setStatusFilter] = React.useState<string>("all");

  const fetchDocs = React.useCallback(async () => {
    try {
      setIsLoading(true);
      const res = await api.getDocuments(1, 50);
      setDocuments(res.items || []);
    } catch (err) {
      console.error("Failed to load documents:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    if (initialDocuments.length === 0) {
      fetchDocs();
    }
  }, [fetchDocs, initialDocuments.length]);

  const handleDocumentDeleted = (deletedId: string) => {
    setDocuments((prev) => prev.filter((d) => d.id !== deletedId));
  };

  // Filtered documents
  const filteredDocuments = React.useMemo(() => {
    return documents.filter((doc) => {
      const matchesSearch = doc.filename
        .toLowerCase()
        .includes(searchQuery.toLowerCase());
      if (!matchesSearch) return false;

      if (statusFilter === "all") return true;
      if (statusFilter === "processing") {
        return [
          "parsing",
          "chunking",
          "extracting_concepts",
          "generating_summary",
          "generating_questions",
          "evaluating",
          "retrying",
        ].includes(doc.status);
      }
      return doc.status === statusFilter;
    });
  }, [documents, searchQuery, statusFilter]);

  return (
    <section id="documents" className="space-y-4">
      {/* Section Header with Search and Filter Bar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <FileText className="h-5 w-5 text-primary" />
            Recent Lecture Documents
          </h2>
          <p className="text-xs text-muted-foreground">
            Manage your uploaded files and check real-time study pack generation
            status.
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* Refresh button */}
          <Button
            variant="outline"
            size="sm"
            onClick={fetchDocs}
            disabled={isLoading}
            className="h-8 gap-1 text-xs"
            title="Refresh documents list"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${isLoading ? "animate-spin text-primary" : ""}`}
            />
            <span className="hidden sm:inline">Refresh</span>
          </Button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center justify-between">
        {/* Search input */}
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search documents by name..."
            className="h-9 w-full rounded-lg border bg-background pl-9 pr-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
          />
        </div>

        {/* Status filter pills */}
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          {[
            { id: "all", label: "All" },
            { id: "completed", label: "Completed" },
            { id: "processing", label: "In Progress" },
            { id: "uploaded", label: "Uploaded" },
            { id: "failed", label: "Failed" },
          ].map((pill) => (
            <button
              key={pill.id}
              onClick={() => setStatusFilter(pill.id)}
              className={`rounded-full px-3 py-1 font-medium transition-colors ${
                statusFilter === pill.id
                  ? "bg-primary text-primary-foreground shadow-xs"
                  : "bg-muted/70 text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              {pill.label}
            </button>
          ))}
        </div>
      </div>

      {/* Documents Grid / Skeletons / Empty State */}
      {isLoading && documents.length === 0 ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="rounded-xl border p-5 space-y-3">
              <div className="flex justify-between items-center">
                <Skeleton className="h-10 w-10 rounded-lg" />
                <Skeleton className="h-5 w-20 rounded-full" />
              </div>
              <Skeleton className="h-5 w-3/4" />
              <Skeleton className="h-4 w-1/2" />
              <div className="pt-2 border-t flex justify-between">
                <Skeleton className="h-4 w-20" />
                <Skeleton className="h-6 w-16" />
              </div>
            </div>
          ))}
        </div>
      ) : filteredDocuments.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {filteredDocuments.map((doc) => (
            <DocumentCard
              key={doc.id}
              document={doc}
              onDeleted={handleDocumentDeleted}
            />
          ))}
        </div>
      ) : (
        /* Empty State */
        <div className="flex flex-col items-center justify-center rounded-xl border border-dashed p-10 text-center bg-card/40">
          <div className="flex h-12 w-12 items-center justify-center rounded-full bg-primary/10 text-primary mb-3">
            <FolderOpen className="h-6 w-6" />
          </div>
          <h3 className="text-base font-semibold text-foreground">
            {searchQuery || statusFilter !== "all"
              ? "No matching documents found"
              : "No documents uploaded yet"}
          </h3>
          <p className="mt-1 text-xs text-muted-foreground max-w-sm">
            {searchQuery || statusFilter !== "all"
              ? "Try adjusting your search query or status filter to locate the document."
              : "Upload your first lecture notes, slide presentation, or textbook chapter to generate an AI study pack."}
          </p>
          {onUploadClick && (
            <Button size="sm" onClick={onUploadClick} className="mt-4 gap-2">
              <FileText className="h-4 w-4" />
              <span>Upload Document</span>
            </Button>
          )}
        </div>
      )}
    </section>
  );
}
