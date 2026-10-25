import {
  UploadUrlRequest,
  UploadUrlResponse,
  CompleteUploadResponse,
  Video,
  Job,
  UsageSummary,
  MultipartPartUrlResponse,
  TranscriptResponse,
  TranscriptWordsResponse,
  Speaker,
  ProxyUrlResponse,
  ExportFormat,
  ReviewSessionCreateRequest,
  ReviewSessionCreatedResponse,
  ReviewSessionOwnerItem,
  ReviewSessionPublic,
  ReviewRating,
  ReviewRatingUpsertRequest,
  ReviewSurvey,
  ReviewSurveyUpsertRequest,
  GateReport,
  VideoAnalysisResponse,
  ReframeResponse,
  ReframeUpdateRequest,
  ReframeRegenerateRequest,
  CaptionStyle,
  ExportPreset,
  UserPlanMe,
  ClipCaptions,
  ClipCleanup,
  ClipCleanupAnalyzeResult,
  ExportRecord,
  CreateExportPayload,
  VideoClipsResponse,
  ClipEditRecord,
  ClipEditDoc,
  ClipEditSaveRequest,
  ClipEditCheckpointRequest,
  ClipEditVersionSummary,
  ClipAlternative,
  ClipRegenerateRequest,
  ClipBulkActionRequest,
  EditorEventsBatchRequest,
  EditorMetricsResponse,
  PlanBillingItem,
  UserBillingMe,
  TopUpPackItem,
  InvoiceListItem,
  TakedownNoticePayload,
  SupportTicketPayload,
  FunnelMetricsResponse,
  ProductHealthMetricsResponse,
  MoneyMetricsResponse,
  AbuseMetricsResponse,
  BrandKit,
  BrandAsset,
  VariantSet,
  ClipVariant,
  VariantGenerateRequest,
  VariantBatchExportRequest,
  ExportPerformanceMetrics,
} from "@clip-it-up/shared";


const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  code: string;
  details?: any;
  server_doc?: any;
  server_version?: number;

  constructor(message: string, code: string = "UNKNOWN_ERROR", details?: any) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.details = details;
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  token?: string | null
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const headers = new Headers(options.headers || {});

  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorData;
    try {
      errorData = await response.json();
    } catch {
      errorData = { error: { code: `HTTP_${response.status}`, message: response.statusText } };
    }

    const err = errorData?.error || {
      code: `HTTP_${response.status}`,
      message: response.statusText || "Request failed",
    };
    const apiError = new ApiError(err.message, err.code, err.details);
    if (err.server_doc) (apiError as any).server_doc = err.server_doc;
    if (err.server_version) (apiError as any).server_version = err.server_version;
    throw apiError;
  }

  return response.json();
}

