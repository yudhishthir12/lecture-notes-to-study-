"use client";

import * as React from "react";
import {
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  Award,
  Sparkles,
  Info,
} from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { EvaluationResult } from "@/types";

interface EvaluationTabProps {
  evaluation?: EvaluationResult | null;
}

export function EvaluationTab({ evaluation }: EvaluationTabProps) {
  if (!evaluation) {
    return (
      <div className="rounded-xl border border-dashed p-10 text-center text-xs text-muted-foreground">
        No evaluation audit data available for this study pack.
      </div>
    );
  }

  const criteria = [
    {
      title: "Faithfulness & Grounding",
      score: evaluation.faithfulness,
      description:
        "Verification that content adheres strictly to lecture material with zero hallucination.",
    },
    {
      title: "Curricular Coverage",
      score: evaluation.coverage,
      description:
        "Ensures all primary topics, theorems, and slide sections were comprehensively extracted.",
    },
    {
      title: "Answer Key Accuracy",
      score: evaluation.answer_accuracy,
      description:
        "Step-by-step mathematical and conceptual validation of all generated test answers.",
    },
    {
      title: "Clarity & Pedagogical Structure",
      score: evaluation.clarity,
      description:
        "Assessment of readability, clear formatting, and structured active recall hierarchy.",
    },
  ];

  const overallPercentage = (evaluation.overall_score / 5) * 100;

  return (
    <div className="space-y-6">
      {/* Header Summary Banner */}
      <Card className="border-primary/20 bg-gradient-to-r from-card via-card to-primary/5">
        <CardContent className="p-6">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <Badge
                  variant="outline"
                  className="border-primary/40 text-primary"
                >
                  Quality Audit Report
                </Badge>
                {evaluation.passed ? (
                  <Badge variant="success" className="gap-1">
                    <CheckCircle2 className="h-3 w-3" />
                    Passed Benchmark
                  </Badge>
                ) : (
                  <Badge variant="warning" className="gap-1">
                    <AlertTriangle className="h-3 w-3" />
                    Correction Advised
                  </Badge>
                )}
              </div>
              <h3 className="text-xl font-bold text-foreground">
                Automated Self-Reflection & Rubric Validation
              </h3>
              <p className="text-xs text-muted-foreground">
                Every study pack undergoes an automated multi-criteria audit
                before delivery.
              </p>
            </div>

            {/* Score Ring Display */}
            <div className="flex items-center gap-3 rounded-xl border bg-background/80 p-4 shadow-sm">
              <Award className="h-8 w-8 text-primary" />
              <div>
                <div className="flex items-baseline gap-1">
                  <span className="text-3xl font-extrabold text-foreground">
                    {evaluation.overall_score.toFixed(1)}
                  </span>
                  <span className="text-xs text-muted-foreground">/ 5.0</span>
                </div>
                <span className="text-[11px] font-medium text-muted-foreground">
                  Overall Quality Score
                </span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Criteria Progress Bars */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {criteria.map((item) => {
          const percent = (item.score / 5) * 100;
          return (
            <Card key={item.title}>
              <CardContent className="p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-semibold text-sm text-foreground">
                    {item.title}
                  </h4>
                  <span className="text-xs font-bold text-primary">
                    {item.score} / 5
                  </span>
                </div>

                <Progress
                  value={percent}
                  indicatorClassName={
                    item.score >= 4
                      ? "bg-emerald-500"
                      : item.score >= 3
                        ? "bg-amber-500"
                        : "bg-rose-500"
                  }
                />

                <p className="text-xs text-muted-foreground leading-relaxed">
                  {item.description}
                </p>
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Issues or Anomalies Identified */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-primary" />
            Detected Shortcomings & Audit Log
          </CardTitle>
          <CardDescription>
            Defects flagged by the self-reflection evaluator.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {evaluation.issues && evaluation.issues.length > 0 ? (
            <ul className="space-y-2 text-xs">
              {evaluation.issues.map((issue, idx) => (
                <li
                  key={idx}
                  className="flex items-start gap-2 rounded-md bg-amber-500/10 p-2.5 text-amber-900 dark:text-amber-300 border border-amber-500/20"
                >
                  <AlertTriangle className="h-4 w-4 shrink-0 text-amber-500 mt-0.5" />
                  <span>{issue}</span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="flex items-center gap-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 p-3 text-xs text-emerald-800 dark:text-emerald-300">
              <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
              <span>
                Zero hallucinations, missing citations, or inconsistencies
                detected in this study pack.
              </span>
            </div>
          )}

          {evaluation.failed_sections &&
            evaluation.failed_sections.length > 0 && (
              <div className="mt-4 pt-3 border-t text-xs text-muted-foreground">
                <span className="font-medium text-foreground">
                  Automated retries executed for sections:{" "}
                </span>
                <span className="font-mono text-primary">
                  {evaluation.failed_sections.join(", ")}
                </span>
              </div>
            )}
        </CardContent>
      </Card>
    </div>
  );
}
