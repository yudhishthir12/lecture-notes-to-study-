/**
 * TypeScript type definitions for LectureForge AI.
 * Aligned with backend schemas and data models.
 */

export type DocumentStatus =
  | "uploaded"
  | "parsing"
  | "chunking"
  | "extracting_concepts"
  | "generating_summary"
  | "generating_questions"
  | "evaluating"
  | "retrying"
  | "completed"
  | "failed";

export type StudyPackStatus = "generating" | "completed" | "failed" | "warning";

export type QuestionType = "mcq" | "short_answer" | "conceptual";

export type DifficultyLevel = "easy" | "medium" | "hard";

export type FileType = "pdf" | "pptx" | "txt";

export interface SourceReference {
  page_numbers: number[];
  section_title?: string | null;
  slide_numbers?: number[] | null;
}

export interface Concept {
  name: string;
  description: string;
  source_ref: SourceReference;
}

export interface KeyTerm {
  term: string;
  definition: string;
  source_ref: SourceReference;
}

export interface Formula {
  expression: string;
  description: string;
  source_ref: SourceReference;
}

export interface MCQOption {
  label: string; // 'A' | 'B' | 'C' | 'D'
  text: string;
}

export interface PracticeQuestion {
  id: string;
  question_text: string;
  question_type: QuestionType;
  difficulty: DifficultyLevel;
  options?: MCQOption[] | null;
  correct_answer: string;
  explanation: string;
  source_ref: SourceReference;
}

export interface Summary {
  overview: string;
  detailed_summary: string;
}

export interface EvaluationResult {
  faithfulness: number;
  coverage: number;
  answer_accuracy: number;
  clarity: number;
  overall_score: number;
  passed: boolean;
  issues: string[];
  failed_sections: string[];
}

export interface PipelineMetadata {
  prompt_version: string;
  model_name: string;
  retry_count: number;
  processing_time_seconds: number;
  token_usage?: Record<string, unknown> | null;
}

export interface StudyPackMetadata {
  topic: string;
  document_id: string;
  source_pages: number[];
  generated_at: string;
}

export interface StudyPackContent {
  metadata: StudyPackMetadata;
  summary: Summary;
  concepts: Concept[];
  key_terms: KeyTerm[];
  formulas: Formula[];
  practice_questions: PracticeQuestion[];
  evaluation?: EvaluationResult | null;
  pipeline_metadata?: PipelineMetadata | null;
}

export interface StudyPack {
  id: string;
  document_id: string;
  status: StudyPackStatus;
  content: StudyPackContent;
  evaluation?: EvaluationResult | null;
  created_at: string;
  updated_at: string;
}

export interface StudyPackResponse {
  id: string;
  document_id: string;
  status: StudyPackStatus;
  content: StudyPackContent;
  evaluation?: EvaluationResult | null;
  created_at: string;
  updated_at: string;
}

export interface Document {
  id: string;
  filename: string;
  file_type: string;
  file_size: number;
  status: DocumentStatus;
  page_count?: number | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
  has_study_pack: boolean;
  human_readable_size?: string;
  extracted_text?: string | null;
  chunks_count?: number;
}

export interface DocumentListResponse {
  items: Document[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface DocumentStatusResponse {
  id: string;
  filename: string;
  status: DocumentStatus;
  current_stage?: string | null;
  progress_percentage: number;
  error_message?: string | null;
  updated_at: string;
}

export interface StudyPackListResponse {
  items: StudyPackResponse[];
  total: number;
}

export interface RegeneratePayload {
  sections: string[];
}

export interface RegenerateResponse {
  message: string;
  study_pack_id: string;
  pipeline_run_id: string;
  status: string;
}
