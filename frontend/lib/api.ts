/**
 * API client for LectureForge AI backend communication.
 * Handles document uploads with progress, retrieval, generation triggers, and file exports.
 */

import {
  Document,
  DocumentListResponse,
  DocumentStatusResponse,
  StudyPack,
  StudyPackResponse,
  EvaluationResult,
  RegenerateResponse,
} from "@/types";

/**
 * Resolves API base URL strictly from environment configuration (NEXT_PUBLIC_API_URL).
 * If not explicitly configured, defaults to relative '/api' route for reverse-proxy / same-origin setups.
 * Never hardcodes any host or port in code.
 */
const getBaseUrl = (): string => {
  const envUrl =
    process.env.NEXT_PUBLIC_API_URL ||
    (typeof window === "undefined" ? process.env.BACKEND_URL : undefined);

  if (envUrl) {
    const clean = envUrl.replace(/\/+$/, "");
    return clean.endsWith("/api") ? clean : `${clean}/api`;
  }

  // Relative path defaults for reverse-proxy, production ingress, or dev rewrites
  return "/api";
};

const API_BASE_URL = getBaseUrl();

class ApiError extends Error {
  status: number;
  detail?: string;

  constructor(status: number, message: string, detail?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorDetail = res.statusText;
    try {
      const errJson = await res.json();
      errorDetail =
        errJson.detail || errJson.message || JSON.stringify(errJson);
    } catch {
      // Non-JSON response
    }
    throw new ApiError(
      res.status,
      `API request failed with status ${res.status}: ${errorDetail}`,
      errorDetail,
    );
  }
  return res.json() as Promise<T>;
}

export const api = {
  /**
   * Upload a lecture document (PDF, PPTX, TXT) with upload progress tracking.
   */
  async uploadDocument(
    file: File,
    onProgress?: (percent: number) => void,
  ): Promise<Document> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const endpoint = `${API_BASE_URL}/documents/upload`;

      xhr.open("POST", endpoint);

      if (xhr.upload && onProgress) {
        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable) {
            const percent = Math.round((event.loaded / event.total) * 100);
            onProgress(percent);
          }
        };
      }

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            const doc = JSON.parse(xhr.responseText) as Document;
            resolve(doc);
          } catch (e) {
            reject(new Error("Failed to parse upload server response"));
          }
        } else {
          let detail = xhr.statusText;
          try {
            const err = JSON.parse(xhr.responseText);
            detail = err.detail || err.message || detail;
          } catch {
            // Keep statusText
          }
          reject(new ApiError(xhr.status, `Upload failed: ${detail}`, detail));
        }
      };

      xhr.onerror = () => {
        reject(
          new Error(
            "Network error during document upload. Please ensure backend is running.",
          ),
        );
      };

      const formData = new FormData();
      formData.append("file", file);
      xhr.send(formData);
    });
  },

  /**
   * Fetch paginated list of uploaded documents.
   */
  async getDocuments(
    page = 1,
    pageSize = 10,
    status?: string,
  ): Promise<DocumentListResponse> {
    const params = new URLSearchParams({
      page: page.toString(),
      page_size: pageSize.toString(),
    });
    if (status) {
      params.append("status", status);
    }

    const res = await fetch(`${API_BASE_URL}/documents?${params.toString()}`, {
      cache: "no-store",
    });
    return handleResponse<DocumentListResponse>(res);
  },

  /**
   * Fetch specific document by ID.
   */
  async getDocument(id: string): Promise<Document> {
    const res = await fetch(`${API_BASE_URL}/documents/${id}`, {
      cache: "no-store",
    });
    return handleResponse<Document>(res);
  },

  /**
   * Fetch document real-time processing status.
   */
  async getDocumentStatus(id: string): Promise<DocumentStatusResponse> {
    const res = await fetch(`${API_BASE_URL}/documents/${id}/status`, {
      cache: "no-store",
    });
    return handleResponse<DocumentStatusResponse>(res);
  },

  /**
   * Trigger study pack generation pipeline for a document.
   */
  async generateStudyPack(documentId: string): Promise<DocumentStatusResponse> {
    const res = await fetch(
      `${API_BASE_URL}/documents/${documentId}/generate`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      },
    );
    return handleResponse<DocumentStatusResponse>(res);
  },

  /**
   * Fetch complete study pack by ID.
   */
  async getStudyPack(id: string): Promise<StudyPack> {
    const res = await fetch(`${API_BASE_URL}/study-packs/${id}`, {
      cache: "no-store",
    });
    return handleResponse<StudyPackResponse>(res);
  },

  /**
   * Trigger partial regeneration of study pack sections.
   */
  async regenerateSection(
    studyPackId: string,
    sections: string[],
  ): Promise<RegenerateResponse> {
    const res = await fetch(
      `${API_BASE_URL}/study-packs/${studyPackId}/regenerate`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ sections }),
      },
    );
    return handleResponse<RegenerateResponse>(res);
  },

  /**
   * Fetch quality evaluation results for a study pack.
   */
  async getEvaluation(studyPackId: string): Promise<EvaluationResult> {
    const res = await fetch(
      `${API_BASE_URL}/study-packs/${studyPackId}/evaluation`,
      {
        cache: "no-store",
      },
    );
    return handleResponse<EvaluationResult>(res);
  },

  /**
   * Download study pack as Markdown (.md).
   */
  async exportMarkdown(studyPackId: string): Promise<Blob> {
    const res = await fetch(
      `${API_BASE_URL}/study-packs/${studyPackId}/export/markdown`,
    );
    if (!res.ok) {
      throw new Error(`Failed to export Markdown: ${res.statusText}`);
    }
    return res.blob();
  },

  /**
   * Download study pack as PDF document.
   */
  async exportPdf(studyPackId: string): Promise<Blob> {
    const res = await fetch(
      `${API_BASE_URL}/study-packs/${studyPackId}/export/pdf`,
    );
    if (!res.ok) {
      throw new Error(`Failed to export PDF: ${res.statusText}`);
    }
    return res.blob();
  },

  /**
   * Download study pack flashcards as Anki CSV (.csv).
   */
  async exportAnki(studyPackId: string): Promise<Blob> {
    const res = await fetch(
      `${API_BASE_URL}/study-packs/${studyPackId}/export/anki`,
    );
    if (!res.ok) {
      throw new Error(`Failed to export Anki flashcards: ${res.statusText}`);
    }
    return res.blob();
  },

  /**
   * Permanently delete a document and associated study pack.
   */
  async deleteDocument(id: string): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/documents/${id}`, {
      method: "DELETE",
    });
    if (!res.ok && res.status !== 204) {
      throw new Error(`Failed to delete document: ${res.statusText}`);
    }
  },
};
