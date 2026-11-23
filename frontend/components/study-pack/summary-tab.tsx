"use client";

import * as React from "react";
import { FileText, RefreshCw, Sparkles, BookOpen } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Summary } from "@/types";

interface SummaryTabProps {
  summary: Summary;
  onRegenerate?: () => void;
  isRegenerating?: boolean;
}

export function SummaryTab({
  summary,
  onRegenerate,
  isRegenerating = false,
}: SummaryTabProps) {
  return (
    <div className="space-y-6">
      {/* Header bar */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
            <FileText className="h-5 w-5 text-primary" />
            Lecture Summary & Digest
          </h3>
          <p className="text-xs text-muted-foreground">
            Structured synthesis extracted directly from the uploaded material.
          </p>
        </div>

        {onRegenerate && (
          <Button
            variant="outline"
            size="sm"
            onClick={onRegenerate}
            disabled={isRegenerating}
            className="gap-1.5 h-8 text-xs"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${isRegenerating ? "animate-spin text-primary" : ""}`}
            />
            <span>Regenerate Summary</span>
          </Button>
        )}
      </div>

      {/* High-level Overview */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2 text-primary">
            <Sparkles className="h-4 w-4" />
            Executive Overview
          </CardTitle>
          <CardDescription>
            Quick 2-minute synthesis of core lecture takeaways.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-lg bg-primary/5 border border-primary/15 p-4 text-sm leading-relaxed text-foreground">
            {summary.overview}
          </div>
        </CardContent>
      </Card>

      {/* Detailed Breakdown */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-indigo-500" />
            Detailed Structural Breakdown
          </CardTitle>
          <CardDescription>
            Exhaustive topic-by-topic breakdown of principles, methodology, and
            conclusions.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <article className="prose prose-sm dark:prose-invert max-w-none leading-relaxed text-foreground/90 whitespace-pre-line space-y-4 font-normal">
            {summary.detailed_summary}
          </article>
        </CardContent>
      </Card>
    </div>
  );
}
