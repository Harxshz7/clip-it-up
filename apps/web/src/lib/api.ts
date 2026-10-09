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
} from "@clip-it-up/shared";


const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiError extends Error {
  code: string;
  details?: any;

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
    throw new ApiError(err.message, err.code, err.details);
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
};


