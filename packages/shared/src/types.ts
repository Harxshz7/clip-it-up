export type VideoStatus = 'uploading' | 'uploaded' | 'processing' | 'ready' | 'failed';

export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';

export type TranscriptStatus = 'running' | 'ready' | 'failed';

export type ExportFormat = 'txt' | 'srt' | 'vtt' | 'json';

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
  width?: number | null;
  height?: number | null;
  fps?: number | null;
  has_audio: boolean;
  proxy_key?: string | null;
  audio_key?: string | null;
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
  partial_results?: Record<string, any>;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
  stages?: JobStage[];
}

export interface Speaker {
  id: string;
  transcript_id: string;
  label: string; // e.g. SPEAKER_00
  display_name?: string | null;
}

export interface TranscriptWord {
  id: string;
  transcript_id: string;
  idx: number;
  word: string;
  start_ms: number;
  end_ms: number;
  speaker?: string | null;
  confidence?: number | null;
}

export interface TranscriptSegment {
  id: string;
  transcript_id: string;
  idx: number;
  start_ms: number;
  end_ms: number;
  speaker?: string | null;
  text: string;
  words?: TranscriptWord[];
}

export interface Transcript {
  id: string;
  video_id: string;
  language?: string | null;
  status: TranscriptStatus;
  model?: string | null;
  backend?: string | null;
  word_count: number;
  created_at: string;
  speakers?: Speaker[];
  segments?: TranscriptSegment[];
}

export interface TranscriptResponse {
  transcript: Transcript;
  speakers: Speaker[];
  segments: TranscriptSegment[];
  total_segments: number;
  has_more?: boolean;
}

export interface TranscriptWordsResponse {
  words: TranscriptWord[];
  from_ms?: number | null;
  to_ms?: number | null;
  total: number;
}

export interface UpdateSpeakerRequest {
  display_name: string;
}

export interface ProxyUrlResponse {
  video_id: string;
  proxy_url: string;
  expires_in_seconds: number;
  content_type: string;
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
  video_id?: string;
  user_id?: string;
  status: JobStatus;
  current_stage?: PipelineStageName | null;
  progress: number;
  error?: string | null;
  partial_results?: Record<string, any>;
  stages: JobStage[];
  timestamp: string;
}

export interface TranscriptReadyEventPayload {
  job_id: string;
  video_id: string;
  transcript_id: string;
  partial_results: {
    transcript: boolean;
    [key: string]: any;
  };
  timestamp: string;
}

export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, any>;
  };
}

// Phase 2 Types

export type MomentStatus = 'candidate' | 'scored' | 'selected' | 'rejected';
export type VariantLength = '15' | '30' | '45' | '60' | 'auto';
export type FeedbackReasonTag = 'boring' | 'no_context' | 'bad_start' | 'bad_end' | 'off_topic' | 'other';

export interface ClipScoreBreakdown {
  hook: number;
  emotion: number;
  coherence: number;
  payoff: number;
  novelty: number;
  audio_energy: number;
  laughter: number;
  pause_penalty: number;
  flag_penalty: number;
  flags?: {
    needs_context?: boolean;
    off_topic?: boolean;
    profanity?: boolean;
    sensitive?: boolean;
  };
}

export interface ClipFeedback {
  id: string;
  clip_id: string;
  user_id: string;
  value: 'up' | 'down';
  reason_tag?: FeedbackReasonTag | null;
  created_at: string;
}

export interface ClipFeedbackRequest {
  value: 'up' | 'down';
  reason_tag?: FeedbackReasonTag | null;
}

export interface Clip {
  id: string;
  moment_id: string;
  video_id: string;
  scoring_run_id?: string | null;
  variant_length_s: VariantLength;
  start_ms: number;
  end_ms: number;
  duration_seconds: number;
  hook_text: string;
  title: string;
  final_score: number;
  score_breakdown: ClipScoreBreakdown;
  reason: string;
  model: string;
  prompt_version: string;
  scorer_version: string;
  created_at: string;
  feedback?: ClipFeedback | null;
}

export interface ClipMoment {
  id: string;
  video_id: string;
  transcript_id: string;
  start_ms: number;
  end_ms: number;
  duration_seconds: number;
  rank?: number | null;
  final_score?: number | null;
  status: MomentStatus;
  created_at: string;
  clips: Clip[];
}

export interface VideoClipsResponse {
  video_id: string;
  moments: ClipMoment[];
  total_moments: number;
  total_clips: number;
}

export interface RescoreRequest {
  prompt_version?: string | null;
  weights?: Record<string, number> | null;
}

export interface ScoringRun {
  id: string;
  video_id: string;
  prompt_version: string;
  scorer_version: string;
  weights: Record<string, any>;
  model: string;
  input_tokens: number;
  output_tokens: number;
  cost_inr: number;
  created_at: string;
}

export interface ClipScoredEventPayload {
  job_id: string;
  video_id: string;
  moment_id: string;
  clip_id: string;
  final_score: number;
  hook_text: string;
  title: string;
  duration_seconds: number;
  scored_count: number;
  total_count: number;
  partial_results: {
    clips_count: number;
  };
  timestamp: string;
}

export interface EvalVideo {
  id: string;
  slug: string;
  title: string;
  source_url?: string | null;
  duration_seconds?: number | null;
  meta: Record<string, any>;
  created_at: string;
}

export interface EvalClipRating {
  id: string;
  video_slug: string;
  start_ms: number;
  end_ms: number;
  clip_id?: string | null;
  rater_id: string;
  score: number;
  comment?: string | null;
  created_at: string;
}

