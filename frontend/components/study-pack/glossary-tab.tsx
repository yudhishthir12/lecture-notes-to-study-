"use client";

import * as React from "react";
import { BookmarkCheck, Search, Copy, Check, Bookmark } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { KeyTerm } from "@/types";
import { toast } from "sonner";

interface GlossaryTabProps {
  terms: KeyTerm[];
}

export function GlossaryTab({ terms = [] }: GlossaryTabProps) {
  const [search, setSearch] = React.useState("");
  const [copiedTerm, setCopiedTerm] = React.useState<string | null>(null);

  const filteredTerms = React.useMemo(() => {
    return terms.filter(
      (t) =>
        t.term.toLowerCase().includes(search.toLowerCase()) ||
        t.definition.toLowerCase().includes(search.toLowerCase()),
    );
  }, [terms, search]);

  const handleCopy = (term: KeyTerm) => {
    navigator.clipboard.writeText(`${term.term}: ${term.definition}`);
    setCopiedTerm(term.term);
    toast.success(`Copied "${term.term}" to clipboard`);
    setTimeout(() => setCopiedTerm(null), 2000);
  };

  return (
    <div className="space-y-4">
      {/* Header & Filter */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 className="text-lg font-bold text-foreground flex items-center gap-2">
            <BookmarkCheck className="h-5 w-5 text-primary" />
            Domain Glossary & Terminology ({terms.length})
          </h3>
          <p className="text-xs text-muted-foreground">
            Precise academic definitions with verified source references.
          </p>
        </div>

        <div className="relative max-w-xs w-full">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search vocabulary..."
            className="h-9 w-full rounded-lg border bg-background pl-9 pr-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/40"
          />
        </div>
      </div>

      {/* Terms list */}
      {filteredTerms.length > 0 ? (
        <div className="space-y-3">
          {filteredTerms.map((item, index) => (
            <Card
              key={item.term + index}
              className="transition-colors hover:border-primary/40"
            >
              <CardContent className="p-4 sm:p-5 flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                <div className="space-y-1.5 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-foreground text-base">
                      {item.term}
                    </span>
                  </div>
                  <p className="text-sm text-foreground/90 leading-relaxed">
                    {item.definition}
                  </p>

                  {/* Source reference citation */}
                  {item.source_ref && (
                    <div className="flex flex-wrap items-center gap-2 pt-2 text-[11px] text-muted-foreground">
                      <Bookmark className="h-3 w-3 text-primary" />
                      <span>Citation:</span>
                      {item.source_ref.section_title && (
                        <span className="bg-muted px-2 py-0.5 rounded">
                          {item.source_ref.section_title}
                        </span>
                      )}
                      {item.source_ref.page_numbers?.length > 0 && (
                        <span className="bg-muted px-2 py-0.5 rounded">
                          Page {item.source_ref.page_numbers.join(", ")}
                        </span>
                      )}
                    </div>
                  )}
                </div>

                {/* Copy button */}
                <button
                  onClick={() => handleCopy(item)}
                  className="shrink-0 p-2 text-muted-foreground hover:text-foreground hover:bg-muted rounded-md transition-colors"
                  title="Copy term and definition"
                >
                  {copiedTerm === item.term ? (
                    <Check className="h-4 w-4 text-emerald-500" />
                  ) : (
                    <Copy className="h-4 w-4" />
                  )}
                </button>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="rounded-xl border border-dashed p-8 text-center text-xs text-muted-foreground">
          No terms found matching your query.
        </div>
      )}
    </div>
  );
}
