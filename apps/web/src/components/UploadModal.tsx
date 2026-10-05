"use client";

import { useState, useRef, ChangeEvent, DragEvent } from "react";
import { useRouter } from "next/navigation";
import { X, UploadCloud, Film, CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import { useAppStore } from "@/lib/store";
import { api, ApiError } from "@/lib/api";
import { formatBytes } from "@/lib/utils";

const ALLOWED_TYPES = ["video/mp4", "video/quicktime", "video/x-matroska", "video/webm"];
const MAX_SIZE_BYTES = 5 * 1024 * 1024 * 1024; // 5 GB

export function UploadModal() {
  const router = useRouter();
  const isOpen = useAppStore((s) => s.isUploadModalOpen);
  const setOpen = useAppStore((s) => s.setUploadModalOpen);

  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [uploadStageText, setUploadStageText] = useState<string>("");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleClose = () => {
    if (isUploading) return;
    setFile(null);
    setUploadProgress(0);
    setErrorMessage(null);
    setOpen(false);
  };

  const handleFileSelect = (selectedFile: File) => {
    setErrorMessage(null);
    if (!ALLOWED_TYPES.includes(selectedFile.type) && !selectedFile.name.match(/\.(mp4|mov|mkv|webm)$/i)) {
      setErrorMessage("Unsupported file format. Please upload MP4, MOV, MKV, or WEBM.");
      return;
    }

    if (selectedFile.size > MAX_SIZE_BYTES) {
      setErrorMessage("File exceeds 5 GB maximum upload limit.");
      return;
    }

    setFile(selectedFile);
  };

  const onDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const onDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleStartUpload = async () => {
    if (!file) return;

    setIsUploading(true);
    setUploadProgress(0);
    setErrorMessage(null);
    setUploadStageText("Requesting presigned upload URL...");

    try {
      // 1. Request presigned URL from API
      const uploadInfo = await api.requestUploadUrl({
        filename: file.name,
        content_type: file.type || "video/mp4",
        size_bytes: file.size,
      });

      // 2. Upload file directly to S3/MinIO
      setUploadStageText(
        uploadInfo.upload_type === "multipart"
          ? `Uploading in ${uploadInfo.total_parts} parts directly to storage...`
          : "Uploading directly to storage via presigned PUT URL..."
      );

      if (uploadInfo.upload_type === "multipart") {
        await api.uploadMultipartToS3(file, uploadInfo, null, (pct) => {
          setUploadProgress(pct);
        });
      } else if (uploadInfo.upload_url) {
        await api.uploadDirectToS3(uploadInfo.upload_url, file, (pct) => {
          setUploadProgress(pct);
        });
      }

      // 3. Mark complete on API to trigger pipeline
      setUploadProgress(100);
      setUploadStageText("Verifying storage object & initializing processing pipeline...");
      const completeRes = await api.completeUpload(uploadInfo.video_id);

      // 4. Redirect to job progress page
      handleClose();
      router.push(`/videos/${completeRes.video_id}`);
    } catch (err: any) {
      console.error("Upload failed:", err);
      const msg = err instanceof ApiError ? err.message : err?.message || "Upload failed. Please try again.";
      setErrorMessage(msg);
      setIsUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-full max-w-lg rounded-2xl border border-white/10 bg-[#121622] p-6 shadow-2xl relative">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-white/10">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-purple-500/10 text-purple-400">
              <UploadCloud className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Upload Long Video</h2>
              <p className="text-xs text-zinc-400">Direct-to-storage upload (up to 5 GB)</p>
            </div>
          </div>
          {!isUploading && (
            <button
              onClick={handleClose}
              className="rounded-lg p-1.5 text-zinc-400 hover:text-white hover:bg-white/10 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          )}
        </div>

        {/* Body */}
        <div className="mt-5 space-y-4">
          {!file && !isUploading && (
            <div
              onDragOver={onDragOver}
              onDragLeave={onDragLeave}
              onDrop={onDrop}
              onClick={() => fileInputRef.current?.click()}
              className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 text-center cursor-pointer transition-all ${
                isDragging
                  ? "border-purple-500 bg-purple-500/10 scale-[0.99]"
                  : "border-white/15 hover:border-purple-500/50 hover:bg-white/[0.02]"
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                accept="video/mp4,video/quicktime,video/x-matroska,video/webm"
                className="hidden"
                onChange={(e: ChangeEvent<HTMLInputElement>) => {
                  if (e.target.files?.[0]) handleFileSelect(e.target.files[0]);
                }}
              />
              <div className="h-12 w-12 rounded-full bg-purple-950/60 flex items-center justify-center border border-purple-800/60 text-purple-400 mb-3">
                <Film className="w-6 h-6" />
              </div>
              <p className="text-sm font-medium text-white mb-1">
                Drag and drop your video here, or <span className="text-purple-400 underline">browse</span>
              </p>
              <p className="text-xs text-zinc-500">Supports MP4, MOV, MKV, WEBM (Max 5 GB)</p>
            </div>
          )}

          {file && !isUploading && (
            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 flex items-center justify-between">
              <div className="flex items-center gap-3 overflow-hidden">
                <div className="p-2.5 rounded-lg bg-purple-500/20 text-purple-300 shrink-0">
                  <Film className="w-5 h-5" />
                </div>
                <div className="truncate">
                  <p className="text-sm font-medium text-white truncate">{file.name}</p>
                  <p className="text-xs text-zinc-400">{formatBytes(file.size)}</p>
                </div>
              </div>
              <button
                onClick={() => setFile(null)}
                className="text-xs text-zinc-400 hover:text-red-400 px-2 py-1 rounded transition-colors"
              >
                Change
              </button>
            </div>
          )}

          {/* Upload Progress State */}
          {isUploading && (
            <div className="space-y-3 py-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-zinc-300 font-medium flex items-center gap-2">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-purple-400" />
                  {uploadStageText}
                </span>
                <span className="text-purple-400 font-semibold">{uploadProgress}%</span>
              </div>
              <div className="w-full bg-zinc-800 rounded-full h-2.5 overflow-hidden">
                <div
                  className="bg-gradient-to-r from-purple-500 to-indigo-500 h-2.5 rounded-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                />
              </div>
              <p className="text-[11px] text-zinc-500">
                Uploading {file?.name} ({formatBytes(file?.size || 0)})
              </p>
            </div>
          )}

          {/* Error display */}
          {errorMessage && (
            <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-3 flex items-start gap-2.5 text-xs text-red-300">
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}
        </div>

        {/* Footer actions */}
        <div className="mt-6 flex items-center justify-end gap-3 pt-4 border-t border-white/10">
          {!isUploading && (
            <button
              onClick={handleClose}
              className="px-4 py-2 text-sm font-medium text-zinc-400 hover:text-white rounded-lg transition-colors"
            >
              Cancel
            </button>
          )}
          {file && !isUploading && (
            <button
              onClick={handleStartUpload}
              className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-purple-600 to-indigo-600 px-5 py-2 text-sm font-semibold text-white shadow-lg shadow-purple-500/25 hover:from-purple-500 hover:to-indigo-500 active:scale-95 transition-all"
            >
              <UploadCloud className="w-4 h-4" />
              Start Upload
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
