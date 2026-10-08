"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Video,
  ReviewSessionOwnerItem,
  ReviewSessionCreateRequest,
} from "@clip-it-up/shared";
import { api } from "@/lib/api";
import {
  ArrowLeft,
  Sparkles,
  Users,
  Plus,
  Copy,
  Check,
  ExternalLink,
  Trash2,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Send,
  Loader2,
  FileCheck,
  DollarSign,
  Calendar,
  Layers,
} from "lucide-react";

export default function VideoReviewsPage() {
  const params = useParams();
  const videoId = params.id as string;

  const [video, setVideo] = useState<Video | null>(null);
  const [sessions, setSessions] = useState<ReviewSessionOwnerItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [copiedToken, setCopiedToken] = useState<string | null>(null);

  // Create session modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creatorName, setCreatorName] = useState("");
  const [creatorEmail, setCreatorEmail] = useState("");
  const [expiresInDays, setExpiresInDays] = useState(14);
  const [topN, setTopN] = useState(8);
  const [creating, setCreating] = useState(false);

  // Selected session to view results
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);

  const fetchSessionsAndVideo = useCallback(async () => {
    try {
      setLoading(true);
      const [videoData, sessionsData] = await Promise.all([
        api.getVideo(videoId),
        api.getReviewSessions(videoId),
      ]);
      setVideo(videoData);
      setSessions(sessionsData);
      if (sessionsData.length > 0 && !selectedSessionId) {
        setSelectedSessionId(sessionsData[0].id);
      }
    } catch (err) {
      console.error("Failed to load review sessions:", err);
    } finally {
      setLoading(false);
    }
  }, [videoId, selectedSessionId]);

  useEffect(() => {
    if (videoId) fetchSessionsAndVideo();
  }, [videoId, fetchSessionsAndVideo]);

  const handleCreateSession = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!creatorName.trim()) return;

    try {
      setCreating(true);
      const res = await api.createReviewSession(videoId, {
        creator_name: creatorName.trim(),
        creator_email: creatorEmail.trim() || null,
        expires_in_days: expiresInDays,
        top_n: topN,
      });

      setShowCreateModal(false);
      setCreatorName("");
      setCreatorEmail("");
      await fetchSessionsAndVideo();
      setSelectedSessionId(res.id);
    } catch (err: any) {
      alert(err?.message || "Failed to create review session");
    } finally {
      setCreating(false);
    }
  };

  const handleCopyLink = (token: string, url: string) => {
    navigator.clipboard.writeText(url);
    setCopiedToken(token);
    setTimeout(() => setCopiedToken(null), 2000);
  };

  const handleDeleteSession = async (sessionId: string) => {
    if (!confirm("Are you sure you want to delete this review session?")) return;
    try {
      await api.deleteReviewSession(sessionId);
      await fetchSessionsAndVideo();
      if (selectedSessionId === sessionId) {
        setSelectedSessionId(null);
      }
    } catch (err: any) {
      alert(err?.message || "Failed to delete review session");
    }
  };

  const selectedSession = sessions.find((s) => s.id === selectedSessionId);

  if (loading && !video) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-3">
        <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
        <p className="text-sm text-zinc-400">Loading creator review sessions...</p>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-12">
      {/* Navigation Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <Link
            href={`/videos/${videoId}`}
            className="inline-flex items-center gap-1.5 text-xs font-semibold text-zinc-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" /> Back to Video
          </Link>
          <span className="text-zinc-600">•</span>
          <span className="text-xs text-purple-400 font-semibold">Phase 2.5 Reality Check</span>
        </div>

        <div className="flex items-center gap-2.5">
          <Link
            href="/reviews/gate"
            className="px-3.5 py-2 rounded-xl bg-zinc-900 border border-white/10 hover:border-purple-500/50 text-xs font-bold text-zinc-200 hover:text-white flex items-center gap-1.5 transition-colors"
          >
            <Layers className="w-3.5 h-3.5 text-purple-400" />
            <span>Gate Decision Report</span>
          </Link>

          <button
            type="button"
            onClick={() => setShowCreateModal(true)}
            className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-xs font-bold text-white shadow-md shadow-purple-600/20 flex items-center gap-1.5 transition-colors"
          >
            <Plus className="w-4 h-4" /> Create Review Link
          </button>
        </div>
      </div>

      {/* Title Card */}
      <div className="glass-panel p-6 rounded-3xl border border-white/10 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1">
          <span className="text-xs font-bold text-purple-400 uppercase tracking-wider">
            Creator Reality Check Kit
          </span>
          <h1 className="text-xl sm:text-2xl font-black text-white">
            {video?.original_filename || "Video Reviews"}
          </h1>
          <p className="text-xs text-zinc-400">
            Send private review links to 5 creators to validate AI selection accuracy and willingness to pay.
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <div className="px-4 py-2 rounded-2xl bg-zinc-900 border border-white/5 text-center">
            <span className="text-[10px] text-zinc-500 uppercase font-semibold block">Total Sessions</span>
            <span className="text-base font-bold text-white">{sessions.length}</span>
          </div>
          <div className="px-4 py-2 rounded-2xl bg-zinc-900 border border-white/5 text-center">
            <span className="text-[10px] text-zinc-500 uppercase font-semibold block">Submitted</span>
            <span className="text-base font-bold text-emerald-400">
              {sessions.filter((s) => s.status === "submitted").length}
            </span>
          </div>
        </div>
      </div>

      {/* Main Grid: Sessions List on Left, Selected Session Breakdown on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Sessions List */}
        <div className="lg:col-span-5 space-y-3">
          <h2 className="text-xs font-bold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
            <Users className="w-3.5 h-3.5" /> Creator Sessions ({sessions.length})
          </h2>

          {sessions.length === 0 ? (
            <div className="glass-panel p-8 rounded-2xl border border-white/5 text-center space-y-3">
              <Users className="w-8 h-8 text-zinc-600 mx-auto" />
              <p className="text-xs text-zinc-400">No review sessions created yet.</p>
              <button
                type="button"
                onClick={() => setShowCreateModal(true)}
                className="px-3 py-1.5 rounded-xl bg-purple-600 text-xs font-bold text-white"
              >
                Create First Link
              </button>
            </div>
          ) : (
            <div className="space-y-2.5">
              {sessions.map((s) => {
                const isSelected = s.id === selectedSessionId;
                const isSubmitted = s.status === "submitted";

                return (
                  <div
                    key={s.id}
                    onClick={() => setSelectedSessionId(s.id)}
                    className={`p-4 rounded-2xl border transition-all cursor-pointer space-y-3 ${
                      isSelected
                        ? "bg-purple-950/20 border-purple-500/40 shadow-lg shadow-purple-950/30"
                        : "bg-zinc-900/60 border-white/5 hover:border-white/20 hover:bg-zinc-900"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="text-sm font-bold text-white">{s.creator_name}</h3>
                        {s.creator_email && (
                          <span className="text-[11px] text-zinc-500 block">{s.creator_email}</span>
                        )}
                      </div>

                      <span
                        className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wider ${
                          isSubmitted
                            ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                            : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                        }`}
                      >
                        {s.status}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-xs text-zinc-400 pt-1 border-t border-white/5">
                      <span>
                        Rated: <strong className="text-zinc-200">{s.rated_clips_count}</strong>/{s.total_clips}
                      </span>

                      <div className="flex items-center gap-1.5" onClick={(e) => e.stopPropagation()}>
                        <button
                          type="button"
                          onClick={() => handleCopyLink(s.token, s.shareable_url)}
                          className="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors flex items-center gap-1 text-[11px]"
                          title="Copy Link"
                        >
                          {copiedToken === s.token ? (
                            <>
                              <Check className="w-3.5 h-3.5 text-emerald-400" />
                              <span className="text-emerald-400">Copied</span>
                            </>
                          ) : (
                            <>
                              <Copy className="w-3.5 h-3.5" />
                              <span>Copy</span>
                            </>
                          )}
                        </button>

                        <a
                          href={s.shareable_url}
                          target="_blank"
                          rel="noreferrer"
                          className="p-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors"
                          title="Open Link"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                        </a>

                        <button
                          type="button"
                          onClick={() => handleDeleteSession(s.id)}
                          className="p-1.5 rounded-lg bg-zinc-800 hover:bg-red-950 hover:text-red-400 text-zinc-400 transition-colors"
                          title="Delete Session"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Right Column: Selected Session Detail */}
        <div className="lg:col-span-7 space-y-4">
          {selectedSession ? (
            <div className="glass-panel p-6 rounded-3xl border border-white/10 space-y-6">
              {/* Creator Summary Header */}
              <div className="flex items-start justify-between pb-4 border-b border-white/10">
                <div>
                  <span className="text-[10px] font-bold text-purple-400 uppercase tracking-wider">
                    Creator Results
                  </span>
                  <h2 className="text-lg font-bold text-white mt-0.5">{selectedSession.creator_name}</h2>
                  <p className="text-xs text-zinc-400">
                    Created: {new Date(selectedSession.created_at).toLocaleDateString()} • Expires:{" "}
                    {new Date(selectedSession.expires_at).toLocaleDateString()}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => handleCopyLink(selectedSession.token, selectedSession.shareable_url)}
                  className="px-3 py-1.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-xs font-semibold text-white flex items-center gap-1.5"
                >
                  {copiedToken === selectedSession.token ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  <span>{copiedToken === selectedSession.token ? "Copied Link" : "Copy Review Link"}</span>
                </button>
              </div>

              {/* Ratings List */}
              <div className="space-y-3">
                <h3 className="text-xs font-bold text-zinc-300 uppercase tracking-wider">
                  Ratings ({selectedSession.ratings.length} Submitted)
                </h3>

                {selectedSession.ratings.length === 0 ? (
                  <p className="text-xs text-zinc-500 italic">No clip ratings recorded yet.</p>
                ) : (
                  <div className="space-y-2">
                    {selectedSession.ratings.map((r, i) => (
                      <div
                        key={r.id}
                        className="p-3 rounded-xl bg-zinc-900/80 border border-white/5 flex items-start justify-between gap-3 text-xs"
                      >
                        <div className="space-y-1">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-zinc-500">#{i + 1}</span>
                            <span
                              className={`font-bold capitalize px-2 py-0.5 rounded-md ${
                                r.verdict === "post_as_is"
                                  ? "bg-emerald-500/20 text-emerald-300"
                                  : r.verdict === "post_with_edits"
                                  ? "bg-amber-500/20 text-amber-300"
                                  : "bg-rose-500/20 text-rose-300"
                              }`}
                            >
                              {r.verdict.replace(/_/g, " ")}
                            </span>
                            {r.reason_tag && (
                              <span className="px-2 py-0.5 rounded-md bg-zinc-800 text-zinc-300 font-mono text-[10px]">
                                {r.reason_tag}
                              </span>
                            )}
                          </div>
                          {r.comment && <p className="text-zinc-300 italic">"{r.comment}"</p>}
                        </div>

                        {r.watch_ms > 0 && (
                          <span className="text-[11px] text-zinc-500 shrink-0">
                            Watched {Math.round(r.watch_ms / 1000)}s
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Survey Responses */}
              <div className="space-y-3 pt-4 border-t border-white/10">
                <h3 className="text-xs font-bold text-zinc-300 uppercase tracking-wider flex items-center gap-1.5">
                  <FileCheck className="w-3.5 h-3.5 text-purple-400" /> Exit Survey Feedback
                </h3>

                {!selectedSession.survey ? (
                  <p className="text-xs text-zinc-500 italic">Exit survey not yet completed by creator.</p>
                ) : (
                  <div className="space-y-3 text-xs">
                    <div className="p-3 rounded-xl bg-zinc-900/60 border border-white/5 space-y-1">
                      <span className="text-zinc-400 block font-semibold">Missing Feature for Immediate Post:</span>
                      <p className="text-zinc-200">{selectedSession.survey.missing_text || "—"}</p>
                    </div>

                    <div className="p-3 rounded-xl bg-zinc-900/60 border border-white/5 space-y-1">
                      <span className="text-zinc-400 block font-semibold">Current Workflow & Cost:</span>
                      <p className="text-zinc-200">
                        {selectedSession.survey.current_workflow_text || "—"} • Cost:{" "}
                        {selectedSession.survey.current_cost_text || "—"}
                      </p>
                    </div>

                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                      <div className="p-3 rounded-xl bg-zinc-900/60 border border-white/5">
                        <span className="text-[10px] text-zinc-500 uppercase block font-bold">Willingness to Pay</span>
                        <span className="text-sm font-bold text-purple-300 font-mono">
                          {selectedSession.survey.price_open_inr
                            ? `₹${selectedSession.survey.price_open_inr.toLocaleString()}/mo`
                            : "—"}
                        </span>
                      </div>

                      <div className="p-3 rounded-xl bg-zinc-900/60 border border-white/5">
                        <span className="text-[10px] text-zinc-500 uppercase block font-bold">Accepts ₹1,500/mo?</span>
                        <span className="text-sm font-bold text-white">
                          {selectedSession.survey.accepts_1500 === true ? (
                            <span className="text-emerald-400">Yes</span>
                          ) : selectedSession.survey.accepts_1500 === false ? (
                            <span className="text-rose-400">No</span>
                          ) : (
                            "—"
                          )}
                        </span>
                      </div>

                      <div className="p-3 rounded-xl bg-zinc-900/60 border border-white/5">
                        <span className="text-[10px] text-zinc-500 uppercase block font-bold">Upload Next Video?</span>
                        <span className="text-sm font-bold text-white capitalize">
                          {selectedSession.survey.would_upload_next || "—"}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="glass-panel p-12 rounded-3xl border border-white/5 text-center space-y-2">
              <p className="text-xs text-zinc-400">Select a creator session from the left to view detailed ratings.</p>
            </div>
          )}
        </div>
      </div>

      {/* Create Review Session Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="max-w-md w-full glass-panel p-6 rounded-3xl border border-white/10 space-y-5 animate-in zoom-in-95 duration-200">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <Users className="w-5 h-5 text-purple-400" /> Create Review Link
              </h2>
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="text-zinc-500 hover:text-white text-sm"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateSession} className="space-y-4 text-xs">
              <div className="space-y-1.5">
                <label className="font-bold text-zinc-300">Creator Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Aarav Sharma"
                  value={creatorName}
                  onChange={(e) => setCreatorName(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-white/10 text-white placeholder:text-zinc-600 focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="space-y-1.5">
                <label className="font-bold text-zinc-300">Creator Email (Optional)</label>
                <input
                  type="email"
                  placeholder="aarav@creator.test"
                  value={creatorEmail}
                  onChange={(e) => setCreatorEmail(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-white/10 text-white placeholder:text-zinc-600 focus:outline-none focus:border-purple-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="font-bold text-zinc-300">Expires in (Days)</label>
                  <input
                    type="number"
                    min="1"
                    max="90"
                    value={expiresInDays}
                    onChange={(e) => setExpiresInDays(parseInt(e.target.value) || 14)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-white/10 text-white font-mono"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="font-bold text-zinc-300">Top N Clips to Cut</label>
                  <input
                    type="number"
                    min="1"
                    max="30"
                    value={topN}
                    onChange={(e) => setTopN(parseInt(e.target.value) || 8)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-white/10 text-white font-mono"
                  />
                </div>
              </div>

              <div className="pt-3 flex items-center justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2.5 rounded-xl bg-zinc-800 text-zinc-300 font-bold hover:bg-zinc-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="px-5 py-2.5 rounded-xl bg-purple-600 hover:bg-purple-500 text-white font-bold flex items-center gap-1.5 disabled:opacity-50"
                >
                  {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                  <span>Generate Link</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
