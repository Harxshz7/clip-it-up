'use client';

import React, { useState } from 'react';
import { ClipMoment, Clip, VariantLength, FeedbackReasonTag } from '@clip-it-up/shared';

interface ClipCardProps {
  moment: ClipMoment;
  proxyUrl?: string | null;
  onSeek: (startMs: number, endMs: number) => void;
  onFeedback: (clipId: string, value: 'up' | 'down', reasonTag?: FeedbackReasonTag) => Promise<void>;
  onDeleteFeedback: (clipId: string) => Promise<void>;
  isPlaying?: boolean;
}

export const ClipCard: React.FC<ClipCardProps> = ({
  moment,
  proxyUrl,
  onSeek,
  onFeedback,
  onDeleteFeedback,
  isPlaying,
}) => {
  const [selectedVariantLength, setSelectedVariantLength] = useState<VariantLength>('auto');
  const [showTooltip, setShowTooltip] = useState(false);
  const [showReasonMenu, setShowReasonMenu] = useState<'up' | 'down' | null>(null);
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);

  // Find active variant or fallback to first
  const activeClip: Clip | undefined =
    moment.clips.find((c) => c.variant_length_s === selectedVariantLength) ||
    moment.clips[0] ||
    ({
      id: moment.id,
      moment_id: moment.id,
      video_id: moment.video_id,
      variant_length_s: 'auto',
      start_ms: moment.start_ms,
      end_ms: moment.end_ms,
      duration_seconds: moment.duration_seconds,
      hook_text: 'Top moment candidate',
      title: 'Top Candidate Clip',
      final_score: moment.final_score || 0.75,
      score_breakdown: {
        hook: 0.8,
        emotion: 0.7,
        coherence: 0.8,
        payoff: 0.75,
        novelty: 0.7,
        audio_energy: 0.65,
        laughter: 0.1,
        pause_penalty: 0.0,
        flag_penalty: 0.0,
      },
      reason: 'Identified strong narrative arc and hook.',
      model: 'claude-3-5-sonnet',
      prompt_version: 'v1',
      scorer_version: 'v1',
      created_at: moment.created_at,
    } as Clip);

  const scorePct = Math.round((activeClip.final_score || 0.0) * 100);
  const breakdown = activeClip.score_breakdown || {};
  const currentFeedback = activeClip.feedback?.value;

  const availableLengths: VariantLength[] = (['auto', '15', '30', '45', '60'] as VariantLength[]).filter(
    (len) => moment.clips.some((c) => c.variant_length_s === len) || len === 'auto'
  );

  const getScoreColor = (score: number) => {
    if (score >= 0.75) return 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30';
    if (score >= 0.55) return 'text-amber-400 bg-amber-500/10 border-amber-500/30';
    return 'text-purple-400 bg-purple-500/10 border-purple-500/30';
  };

  const handleFeedbackClick = async (val: 'up' | 'down') => {
    if (currentFeedback === val) {
      // Toggle off
      await onDeleteFeedback(activeClip.id);
      return;
    }
    if (val === 'down') {
      setShowReasonMenu('down');
    } else {
      setIsSubmittingFeedback(true);
      await onFeedback(activeClip.id, 'up');
      setIsSubmittingFeedback(false);
    }
  };

  const handleReasonSelect = async (reason: FeedbackReasonTag) => {
    setIsSubmittingFeedback(true);
    await onFeedback(activeClip.id, 'down', reason);
    setShowReasonMenu(null);
    setIsSubmittingFeedback(false);
  };

  return (
    <div
      className="group relative flex flex-col justify-between rounded-xl bg-[#111420]/90 border border-white/10 hover:border-purple-500/50 hover:shadow-[0_0_25px_rgba(168,85,247,0.15)] transition-all duration-300 p-5 backdrop-blur-md"
      id={`clip-card-${moment.id}`}
    >
      {/* Top Header: Rank & Score Badge with Tooltip */}
      <div>
        <div className="flex items-center justify-between gap-3 mb-3">
          <div className="flex items-center gap-2">
            {moment.rank ? (
              <span className="flex items-center justify-center w-6 h-6 rounded-full bg-purple-600/30 text-purple-300 font-bold text-xs border border-purple-500/40">
                #{moment.rank}
              </span>
            ) : null}
            <span className="text-xs font-mono text-zinc-400 bg-white/5 px-2 py-0.5 rounded">
              {(activeClip.start_ms / 1000).toFixed(1)}s - {(activeClip.end_ms / 1000).toFixed(1)}s
            </span>
            <span className="text-xs font-semibold text-zinc-300 bg-zinc-800/80 px-2 py-0.5 rounded-full border border-white/5">
              {activeClip.duration_seconds.toFixed(0)}s
            </span>
          </div>

          {/* Virality Score Badge & Tooltip Trigger */}
          <div className="relative">
            <button
              type="button"
              onMouseEnter={() => setShowTooltip(true)}
              onMouseLeave={() => setShowTooltip(false)}
              onClick={() => setShowTooltip(!showTooltip)}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-xs font-bold transition-transform hover:scale-105 ${getScoreColor(
                activeClip.final_score
              )}`}
            >
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
              </svg>
              <span>{scorePct}%</span>
            </button>

            {/* Score Breakdown Tooltip */}
            {showTooltip && (
              <div className="absolute right-0 top-8 z-30 w-64 p-3.5 rounded-xl bg-[#161a29] border border-purple-500/30 shadow-2xl backdrop-blur-xl text-xs space-y-2 animate-in fade-in zoom-in-95 duration-150">
                <div className="font-semibold text-zinc-200 border-b border-white/10 pb-1.5 flex justify-between">
                  <span>Score Breakdown</span>
                  <span className="text-purple-400 font-mono">{scorePct}/100</span>
                </div>

                <div className="space-y-1.5">
                  {[
                    { label: 'Hook Impact', val: breakdown.hook || 0.8 },
                    { label: 'Emotion', val: breakdown.emotion || 0.7 },
                    { label: 'Coherence', val: breakdown.coherence || 0.85 },
                    { label: 'Payoff / Punch', val: breakdown.payoff || 0.75 },
                    { label: 'Novelty', val: breakdown.novelty || 0.7 },
                    { label: 'Audio Energy', val: breakdown.audio_energy || 0.6 },
                    { label: 'Laughter', val: breakdown.laughter || 0.0 },
                  ].map((sig) => (
                    <div key={sig.label} className="flex items-center justify-between gap-2">
                      <span className="text-zinc-400 text-[11px] w-24 truncate">{sig.label}</span>
                      <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                        <div
                          className="h-full bg-gradient-to-r from-purple-500 to-indigo-400 rounded-full"
                          style={{ width: `${Math.round(sig.val * 100)}%` }}
                        />
                      </div>
                      <span className="font-mono text-zinc-300 text-[10px] w-7 text-right">
                        {Math.round(sig.val * 100)}%
                      </span>
                    </div>
                  ))}
                </div>

                {breakdown.flags && Object.values(breakdown.flags).some(Boolean) && (
                  <div className="pt-1.5 border-t border-white/10 flex flex-wrap gap-1">
                    {breakdown.flags.needs_context && (
                      <span className="px-1.5 py-0.5 bg-amber-500/20 text-amber-300 border border-amber-500/30 rounded text-[10px]">
                        Needs Context
                      </span>
                    )}
                    {breakdown.flags.off_topic && (
                      <span className="px-1.5 py-0.5 bg-red-500/20 text-red-300 border border-red-500/30 rounded text-[10px]">
                        Off Topic
                      </span>
                    )}
                    {breakdown.flags.profanity && (
                      <span className="px-1.5 py-0.5 bg-orange-500/20 text-orange-300 border border-orange-500/30 rounded text-[10px]">
                        Profanity
                      </span>
                    )}
                    {breakdown.flags.sensitive && (
                      <span className="px-1.5 py-0.5 bg-rose-500/20 text-rose-300 border border-rose-500/30 rounded text-[10px]">
                        Sensitive
                      </span>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Title */}
        <h3 className="font-semibold text-zinc-100 text-sm leading-snug line-clamp-2 mb-2 group-hover:text-purple-300 transition-colors">
          {activeClip.title || 'High Virality Moment'}
        </h3>

        {/* Hook Quote */}
        <div className="relative pl-3 border-l-2 border-purple-500/50 my-2.5">
          <p className="text-xs italic text-zinc-300 line-clamp-2">
            &ldquo;{activeClip.hook_text}&rdquo;
          </p>
        </div>

        {/* Why Chosen Reason */}
        <p className="text-[11px] text-zinc-400 line-clamp-2 mb-3">
          <span className="text-purple-400 font-medium">Why: </span>
          {activeClip.reason}
        </p>

        {/* Variant Switcher Tabs */}
        {availableLengths.length > 1 && (
          <div className="flex items-center gap-1 my-3 bg-zinc-900/90 p-1 rounded-lg border border-white/5">
            {availableLengths.map((len) => (
              <button
                key={len}
                type="button"
                onClick={() => setSelectedVariantLength(len)}
                className={`flex-1 py-1 text-[11px] font-medium rounded transition-all ${
                  selectedVariantLength === len
                    ? 'bg-purple-600 text-white shadow-sm'
                    : 'text-zinc-400 hover:text-zinc-200 hover:bg-white/5'
                }`}
              >
                {len === 'auto' ? 'Auto' : `${len}s`}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Card Footer: Preview Seek & Thumbs Feedback */}
      <div className="pt-3 border-t border-white/10 flex items-center justify-between gap-2 mt-auto">
        <button
          type="button"
          onClick={() => onSeek(activeClip.start_ms, activeClip.end_ms)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-purple-600/20 hover:bg-purple-600/40 text-purple-200 border border-purple-500/30 rounded-lg text-xs font-medium transition-all hover:scale-102"
        >
          <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M8 5v14l11-7z" />
          </svg>
          <span>Preview Range</span>
        </button>

        {/* Thumbs Feedback */}
        <div className="relative flex items-center gap-1">
          <button
            type="button"
            title="Thumbs Up"
            onClick={() => handleFeedbackClick('up')}
            disabled={isSubmittingFeedback}
            className={`p-1.5 rounded-lg border text-xs transition-colors ${
              currentFeedback === 'up'
                ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400'
                : 'bg-zinc-800/60 border-white/5 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700/60'
            }`}
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3" />
            </svg>
          </button>

          <button
            type="button"
            title="Thumbs Down"
            onClick={() => handleFeedbackClick('down')}
            disabled={isSubmittingFeedback}
            className={`p-1.5 rounded-lg border text-xs transition-colors ${
              currentFeedback === 'down'
                ? 'bg-rose-500/20 border-rose-500/50 text-rose-400'
                : 'bg-zinc-800/60 border-white/5 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700/60'
            }`}
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h3a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3" />
            </svg>
          </button>

          {/* Thumbs Down Reason Dropdown */}
          {showReasonMenu === 'down' && (
            <div className="absolute right-0 bottom-9 z-40 w-44 p-2 rounded-xl bg-[#161a29] border border-rose-500/30 shadow-2xl backdrop-blur-xl text-xs space-y-1">
              <div className="text-[11px] font-semibold text-zinc-300 px-2 py-1">Why not usable?</div>
              {[
                { tag: 'boring', label: 'Boring / Slow' },
                { tag: 'no_context', label: 'Missing Context' },
                { tag: 'bad_start', label: 'Bad Hook / Start' },
                { tag: 'bad_end', label: 'Cut Mid-Sentence' },
                { tag: 'off_topic', label: 'Off Topic' },
                { tag: 'other', label: 'Other Issue' },
              ].map(({ tag, label }) => (
                <button
                  key={tag}
                  type="button"
                  onClick={() => handleReasonSelect(tag as FeedbackReasonTag)}
                  className="w-full text-left px-2.5 py-1.5 rounded hover:bg-rose-500/20 text-zinc-300 hover:text-rose-200 text-[11px] transition-colors"
                >
                  {label}
                </button>
              ))}
              <button
                type="button"
                onClick={() => setShowReasonMenu(null)}
                className="w-full text-center text-[10px] text-zinc-500 hover:text-zinc-400 pt-1"
              >
                Cancel
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
