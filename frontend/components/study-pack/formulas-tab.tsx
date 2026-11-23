"use client";

import * as React from "react";
import { Binary, Bookmark, Copy, Check } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Formula } from "@/types";
import { toast } from "sonner";

interface FormulasTabProps {
  formulas: Formula[];
}

export function FormulasTab({ formulas = [] }: FormulasTabProps) {
  const [copiedIdx, setCopiedIdx] = React.useState<number | null>(null);

  const handleCopy = (expression: string, idx: number) => {
    navigator.clipboard.writeText(expression);
    setCopiedIdx(idx);
    toast.success("Formula copied to clipboard");
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  if (!formulas || formulas.length === 0) {
    return (
      <div className="rounded-xl border border-dashed p-10 text-center">
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-muted mx-auto mb-2 text-muted-foreground">
          <Binary className="h-5 w-5" />
        </div>
        <h4 className="text-sm font-semibold text-foreground">
          No Mathematical Formulas Detected
        </h4>
        <p className="text-xs text-muted-foreground mt-1">
          This lecture contains primarily conceptual descriptions or qualitative
          analyses.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
          <Binary className="h-5 w-5 text-primary" />
          Mathematical Equations & Algorithms ({formulas.length})
        </h3>
        <p className="text-xs text-muted-foreground">
          Key mathematical relationships, algorithms, and computational rules.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {formulas.map((formula, idx) => (
          <Card key={idx} className="flex flex-col justify-between">
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between gap-2">
                <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                  Formula #{idx + 1}
                </CardTitle>
                <button
                  onClick={() => handleCopy(formula.expression, idx)}
                  className="p-1.5 text-muted-foreground hover:text-foreground hover:bg-muted rounded transition-colors"
                  title="Copy equation"
                >
                  {copiedIdx === idx ? (
                    <Check className="h-3.5 w-3.5 text-emerald-500" />
                  ) : (
                    <Copy className="h-3.5 w-3.5" />
                  )}
                </button>
              </div>

              {/* Formula code / LaTeX display box */}
              <div className="mt-2 rounded-lg bg-muted/60 p-3.5 font-mono text-sm text-foreground overflow-x-auto border">
                <code>{formula.expression}</code>
              </div>
            </CardHeader>

            <CardContent className="pt-2 flex-1 flex flex-col justify-between">
              <p className="text-sm text-foreground/90 leading-relaxed">
                {formula.description}
              </p>

              {formula.source_ref && (
                <div className="mt-4 pt-3 border-t flex items-center gap-2 text-[11px] text-muted-foreground">
                  <Bookmark className="h-3 w-3 text-primary" />
                  <span>Citation:</span>
                  {formula.source_ref.section_title && (
                    <span className="bg-muted px-2 py-0.5 rounded">
                      {formula.source_ref.section_title}
                    </span>
                  )}
                  {formula.source_ref.page_numbers?.length > 0 && (
                    <span className="bg-muted px-2 py-0.5 rounded">
                      Page {formula.source_ref.page_numbers.join(", ")}
                    </span>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
