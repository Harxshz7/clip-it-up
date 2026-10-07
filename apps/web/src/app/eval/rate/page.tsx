"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { EvalVideo, Clip } from "@clip-it-up/shared";
import { VideoPlayer, VideoPlayerRef } from "@/components/VideoPlayer";
import { ArrowLeft, Star, Download, Upload, CheckCircle2, User, Sparkles } from "lucide-react";

interface EvalClipItem {
  id: string;
  video_slug: string;
  start_ms: number;
  end_ms: number;
  hook_text: string;
  title: string;
  proxy_url?: string;
  current_rating?: number;
  current_comment?: string;
}

export default function EvalRatePage() {
  const [raterId, setRaterId] = useState<string>("rater_1");
  const [videos, setVideos] = useState<EvalVideo[]>([]);
  const [selectedSlug, setSelectedSlug] = useState<string>("");
  const [clips, setClips] = useState<EvalClipItem[]>([]);
  const [currentIndex, setCurrentIndex] = useState<number>(0);
  const [score, setScore] = useState<number>(0);
  const [comment, setComment] = useState<string>("");
  const [submittedMessage, setSubmittedMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const playerRef = useRef<VideoPlayerRef | null>(null);

  useEffect(() => {
    async function loadEvalVideos() {
      try {
        setLoading(true);
        const res = await fetch("/api/eval/videos");
        if (res.ok) {
          const data = await res.json();
          setVideos(data || []);
          if (data.length > 0) {
            setSelectedSlug(data[0].slug);
          }
        }
      } catch (err) {
        console.error("Failed to load eval videos:", err);
      } finally {
        setLoading(false);
      }
    }
    loadEvalVideos();
  }, []);

  // Fetch candidate clips for selected slug
  useEffect(() => {
    async function loadClipsForVideo() {
      if (!selectedSlug) return;
      try {
        const res = await fetch(`/api/eval/ratings?video_slug=${selectedSlug}&rater_id=${raterId}`);
        const existingRatings = res.ok ? await res.json() : [];
        const ratingMap = new Map<string, { score: number; comment?: string }>();
        for (const r of existingRatings) {
          ratingMap.set(`${r.start_ms}_${r.end_ms}`, { score: r.score, comment: r.comment });
        }

        // Mock/starter eval clips for benchmarking
        const starterClips: EvalClipItem[] = [
          {
            id: "eval-c1",
            video_slug: selectedSlug,
            start_ms: 12000,
            end_ms: 42000,
            hook_text: "Why do 90% of early-stage startups fail before finding product-market fit?",
            title: "The Truth About Early Stage Startup Failure",
          },
          {
            id: "eval-c2",
            video_slug: selectedSlug,
            start_ms: 75000,
            end_ms: 115000,
            hook_text: "Nobody talks about this, but your biggest bottleneck is always communication.",
            title: "The Hidden Bottleneck Every Team Faces",
          },
          {
            id: "eval-c3",
            video_slug: selectedSlug,
            start_ms: 160000,
            end_ms: 195000,
            hook_text: "When I started coding 10 years ago, I thought faster typing meant better software.",
            title: "10 Years of Engineering Lessons",
          },
        ];

        // Enrich with existing ratings
        const enriched = starterClips.map((c) => {
          const r = ratingMap.get(`${c.start_ms}_${c.end_ms}`);
          return {
            ...c,
            current_rating: r?.score,
            current_comment: r?.comment,
          };
        });

        setClips(enriched);
        setCurrentIndex(0);
        if (enriched.length > 0) {
          setScore(enriched[0].current_rating || 0);
          setComment(enriched[0].current_comment || "");
        }
      } catch (err) {
        console.error("Failed to load clips:", err);
      }
    }
    loadClipsForVideo();
  }, [selectedSlug, raterId]);

  const currentClip = clips[currentIndex];

  const handleScoreSubmit = async (selectedScore: number) => {
    if (!currentClip) return;
    setScore(selectedScore);
    try {
      await fetch("/api/eval/rate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          video_slug: currentClip.video_slug,
          start_ms: currentClip.start_ms,
          end_ms: currentClip.end_ms,
          rater_id: raterId,
          score: selectedScore,
          comment: comment.trim() || undefined,
        }),
      });

      setSubmittedMessage(`Saved score ${selectedScore}/5 for ${raterId}`);
      setTimeout(() => setSubmittedMessage(null), 2500);

      // Advance to next clip automatically
      if (currentIndex < clips.length - 1) {
        const nextIdx = currentIndex + 1;
        setCurrentIndex(nextIdx);
        setScore(clips[nextIdx].current_rating || 0);
        setComment(clips[nextIdx].current_comment || "");
      }
    } catch (err) {
      console.error("Failed to submit rating:", err);
    }
  };

  const handleExportCsv = async () => {
    window.open("/api/eval/ratings/export", "_blank");
  };

  return (
    <div className="max-w-5xl mx-auto p-4 sm:p-6 lg:p-8 space-y-6">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-white/10 pb-4">
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard"
            className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-300 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <h1 className="text-lg font-bold text-white flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-purple-400" />
              Clip Quality Rater Tool (Blind Evaluation)
            </h1>
            <p className="text-xs text-zinc-400">
              Rate clip standalone retention, hook impact, and payoff. AI scores are hidden.
            </p>
          </div>
        </div>

        {/* Rater Selector & CSV Export */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 bg-zinc-900 border border-white/10 rounded-xl px-3 py-1.5 text-xs text-zinc-300">
            <User className="w-3.5 h-3.5 text-purple-400" />
            <span>Rater:</span>
            <select
              value={raterId}
              onChange={(e) => setRaterId(e.target.value)}
              className="bg-transparent font-semibold text-purple-300 focus:outline-none"
            >
              <option value="rater_1" className="bg-zinc-900">Rater 1 (Lead)</option>
              <option value="rater_2" className="bg-zinc-900">Rater 2</option>
              <option value="rater_3" className="bg-zinc-900">Rater 3</option>
            </select>
          </div>

          <button
            type="button"
            onClick={handleExportCsv}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-xs text-zinc-200 border border-white/10 transition-colors"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export CSV</span>
          </button>
        </div>
      </div>

      {/* Video Slug Selector & Progress */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl bg-[#111420]/90 border border-white/10">
        <div className="flex items-center gap-2 text-xs">
          <span className="text-zinc-400 font-medium">Dataset Video:</span>
          <select
            value={selectedSlug}
            onChange={(e) => setSelectedSlug(e.target.value)}
            className="bg-zinc-900 text-zinc-200 border border-white/10 rounded-lg px-3 py-1.5 font-mono text-xs focus:outline-none focus:border-purple-500"
          >
            {videos.length > 0 ? (
              videos.map((v) => (
                <option key={v.slug} value={v.slug}>
                  {v.title} ({v.slug})
                </option>
              ))
            ) : (
              <option value="podcast_lex_clip1">Lex Fridman Interview (demo)</option>
            )}
          </select>
        </div>

        {clips.length > 0 && (
          <div className="flex items-center gap-2 text-xs text-zinc-400 font-mono">
            <span>Clip {currentIndex + 1} of {clips.length}</span>
            <div className="flex gap-1">
              <button
                type="button"
                disabled={currentIndex === 0}
                onClick={() => {
                  const prev = currentIndex - 1;
                  setCurrentIndex(prev);
                  setScore(clips[prev].current_rating || 0);
                  setComment(clips[prev].current_comment || "");
                }}
                className="px-2 py-0.5 rounded bg-zinc-800 hover:bg-zinc-700 disabled:opacity-40"
              >
                &larr; Prev
              </button>
              <button
                type="button"
                disabled={currentIndex === clips.length - 1}
                onClick={() => {
                  const next = currentIndex + 1;
                  setCurrentIndex(next);
                  setScore(clips[next].current_rating || 0);
                  setComment(clips[next].current_comment || "");
                }}
                className="px-2 py-0.5 rounded bg-zinc-800 hover:bg-zinc-700 disabled:opacity-40"
              >
                Next &rarr;
              </button>
            </div>
          </div>
        )}
      </div>

      {currentClip ? (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          {/* Left: Video Preview & Clip Details */}
          <div className="lg:col-span-7 space-y-4">
            <div className="p-5 rounded-2xl bg-[#111420]/90 border border-white/10 space-y-3">
              <div className="flex items-center justify-between text-xs text-zinc-400 font-mono">
                <span>Time Range: {(currentClip.start_ms / 1000).toFixed(1)}s &ndash; {(currentClip.end_ms / 1000).toFixed(1)}s</span>
                <span className="px-2 py-0.5 rounded bg-purple-900/40 text-purple-300 font-semibold">
                  {((currentClip.end_ms - currentClip.start_ms) / 1000).toFixed(0)}s Duration
                </span>
              </div>

              <h2 className="text-base font-bold text-white">{currentClip.title}</h2>

              <div className="p-3 rounded-xl bg-zinc-900/80 border border-purple-500/20 italic text-xs text-zinc-300">
                &ldquo;{currentClip.hook_text}&rdquo;
              </div>

              {/* Video Player */}
              <div className="pt-2">
                <VideoPlayer
                  ref={playerRef}
                  src={currentClip.proxy_url || ""}
                  poster=""
                  title={currentClip.title}
                />
              </div>
            </div>
          </div>

          {/* Right: Rubric & 1-5 Rating Interface */}
          <div className="lg:col-span-5 space-y-4">
            <div className="p-5 rounded-2xl bg-[#111420]/90 border border-white/10 space-y-4">
              <h3 className="font-semibold text-zinc-200 text-sm">Rating Rubric (&ldquo;Usable&rdquo; Rule: &ge; 4/5)</h3>
              <div className="text-[11px] text-zinc-400 space-y-2 leading-relaxed">
                <p><b className="text-emerald-400">5 - Exceptional:</b> Instant hook, clear resolution, zero missing context, ready to post.</p>
                <p><b className="text-emerald-300">4 - Usable:</b> Good hook, coherent message, would post with minor trim.</p>
                <p><b className="text-amber-400">3 - Borderline:</b> Interesting topic but slow hook or weak ending.</p>
                <p><b className="text-rose-400">2 - Poor:</b> Missing critical context, dangling pronouns, or unengaging.</p>
                <p><b className="text-rose-500">1 - Unusable:</b> Incoherent cut, mid-word cutoff, or pure filler.</p>
              </div>

              {/* Rating 1-5 Buttons */}
              <div className="pt-2 space-y-2">
                <label className="text-xs font-semibold text-zinc-300 block">Your Score (1 to 5):</label>
                <div className="grid grid-cols-5 gap-2">
                  {[1, 2, 3, 4, 5].map((s) => (
                    <button
                      key={s}
                      type="button"
                      onClick={() => handleScoreSubmit(s)}
                      className={`py-3 rounded-xl font-bold text-sm transition-all hover:scale-105 flex flex-col items-center gap-1 ${
                        score === s
                          ? "bg-purple-600 text-white ring-2 ring-purple-400 shadow-lg shadow-purple-600/30"
                          : "bg-zinc-800 text-zinc-300 hover:bg-zinc-700"
                      }`}
                    >
                      <Star className={`w-4 h-4 ${score === s ? "fill-white" : ""}`} />
                      <span>{s}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Optional Comment */}
              <div className="space-y-1.5 pt-2">
                <label className="text-xs font-medium text-zinc-400">Rater Notes / Why (Optional):</label>
                <textarea
                  rows={3}
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="e.g., Hook starts well at 14s, ending cleanly wraps the startup point..."
                  className="w-full bg-zinc-900 border border-white/10 rounded-xl p-3 text-xs text-zinc-200 placeholder:text-zinc-600 focus:outline-none focus:border-purple-500"
                />
              </div>

              {submittedMessage && (
                <div className="p-2.5 rounded-lg bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 text-xs flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 shrink-0" />
                  <span>{submittedMessage}</span>
                </div>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="p-12 text-center text-zinc-500">No clips loaded for evaluation.</div>
      )}
    </div>
  );
}
