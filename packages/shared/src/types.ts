export type VideoStatus = 'uploading' | 'uploaded' | 'processing' | 'ready' | 'failed';

export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';

export type PipelineStageName =
  | 'ingest'
  | 'proxy'
  | 'transcribe'
  | 'candidates'
  | 'score'
  | 'render';

export const PIPELINE_STAGES: PipelineStageName[] = [
  'ingest',
  'proxy',
  'transcribe',
  'candidates',
  'score',
  'render',
];

export interface User {
  id: string;
  clerk_user_id: string;
  email: string;
  created_at: string;
}

export interface Project {
  id: string;
  user_id: string;
  name: string;
  created_at: string;
}

export interface Video {
  id: string;
  project_id?: string | null;
  user_id: string;
  original_filename: string;
  storage_key: string;
  size_bytes: number;
  duration_seconds?: number | null;
  content_type: string;
  status: VideoStatus;
  created_at: string;
}

export interface JobStage {
  id: string;
  job_id: string;
  name: PipelineStageName;
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled';
  progress: number;
  started_at?: string | null;
  finished_at?: string | null;
  duration_ms?: number | null;
  cost_inr: number;
  meta: Record<string, any>;
}

export interface Job {
  id: string;
  video_id: string;
  user_id: string;
  status: JobStatus;
  current_stage?: PipelineStageName | null;
  progress: number;
  error?: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  stages?: JobStage[];
}

export interface Usage {
  id: string;
  user_id: string;
  video_id?: string | null;
  job_id?: string | null;
  metric: string;
  quantity: number;
  cost_inr: number;
  created_at: string;
}

export interface UsageSummary {
  month: string;
  total_cost_inr: number;
  metrics: {
    metric: string;
    total_quantity: number;
    total_cost_inr: number;
  }[];
}

export interface UploadUrlRequest {
  filename: string;
  content_type: string;
  size_bytes: number;
  project_id?: string | null;
}

export interface UploadUrlResponse {
  video_id: string;
  storage_key: string;
  upload_type: 'direct_put' | 'multipart';
  upload_url?: string;
  upload_id?: string;
  part_urls?: { part_number: number; upload_url: string }[];
  part_size?: number;
  total_parts?: number;
}

export interface MultipartPartUrlRequest {
  video_id: string;
  upload_id: string;
  part_number: number;
}

export interface MultipartPartUrlResponse {
  part_number: number;
  upload_url: string;
}

export interface MultipartCompleteRequest {
  upload_id: string;
  parts: { part_number: number; etag: string }[];
}

export interface CompleteUploadResponse {
  video: Video;
  job: Job;
}

export interface JobEventPayload {
  job_id: string;
  status: JobStatus;
  current_stage?: PipelineStageName | null;
  progress: number;
  error?: string | null;
  stages: JobStage[];
  timestamp: string;
}

export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, any>;
  };
}
