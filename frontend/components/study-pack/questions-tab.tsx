"use client";

import * as React from "react";
import {
  HelpCircle,
  CheckCircle2,
  Eye,
  EyeOff,
  RefreshCw,
  Bookmark,
  Check,
  X,
  Sparkles,
} from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PracticeQuestion, QuestionType, DifficultyLevel } from "@/types";
import { getDifficultyColor } from "@/lib/utils";
import { toast } from "sonner";

interface QuestionsTabProps {
  questions: PracticeQuestion[];
  onRegenerateQuestions?: () => void;
  isRegenerating?: boolean;
}

export function QuestionsTab({
  questions = [],
  onRegenerateQuestions,
  isRegenerating = false,
}: QuestionsTabProps) {
  const [selectedType, setSelectedType] = React.useState<string>("all");
  const [selectedDifficulty, setSelectedDifficulty] =
    React.useState<string>("all");
  const [revealedAnswers, setRevealedAnswers] = React.useState<
    Record<string, boolean>
  >({});
  const [userSelectedOptions, setUserSelectedOptions] = React.useState<
    Record<string, string>
  >({});

  // Filter questions
  const filteredQuestions = React.useMemo(() => {
    return questions.filter((q) => {
      const matchType =
        selectedType === "all" || q.question_type === selectedType;
      const matchDiff =
        selectedDifficulty === "all" || q.difficulty === selectedDifficulty;
      return matchType && matchDiff;
    });
  }, [questions, selectedType, selectedDifficulty]);

  const toggleReveal = (id: string) => {
    setRevealedAnswers((prev) => ({
      ...prev,
      [id]: !prev[id],
    }));
  };

  const handleSelectOption = (questionId: string, optionLabel: string) => {
    setUserSelectedOptions((prev) => ({
      ...prev,
      [questionId]: optionLabel,
    }));
  };

  const handleRegenerateSingle = (qId: string) => {
    toast.info("Regenerating question...", {
      description: "Request sent to AI reflection pipeline.",
    });
  };

  return (
    <div className="space-y-6">
      {/* Header and Filter Controls */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
            <HelpCircle className="h-5 w-5 text-primary" />
            Practice Questions & Exam Rubrics ({questions.length})
          </h3>
          <p className="text-xs text-muted-foreground">
            Test comprehension with active recall, multiple choice, and
            conceptual drills.
          </p>
        </div>

        {onRegenerateQuestions && (
          <Button
            variant="outline"
            size="sm"
            onClick={onRegenerateQuestions}
            disabled={isRegenerating}
            className="gap-1.5 h-8 text-xs"
          >
            <RefreshCw
              className={`h-3.5 w-3.5 ${isRegenerating ? "animate-spin text-primary" : ""}`}
            />
            <span>Regenerate Questions</span>
          </Button>
        )}
      </div>

      {/* Filter Row */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b pb-4">
        {/* Type filter */}
        <div className="flex items-center gap-1 text-xs">
          <span className="text-muted-foreground mr-1">Type:</span>
          {[
            { id: "all", label: "All" },
            { id: "mcq", label: "Multiple Choice" },
            { id: "short_answer", label: "Short Answer" },
            { id: "conceptual", label: "Conceptual" },
          ].map((type) => (
            <button
              key={type.id}
              onClick={() => setSelectedType(type.id)}
              className={`rounded-full px-2.5 py-1 font-medium transition-colors ${
                selectedType === type.id
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:text-foreground"
              }`}
            >
              {type.label}
            </button>
          ))}
        </div>

        {/* Difficulty filter */}
        <div className="flex items-center gap-1 text-xs">
          <span className="text-muted-foreground mr-1">Difficulty:</span>
          {[
            { id: "all", label: "All" },
            { id: "easy", label: "Easy" },
            { id: "medium", label: "Medium" },
            { id: "hard", label: "Hard" },
          ].map((diff) => (
            <button
              key={diff.id}
              onClick={() => setSelectedDifficulty(diff.id)}
              className={`rounded-full px-2.5 py-1 font-medium transition-colors ${
                selectedDifficulty === diff.id
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:text-foreground"
              }`}
            >
              {diff.label}
            </button>
          ))}
        </div>
      </div>

      {/* Questions List */}
      {filteredQuestions.length > 0 ? (
        <div className="space-y-5">
          {filteredQuestions.map((q, index) => {
            const isRevealed = !!revealedAnswers[q.id];
            const selectedOption = userSelectedOptions[q.id];
            const diffStyle = getDifficultyColor(q.difficulty);

            return (
              <Card key={q.id || index} className="overflow-hidden">
                <CardHeader className="p-5 pb-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                        {index + 1}
                      </span>
                      <Badge
                        variant="outline"
                        className="uppercase text-[10px]"
                      >
                        {q.question_type.replace("_", " ")}
                      </Badge>
                      <Badge className={diffStyle.badge}>
                        {diffStyle.label}
                      </Badge>
                    </div>

                    <div className="flex items-center gap-1.5">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleReveal(q.id)}
                        className="h-7 text-xs gap-1"
                      >
                        {isRevealed ? (
                          <>
                            <EyeOff className="h-3.5 w-3.5" />
                            <span>Hide Answer</span>
                          </>
                        ) : (
                          <>
                            <Eye className="h-3.5 w-3.5" />
                            <span>Reveal Answer</span>
                          </>
                        )}
                      </Button>

                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => handleRegenerateSingle(q.id)}
                        className="h-7 w-7 text-muted-foreground hover:text-foreground"
                        title="Regenerate this question"
                      >
                        <RefreshCw className="h-3 w-3" />
                      </Button>
                    </div>
                  </div>

                  {/* Question Prompt */}
                  <h4 className="mt-3 text-base font-semibold text-foreground leading-snug">
                    {q.question_text}
                  </h4>
                </CardHeader>

                <CardContent className="p-5 pt-0 space-y-4">
                  {/* MCQ Options Display */}
                  {q.question_type === "mcq" && q.options && (
                    <div className="grid grid-cols-1 gap-2 pt-2">
                      {q.options.map((opt) => {
                        const isChosen = selectedOption === opt.label;
                        const isCorrect = q.correct_answer === opt.label;

                        let optionStyle =
                          "border-border bg-card hover:bg-muted/50";
                        if (isRevealed) {
                          if (isCorrect) {
                            optionStyle =
                              "border-emerald-500 bg-emerald-50 text-emerald-900 dark:bg-emerald-950/40 dark:text-emerald-300";
                          } else if (isChosen && !isCorrect) {
                            optionStyle =
                              "border-rose-500 bg-rose-50 text-rose-900 dark:bg-rose-950/40 dark:text-rose-300";
                          }
                        } else if (isChosen) {
                          optionStyle =
                            "border-primary bg-primary/10 text-primary font-medium";
                        }

                        return (
                          <button
                            key={opt.label}
                            type="button"
                            onClick={() => handleSelectOption(q.id, opt.label)}
                            className={`flex items-start gap-3 rounded-lg border p-3 text-left text-sm transition-all duration-150 ${optionStyle}`}
                          >
                            <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-md border font-bold text-xs uppercase">
                              {opt.label}
                            </span>
                            <span className="flex-1">{opt.text}</span>
                            {isRevealed && isCorrect && (
                              <Check className="h-4 w-4 text-emerald-600 shrink-0 mt-0.5" />
                            )}
                            {isRevealed && isChosen && !isCorrect && (
                              <X className="h-4 w-4 text-rose-600 shrink-0 mt-0.5" />
                            )}
                          </button>
                        );
                      })}
                    </div>
                  )}

                  {/* Revealed Answer & Explanation Block */}
                  {isRevealed && (
                    <div className="rounded-lg border border-primary/20 bg-primary/5 p-4 space-y-2 text-sm animate-in fade-in-50 duration-200">
                      <div className="flex items-center gap-1.5 font-bold text-primary">
                        <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                        <span>Correct Answer: {q.correct_answer}</span>
                      </div>
                      <div className="text-foreground/90 text-xs sm:text-sm leading-relaxed">
                        <strong className="text-foreground">
                          Explanation:{" "}
                        </strong>
                        {q.explanation}
                      </div>
                    </div>
                  )}

                  {/* Source Citation */}
                  {q.source_ref && (
                    <div className="pt-2 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground border-t">
                      <span className="flex items-center gap-1 font-medium text-foreground">
                        <Bookmark className="h-3 w-3 text-primary" />
                        Source Reference:
                      </span>
                      {q.source_ref.section_title && (
                        <span className="bg-muted px-2 py-0.5 rounded">
                          {q.source_ref.section_title}
                        </span>
                      )}
                      {q.source_ref.page_numbers?.length > 0 && (
                        <span className="bg-muted px-2 py-0.5 rounded">
                          Page(s): {q.source_ref.page_numbers.join(", ")}
                        </span>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      ) : (
        <div className="rounded-xl border border-dashed p-10 text-center text-xs text-muted-foreground">
          No questions match the current type and difficulty filters.
        </div>
      )}
    </div>
  );
}
