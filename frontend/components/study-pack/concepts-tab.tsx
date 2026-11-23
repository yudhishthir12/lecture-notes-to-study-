"use client";

import * as React from "react";
import { BookOpen, Search, RefreshCw, Bookmark, Layers } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Concept } from "@/types";

interface ConceptsTabProps {
  concepts: Concept[];
  onRegenerate?: () => void;
  isRegenerating?: boolean;
}

export function ConceptsTab({
  concepts = [],
  onRegenerate,
  isRegenerating = false,
}: ConceptsTabProps) {
  const [search, setSearch] = React.useState("");

  const filteredConcepts = React.useMemo(() => {
    return concepts.filter(
      (c) =>
        c.name.toLowerCase().includes(search.toLowerCase()) ||
        c.description.toLowerCase().includes(search.toLowerCase()),
    );
  }, [concepts, search]);

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
            <BookOpen className="h-5 w-5 text-primary" />
            Core Academic Concepts ({concepts.length})
          </h3>
          <p className="text-xs text-muted-foreground">
            Key theoretical foundations with traceable source citations.
          </p>
        </div>

        <div className="flex items-center gap-2">
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
              <span>Regenerate Concepts</span>
            </Button>
          )}
        </div>
      </div>

      {/* Search Input */}
      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Filter concepts..."
          className="h-9 w-full rounded-lg border bg-background pl-9 pr-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
        />
      </div>

      {/* Concepts Grid */}
      {filteredConcepts.length > 0 ? (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {filteredConcepts.map((concept, index) => (
            <Card
              key={concept.name + index}
              className="flex flex-col justify-between transition-all duration-200 hover:border-primary/40 hover:shadow-xs"
            >
              <CardHeader className="pb-2">
                <div className="flex items-start justify-between gap-2">
                  <CardTitle className="text-base font-semibold text-foreground flex items-center gap-2">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-bold text-primary">
                      {index + 1}
                    </span>
                    <span>{concept.name}</span>
                  </CardTitle>
                </div>
              </CardHeader>
              <CardContent className="pt-0 flex-1 flex flex-col justify-between">
                <p className="text-sm text-foreground/90 leading-relaxed">
                  {concept.description}
                </p>

                {/* Source Citation */}
                {concept.source_ref && (
                  <div className="mt-4 pt-3 border-t flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                    <span className="font-medium text-foreground flex items-center gap-1">
                      <Bookmark className="h-3 w-3 text-primary" />
                      Citation:
                    </span>
                    {concept.source_ref.section_title && (
                      <span className="bg-muted px-2 py-0.5 rounded">
                        {concept.source_ref.section_title}
                      </span>
                    )}
                    {concept.source_ref.page_numbers?.length > 0 && (
                      <span className="bg-muted px-2 py-0.5 rounded">
                        Page(s): {concept.source_ref.page_numbers.join(", ")}
                      </span>
                    )}
                    {concept.source_ref.slide_numbers?.length ? (
                      <span className="bg-muted px-2 py-0.5 rounded">
                        Slide(s): {concept.source_ref.slide_numbers.join(", ")}
                      </span>
                    ) : null}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-dashed p-8 text-center text-xs text-muted-foreground">
          No concepts match your filter.
        </div>
      )}
    </div>
  );
}
