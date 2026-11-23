"use client";

import * as React from "react";
import Link from "next/link";
import {
  BookOpen,
  Sparkles,
  UploadCloud,
  FileText,
  GraduationCap,
  ArrowRight,
  Clock,
  Layers,
  CheckCircle2,
  AlertCircle,
  HelpCircle,
  Award,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { RecentDocuments } from "@/components/dashboard/recent-documents";
import { UploadDialog } from "@/components/upload/upload-dialog";
import { Document, DocumentListResponse } from "@/types";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/utils";

export default function DashboardPage() {
  const [documents, setDocuments] = React.useState<Document[]>([]);
  const [isLoading, setIsLoading] = React.useState(true);
  const [isUploadOpen, setIsUploadOpen] = React.useState(false);

  const loadData = React.useCallback(async () => {
    try {
      setIsLoading(true);
      const res: DocumentListResponse = await api.getDocuments(1, 30);
      setDocuments(res.items || []);
    } catch (err) {
      console.error("Error fetching dashboard documents:", err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    loadData();
  }, [loadData]);

  // Aggregate metrics
  const completedDocs = documents.filter((d) => d.status === "completed");
  const processingDocs = documents.filter((d) =>
    [
      "parsing",
      "chunking",
      "extracting_concepts",
      "generating_summary",
      "generating_questions",
      "evaluating",
      "retrying",
    ].includes(d.status),
  );
  const studyPacksReady = documents.filter((d) => d.has_study_pack);

  return (
    <div className="space-y-8">
      {/* Welcome Hero Banner */}
      <section className="relative overflow-hidden rounded-2xl border bg-gradient-to-br from-card via-card to-primary/5 p-6 sm:p-8 shadow-sm">
        <div className="relative z-10 flex flex-col gap-6 md:flex-row md:items-center md:justify-between">
          <div className="max-w-2xl space-y-2">
            <div className="inline-flex items-center gap-1.5 rounded-full border border-primary/30 bg-primary/10 px-3 py-1 text-xs font-semibold text-primary">
              <Sparkles className="h-3.5 w-3.5" />
              <span>AI Study Pack Generator</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground">
              Turn Lecture Notes & Slides into Masterful Study Packs
            </h1>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Upload your PDF textbooks, PowerPoint slide decks, or lecture
              transcripts. LectureForge extracts verified concepts, builds
              active recall quizzes, and validates every answer with citations.
            </p>

            <div className="pt-2 flex flex-wrap items-center gap-3">
              <Button
                onClick={() => setIsUploadOpen(true)}
                size="lg"
                className="gap-2 shadow-md shadow-primary/20"
              >
                <UploadCloud className="h-4 w-4" />
                <span>Upload Lecture Notes</span>
              </Button>
              <a
                href="#study-packs"
                className="inline-flex items-center gap-1.5 text-xs font-semibold text-muted-foreground hover:text-foreground p-2 transition-colors"
              >
                <span>Browse Ready Packs</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </a>
            </div>
          </div>

          {/* Quick Metrics Panel */}
          <div className="grid grid-cols-2 gap-3 sm:gap-4 md:w-80">
            <div className="rounded-xl border bg-card/60 p-4 shadow-2xs backdrop-blur-sm">
              <div className="flex items-center gap-2 text-muted-foreground text-xs font-medium">
                <FileText className="h-4 w-4 text-primary" />
                <span>Documents</span>
              </div>
              <p className="mt-2 text-2xl font-bold text-foreground">
                {isLoading ? (
                  <Skeleton className="h-7 w-12" />
                ) : (
                  documents.length
                )}
              </p>
            </div>

            <div className="rounded-xl border bg-card/60 p-4 shadow-2xs backdrop-blur-sm">
              <div className="flex items-center gap-2 text-muted-foreground text-xs font-medium">
                <GraduationCap className="h-4 w-4 text-emerald-500" />
                <span>Study Packs</span>
              </div>
              <p className="mt-2 text-2xl font-bold text-foreground">
                {isLoading ? (
                  <Skeleton className="h-7 w-12" />
                ) : (
                  studyPacksReady.length
                )}
              </p>
            </div>

            <div className="rounded-xl border bg-card/60 p-4 shadow-2xs backdrop-blur-sm">
              <div className="flex items-center gap-2 text-muted-foreground text-xs font-medium">
                <Clock className="h-4 w-4 text-sky-500" />
                <span>In Progress</span>
              </div>
              <p className="mt-2 text-2xl font-bold text-foreground">
                {isLoading ? (
                  <Skeleton className="h-7 w-12" />
                ) : (
                  processingDocs.length
                )}
              </p>
            </div>

            <div className="rounded-xl border bg-card/60 p-4 shadow-2xs backdrop-blur-sm">
              <div className="flex items-center gap-2 text-muted-foreground text-xs font-medium">
                <CheckCircle2 className="h-4 w-4 text-indigo-500" />
                <span>Completed</span>
              </div>
              <p className="mt-2 text-2xl font-bold text-foreground">
                {isLoading ? (
                  <Skeleton className="h-7 w-12" />
                ) : (
                  completedDocs.length
                )}
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Generated Study Packs Section */}
      <section id="study-packs" className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold tracking-tight text-foreground flex items-center gap-2">
              <GraduationCap className="h-5 w-5 text-primary" />
              Ready Study Packs ({studyPacksReady.length})
            </h2>
            <p className="text-xs text-muted-foreground">
              Comprehensive packs ready for study, interactive quiz drills, and
              flashcard export.
            </p>
          </div>
        </div>

        {isLoading ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="rounded-xl border p-5 space-y-3">
                <Skeleton className="h-5 w-1/3" />
                <Skeleton className="h-6 w-3/4" />
                <Skeleton className="h-4 w-1/2" />
              </div>
            ))}
          </div>
        ) : studyPacksReady.length > 0 ? (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {studyPacksReady.map((doc) => (
              <Card
                key={doc.id}
                className="group relative overflow-hidden transition-all duration-200 hover:border-primary/50 hover:shadow-md"
              >
                <CardContent className="p-5 flex flex-col justify-between h-full space-y-4">
                  <div>
                    <div className="flex items-center justify-between">
                      <Badge
                        variant="outline"
                        className="border-emerald-300 text-emerald-700 dark:text-emerald-400 dark:border-emerald-800 text-[11px] gap-1"
                      >
                        <CheckCircle2 className="h-3 w-3" />
                        Pack Ready
                      </Badge>
                      <span className="text-[11px] text-muted-foreground">
                        {formatDate(doc.created_at)}
                      </span>
                    </div>

                    <Link
                      href={`/study-packs/${doc.id}`}
                      className="mt-3 block text-base font-bold text-foreground group-hover:text-primary transition-colors line-clamp-1"
                    >
                      {doc.filename.replace(/\.[^/.]+$/, "")}
                    </Link>

                    <p className="text-xs text-muted-foreground line-clamp-2 mt-1">
                      Source: {doc.filename} ({doc.file_type.toUpperCase()})
                    </p>
                  </div>

                  <div className="flex items-center justify-between border-t pt-3">
                    <span className="text-xs text-muted-foreground">
                      {doc.page_count
                        ? `${doc.page_count} pages analyzed`
                        : "Full lecture notes"}
                    </span>
                    <Link href={`/study-packs/${doc.id}`}>
                      <Button size="sm" className="gap-1.5 h-8 text-xs">
                        <span>Study Now</span>
                        <ArrowRight className="h-3.5 w-3.5" />
                      </Button>
                    </Link>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-dashed p-8 text-center text-xs text-muted-foreground">
            No study packs have been generated yet. Upload a document below and
            click &quot;Generate Study Pack&quot;.
          </div>
        )}
      </section>

      {/* Recent Documents Section */}
      <RecentDocuments
        initialDocuments={documents}
        onUploadClick={() => setIsUploadOpen(true)}
      />

      {/* Upload Dialog Modal */}
      <UploadDialog
        open={isUploadOpen}
        onOpenChange={setIsUploadOpen}
        onUploadSuccess={() => {
          loadData();
        }}
      />
    </div>
  );
}