export const api = {
  // 1. Request presigned upload URL
  async requestUploadUrl(
    payload: UploadUrlRequest,
    token?: string | null
  ): Promise<UploadUrlResponse> {
    return request<UploadUrlResponse>("/videos/upload-url", {
      method: "POST",
      body: JSON.stringify(payload),
    }, token);
  },

  // 2. Direct single-part upload to S3 presigned PUT URL with XHR progress
  async uploadDirectToS3(
    presignedUrl: string,
    file: File,
    onProgress?: (progress: number) => void
  ): Promise<void> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("PUT", presignedUrl, true);
      xhr.setRequestHeader("Content-Type", file.type);

      if (xhr.upload && onProgress) {
        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable) {
            const percentComplete = Math.round((event.loaded / event.total) * 100);
            onProgress(percentComplete);
          }
        };
      }

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve();
        } else {
          reject(new Error(`S3 direct upload failed with status ${xhr.status}`));
        }
      };

      xhr.onerror = () => reject(new Error("Network error during S3 upload"));
      xhr.send(file);
    });
  },

  // 3. Multipart chunked upload to S3 with part retry
  async uploadMultipartToS3(
    file: File,
    uploadInfo: UploadUrlResponse,
    token?: string | null,
    onProgress?: (progress: number) => void
  ): Promise<void> {
    const { video_id, upload_id, part_urls, part_size = 10 * 1024 * 1024 } = uploadInfo;
    if (!upload_id || !part_urls) {
      throw new Error("Missing multipart upload configuration");
    }

    const totalParts = part_urls.length;
    const completedParts: { part_number: number; etag: string }[] = [];
    let loadedBytesPerPart: number[] = new Array(totalParts).fill(0);

    const updateCombinedProgress = () => {
      if (!onProgress) return;
      const totalLoaded = loadedBytesPerPart.reduce((acc, curr) => acc + curr, 0);
      const pct = Math.min(100, Math.round((totalLoaded / file.size) * 100));
      onProgress(pct);
    };

    // Upload part with retry
    const uploadSinglePart = async (partInfo: { part_number: number; upload_url: string }, attempt = 1): Promise<void> => {
      const partIndex = partInfo.part_number - 1;
      const start = partIndex * part_size;
      const end = Math.min(start + part_size, file.size);
      const chunk = file.slice(start, end);

      let targetUrl = partInfo.upload_url;

      // If retry, request fresh part URL
      if (attempt > 1) {
        const fresh = await request<MultipartPartUrlResponse>(
          "/videos/multipart/part-url",
          {
            method: "POST",
            body: JSON.stringify({
              video_id,
              upload_id,
              part_number: partInfo.part_number,
            }),
          },
          token
        );
        targetUrl = fresh.upload_url;
      }

      return new Promise<void>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("PUT", targetUrl, true);

        if (xhr.upload) {
          xhr.upload.onprogress = (evt) => {
            if (evt.lengthComputable) {
              loadedBytesPerPart[partIndex] = evt.loaded;
              updateCombinedProgress();
            }
          };
        }

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            const rawEtag = xhr.getResponseHeader("ETag") || `part-${partInfo.part_number}`;
            const cleanEtag = rawEtag.replace(/"/g, "");
            completedParts.push({ part_number: partInfo.part_number, etag: cleanEtag });
            loadedBytesPerPart[partIndex] = chunk.size;
            updateCombinedProgress();
            resolve();
          } else {
            if (attempt < 3) {
              uploadSinglePart(partInfo, attempt + 1).then(resolve).catch(reject);
            } else {
              reject(new Error(`Part ${partInfo.part_number} failed after ${attempt} attempts.`));
            }
          }
        };

        xhr.onerror = () => {
          if (attempt < 3) {
            uploadSinglePart(partInfo, attempt + 1).then(resolve).catch(reject);
          } else {
            reject(new Error(`Network failure uploading part ${partInfo.part_number}`));
          }
        };

        xhr.send(chunk);
      });
    };

    // Execute uploads with concurrency of 4 parts
    const concurrency = 4;
    for (let i = 0; i < part_urls.length; i += concurrency) {
      const batch = part_urls.slice(i, i + concurrency);
      await Promise.all(batch.map((p) => uploadSinglePart(p)));
    }

    // Complete multipart upload on API
    await request(
      `/videos/multipart/complete/${video_id}`,
      {
        method: "POST",
        body: JSON.stringify({
          upload_id,
          parts: completedParts.sort((a, b) => a.part_number - b.part_number),
        }),
      },
      token
    );
  },

  // 4. Mark upload complete and trigger job
  async completeUpload(videoId: string, token?: string | null): Promise<CompleteUploadResponse> {
    return request<CompleteUploadResponse>(`/videos/${videoId}/complete`, {
      method: "POST",
    }, token);
  },

  // 5. Video queries
  async getVideos(token?: string | null): Promise<Video[]> {
    return request<Video[]>("/videos", {}, token);
  },

  async getVideo(videoId: string, token?: string | null): Promise<Video> {
    return request<Video>(`/videos/${videoId}`, {}, token);
  },

  async getVideoClips(
    videoId: string,
    params?: { status?: string; min_score?: number; sort?: string },
    token?: string | null
  ): Promise<VideoClipsResponse> {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set("status", params.status);
    if (params?.min_score !== undefined) searchParams.set("min_score", params.min_score.toString());
    if (params?.sort) searchParams.set("sort", params.sort);
    const queryStr = searchParams.toString() ? `?${searchParams.toString()}` : "";
    return request<VideoClipsResponse>(`/videos/${videoId}/clips${queryStr}`, {}, token);
  },

  // 6. Job queries & control
  async getJob(jobId: string, token?: string | null): Promise<Job> {
    return request<Job>(`/jobs/${jobId}`, {}, token);
  },

  async cancelJob(jobId: string, token?: string | null): Promise<Job> {
    return request<Job>(`/jobs/${jobId}/cancel`, {
      method: "POST",
    }, token);
  },

  // 7. Usage summary
  async getUsageSummary(token?: string | null): Promise<UsageSummary> {
    return request<UsageSummary>("/usage/summary", {}, token);
  },

  // 8. Phase 1 Transcript endpoints
  async getTranscript(
    videoId: string,
    params?: { from_ms?: number; to_ms?: number },
    token?: string | null
  ): Promise<TranscriptResponse> {
    const searchParams = new URLSearchParams();
    if (params?.from_ms !== undefined) searchParams.set("from_ms", params.from_ms.toString());
    if (params?.to_ms !== undefined) searchParams.set("to_ms", params.to_ms.toString());
    const queryStr = searchParams.toString() ? `?${searchParams.toString()}` : "";
    return request<TranscriptResponse>(`/videos/${videoId}/transcript${queryStr}`, {}, token);
  },

  async getTranscriptWords(
    videoId: string,
    params?: { from_ms?: number; to_ms?: number },
    token?: string | null
  ): Promise<TranscriptWordsResponse> {
    const searchParams = new URLSearchParams();
    if (params?.from_ms !== undefined) searchParams.set("from_ms", params.from_ms.toString());
    if (params?.to_ms !== undefined) searchParams.set("to_ms", params.to_ms.toString());
    const queryStr = searchParams.toString() ? `?${searchParams.toString()}` : "";
    return request<TranscriptWordsResponse>(`/videos/${videoId}/transcript/words${queryStr}`, {}, token);
  },

  async updateSpeaker(
    videoId: string,
    speakerId: string,
    displayName: string,
    token?: string | null
  ): Promise<Speaker> {
    return request<Speaker>(
      `/videos/${videoId}/speakers/${speakerId}`,
      {
        method: "PATCH",
        body: JSON.stringify({ display_name: displayName }),
      },
      token
    );
  },

  async getProxyUrl(videoId: string, token?: string | null): Promise<ProxyUrlResponse> {
    return request<ProxyUrlResponse>(`/videos/${videoId}/proxy-url`, {}, token);
  },

  getExportUrl(videoId: string, format: ExportFormat): string {
    return `${API_BASE_URL}/videos/${videoId}/transcript/export?format=${format}`;
  },

  async exportTranscriptText(videoId: string, format: ExportFormat, token?: string | null): Promise<string> {
    const url = `${API_BASE_URL}/videos/${videoId}/transcript/export?format=${format}`;
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const res = await fetch(url, { headers });
    if (!res.ok) throw new ApiError(`Failed to export transcript (${res.status})`, `HTTP_${res.status}`);
    return res.text();
  },

  // 9. Phase 2.5 Creator Review Endpoints
  async createReviewSession(
    videoId: string,
    payload: ReviewSessionCreateRequest,
    token?: string | null
  ): Promise<ReviewSessionCreatedResponse> {
    return request<ReviewSessionCreatedResponse>(
      `/videos/${videoId}/review-sessions`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      token
    );
  },

  async getReviewSessions(
    videoId: string,
    token?: string | null
  ): Promise<ReviewSessionOwnerItem[]> {
    return request<ReviewSessionOwnerItem[]>(
      `/review-sessions?video_id=${videoId}`,
      {},
      token
    );
  },

  async getReviewSessionDetail(
    sessionId: string,
    token?: string | null
  ): Promise<ReviewSessionOwnerItem> {
    return request<ReviewSessionOwnerItem>(
      `/review-sessions/${sessionId}`,
      {},
      token
    );
  },

  async deleteReviewSession(
    sessionId: string,
    token?: string | null
  ): Promise<void> {
    return request<void>(
      `/review-sessions/${sessionId}`,
      {
        method: "DELETE",
      },
      token
    );
  },

  // Public Review Endpoints (No login)
  async getPublicReviewSession(
    reviewToken: string,
    showReasons: boolean = false
  ): Promise<ReviewSessionPublic> {
    const query = showReasons ? "?show_reasons=true" : "";
    return request<ReviewSessionPublic>(`/review/${reviewToken}${query}`, {});
  },

  async upsertReviewRating(
    reviewToken: string,
    clipId: string,
    payload: ReviewRatingUpsertRequest
  ): Promise<ReviewRating> {
    return request<ReviewRating>(`/review/${reviewToken}/ratings/${clipId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },

  async upsertReviewSurvey(
    reviewToken: string,
    payload: ReviewSurveyUpsertRequest
  ): Promise<ReviewSurvey> {
    return request<ReviewSurvey>(`/review/${reviewToken}/survey`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },

  async submitReviewSession(
    reviewToken: string
  ): Promise<{ status: string; session_id: string; submitted_at: string; message: string }> {
    return request<{ status: string; session_id: string; submitted_at: string; message: string }>(
      `/review/${reviewToken}/submit`,
      {
        method: "POST",
      }
    );
  },

  // Gate Report
  async getGateReport(token?: string | null): Promise<GateReport> {
    return request<GateReport>("/reviews/gate", {}, token);
  },

  // Phase 3 Video Analysis & Reframe
  async triggerVideoAnalysis(
    videoId: string,
    version: string = "v1",
    token?: string | null
  ): Promise<VideoAnalysisResponse> {
    return request<VideoAnalysisResponse>(
      `/videos/${videoId}/analysis?version=${version}`,
      { method: "POST" },
      token
    );
  },

  async getVideoAnalysis(
    videoId: string,
    version: string = "v1",
    token?: string | null
  ): Promise<VideoAnalysisResponse> {
    return request<VideoAnalysisResponse>(
      `/videos/${videoId}/analysis?version=${version}`,
      {},
      token
    );
  },

  async getClipReframe(
    clipId: string,
    version: string = "v1",
    token?: string | null
  ): Promise<ReframeResponse> {
    return request<ReframeResponse>(
      `/clips/${clipId}/reframe?analysis_version=${version}`,
      {},
      token
    );
  },

  async regenerateClipReframe(
    clipId: string,
    payload: ReframeRegenerateRequest,
    token?: string | null
  ): Promise<ReframeResponse> {
    return request<ReframeResponse>(
      `/clips/${clipId}/reframe/regenerate`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      token
    );
  },

  async updateClipReframe(
    clipId: string,
    payload: ReframeUpdateRequest,
    token?: string | null
  ): Promise<ReframeResponse> {
    return request<ReframeResponse>(
      `/clips/${clipId}/reframe`,
      {
        method: "PUT",
        body: JSON.stringify(payload),
      },
      token
    );
  },

  async revertClipReframeEdits(
    clipId: string,
    token?: string | null
  ): Promise<ReframeResponse> {
    return request<ReframeResponse>(
      `/clips/${clipId}/reframe/edits`,
      {
        method: "DELETE",
      },
      token
    );
  },

  // -------------------------------------------------------------------------
  // Phase 4: Exports, Captions, Cleanups, Presets & Plans
  // -------------------------------------------------------------------------

  async getCaptionStyles(token?: string | null): Promise<CaptionStyle[]> {
    return request<CaptionStyle[]>("/caption-styles", {}, token);
  },

  async getExportPresets(token?: string | null): Promise<ExportPreset[]> {
    return request<ExportPreset[]>("/export-presets", {}, token);
  },

  async getMyPlan(token?: string | null): Promise<UserPlanMe> {
    return request<UserPlanMe>("/plans/me", {}, token);
  },

  async getClipCaptions(clipId: string, token?: string | null): Promise<ClipCaptions> {
    return request<ClipCaptions>(`/clips/${clipId}/captions`, {}, token);
  },

  async updateClipCaptions(
    clipId: string,
    payload: { words: any[]; style_key?: string; style_overrides?: any },
    token?: string | null
  ): Promise<ClipCaptions> {
    return request<ClipCaptions>(
      `/clips/${clipId}/captions`,
      {
        method: "PUT",
        body: JSON.stringify(payload),
      },
      token
    );
  },

  async regenerateClipCaptions(
    clipId: string,
    payload: { style_key?: string; language?: string },
    token?: string | null
  ): Promise<ClipCaptions> {
    return request<ClipCaptions>(
      `/clips/${clipId}/captions/regenerate`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      token
    );
  },

  async getClipCleanup(clipId: string, token?: string | null): Promise<ClipCleanup> {
    return request<ClipCleanup>(`/clips/${clipId}/cleanup`, {}, token);
  },

  async updateClipCleanup(
    clipId: string,
    payload: { options?: any; removals?: any[] },
    token?: string | null
  ): Promise<ClipCleanup> {
    return request<ClipCleanup>(
      `/clips/${clipId}/cleanup`,
      {
        method: "PUT",
        body: JSON.stringify(payload),
      },
      token
    );
  },

  async analyzeClipCleanup(
    clipId: string,
    options?: any,
    token?: string | null
  ): Promise<ClipCleanupAnalyzeResult> {
    return request<ClipCleanupAnalyzeResult>(
      `/clips/${clipId}/cleanup/analyze`,
      {
        method: "POST",
        body: JSON.stringify(options || {}),
      },
      token
    );
  },

  async createClipExports(
    clipId: string,
    payload: CreateExportPayload,
    token?: string | null
  ): Promise<ExportRecord[]> {
    return request<ExportRecord[]>(
      `/clips/${clipId}/exports`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      token
    );
  },

  async getExport(exportId: string, token?: string | null): Promise<ExportRecord> {
    return request<ExportRecord>(`/exports/${exportId}`, {}, token);
  },

  async listClipExports(clipId: string, token?: string | null): Promise<ExportRecord[]> {
    return request<ExportRecord[]>(`/clips/${clipId}/exports`, {}, token);
  },

  async getExportDownloadUrl(
    exportId: string,
    token?: string | null
  ): Promise<{ export_id: string; download_url: string; expires_in_seconds: number }> {
    return request<{ export_id: string; download_url: string; expires_in_seconds: number }>(
      `/exports/${exportId}/download-url`,
      {},
      token
    );
  },

  // ----------------------------------------------------
  // Phase 5: Editor Endpoints
  // ----------------------------------------------------

  async getClipEdit(clipId: string, token?: string | null): Promise<ClipEditRecord> {
    return request<ClipEditRecord>(`/clips/${clipId}/edit`, {}, token);
  },

  async saveClipEdit(
    clipId: string,
    payload: ClipEditSaveRequest,
    ifMatch?: number | null,
    token?: string | null
  ): Promise<ClipEditRecord> {
    const headers: Record<string, string> = {};
    if (ifMatch !== undefined && ifMatch !== null) {
      headers["If-Match"] = `"${ifMatch}"`;
    }
    return request<ClipEditRecord>(
      `/clips/${clipId}/edit`,
      {
        method: "PUT",
        headers,
        body: JSON.stringify(payload),
      },
      token
    );
  },

  async createCheckpoint(
    clipId: string,
    label: string,
    token?: string | null
  ): Promise<ClipEditRecord> {
    return request<ClipEditRecord>(
      `/clips/${clipId}/edit/checkpoint`,
      {
        method: "POST",
        body: JSON.stringify({ label }),
      },
      token
    );
  },

  async listEditVersions(
    clipId: string,
    token?: string | null
  ): Promise<ClipEditVersionSummary[]> {
    return request<ClipEditVersionSummary[]>(`/clips/${clipId}/edit/versions`, {}, token);
  },

  async restoreEditVersion(
    clipId: string,
    version: number,
    token?: string | null
  ): Promise<ClipEditRecord> {
    return request<ClipEditRecord>(
      `/clips/${clipId}/edit/restore`,
      {
        method: "POST",
        body: JSON.stringify({ version }),
      },
      token
    );
  },

  async resetEditToAuto(clipId: string, token?: string | null): Promise<ClipEditRecord> {
    return request<ClipEditRecord>(
      `/clips/${clipId}/edit/reset`,
      {
        method: "POST",
      },
      token
    );
  },

  async listClipAlternatives(
    clipId: string,
    kind?: "hook" | "range",
    token?: string | null
  ): Promise<ClipAlternative[]> {
    const q = kind ? `?kind=${kind}` : "";
    return request<ClipAlternative[]>(`/clips/${clipId}/alternatives${q}`, {}, token);
  },

  async regenerateClip(
    clipId: string,
    payload: ClipRegenerateRequest,
    token?: string | null
  ): Promise<{ job_id: string; mode: string; alternative: ClipAlternative }> {
    return request<{ job_id: string; mode: string; alternative: ClipAlternative }>(
      `/clips/${clipId}/regenerate`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      token
    );
  },

  async bulkClipActions(
    payload: ClipBulkActionRequest,
    token?: string | null
  ): Promise<any> {
    return request<any>(
      `/clips/bulk`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      token
    );
  },

  async recordEditorEvents(
    payload: EditorEventsBatchRequest,
    token?: string | null
  ): Promise<{ status: string; count: number }> {
    return request<{ status: string; count: number }>(
      `/editor/events`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      token
    );
  },

  async getEditorMetrics(token?: string | null): Promise<EditorMetricsResponse> {
    return request<EditorMetricsResponse>(`/admin/editor-metrics`, {}, token);
  },

  async listExportPresets(token?: string | null): Promise<ExportPreset[]> {
    return request<ExportPreset[]>("/export-presets", {}, token);
  },

  async createClipExport(
    clipId: string,
    payload: CreateExportPayload,
    token?: string | null
  ): Promise<ExportRecord[]> {
    return request<ExportRecord[]>(
      `/clips/${clipId}/exports`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      token
    );
  },

  async submitClipFeedback(
    clipId: string,
    payload: { value: "up" | "down"; reason_tag?: string },
    token?: string | null
  ): Promise<any> {
    return request<any>(
      `/clips/${clipId}/feedback`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      token
    );
  },

  async deleteClipFeedback(clipId: string, token?: string | null): Promise<any> {
    return request<any>(`/clips/${clipId}/feedback`, { method: "DELETE" }, token);
  },

  async rescoreVideo(videoId: string, token?: string | null): Promise<any> {
    return request<any>(`/videos/${videoId}/rescore`, { method: "POST" }, token);
  },

  // ----------------------------------------------------
  // Phase 6: Billing, Legal, Admin, Ops
  // ----------------------------------------------------
  async getBillingPlans(): Promise<{ plans: PlanBillingItem[]; top_up_packs: TopUpPackItem[]; currency_default: string }> {
    return request<{ plans: PlanBillingItem[]; top_up_packs: TopUpPackItem[]; currency_default: string }>("/billing/plans");
  },

  async getBillingMe(token?: string | null): Promise<UserBillingMe> {
    return request<UserBillingMe>("/billing/me", {}, token);
  },

  async createCheckout(
    payload: {
      plan_key: string;
      provider?: string;
      currency?: string;
      country?: string;
      customer_name?: string;
      customer_email?: string;
      customer_gstin?: string;
      billing_address?: any;
    },
    token?: string | null
  ): Promise<any> {
    return request<any>("/billing/checkout", {
      method: "POST",
      body: JSON.stringify(payload),
    }, token);
  },

  async buyTopUp(
    payload: {
      pack_key: string;
      provider?: string;
      currency?: string;
      country?: string;
      customer_name?: string;
      customer_email?: string;
    },
    token?: string | null
  ): Promise<any> {
    return request<any>("/billing/top-up", {
      method: "POST",
      body: JSON.stringify(payload),
    }, token);
  },

  async cancelSubscription(token?: string | null): Promise<any> {
    return request<any>("/billing/subscriptions/cancel", { method: "POST" }, token);
  },

  async resumeSubscription(token?: string | null): Promise<any> {
    return request<any>("/billing/subscriptions/resume", { method: "POST" }, token);
  },

  async changePlan(planKey: string, token?: string | null): Promise<any> {
    return request<any>("/billing/subscriptions/change-plan", {
      method: "POST",
      body: JSON.stringify({ plan_key: planKey }),
    }, token);
  },

  async getInvoices(token?: string | null): Promise<InvoiceListItem[]> {
    return request<InvoiceListItem[]>("/billing/invoices", {}, token);
  },

  getInvoiceDownloadUrl(invoiceId: string): string {
    return `${API_BASE_URL}/billing/invoices/${invoiceId}/download`;
  },

  async acceptTerms(doc: string, version: string, token?: string | null): Promise<any> {
    return request<any>("/legal/accept-terms", {
      method: "POST",
      body: JSON.stringify({ doc, version }),
    }, token);
  },

  async submitTakedown(payload: TakedownNoticePayload): Promise<any> {
    return request<any>("/legal/dmca/takedown", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async submitCounterNotice(ticketId: string, payload: { statement: string; contact_email: string; signature: string }): Promise<any> {
    return request<any>(`/legal/dmca/${ticketId}/counter-notice`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  async deleteVideo(videoId: string, token?: string | null): Promise<any> {
    return request<any>(`/legal/videos/${videoId}`, { method: "DELETE" }, token);
  },

  async requestAccountDeletion(token?: string | null): Promise<any> {
    return request<any>("/legal/account/delete", { method: "POST" }, token);
  },

  async downloadUserData(token?: string | null): Promise<any> {
    return request<any>("/legal/account/export-data", {}, token);
  },

  async submitSupportTicket(payload: SupportTicketPayload, token?: string | null): Promise<any> {
    return request<any>("/legal/support/ticket", {
      method: "POST",
      body: JSON.stringify(payload),
    }, token);
  },

  async getAdminFunnelMetrics(token?: string | null): Promise<FunnelMetricsResponse> {
    return request<FunnelMetricsResponse>("/admin/metrics/funnel", {}, token);
  },

  async getAdminProductHealthMetrics(token?: string | null): Promise<ProductHealthMetricsResponse> {
    return request<ProductHealthMetricsResponse>("/admin/metrics/product-health", {}, token);
  },

  async getAdminMoneyMetrics(token?: string | null): Promise<MoneyMetricsResponse> {
    return request<MoneyMetricsResponse>("/admin/metrics/money", {}, token);
  },

  async getAdminAbuseMetrics(token?: string | null): Promise<AbuseMetricsResponse> {
    return request<AbuseMetricsResponse>("/admin/metrics/abuse", {}, token);
  },

  async getAdminInvites(token?: string | null): Promise<any[]> {
    return request<any[]>("/admin/invites", {}, token);
  },

  async createAdminInvite(payload: { code: string; max_uses?: number; expires_in_days?: number }, token?: string | null): Promise<any> {
    return request<any>("/admin/invites", {
      method: "POST",
      body: JSON.stringify(payload),
    }, token);
  },

  async revokeAdminInvite(code: string, token?: string | null): Promise<any> {
    return request<any>(`/admin/invites/${code}`, { method: "DELETE" }, token);
  },

  getAdminInvoicesExportUrl(month: string): string {
    return `${API_BASE_URL}/admin/invoices/export?month=${month}`;
  },

  async getDeepHealth(): Promise<any> {
    return request<any>("/health/deep");
  },

  // ----------------------------------------------------
  // Phase 7a: Brand Kit and Auto-Variants
  // ----------------------------------------------------
  async listBrandKits(token?: string | null): Promise<BrandKit[]> {
    return request<BrandKit[]>("/brand-kits", {}, token);
  },

  async getBrandKit(id: string, token?: string | null): Promise<BrandKit> {
    return request<BrandKit>(`/brand-kits/${id}`, {}, token);
  },

  async getDefaultBrandKit(token?: string | null): Promise<BrandKit | null> {
    try {
      return await request<BrandKit>("/brand-kits/default", {}, token);
    } catch {
      return null;
    }
  },

  async createBrandKit(payload: Partial<BrandKit>, token?: string | null): Promise<BrandKit> {
    return request<BrandKit>(
      "/brand-kits",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      token
    );
  },

  async updateBrandKit(id: string, payload: Partial<BrandKit>, token?: string | null): Promise<BrandKit> {
    return request<BrandKit>(
      `/brand-kits/${id}`,
      {
        method: "PUT",
        body: JSON.stringify(payload),
      },
      token
    );
  },

  async setDefaultBrandKit(id: string, token?: string | null): Promise<BrandKit> {
    return request<BrandKit>(`/brand-kits/${id}/default`, { method: "PUT" }, token);
  },

  async deleteBrandKit(id: string, token?: string | null): Promise<any> {
    return request<any>(`/brand-kits/${id}`, { method: "DELETE" }, token);
  },

  async getBrandAssetUploadUrl(
    payload: { filename: string; content_type: string; size_bytes: number; kind: string },
    token?: string | null
  ): Promise<{ asset_id: string; upload_url: string; storage_key: string }> {
    return request<{ asset_id: string; upload_url: string; storage_key: string }>(
      "/brand-assets/upload-url",
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      token
    );
  },

  async completeBrandAsset(
    assetId: string,
    payload: { license_acknowledged?: boolean },
    token?: string | null
  ): Promise<BrandAsset> {
    return request<BrandAsset>(
      `/brand-assets/${assetId}/complete`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      token
    );
  },

  async deleteBrandAsset(assetId: string, token?: string | null): Promise<any> {
    return request<any>(`/brand-assets/${assetId}`, { method: "DELETE" }, token);
  },

  async generateVariants(
    clipId: string,
    payload: VariantGenerateRequest,
    token?: string | null
  ): Promise<VariantSet> {
    return request<VariantSet>(
      `/clips/${clipId}/variants`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      token
    );
  },

  async getClipVariants(clipId: string, token?: string | null): Promise<VariantSet | null> {
    try {
      return await request<VariantSet>(`/clips/${clipId}/variants`, {}, token);
    } catch {
      return null;
    }
  },

  async deleteVariant(variantId: string, token?: string | null): Promise<any> {
    return request<any>(`/variants/${variantId}`, { method: "DELETE" }, token);
  },

  async batchExportVariants(
    setId: string,
    payload: VariantBatchExportRequest,
    token?: string | null
  ): Promise<{ set_id: string; export_ids: string[]; count: number; message: string }> {
    return request<{ set_id: string; export_ids: string[]; count: number; message: string }>(
      `/variant-sets/${setId}/export`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
      token
    );
  },

  async updateExportMetrics(
    exportId: string,
    payload: ExportPerformanceMetrics,
    token?: string | null
  ): Promise<any> {
    return request<any>(
      `/exports/${exportId}/metrics`,
      {
        method: "PATCH",
        body: JSON.stringify(payload),
      },
      token
    );
  },

  getVariantSetZipDownloadUrl(setId: string): string {
    return `${API_BASE_URL}/variant-sets/${setId}/download-zip`;
  },
};


