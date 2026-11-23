"use client";

import * as React from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import {
  BookOpen,
  FileText,
  BookmarkCheck,
  Binary,
  HelpCircle,
  ShieldCheck,
  Download,
  FileDown,
  Layers,
  ArrowLeft,
  Sparkles,
  RefreshCw,
  Share2,
} from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { OverviewTab } from "@/components/study-pack/overview-tab";
import { SummaryTab } from "@/components/study-pack/summary-tab";
import { ConceptsTab } from "@/components/study-pack/concepts-tab";
import { GlossaryTab } from "@/components/study-pack/glossary-tab";
import { FormulasTab } from "@/components/study-pack/formulas-tab";
import { QuestionsTab } from "@/components/study-pack/questions-tab";
import { EvaluationTab } from "@/components/study-pack/evaluation-tab";
import { StudyPack, StudyPackContent, EvaluationResult } from "@/types";
import { api } from "@/lib/api";
import { downloadBlob, formatDate } from "@/lib/utils";
import { toast } from "sonner";

export default function StudyPackViewerPage() {
  const params = useParams();
  const router = useRouter();
  const studyPackId = params?.id as string;

  const [studyPack, setStudyPack] = React.useState<StudyPack | null>(null);
  const [evaluation, setEvaluation] = React.useState<EvaluationResult | null>(
    null,
  );
  const [activeTab, setActiveTab] = React.useState("overview");
  const [isLoading, setIsLoading] = React.useState(true);
  const [isExporting, setIsExporting] = React.useState<string | null>(null);
  const [isRegenerating, setIsRegenerating] = React.useState(false);
  const [errorMsg, setErrorMsg] = React.useState<string | null>(null);

  // Load study pack data
  const loadData = React.useCallback(async () => {
    if (!studyPackId) return;
    try {
      setIsLoading(true);
      setErrorMsg(null);
      const pack = await api.getStudyPack(studyPackId);
      setStudyPack(pack);

      // Attempt to load separate evaluation if not in pack
      if (pack.evaluation) {
        setEvaluation(pack.evaluation);
      } else {
        try {
          const evalRes = await api.getEvaluation(studyPackId);
          setEvaluation(evalRes);
        } catch {
          // Optional evaluation
        }
      }
    } catch (err: any) {
      console.error("Failed to load study pack:", err);
      setErrorMsg(err.detail || err.message || "Could not load study pack.");
    } finally {
      setIsLoading(false);
    }
  }, [studyPackId]);

  React.useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle file exports
  const handleExport = async (format: "markdown" | "pdf" | "anki") => {
    if (!studyPackId) return;
    try {
      setIsExporting(format);
      let blob: Blob;
      let filename: string;

      const topicSlug = (studyPack?.content.metadata.topic || "study_pack")
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "_");

      if (format === "markdown") {
        blob = await api.exportMarkdown(studyPackId);
        filename = `${topicSlug}_notes.md`;
      } else if (format === "pdf") {
        blob = await api.exportPdf(studyPackId);
        filename = `${topicSlug}_booklet.pdf`;
      } else {
        blob = await api.exportAnki(studyPackId);
        filename = `${topicSlug}_anki_deck.csv`;
      }

      downloadBlob(blob, filename);
      toast.success(`Exported ${format.toUpperCase()} successfully!`);
    } catch (err: any) {
      console.error(`Export ${format} failed:`, err);
      toast.error(`Export failed`, {
        description: err.message || `Could not export ${format.toUpperCase()}`,
      });
    } finally {
      setIsExporting(null);
    }
  };

  // Section regeneration trigger
  const handleRegenerate = async (section: string) => {
    if (!studyPackId) return;
    try {
      setIsRegenerating(true);
      const res = await api.regenerateSection(studyPackId, [section]);
      toast.info("Regeneration scheduled", {
        description: res.message || `Scheduled regeneration for ${section}.`,
      });
      loadData();
    } catch (err: any) {
      toast.error("Regeneration failed", {
        description: err.detail || err.message,
      });
    } finally {
      setIsRegenerating(false);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <Skeleton className="h-8 w-64" />
          <div className="flex gap-2">
            <Skeleton className="h-9 w-24" />
            <Skeleton className="h-9 w-24" />
          </div>
        </div>
        <Skeleton className="h-10 w-full rounded-lg" />
        <Skeleton className="h-96 w-full rounded-xl" />
      </div>
    );
  }

  if (errorMsg || !studyPack) {
    return (
      <div className="rounded-xl border border-destructive/20 bg-destructive/10 p-10 text-center space-y-4">
        <h3 className="text-lg font-bold text-destructive">
          Failed to Load Study Pack
        </h3>
        <p className="text-sm text-muted-foreground">
          {errorMsg || "Study pack not found."}
        </p>
        <div className="flex justify-center gap-3">
          <Button variant="outline" onClick={() => router.push("/")}>
            Back to Dashboard
          </Button>
          <Button onClick={loadData}>Retry</Button>
        </div>
      </div>
    );
  }

  const { content } = studyPack;
  const evalResult = evaluation || content.evaluation;

  return (
    <div className="space-y-6">
      {/* Top Navigation & Action Toolbar */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b pb-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <Link
              href="/"
              className="text-xs font-semibold text-muted-foreground hover:text-foreground inline-flex items-center gap-1 transition-colors"
            >
              <ArrowLeft className="h-3.5 w-3.5" />
              <span>Dashboard</span>
            </Link>
            <span className="text-muted-foreground">•</span>
            <Link
              href={`/documents/${studyPack.document_id}`}
              className="text-xs font-semibold text-primary hover:underline"
            >
              Document Details
            </Link>
          </div>

          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold tracking-tight text-foreground truncate max-w-xl">
              {content.metadata.topic || "Lecture Study Pack"}
            </h1>
            {evalResult && (
              <Badge
                variant="outline"
                className="text-xs font-bold border-primary/40 text-primary"
              >
                Score: {evalResult.overall_score.toFixed(1)}/5
              </Badge>
            )}
          </div>
        </div>

        {/* Export Buttons */}
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleExport("markdown")}
            disabled={isExporting !== null}
            className="gap-1.5 h-8 text-xs"
            title="Download clean Markdown"
          >
            <FileDown className="h-3.5 w-3.5" />
            <span>Markdown</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => handleExport("pdf")}
            disabled={isExporting !== null}
            className="gap-1.5 h-8 text-xs"
            title="Download formatted PDF booklet"
          >
            <Download className="h-3.5 w-3.5" />
            <span>PDF Booklet</span>
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => handleExport("anki")}
            disabled={isExporting !== null}
            className="gap-1.5 h-8 text-xs"
            title="Export Anki flashcard CSV"
          >
            <Layers className="h-3.5 w-3.5" />
            <span>Anki CSV</span>
          </Button>
        </div>
      </div>

      {/* Primary Tab Navigation */}
      <Tabs
        value={activeTab}
        onValueChange={setActiveTab}
        className="space-y-6"
      >
        <TabsList className="grid grid-cols-3 sm:grid-cols-7 h-auto p-1 gap-1">
          <TabsTrigger value="overview" className="gap-1.5 py-2 text-xs">
            <BookOpen className="h-3.5 w-3.5" />
            <span>Overview</span>
          </TabsTrigger>
          <TabsTrigger value="summary" className="gap-1.5 py-2 text-xs">
            <FileText className="h-3.5 w-3.5" />
            <span>Summary</span>
          </TabsTrigger>
          <TabsTrigger value="concepts" className="gap-1.5 py-2 text-xs">
            <Sparkles className="h-3.5 w-3.5" />
            <span>Concepts</span>
          </TabsTrigger>
          <TabsTrigger value="glossary" className="gap-1.5 py-2 text-xs">
            <BookmarkCheck className="h-3.5 w-3.5" />
            <span>Glossary</span>
          </TabsTrigger>
          <TabsTrigger value="formulas" className="gap-1.5 py-2 text-xs">
            <Binary className="h-3.5 w-3.5" />
            <span>Formulas</span>
          </TabsTrigger>
          <TabsTrigger value="questions" className="gap-1.5 py-2 text-xs">
            <HelpCircle className="h-3.5 w-3.5" />
            <span>Questions</span>
          </TabsTrigger>
          <TabsTrigger value="evaluation" className="gap-1.5 py-2 text-xs">
            <ShieldCheck className="h-3.5 w-3.5" />
            <span>Audit</span>
          </TabsTrigger>
        </TabsList>

        {/* Tab 1: Overview */}
        <TabsContent value="overview">
          <OverviewTab
            content={content}
            evaluation={evalResult}
            onSelectTab={(tab) => setActiveTab(tab)}
          />
        </TabsContent>

        {/* Tab 2: Summary */}
        <TabsContent value="summary">
          <SummaryTab
            summary={content.summary}
            onRegenerate={() => handleRegenerate("summary")}
            isRegenerating={isRegenerating}
          />
        </TabsContent>

        {/* Tab 3: Key Concepts */}
        <TabsContent value="concepts">
          <ConceptsTab
            concepts={content.concepts}
            onRegenerate={() => handleRegenerate("concepts")}
            isRegenerating={isRegenerating}
          />
        </TabsContent>

        {/* Tab 4: Glossary */}
        <TabsContent value="glossary">
          <GlossaryTab terms={content.key_terms} />
        </TabsContent>

        {/* Tab 5: Formulas */}
        <TabsContent value="formulas">
          <FormulasTab formulas={content.formulas} />
        </TabsContent>

        {/* Tab 6: Practice Questions */}
        <TabsContent value="questions">
          <QuestionsTab
            questions={content.practice_questions}
            onRegenerateQuestions={() => handleRegenerate("questions")}
            isRegenerating={isRegenerating}
          />
        </TabsContent>

        {/* Tab 7: Quality Evaluation Audit */}
        <TabsContent value="evaluation">
          <EvaluationTab evaluation={evalResult} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
