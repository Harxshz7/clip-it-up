"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import {
  ReviewSessionPublic,
  ReviewClipPublic,
  ReviewVerdict,
  ReviewReasonTag,
  UploadIntent,
} from "@clip-it-up/shared";
import { api } from "@/lib/api";
import {
  Sparkles,
  Play,
  Pause,
  RotateCcw,
  Volume2,
  VolumeX,
  Maximize,
  Download,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  Check,
  Loader2,
  Film,
  Send,
  ArrowRight,
  Smartphone,
  Tv,
} from "lucide-react";

const REASON_TAGS: { id: ReviewReasonTag; label: string }[] = [
  { id: "bad_start", label: "Bad start / Hook cut" },
  { id: "bad_end", label: "Bad ending / Cutoff" },
  { id: "no_context", label: "Needs context" },
  { id: "boring", label: "Boring / Low energy" },
  { id: "off_topic", label: "Off topic / Rambling" },
  { id: "too_long", label: "Too long" },
  { id: "too_short", label: "Too short" },
  { id: "other", label: "Other" },
];

export default function PublicReviewPage() {
  const params = useParams();
  const token = params.token as string;

  const [session, setSession] = useState<ReviewSessionPublic | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Workflow steps: "intro" | "clips" | "survey" | "thankyou"
  const [step, setStep] = useState<"intro" | "clips" | "survey" | "thankyou">("intro");

  // Clips rating state
  const [currentClipIndex, setCurrentClipIndex] = useState(0);
  const [aspectRatio, setAspectRatio] = useState<"vertical_center" | "horizontal">("vertical_center");
  const [ratingsMap, setRatingsMap] = useState<
    Record<
      string,
      {
        verdict: ReviewVerdict;
        reason_tag?: ReviewReasonTag | null;
        comment: string;
        watch_ms: number;
      }
    >
  >({});
  const [savingClip, setSavingClip] = useState(false);
  const [lastSavedTime, setLastSavedTime] = useState<number | null>(null);

  // Video playback state
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isMuted, setIsMuted] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const watchTimeTrackerRef = useRef<{ startMs: number; totalMs: number }>({ startMs: 0, totalMs: 0 });

  // Survey state
  const [surveyMissing, setSurveyMissing] = useState("");
  const [surveyWorkflow, setSurveyWorkflow] = useState("");
  const [surveyCost, setSurveyCost] = useState("");
  const [surveyPriceOpen, setSurveyPriceOpen] = useState<string>("");
  const [surveyAccepts1500, setSurveyAccepts1500] = useState<boolean | null>(null);
  const [surveyAccepts4000, setSurveyAccepts4000] = useState<boolean | null>(null);
  const [surveyWouldUpload, setSurveyWouldUpload] = useState<UploadIntent | "">("");
  const [surveyTimeframe, setSurveyTimeframe] = useState("");
  const [surveyEmailOptin, setSurveyEmailOptin] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  // Fetch review session
  const fetchSession = useCallback(async () => {
    try {
      setLoading(true);
      const data = await api.getPublicReviewSession(token);
      setSession(data);

      // Pre-fill ratings
      const initialMap: typeof ratingsMap = {};
      data.clips.forEach((clip) => {
        if (clip.rating) {
          initialMap[clip.clip_id] = {
            verdict: clip.rating.verdict,
            reason_tag: clip.rating.reason_tag as ReviewReasonTag,
            comment: clip.rating.comment || "",
            watch_ms: clip.rating.watch_ms || 0,
          };
        }
      });
      setRatingsMap(initialMap);

      // Pre-fill survey if exists
      if (data.survey) {
        setSurveyMissing(data.survey.missing_text || "");
        setSurveyWorkflow(data.survey.current_workflow_text || "");
        setSurveyCost(data.survey.current_cost_text || "");
        if (data.survey.price_open_inr) setSurveyPriceOpen(data.survey.price_open_inr.toString());
        setSurveyAccepts1500(data.survey.accepts_1500 ?? null);
        setSurveyAccepts4000(data.survey.accepts_4000 ?? null);
        setSurveyWouldUpload(data.survey.would_upload_next || "");
        setSurveyTimeframe(data.survey.upload_timeframe || "");
        setSurveyEmailOptin(data.survey.email_optin);
      }

      if (data.status === "submitted") {
        setStep("thankyou");
      }
    } catch (err: any) {
      setError(err?.message || "Invalid or expired review link.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    if (token) fetchSession();
  }, [token, fetchSession]);

  // Current clip
  const clips = session?.clips || [];
  const currentClip: ReviewClipPublic | undefined = clips[currentClipIndex];
  const currentRating = currentClip ? ratingsMap[currentClip.clip_id] : undefined;

  // Auto-save rating change
  const saveRating = useCallback(
    async (
      clipId: string,
      verdict: ReviewVerdict,
      reasonTag?: ReviewReasonTag | null,
      comment?: string,
      watchMs?: number
    ) => {
      try {
        setSavingClip(true);
        await api.upsertReviewRating(token, clipId, {
          verdict,
          reason_tag: reasonTag || null,
          comment: comment || "",
          watch_ms: watchMs || 0,
        });
        setLastSavedTime(Date.now());
      } catch (err) {
        console.error("Failed to auto-save rating:", err);
      } finally {
        setSavingClip(false);
      }
    },
    [token]
  );

  const handleVerdictSelect = (verdict: ReviewVerdict) => {
    if (!currentClip) return;
    const clipId = currentClip.clip_id;
    const existing = ratingsMap[clipId] || { comment: "", watch_ms: 0 };
    const updated = {
      ...existing,
      verdict,
      reason_tag: verdict === "post_as_is" ? null : existing.reason_tag,
    };
    setRatingsMap((prev) => ({ ...prev, [clipId]: updated }));
    saveRating(clipId, verdict, updated.reason_tag, updated.comment, updated.watch_ms);
  };

  const handleReasonSelect = (reason: ReviewReasonTag) => {
    if (!currentClip) return;
    const clipId = currentClip.clip_id;
    const existing = ratingsMap[clipId];
    if (!existing) return;
    const newReason = existing.reason_tag === reason ? null : reason;
    const updated = { ...existing, reason_tag: newReason };
    setRatingsMap((prev) => ({ ...prev, [clipId]: updated }));
    saveRating(clipId, existing.verdict, newReason, existing.comment, existing.watch_ms);
  };

  const handleCommentChange = (comment: string) => {
    if (!currentClip) return;
    const clipId = currentClip.clip_id;
    const existing = ratingsMap[clipId];
    if (!existing) return;
    const updated = { ...existing, comment };
    setRatingsMap((prev) => ({ ...prev, [clipId]: updated }));
  };

  const handleCommentBlur = () => {
    if (!currentClip) return;
    const clipId = currentClip.clip_id;
    const existing = ratingsMap[clipId];
    if (existing) {
      saveRating(clipId, existing.verdict, existing.reason_tag, existing.comment, existing.watch_ms);
    }
  };

  // Video playback listeners
  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
    } else {
      videoRef.current.play();
    }
  };

  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    setCurrentTime(videoRef.current.currentTime);
    // Accumulate watch time
    if (isPlaying && currentClip) {
      const clipId = currentClip.clip_id;
      const prevMs = ratingsMap[clipId]?.watch_ms || 0;
      setRatingsMap((prev) => ({
        ...prev,
        [clipId]: {
          ...(prev[clipId] || { verdict: "post_as_is", comment: "" }),
          watch_ms: prevMs + 250,
        },
      }));
    }
  };

  // Submit survey and finalize session
  const handleSubmitSurvey = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSubmitting(true);
      await api.upsertReviewSurvey(token, {
        missing_text: surveyMissing || null,
        current_workflow_text: surveyWorkflow || null,
        current_cost_text: surveyCost || null,
        price_open_inr: surveyPriceOpen ? parseFloat(surveyPriceOpen) : null,
        accepts_1500: surveyAccepts1500,
        accepts_4000: surveyAccepts4000,
        would_upload_next: (surveyWouldUpload as UploadIntent) || null,
        upload_timeframe: surveyTimeframe || null,
        email_optin: surveyEmailOptin,
      });

      await api.submitReviewSession(token);
      setStep("thankyou");
    } catch (err: any) {
      alert(err?.message || "Failed to submit survey. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  // Render Loading / Error
  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 text-white flex flex-col items-center justify-center p-4">
        <Loader2 className="w-10 h-10 animate-spin text-purple-400 mb-4" />
        <p className="text-zinc-400 text-sm">Loading creator review kit...</p>
      </div>
    );
  }

  if (error || !session) {
    return (
      <div className="min-h-screen bg-zinc-950 text-white flex flex-col items-center justify-center p-4">
        <div className="max-w-md w-full glass-panel p-8 rounded-2xl border border-red-500/20 text-center space-y-4">
          <div className="h-14 w-14 rounded-full bg-red-950/80 border border-red-800/50 flex items-center justify-center mx-auto text-red-400">
            <XCircle className="w-7 h-7" />
          </div>
          <h1 className="text-xl font-bold">Review Link Unavailable</h1>
          <p className="text-xs text-zinc-400">
            {error || "This review session is expired or does not exist."}
          </p>
        </div>
      </div>
    );
  }

  // Active video source for current clip
  const currentVideoSrc =
    currentClip?.video_urls?.[aspectRatio] ||
    currentClip?.video_urls?.vertical_center ||
    currentClip?.video_urls?.horizontal ||
    "";

  return (
    <div className="min-h-screen bg-[#09090b] text-zinc-100 flex flex-col font-sans selection:bg-purple-500/30">
      {/* Top Header Bar */}
      <header className="border-b border-white/10 bg-zinc-950/80 backdrop-blur-md sticky top-0 z-40">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center text-white shadow-md shadow-purple-500/20">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <span className="text-sm font-bold tracking-tight text-white">clip-it-up</span>
              <span className="ml-2 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-300 border border-purple-500/30">
                Creator Reality Check
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3 text-xs text-zinc-400">
            <span className="hidden sm:inline">Reviewing for:</span>
            <span className="font-semibold text-zinc-200 truncate max-w-[180px]">
              {session.creator_name}
            </span>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-5xl w-full mx-auto px-4 py-6 sm:py-8">
        {/* ================================================================= */}
        {/* STEP 1: INTRO */}
        {/* ================================================================= */}
        {step === "intro" && (
          <div className="max-w-2xl mx-auto space-y-6 animate-in fade-in duration-300">
            {/* Crude Disclaimer Banner */}
            <div className="p-4 rounded-2xl bg-amber-500/10 border border-amber-500/30 text-amber-200 flex items-start gap-3">
              <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              <div className="text-xs space-y-1">
                <p className="font-bold text-amber-300 text-sm">Crucial Note: Raw Preview Cuts</p>
                <p className="text-zinc-300 leading-relaxed">
                  These clips are raw AI candidate selections: <strong>no auto-framing, subtitles, captions, or fine editing yet.</strong>
                  Please judge <em>only</em> whether the underlying moment and hook are worth posting to Shorts/Reels.
                </p>
              </div>
            </div>

            {/* Video & Session Card */}
            <div className="glass-panel p-6 rounded-3xl border border-white/10 space-y-6">
              <div className="space-y-2">
                <span className="text-xs font-semibold text-purple-400 uppercase tracking-wider">
                  Video Review Task
                </span>
                <h1 className="text-xl sm:text-2xl font-black text-white">
                  {session.video_title}
                </h1>
                <p className="text-xs sm:text-sm text-zinc-400 leading-relaxed">
                  Hi {session.creator_name}, our AI extracted the top <strong>{clips.length} moments</strong> from your video.
                  You will review each clip one by one, tell us if you&apos;d post it, and share a 2-minute feedback survey at the end.
                </p>
              </div>

              {/* Privacy Consent Notice */}
              <div className="p-3.5 rounded-xl bg-zinc-900/60 border border-white/5 flex items-center gap-2.5 text-xs text-zinc-400">
                <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>{session.consent_notice}</span>
              </div>

              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => setStep("clips")}
                  className="w-full py-3.5 px-6 rounded-2xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold text-sm shadow-xl shadow-purple-600/25 flex items-center justify-center gap-2 transition-all transform hover:scale-[1.01]"
                >
                  <span>Start Clip Review ({clips.length} Clips)</span>
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* STEP 2: CLIPS PLAYER & RATING */}
        {/* ================================================================= */}
        {step === "clips" && currentClip && (
          <div className="space-y-6 animate-in fade-in duration-300">
            {/* Progress Bar & Counter */}
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-white bg-white/10 px-3 py-1 rounded-full">
                  Clip {currentClipIndex + 1} of {clips.length}
                </span>
                {savingClip && (
                  <span className="text-[11px] text-zinc-400 flex items-center gap-1">
                    <Loader2 className="w-3 h-3 animate-spin text-purple-400" /> Saving...
                  </span>
                )}
                {!savingClip && lastSavedTime && (
                  <span className="text-[11px] text-emerald-400 flex items-center gap-1">
                    <Check className="w-3 h-3" /> Saved
                  </span>
                )}
              </div>

              {/* Aspect Ratio Preview Toggle */}
              <div className="flex items-center bg-zinc-900/90 border border-white/10 rounded-xl p-0.5">
                <button
                  type="button"
                  onClick={() => setAspectRatio("vertical_center")}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
                    aspectRatio === "vertical_center"
                      ? "bg-purple-600 text-white shadow-sm"
                      : "text-zinc-400 hover:text-white"
                  }`}
                >
                  <Smartphone className="w-3.5 h-3.5" />
                  <span>9:16 Vertical</span>
                </button>
                <button
                  type="button"
                  onClick={() => setAspectRatio("horizontal")}
                  className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium transition-colors ${
                    aspectRatio === "horizontal"
                      ? "bg-purple-600 text-white shadow-sm"
                      : "text-zinc-400 hover:text-white"
                  }`}
                >
                  <Tv className="w-3.5 h-3.5" />
                  <span>16:9 Original</span>
                </button>
              </div>
            </div>

            {/* Main Interactive Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              {/* Left: Video Player */}
              <div className="lg:col-span-6 flex flex-col items-center">
                <div
                  className={`relative rounded-2xl overflow-hidden bg-black border border-white/10 shadow-2xl flex items-center justify-center ${
                    aspectRatio === "vertical_center"
                      ? "w-full max-w-[320px] aspect-[9/16]"
                      : "w-full aspect-video"
                  }`}
                >
                  {/* Crude Watermark Overlay */}
                  <div className="absolute top-3 right-3 z-20 px-2 py-0.5 rounded bg-black/60 backdrop-blur-md text-[10px] font-mono tracking-widest text-amber-300/90 border border-amber-500/30 uppercase">
                    Preview Crude Cut
                  </div>

                  <video
                    ref={videoRef}
                    key={currentVideoSrc}
                    src={currentVideoSrc}
                    playsInline
                    loop
                    className="w-full h-full object-contain cursor-pointer"
                    onClick={togglePlay}
                    onPlay={() => setIsPlaying(true)}
                    onPause={() => setIsPlaying(false)}
                    onTimeUpdate={handleTimeUpdate}
                    onLoadedMetadata={() => {
                      if (videoRef.current) setDuration(videoRef.current.duration);
                    }}
                  />

                  {/* Play/Pause Center Overlay */}
                  {!isPlaying && (
                    <button
                      type="button"
                      onClick={togglePlay}
                      className="absolute inset-0 m-auto h-14 w-14 rounded-full bg-purple-600/90 text-white flex items-center justify-center shadow-xl backdrop-blur-md hover:scale-110 transition-transform z-10"
                    >
                      <Play className="w-6 h-6 ml-0.5 fill-white" />
                    </button>
                  )}

                  {/* Bottom Video Controls */}
                  <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/80 via-black/40 to-transparent p-3 flex items-center justify-between text-xs text-white z-20">
                    <div className="flex items-center gap-2">
                      <button type="button" onClick={togglePlay} className="p-1 hover:text-purple-400">
                        {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4 fill-white" />}
                      </button>
                      <span className="font-mono text-[11px]">
                        {Math.floor(currentTime)}s / {Math.floor(duration || currentClip.duration_seconds)}s
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          if (videoRef.current) {
                            videoRef.current.muted = !isMuted;
                            setIsMuted(!isMuted);
                          }
                        }}
                        className="p-1 hover:text-purple-400"
                      >
                        {isMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
                      </button>
                      {currentVideoSrc && (
                        <a
                          href={currentVideoSrc}
                          download={`clip_${currentClip.clip_id}_${aspectRatio}.mp4`}
                          target="_blank"
                          rel="noreferrer"
                          className="p-1 hover:text-purple-400 flex items-center gap-1 text-[11px]"
                          title="Download crude clip"
                        >
                          <Download className="w-3.5 h-3.5" />
                        </a>
                      )}
                    </div>
                  </div>
                </div>

                <p className="text-[11px] text-zinc-500 mt-2 text-center">
                  Click video to play/pause. Spacebar toggles playback.
                </p>
              </div>

              {/* Right: Clip Details & Verdict Buttons */}
              <div className="lg:col-span-6 space-y-5">
                {/* Title and Hook */}
                <div className="glass-panel p-5 rounded-2xl border border-white/10 space-y-3">
                  <div>
                    <span className="text-[11px] font-semibold text-purple-400 uppercase tracking-wider">
                      Moment #{currentClip.rank || currentClipIndex + 1}
                    </span>
                    <h2 className="text-lg font-bold text-white mt-0.5">{currentClip.title}</h2>
                  </div>

                  <div className="p-3 rounded-xl bg-white/5 border border-white/5 text-xs text-zinc-300">
                    <span className="font-semibold text-purple-300">AI Hook:</span> &ldquo;{currentClip.hook_text}&rdquo;
                  </div>

                  {currentClip.why_chosen && (
                    <div className="p-3 rounded-xl bg-purple-950/30 border border-purple-800/30 text-xs text-purple-200">
                      <span className="font-semibold text-purple-400">Why Selected:</span> {currentClip.why_chosen}
                    </div>
                  )}
                </div>

                {/* Big Verdict Decision Buttons */}
                <div className="space-y-3">
                  <label className="text-xs font-bold text-zinc-300 uppercase tracking-wider">
                    Would you post this moment to Shorts / Reels?
                  </label>

                  <div className="grid grid-cols-3 gap-2.5">
                    {/* Post As Is */}
                    <button
                      type="button"
                      onClick={() => handleVerdictSelect("post_as_is")}
                      className={`p-3.5 rounded-2xl border flex flex-col items-center justify-center gap-1.5 font-bold text-xs transition-all ${
                        currentRating?.verdict === "post_as_is"
                          ? "bg-emerald-600 text-white border-emerald-400 shadow-lg shadow-emerald-600/30 scale-[1.02]"
                          : "bg-zinc-900/80 text-zinc-300 border-white/10 hover:border-emerald-500/50 hover:bg-emerald-950/30"
                      }`}
                    >
                      <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                      <span>Post as is</span>
                    </button>

                    {/* Post With Edits */}
                    <button
                      type="button"
                      onClick={() => handleVerdictSelect("post_with_edits")}
                      className={`p-3.5 rounded-2xl border flex flex-col items-center justify-center gap-1.5 font-bold text-xs transition-all ${
                        currentRating?.verdict === "post_with_edits"
                          ? "bg-amber-600 text-white border-amber-400 shadow-lg shadow-amber-600/30 scale-[1.02]"
                          : "bg-zinc-900/80 text-zinc-300 border-white/10 hover:border-amber-500/50 hover:bg-amber-950/30"
                      }`}
                    >
                      <AlertTriangle className="w-5 h-5 text-amber-400" />
                      <span>Post w/ edits</span>
                    </button>

                    {/* No */}
                    <button
                      type="button"
                      onClick={() => handleVerdictSelect("no")}
                      className={`p-3.5 rounded-2xl border flex flex-col items-center justify-center gap-1.5 font-bold text-xs transition-all ${
                        currentRating?.verdict === "no"
                          ? "bg-rose-600 text-white border-rose-400 shadow-lg shadow-rose-600/30 scale-[1.02]"
                          : "bg-zinc-900/80 text-zinc-300 border-white/10 hover:border-rose-500/50 hover:bg-rose-950/30"
                      }`}
                    >
                      <XCircle className="w-5 h-5 text-rose-400" />
                      <span>No</span>
                    </button>
                  </div>
                </div>

                {/* Reason Tag Chips (Shown when 'Post with edits' or 'No' is selected) */}
                {currentRating && (currentRating.verdict === "post_with_edits" || currentRating.verdict === "no") && (
                  <div className="glass-panel p-4 rounded-2xl border border-white/10 space-y-2.5 animate-in fade-in">
                    <label className="text-xs font-semibold text-zinc-300 flex items-center justify-between">
                      <span>What&apos;s the main issue? (Select reason)</span>
                    </label>

                    <div className="flex flex-wrap gap-1.5">
                      {REASON_TAGS.map((tag) => (
                        <button
                          key={tag.id}
                          type="button"
                          onClick={() => handleReasonSelect(tag.id)}
                          className={`px-3 py-1.5 rounded-xl text-xs font-medium transition-all ${
                            currentRating.reason_tag === tag.id
                              ? "bg-purple-600 text-white shadow-md shadow-purple-600/30"
                              : "bg-zinc-800 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700"
                          }`}
                        >
                          {tag.label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {/* Optional Comment Input */}
                {currentRating && (
                  <div className="space-y-1.5">
                    <label className="text-[11px] font-medium text-zinc-400">
                      Optional creator note or edit instruction:
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. Cut first 2 seconds, punch in at 0:15..."
                      value={currentRating.comment || ""}
                      onChange={(e) => handleCommentChange(e.target.value)}
                      onBlur={handleCommentBlur}
                      className="w-full px-3.5 py-2.5 rounded-xl bg-zinc-900 border border-white/10 text-xs text-white placeholder:text-zinc-600 focus:outline-none focus:border-purple-500"
                    />
                  </div>
                )}

                {/* Navigation Buttons: Previous / Next / Go to Survey */}
                <div className="flex items-center justify-between pt-4 border-t border-white/10">
                  <button
                    type="button"
                    disabled={currentClipIndex === 0}
                    onClick={() => {
                      if (currentClipIndex > 0) setCurrentClipIndex(currentClipIndex - 1);
                    }}
                    className="px-4 py-2 rounded-xl bg-zinc-900 border border-white/10 text-xs font-semibold text-zinc-300 hover:bg-zinc-800 disabled:opacity-30 disabled:cursor-not-allowed flex items-center gap-1.5"
                  >
                    <ChevronLeft className="w-4 h-4" /> Previous
                  </button>

                  {currentClipIndex < clips.length - 1 ? (
                    <button
                      type="button"
                      onClick={() => setCurrentClipIndex(currentClipIndex + 1)}
                      className="px-5 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-xs font-bold text-white shadow-md shadow-purple-600/20 flex items-center gap-1.5"
                    >
                      Next Clip <ChevronRight className="w-4 h-4" />
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setStep("survey")}
                      className="px-5 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-emerald-600 hover:opacity-90 text-xs font-bold text-white shadow-lg shadow-purple-600/25 flex items-center gap-1.5"
                    >
                      Continue to Survey ({Object.keys(ratingsMap).length}/{clips.length} Rated) <ArrowRight className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ================================================================= */}
        {/* STEP 3: EXIT SURVEY */}
        {/* ================================================================= */}
        {step === "survey" && (
          <form onSubmit={handleSubmitSurvey} className="max-w-2xl mx-auto space-y-6 animate-in fade-in duration-300">
            <div className="text-center space-y-2">
              <span className="text-xs font-bold text-purple-400 uppercase tracking-wider">
                Step 2 of 2: Reality Check Survey
              </span>
              <h1 className="text-xl sm:text-2xl font-black text-white">Almost Done! Help Us Price & Build</h1>
              <p className="text-xs text-zinc-400">
                Your answers directly decide which features we ship next and our pricing tiers.
              </p>
            </div>

            <div className="glass-panel p-6 rounded-3xl border border-white/10 space-y-5 text-xs">
              {/* Question 1: Missing Features */}
              <div className="space-y-1.5">
                <label className="font-bold text-zinc-200">
                  1. What missing feature would make these clips 100% ready to publish immediately?
                </label>
                <textarea
                  rows={2}
                  required
                  placeholder="e.g. Dynamic karaoke subtitles, face zoom-ins, background music..."
                  value={surveyMissing}
                  onChange={(e) => setSurveyMissing(e.target.value)}
                  className="w-full p-3 rounded-xl bg-zinc-900 border border-white/10 text-white placeholder:text-zinc-600 focus:outline-none focus:border-purple-500"
                />
              </div>

              {/* Question 2: Current Workflow */}
              <div className="space-y-1.5">
                <label className="font-bold text-zinc-200">
                  2. How do you create short-form clips today? (Tools, editor, agency)
                </label>
                <textarea
                  rows={2}
                  placeholder="e.g. InShot on iPhone, CapCut, freelance editor on Upwork..."
                  value={surveyWorkflow}
                  onChange={(e) => setSurveyWorkflow(e.target.value)}
                  className="w-full p-3 rounded-xl bg-zinc-900 border border-white/10 text-white placeholder:text-zinc-600 focus:outline-none focus:border-purple-500"
                />
              </div>

              {/* Question 3: Current Cost / Time */}
              <div className="space-y-1.5">
                <label className="font-bold text-zinc-200">
                  3. Roughly how much time or money do you spend on shorts per month?
                </label>
                <input
                  type="text"
                  placeholder="e.g. 8 hours every weekend or ₹10,000/month to an editor"
                  value={surveyCost}
                  onChange={(e) => setSurveyCost(e.target.value)}
                  className="w-full p-3 rounded-xl bg-zinc-900 border border-white/10 text-white placeholder:text-zinc-600 focus:outline-none focus:border-purple-500"
                />
              </div>

              {/* Question 4: Open Price */}
              <div className="space-y-1.5 pt-2 border-t border-white/10">
                <label className="font-bold text-zinc-200">
                  4. What is the maximum you would pay per month for an AI tool that gives you 15 polished viral clips per video?
                </label>
                <div className="relative">
                  <span className="absolute left-3.5 top-3 text-zinc-400 font-bold">₹</span>
                  <input
                    type="number"
                    min="0"
                    step="100"
                    placeholder="2500"
                    value={surveyPriceOpen}
                    onChange={(e) => setSurveyPriceOpen(e.target.value)}
                    className="w-full pl-8 pr-4 py-2.5 rounded-xl bg-zinc-900 border border-white/10 text-white font-mono placeholder:text-zinc-600 focus:outline-none focus:border-purple-500"
                  />
                </div>
              </div>

              {/* Question 5: Willingness at ₹1,500 and ₹4,000 */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="p-3.5 rounded-2xl bg-zinc-900/60 border border-white/10 space-y-2">
                  <span className="font-semibold text-zinc-300">Would you subscribe at ₹1,500/month?</span>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setSurveyAccepts1500(true)}
                      className={`flex-1 py-1.5 rounded-xl font-bold transition-all ${
                        surveyAccepts1500 === true ? "bg-emerald-600 text-white" : "bg-zinc-800 text-zinc-400"
                      }`}
                    >
                      Yes
                    </button>
                    <button
                      type="button"
                      onClick={() => setSurveyAccepts1500(false)}
                      className={`flex-1 py-1.5 rounded-xl font-bold transition-all ${
                        surveyAccepts1500 === false ? "bg-rose-600 text-white" : "bg-zinc-800 text-zinc-400"
                      }`}
                    >
                      No
                    </button>
                  </div>
                </div>

                <div className="p-3.5 rounded-2xl bg-zinc-900/60 border border-white/10 space-y-2">
                  <span className="font-semibold text-zinc-300">Would you subscribe at ₹4,000/month?</span>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      onClick={() => setSurveyAccepts4000(true)}
                      className={`flex-1 py-1.5 rounded-xl font-bold transition-all ${
                        surveyAccepts4000 === true ? "bg-emerald-600 text-white" : "bg-zinc-800 text-zinc-400"
                      }`}
                    >
                      Yes
                    </button>
                    <button
                      type="button"
                      onClick={() => setSurveyAccepts4000(false)}
                      className={`flex-1 py-1.5 rounded-xl font-bold transition-all ${
                        surveyAccepts4000 === false ? "bg-rose-600 text-white" : "bg-zinc-800 text-zinc-400"
                      }`}
                    >
                      No
                    </button>
                  </div>
                </div>
              </div>

              {/* Question 6: Next Video Upload Intent */}
              <div className="space-y-1.5 pt-2 border-t border-white/10">
                <label className="font-bold text-zinc-200">
                  5. Would you upload your next full video here to generate clips?
                </label>
                <div className="grid grid-cols-3 gap-2">
                  {(["yes", "maybe", "no"] as UploadIntent[]).map((opt) => (
                    <button
                      key={opt}
                      type="button"
                      onClick={() => setSurveyWouldUpload(opt)}
                      className={`py-2 rounded-xl capitalize font-bold transition-all ${
                        surveyWouldUpload === opt
                          ? "bg-purple-600 text-white shadow-md shadow-purple-600/30"
                          : "bg-zinc-900 text-zinc-400 border border-white/10"
                      }`}
                    >
                      {opt}
                    </button>
                  ))}
                </div>

                {surveyWouldUpload === "yes" && (
                  <input
                    type="text"
                    placeholder="When is your next video dropping? (e.g. this Friday, next Tuesday)"
                    value={surveyTimeframe}
                    onChange={(e) => setSurveyTimeframe(e.target.value)}
                    className="w-full mt-2 p-3 rounded-xl bg-zinc-900 border border-white/10 text-white placeholder:text-zinc-600"
                  />
                )}
              </div>

              {/* Email Opt-in */}
              <div className="pt-2">
                <label className="flex items-center gap-2.5 cursor-pointer text-zinc-300">
                  <input
                    type="checkbox"
                    checked={surveyEmailOptin}
                    onChange={(e) => setSurveyEmailOptin(e.target.checked)}
                    className="rounded border-zinc-700 text-purple-600 focus:ring-purple-500"
                  />
                  <span>Email me early access and processed vertical clips when ready</span>
                </label>
              </div>

              <div className="pt-4">
                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full py-3.5 px-6 rounded-2xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-bold text-sm shadow-xl shadow-purple-600/25 flex items-center justify-center gap-2 transition-all disabled:opacity-50"
                >
                  {submitting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" /> Submitting...
                    </>
                  ) : (
                    <>
                      <Send className="w-4 h-4" /> Submit Feedback & Complete Review
                    </>
                  )}
                </button>
              </div>
            </div>
          </form>
        )}

        {/* ================================================================= */}
        {/* STEP 4: THANK YOU */}
        {/* ================================================================= */}
        {step === "thankyou" && (
          <div className="max-w-md mx-auto text-center space-y-6 py-10 animate-in fade-in duration-300">
            <div className="h-16 w-16 rounded-3xl bg-emerald-500/20 border border-emerald-500/30 text-emerald-400 flex items-center justify-center mx-auto shadow-xl shadow-emerald-500/10">
              <CheckCircle2 className="w-9 h-9" />
            </div>

            <div className="space-y-2">
              <h1 className="text-2xl font-black text-white">Thank You, {session.creator_name}!</h1>
              <p className="text-xs text-zinc-400 leading-relaxed">
                Your ratings and feedback have been recorded. You are directly shaping the next generation of AI short-form editing.
              </p>
            </div>

            <div className="glass-panel p-4 rounded-2xl border border-white/10 text-xs text-zinc-300 space-y-2 text-left">
              <div className="flex justify-between">
                <span className="text-zinc-500">Video</span>
                <span className="font-semibold text-white truncate max-w-[200px]">{session.video_title}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Clips Reviewed</span>
                <span className="font-semibold text-white">{clips.length} moments</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Status</span>
                <span className="font-semibold text-emerald-400">Review Submitted</span>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
