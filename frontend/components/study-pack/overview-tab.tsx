"use client";

import * as React from "react";
import Link from "next/link";
import {
  BookOpen,
  CheckCircle2,
  AlertCircle,
  Cpu,
  Clock,
  Layers,
  HelpCircle,
  Binary,
  BookmarkCheck,
  FileText,
  Sparkles,
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
import { StudyPackContent, EvaluationResult } from "@/types";
import { formatDate } from "@/lib/utils";

interface OverviewTabProps {
  content: StudyPackContent;
  evaluation?: EvaluationResult | null;
  onSelectTab?: (tabKey: string) => void;
}

export function OverviewTab({
  content,
  evaluation,
  onSelectTab,
}: OverviewTabProps) {
  const meta = content.metadata;
  const pipeline = content.pipeline_metadata;
  const evalResult = evaluation || content.evaluation;

  const statCards = [
    {
      title: "Core Concepts",
      value: content.concepts?.length || 0,
      icon: BookOpen,
      tab: "concepts",
      color:
        "text-indigo-600 bg-indigo-50 dark:bg-indigo-950/50 dark:text-indigo-400",
    },
    {
      title: "Key Terms",
      value: content.key_terms?.length || 0,
      icon: BookmarkCheck,
      tab: "glossary",
      color: "text-blue-600 bg-blue-50 dark:bg-blue-950/50 dark:text-blue-400",
    },
    {
      title: "Formulas & Rules",
      value: content.formulas?.length || 0,
      icon: Binary,
      tab: "formulas",
      color:
        "text-amber-600 bg-amber-50 dark:bg-amber-950/50 dark:text-amber-400",
    },
    {
      title: "Practice Questions",
      value: content.practice_questions?.length || 0,
      icon: HelpCircle,
      tab: "questions",
      color:
        "text-emerald-600 bg-emerald-50 dark:bg-emerald-950/50 dark:text-emerald-400",
    },
  ];

  return (
    <div className="space-y-6">
      {/* Subject Header Card */}
      <Card className="border-primary/20 bg-gradient-to-r from-card via-card to-primary/5">
        <CardContent className="p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Badge
                  variant="outline"
                  className="border-primary/40 text-primary"
                >
                  Study Pack Topic
                </Badge>
                {evalResult?.passed ? (
                  <Badge variant="success" className="gap-1">
                    <CheckCircle2 className="h-3 w-3" />
                    Passed Quality Audit
                  </Badge>
                ) : (
                  <Badge variant="warning" className="gap-1">
                    <AlertCircle className="h-3 w-3" />
                    Review Recommended
                  </Badge>
                )}
              </div>
              <h2 className="text-2xl font-bold tracking-tight text-foreground">
                {meta.topic || "Untitled Study Pack"}
              </h2>
              <p className="text-xs text-muted-foreground">
                Generated {formatDate(meta.generated_at)}
                {meta.source_pages?.length > 0 &&
                  ` • Covering source pages: ${meta.source_pages.join(", ")}`}
              </p>
            </div>

            {/* Quick Action Button */}
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => onSelectTab?.("questions")}
                className="gap-1.5"
              >
                <HelpCircle className="h-4 w-4 text-emerald-500" />
                <span>Start Practice Quiz</span>
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Metric Counters Grid */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {statCards.map((stat) => {
          const Icon = stat.icon;
          return (
            <Card
              key={stat.title}
              className="cursor-pointer transition-all duration-200 hover:border-primary/50 hover:shadow-sm"
              onClick={() => onSelectTab?.(stat.tab)}
            >
              <CardContent className="p-5 flex items-center justify-between">
                <div>
                  <p className="text-xs font-medium text-muted-foreground">
                    {stat.title}
                  </p>
                  <p className="text-2xl font-bold text-foreground mt-0.5">
                    {stat.value}
                  </p>
                </div>
                <div className={`p-2.5 rounded-lg ${stat.color}`}>
                  <Icon className="h-5 w-5" />
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Summary Highlight Preview */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="text-base flex items-center gap-2">
              <FileText className="h-4 w-4 text-primary" />
              Executive Synthesis
            </CardTitle>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => onSelectTab?.("summary")}
              className="text-xs text-primary h-7"
            >
              View Full Summary →
            </Button>
          </div>
          <CardDescription>
            High-level distillation from your lecture materials.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-relaxed text-foreground/90 whitespace-pre-line bg-muted/30 p-4 rounded-lg border">
            {content.summary?.overview || "No synthesis available."}
          </p>
        </CardContent>
      </Card>

      {/* Pipeline Telemetry & Verification Metadata */}
      {pipeline && (
        <Card className="bg-muted/20">
          <CardHeader className="py-4">
            <CardTitle className="text-sm font-semibold flex items-center gap-2">
              <Cpu className="h-4 w-4 text-muted-foreground" />
              Generation Pipeline & Telemetry
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 text-xs text-muted-foreground">
              <div>
                <span className="block font-medium text-foreground">
                  AI Model
                </span>
                <span>{pipeline.model_name || "Gemini 2.5 Flash"}</span>
              </div>
              <div>
                <span className="block font-medium text-foreground">
                  Prompt Version
                </span>
                <span>{pipeline.prompt_version || "v1.0"}</span>
              </div>
              <div>
                <span className="block font-medium text-foreground">
                  Processing Time
                </span>
                <span>
                  {pipeline.processing_time_seconds
                    ? `${pipeline.processing_time_seconds.toFixed(1)}s`
                    : "N/A"}
                </span>
              </div>
              <div>
                <span className="block font-medium text-foreground">
                  Self-Correction Retries
                </span>
                <span>{pipeline.retry_count || 0} retries</span>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
