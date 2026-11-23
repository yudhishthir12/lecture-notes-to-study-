"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, Home, UploadCloud } from "lucide-react";
import { Button } from "@/components/ui/button";
import { UploadDialog } from "@/components/upload/upload-dialog";

interface HeaderProps {
  title?: string;
  breadcrumbs?: Array<{ label: string; href?: string }>;
}

export function Header({ title, breadcrumbs }: HeaderProps) {
  const pathname = usePathname();
  const [isUploadOpen, setIsUploadOpen] = React.useState(false);

  // Auto-generate breadcrumbs if none provided
  const computedBreadcrumbs = React.useMemo(() => {
    if (breadcrumbs) return breadcrumbs;

    const segments = pathname.split("/").filter(Boolean);
    const crumbs = [{ label: "Dashboard", href: "/" }];

    if (segments.length > 0) {
      if (segments[0] === "documents") {
        crumbs.push({ label: "Documents", href: "/#documents" });
        if (segments[1]) {
          crumbs.push({
            label: "Document Details",
            href: `/${segments.join("/")}`,
          });
        }
      } else if (segments[0] === "study-packs") {
        crumbs.push({ label: "Study Packs", href: "/#study-packs" });
        if (segments[1]) {
          crumbs.push({
            label: "Study Pack Viewer",
            href: `/${segments.join("/")}`,
          });
        }
      }
    }
    return crumbs;
  }, [breadcrumbs, pathname]);

  return (
    <>
      <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b bg-background/80 px-4 sm:px-6 backdrop-blur-md">
        {/* Left: Breadcrumbs navigation */}
        <nav className="flex items-center space-x-1 text-sm text-muted-foreground pl-10 lg:pl-0">
          <Link
            href="/"
            className="flex items-center gap-1 hover:text-foreground transition-colors"
          >
            <Home className="h-4 w-4" />
          </Link>

          {computedBreadcrumbs.map((crumb, index) => {
            const isLast = index === computedBreadcrumbs.length - 1;
            return (
              <React.Fragment key={crumb.label + index}>
                <ChevronRight className="h-3.5 w-3.5 text-muted-foreground/60" />
                {crumb.href && !isLast ? (
                  <Link
                    href={crumb.href}
                    className="hover:text-foreground transition-colors font-medium truncate max-w-[120px] sm:max-w-none"
                  >
                    {crumb.label}
                  </Link>
                ) : (
                  <span className="font-semibold text-foreground truncate max-w-[150px] sm:max-w-[260px]">
                    {crumb.label}
                  </span>
                )}
              </React.Fragment>
            );
          })}
        </nav>

        {/* Right: Quick Upload Action Button */}
        <div className="flex items-center gap-3">
          <Button
            size="sm"
            onClick={() => setIsUploadOpen(true)}
            className="gap-1.5 shadow-sm hidden sm:inline-flex"
          >
            <UploadCloud className="h-4 w-4" />
            <span>Upload Notes</span>
          </Button>
        </div>
      </header>

      <UploadDialog open={isUploadOpen} onOpenChange={setIsUploadOpen} />
    </>
  );
}
