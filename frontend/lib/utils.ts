import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { DocumentStatus, StudyPackStatus, DifficultyLevel } from "@/types";

/**
 * Combines Tailwind classes with clsx and twMerge.
 */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Format ISO datetime string to user-friendly local date/time.
 */
export function formatDate(dateString: string | Date | undefined): string {
  if (!dateString) return "N/A";
  try {
    const date =
      typeof dateString === "string" ? new Date(dateString) : dateString;
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "numeric",
      minute: "2-digit",
    }).format(date);
  } catch {
    return String(dateString);
  }
}

/**
 * Format bytes into human-readable B, KB, MB, GB.
 */
export function formatFileSize(bytes: number | undefined): string {
  if (bytes === undefined || bytes === null || isNaN(bytes)) return "0 B";
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  const idx = Math.min(i, sizes.length - 1);
  return `${parseFloat((bytes / Math.pow(k, idx)).toFixed(1))} ${sizes[idx]}`;
}

/**
 * Return badge color classes based on document processing status.
 */
export function getStatusColor(
  status: DocumentStatus | StudyPackStatus | string,
): {
  badge: string;
  dot: string;
  label: string;
} {
  switch (status) {
    case "completed":
      return {
        badge:
          "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-400 dark:border-emerald-800",
        dot: "bg-emerald-500",
        label: "Completed",
      };
    case "uploaded":
      return {
        badge:
          "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700",
        dot: "bg-slate-400",
        label: "Uploaded",
      };
    case "parsing":
      return {
        badge:
          "bg-sky-50 text-sky-700 border-sky-200 dark:bg-sky-950/40 dark:text-sky-400 dark:border-sky-800",
        dot: "bg-sky-500 animate-pulse",
        label: "Parsing",
      };
    case "chunking":
      return {
        badge:
          "bg-indigo-50 text-indigo-700 border-indigo-200 dark:bg-indigo-950/40 dark:text-indigo-400 dark:border-indigo-800",
        dot: "bg-indigo-500 animate-pulse",
        label: "Chunking",
      };
    case "extracting_concepts":
      return {
        badge:
          "bg-violet-50 text-violet-700 border-violet-200 dark:bg-violet-950/40 dark:text-violet-400 dark:border-violet-800",
        dot: "bg-violet-500 animate-pulse",
        label: "Extracting Concepts",
      };
    case "generating_summary":
      return {
        badge:
          "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-400 dark:border-blue-800",
        dot: "bg-blue-500 animate-pulse",
        label: "Generating Summary",
      };
    case "generating_questions":
      return {
        badge:
          "bg-teal-50 text-teal-700 border-teal-200 dark:bg-teal-950/40 dark:text-teal-400 dark:border-teal-800",
        dot: "bg-teal-500 animate-pulse",
        label: "Generating Questions",
      };
    case "evaluating":
      return {
        badge:
          "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800",
        dot: "bg-amber-500 animate-pulse",
        label: "Evaluating Quality",
      };
    case "retrying":
      return {
        badge:
          "bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-950/40 dark:text-orange-400 dark:border-orange-800",
        dot: "bg-orange-500 animate-pulse",
        label: "Self-Correcting",
      };
    case "generating":
      return {
        badge:
          "bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-400 dark:border-blue-800",
        dot: "bg-blue-500 animate-pulse",
        label: "Generating",
      };
    case "warning":
      return {
        badge:
          "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-400 dark:border-amber-800",
        dot: "bg-amber-500",
        label: "Review Needed",
      };
    case "failed":
      return {
        badge:
          "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-400 dark:border-rose-800",
        dot: "bg-rose-500",
        label: "Failed",
      };
    default:
      return {
        badge:
          "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700",
        dot: "bg-slate-400",
        label: String(status),
      };
  }
}

/**
 * Return badge styling for difficulty levels.
 */
export function getDifficultyColor(difficulty: DifficultyLevel | string): {
  badge: string;
  label: string;
} {
  switch (difficulty?.toLowerCase()) {
    case "easy":
      return {
        badge:
          "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/50 dark:text-emerald-400 dark:border-emerald-800",
        label: "Easy",
      };
    case "medium":
      return {
        badge:
          "bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/50 dark:text-amber-400 dark:border-amber-800",
        label: "Medium",
      };
    case "hard":
      return {
        badge:
          "bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/50 dark:text-rose-400 dark:border-rose-800",
        label: "Hard",
      };
    default:
      return {
        badge:
          "bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700",
        label: String(difficulty),
      };
  }
}

/**
 * Download a Blob in browser with an explicit filename.
 */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
}
