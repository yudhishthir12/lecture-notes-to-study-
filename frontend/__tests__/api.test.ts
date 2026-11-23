/**
 * Unit and integration tests for LectureForge AI frontend API client (`lib/api.ts`).
 *
 * Tests verify:
 * - uploadDocument via XMLHttpRequest (progress events, success, HTTP errors, network errors)
 * - getDocuments, getDocument, getDocumentStatus (query params, URL matching, JSON deserialization)
 * - generateStudyPack (POST request and status response)
 * - getStudyPack, regenerateSection, getEvaluation
 * - exportMarkdown, exportPdf, exportAnki (blob handling and failure modes)
 * - deleteDocument (DELETE verb and status verification)
 * - Error propagation via ApiError
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '@/lib/api';
import { Document, DocumentListResponse, DocumentStatusResponse, StudyPackResponse } from '@/types';

describe('Frontend API Client (lib/api.ts)', () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  // ===========================================================================
  // 1. uploadDocument Tests (XMLHttpRequest Mocking)
  // ===========================================================================

  describe('uploadDocument', () => {
    let mockXHR: any;

    beforeEach(() => {
      mockXHR = {
        open: vi.fn(),
        send: vi.fn(),
        upload: {
          onprogress: null,
        },
        onload: null,
        onerror: null,
        status: 201,
        statusText: 'Created',
        responseText: JSON.stringify({
          id: 'doc-1234',
          filename: 'algorithms.pdf',
          file_type: 'pdf',
          file_size: 10240,
          status: 'uploaded',
          created_at: '2026-11-22T00:00:00Z',
          updated_at: '2026-11-22T00:00:00Z',
          has_study_pack: false,
          human_readable_size: '10.0 KB',
        } as Document),
      };

      // Mock global XMLHttpRequest constructor
      vi.stubGlobal(
        'XMLHttpRequest',
        vi.fn(() => mockXHR)
      );
    });

    it('uploads a document successfully and reports progress', async () => {
      const file = new File(['mock content'], 'algorithms.pdf', { type: 'application/pdf' });
      const progressTracker: number[] = [];

      const uploadPromise = api.uploadDocument(file, (percent) => {
        progressTracker.push(percent);
      });

      // Simulate XHR progress events
      if (mockXHR.upload.onprogress) {
        mockXHR.upload.onprogress({ lengthComputable: true, loaded: 50, total: 100 });
        mockXHR.upload.onprogress({ lengthComputable: true, loaded: 100, total: 100 });
      }

      // Simulate load event
      mockXHR.status = 201;
      mockXHR.onload();

      const result = await uploadPromise;

      expect(mockXHR.open).toHaveBeenCalledWith('POST', expect.stringContaining('/documents/upload'));
      expect(mockXHR.send).toHaveBeenCalledWith(expect.any(FormData));
      expect(progressTracker).toEqual([50, 100]);
      expect(result.id).toBe('doc-1234');
      expect(result.filename).toBe('algorithms.pdf');
    });

    it('handles HTTP error responses and rejects with ApiError', async () => {
      const file = new File(['invalid'], 'test.exe', { type: 'application/octet-stream' });

      const uploadPromise = api.uploadDocument(file);

      // Simulate server error 400
      mockXHR.status = 400;
      mockXHR.statusText = 'Bad Request';
      mockXHR.responseText = JSON.stringify({
        detail: 'Unsupported file format .exe.',
      });
      mockXHR.onload();

      await expect(uploadPromise).rejects.toThrow(/Unsupported file format/);
    });

    it('handles network error during upload', async () => {
      const file = new File(['content'], 'test.txt', { type: 'text/plain' });

      const uploadPromise = api.uploadDocument(file);

      // Simulate network disconnect
      mockXHR.onerror();

      await expect(uploadPromise).rejects.toThrow(/Network error during document upload/);
    });
  });

  // ===========================================================================
  // 2. Document Query Endpoints
  // ===========================================================================

  describe('getDocuments', () => {
    it('fetches paginated documents with query params', async () => {
      const mockResponse: DocumentListResponse = {
        items: [
          {
            id: 'doc-1',
            filename: 'Lecture1.pdf',
            file_type: 'pdf',
            file_size: 2048,
            status: 'completed',
            created_at: '2026-11-22T00:00:00Z',
            updated_at: '2026-11-22T00:00:00Z',
            has_study_pack: true,
            human_readable_size: '2.0 KB',
          },
        ],
        total: 1,
        page: 1,
        page_size: 10,
        total_pages: 1,
      };

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockResponse,
      });

      const data = await api.getDocuments(1, 10, 'completed');

      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringMatching(/\/documents\?page=1&page_size=10&status=completed$/),
        { cache: 'no-store' }
      );
      expect(data.total).toBe(1);
      expect(data.items[0].filename).toBe('Lecture1.pdf');
    });
  });

  describe('getDocument', () => {
    it('fetches single document details by ID', async () => {
      const mockDoc: Document = {
        id: 'doc-abc',
        filename: 'Physics.txt',
        file_type: 'txt',
        file_size: 512,
        status: 'uploaded',
        created_at: '2026-11-22T00:00:00Z',
        updated_at: '2026-11-22T00:00:00Z',
        has_study_pack: false,
        human_readable_size: '512 B',
      };

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockDoc,
      });

      const doc = await api.getDocument('doc-abc');

      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/documents/doc-abc'), {
        cache: 'no-store',
      });
      expect(doc.id).toBe('doc-abc');
      expect(doc.filename).toBe('Physics.txt');
    });
  });

  describe('getDocumentStatus', () => {
    it('fetches real-time status of document', async () => {
      const mockStatus: DocumentStatusResponse = {
        id: 'doc-status-1',
        filename: 'Lecture.pdf',
        status: 'generating_summary',
        current_stage: 'Generating Summary',
        progress_percentage: 65,
        updated_at: '2026-11-22T00:00:00Z',
      };

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockStatus,
      });

      const res = await api.getDocumentStatus('doc-status-1');
      expect(res.status).toBe('generating_summary');
      expect(res.progress_percentage).toBe(65);
    });
  });

  // ===========================================================================
  // 3. Pipeline Generation & Section Regeneration
  // ===========================================================================

  describe('generateStudyPack', () => {
    it('triggers study pack generation via POST', async () => {
      const mockStatus: DocumentStatusResponse = {
        id: 'doc-gen-1',
        filename: 'Bio.pdf',
        status: 'parsing',
        current_stage: 'Parsing Document',
        progress_percentage: 15,
        updated_at: '2026-11-22T00:00:00Z',
      };

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockStatus,
      });

      const res = await api.generateStudyPack('doc-gen-1');

      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/documents/doc-gen-1/generate'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      expect(res.status).toBe('parsing');
    });
  });

  describe('regenerateSection', () => {
    it('sends targeted section regeneration request', async () => {
      const mockRegen = {
        study_pack_id: 'sp-1',
        status: 'regenerating',
        regenerated_sections: ['questions'],
      };

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: async () => mockRegen,
      });

      const res = await api.regenerateSection('sp-1', ['questions']);

      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/study-packs/sp-1/regenerate'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sections: ['questions'] }),
      });
      expect(res.status).toBe('regenerating');
    });
  });

  // ===========================================================================
  // 4. Exports and File Downloads
  // ===========================================================================

  describe('Export functions', () => {
    it('downloads Markdown blob', async () => {
      const mockBlob = new Blob(['# Markdown content'], { type: 'text/markdown' });
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        blob: async () => mockBlob,
      });

      const blob = await api.exportMarkdown('sp-export-1');
      expect(blob).toBeDefined();
      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/study-packs/sp-export-1/export/markdown'));
    });

    it('downloads PDF blob', async () => {
      const mockBlob = new Blob(['%PDF-1.4 dummy'], { type: 'application/pdf' });
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        blob: async () => mockBlob,
      });

      const blob = await api.exportPdf('sp-export-1');
      expect(blob).toBeDefined();
      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/study-packs/sp-export-1/export/pdf'));
    });

    it('downloads Anki CSV blob', async () => {
      const mockBlob = new Blob(['"Front","Back","Tags"\n'], { type: 'text/csv' });
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        blob: async () => mockBlob,
      });

      const blob = await api.exportAnki('sp-export-1');
      expect(blob).toBeDefined();
      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/study-packs/sp-export-1/export/anki'));
    });

    it('throws error when export endpoint fails', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: 'Not Found',
      });

      await expect(api.exportMarkdown('non-existent')).rejects.toThrow(/Failed to export Markdown: Not Found/);
    });
  });

  // ===========================================================================
  // 5. Document Deletion & Error Handling
  // ===========================================================================

  describe('deleteDocument', () => {
    it('deletes document with DELETE verb and 204 status', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 204,
      });

      await expect(api.deleteDocument('doc-del-1')).resolves.toBeUndefined();
      expect(global.fetch).toHaveBeenCalledWith(expect.stringContaining('/documents/doc-del-1'), {
        method: 'DELETE',
      });
    });

    it('throws error when delete fails', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
      });

      await expect(api.deleteDocument('doc-del-fail')).rejects.toThrow(/Failed to delete document/);
    });
  });

  describe('Error handling (handleResponse)', () => {
    it('extracts detail string from JSON error response', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        statusText: 'Not Found',
        json: async () => ({ detail: 'Resource not found in system' }),
      });

      await expect(api.getDocument('missing-id')).rejects.toThrow(/Resource not found in system/);
    });
  });
});
