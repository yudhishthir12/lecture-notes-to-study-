"use client";

import * as React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import {
  BookOpen,
  LayoutDashboard,
  FileText,
  Sparkles,
  Sun,
  Moon,
  UploadCloud,
  ChevronLeft,
  ChevronRight,
  Menu,
  GraduationCap,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { UploadDialog } from "@/components/upload/upload-dialog";

interface SidebarProps {
  className?: string;
}

export function Sidebar({ className }: SidebarProps) {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();
  const [isCollapsed, setIsCollapsed] = React.useState(false);
  const [isMobileOpen, setIsMobileOpen] = React.useState(false);
  const [mounted, setMounted] = React.useState(false);
  const [isUploadOpen, setIsUploadOpen] = React.useState(false);

  React.useEffect(() => {
    setMounted(true);
  }, []);

  const navItems = [
    {
      title: "Dashboard",
      href: "/",
      icon: LayoutDashboard,
      active: pathname === "/",
    },
    {
      title: "Documents",
      href: "/#documents",
      icon: FileText,
      active: pathname.startsWith("/documents"),
    },
    {
      title: "Study Packs",
      href: "/#study-packs",
      icon: GraduationCap,
      active: pathname.startsWith("/study-packs"),
    },
  ];

  return (
    <>
      {/* Mobile Menu Backdrop */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm lg:hidden"
          onClick={() => setIsMobileOpen(false)}
        />
      )}

      {/* Mobile Toggle Button */}
      <div className="fixed top-3 left-4 z-50 lg:hidden">
        <Button
          variant="outline"
          size="icon"
          onClick={() => setIsMobileOpen(!isMobileOpen)}
          className="bg-card shadow-sm"
          aria-label="Toggle navigation menu"
        >
          <Menu className="h-5 w-5" />
        </Button>
      </div>

      {/* Sidebar Container */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-40 flex flex-col border-r bg-card transition-all duration-300 lg:static",
          isCollapsed ? "lg:w-20" : "lg:w-64",
          isMobileOpen
            ? "translate-x-0 w-64 shadow-2xl"
            : "-translate-x-full lg:translate-x-0",
          className,
        )}
      >
        {/* Brand Header */}
        <div className="flex h-16 items-center justify-between border-b px-4">
          <Link
            href="/"
            className="flex items-center gap-3 overflow-hidden font-bold tracking-tight text-foreground transition-opacity hover:opacity-90"
          >
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-primary text-white shadow-md shadow-primary/20">
              <BookOpen className="h-5 w-5" />
            </div>
            {!isCollapsed && (
              <div className="flex flex-col leading-tight">
                <span className="text-base font-bold bg-gradient-to-r from-indigo-600 via-primary to-blue-500 bg-clip-text text-transparent">
                  LectureForge AI
                </span>
                <span className="text-[11px] font-normal text-muted-foreground">
                  Study Pack Engine
                </span>
              </div>
            )}
          </Link>

          {/* Desktop collapse toggle */}
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            className="hidden lg:flex h-7 w-7 items-center justify-center rounded-md border text-muted-foreground hover:bg-muted hover:text-foreground transition-colors"
            title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {isCollapsed ? (
              <ChevronRight className="h-4 w-4" />
            ) : (
              <ChevronLeft className="h-4 w-4" />
            )}
          </button>
        </div>

        {/* Upload Action Button */}
        <div className="p-3">
          <Button
            onClick={() => setIsUploadOpen(true)}
            className={cn(
              "w-full bg-primary hover:bg-primary/90 text-primary-foreground font-medium shadow-sm transition-all",
              isCollapsed ? "px-0 justify-center" : "justify-center gap-2",
            )}
            title="Upload lecture notes"
          >
            <UploadCloud className="h-4 w-4 shrink-0" />
            {!isCollapsed && <span>Upload Document</span>}
          </Button>
        </div>

        {/* Navigation Links */}
        <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <Link
                key={item.title}
                href={item.href}
                onClick={() => setIsMobileOpen(false)}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                  item.active
                    ? "bg-primary/10 text-primary font-semibold dark:bg-primary/20"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                  isCollapsed && "justify-center px-0",
                )}
                title={item.title}
              >
                <Icon
                  className={cn(
                    "h-5 w-5 shrink-0",
                    item.active ? "text-primary" : "text-muted-foreground",
                  )}
                />
                {!isCollapsed && <span>{item.title}</span>}
              </Link>
            );
          })}
        </div>

        {/* Footer Area: Dark Mode Toggle & System Info */}
        <div className="border-t p-3 space-y-2">
          {mounted && (
            <button
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              className={cn(
                "flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-muted hover:text-foreground",
                isCollapsed && "justify-center px-0",
              )}
              title={
                theme === "dark"
                  ? "Switch to light mode"
                  : "Switch to dark mode"
              }
            >
              {theme === "dark" ? (
                <Sun className="h-5 w-5 text-amber-400 shrink-0" />
              ) : (
                <Moon className="h-5 w-5 text-indigo-500 shrink-0" />
              )}
              {!isCollapsed && (
                <span>{theme === "dark" ? "Light Theme" : "Dark Theme"}</span>
              )}
            </button>
          )}

          {!isCollapsed && (
            <div className="rounded-lg bg-muted/60 p-2.5 text-xs text-muted-foreground">
              <div className="flex items-center gap-1.5 font-medium text-foreground">
                <Sparkles className="h-3.5 w-3.5 text-primary" />
                <span>AI Pipeline Active</span>
              </div>
              <p className="mt-1 text-[11px] leading-tight text-muted-foreground">
                Transforms slides & notes with verified citations
              </p>
            </div>
          )}
        </div>
      </aside>

      <UploadDialog open={isUploadOpen} onOpenChange={setIsUploadOpen} />
    </>
  );
}
