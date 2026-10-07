'use client';

import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { ClipMoment, Clip, VideoClipsResponse, FeedbackReasonTag, ClipScoredEventPayload } from '@clip-it-up/shared';
import { ClipCard } from './ClipCard';

interface ClipsDeckProps {
  videoId: string;
  proxyUrl?: string | null;
  onSeek: (startMs: number, endMs: number) => void;
  isJobRunning?: boolean;
}

export const ClipsDeck: React.FC<ClipsDeckProps> = ({
  videoId,
  proxyUrl,
  onSeek,
  isJobRunning,
}) => {
  const [moments, setMoments] = useState<ClipMoment[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [sortBy, setSortBy] = useState<'score' | 'time' | 'rank'>('score');
  const [minScore, setMinScore] = useState<number>(0);
  const [isRescoring, setIsRescoring] = useState(false);
  const [streamingNotice, setStreamingNotice] = useState<string | null>(null);

  const fetchClips = useCallback(async () => {
    try {
      const res = await fetch(`/api/videos/${videoId}/clips?sort=${sortBy}`, {
        headers: { 'Content-Type': 'application/json' },
      });
      if (res.ok) {
        const data: VideoClipsResponse = await res.json();
        setMoments(data.moments || []);
      }
    } catch (err) {
      console.error('Failed to fetch clips:', err);
    } finally {
      setLoading(false);
    }
  }, [videoId, sortBy]);

  useEffect(() => {
    fetchClips();
  }, [fetchClips]);

  // Listen for real-time clip_scored SSE events emitted by the backend
  useEffect(() => {
    const handleClipScoredEvent = (e: CustomEvent<ClipScoredEventPayload>) => {
      const payload = e.detail;
      if (payload && payload.video_id === videoId) {
        setStreamingNotice(`Scored ${payload.scored_count} of ${payload.total_count} candidate clips...`);
        fetchClips();
      }
    };

    window.addEventListener('clip_scored' as any, handleClipScoredEvent as any);
    return () => {
      window.removeEventListener('clip_scored' as any, handleClipScoredEvent as any);
    };
  }, [videoId, fetchClips]);

  const handleFeedback = async (clipId: string, value: 'up' | 'down', reasonTag?: FeedbackReasonTag) => {
    try {
      await fetch(`/api/clips/${clipId}/feedback`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value, reason_tag: reasonTag }),
      });
      fetchClips();
    } catch (err) {
      console.error('Failed to submit feedback:', err);
    }
  };

  const handleDeleteFeedback = async (clipId: string) => {
    try {
      await fetch(`/api/clips/${clipId}/feedback`, {
        method: 'DELETE',
      });
      fetchClips();
    } catch (err) {
      console.error('Failed to delete feedback:', err);
    }
  };

  const handleRescore = async () => {
    setIsRescoring(true);
    try {
      const res = await fetch(`/api/videos/${videoId}/rescore`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (res.ok) {
        setStreamingNotice('Rescoring enqueued... Analyzing viral hooks.');
      }
    } catch (err) {
      console.error('Failed to trigger rescore:', err);
    } finally {
      setIsRescoring(false);
    }
  };

  const filteredMoments = useMemo(() => {
    return moments.filter((m) => {
      if (filterStatus !== 'all' && m.status !== filterStatus) return false;
      if (minScore > 0 && (m.final_score || 0) < minScore) return false;
      return true;
    });
  }, [moments, filterStatus, minScore]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center p-16 space-y-4">
        <div className="w-10 h-10 border-2 border-purple-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-zinc-400 text-sm">Discovering high-retention clips...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Control Bar: Filters, Sort, Rescore, and Status Banner */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 rounded-xl bg-[#111420]/80 border border-white/10 backdrop-blur-md">
        <div className="flex flex-wrap items-center gap-3">
          {/* Status Filter */}
          <div className="flex items-center gap-1 bg-zinc-900/90 p-1 rounded-lg border border-white/5 text-xs">
            {['all', 'selected', 'scored'].map((st) => (
              <button
                key={st}
                type="button"
                onClick={() => setFilterStatus(st)}
                className={`px-3 py-1 rounded capitalize font-medium transition-colors ${
                  filterStatus === st ? 'bg-purple-600 text-white' : 'text-zinc-400 hover:text-zinc-200'
                }`}
              >
                {st}
              </button>
            ))}
          </div>

          {/* Sort By */}
          <div className="flex items-center gap-2 text-xs text-zinc-400">
            <span>Sort:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="bg-zinc-900 text-zinc-200 border border-white/10 rounded-lg px-2.5 py-1 focus:outline-none focus:border-purple-500"
            >
              <option value="score">Virality Score</option>
              <option value="time">Chronological</option>
              <option value="rank">Rank Order</option>
            </select>
          </div>

          {/* Min Score Filter */}
          <div className="flex items-center gap-2 text-xs text-zinc-400">
            <span>Min Score:</span>
            <select
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              className="bg-zinc-900 text-zinc-200 border border-white/10 rounded-lg px-2.5 py-1 focus:outline-none focus:border-purple-500"
            >
              <option value={0}>All Scores</option>
              <option value={0.6}>&gt; 60%</option>
              <option value={0.75}>&gt; 75% Top Tier</option>
              <option value={0.85}>&gt; 85% Viral</option>
            </select>
          </div>
        </div>

        {/* Right side: Rescore Button & Stats */}
        <div className="flex items-center gap-3">
          <span className="text-xs text-zinc-400 font-mono">
            {filteredMoments.length} {filteredMoments.length === 1 ? 'clip' : 'clips'} found
          </span>
          <button
            type="button"
            onClick={handleRescore}
            disabled={isRescoring}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white rounded-lg text-xs font-semibold shadow-md transition-transform hover:scale-102 disabled:opacity-50"
          >
            <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
            </svg>
            <span>{isRescoring ? 'Rescoring...' : 'Rescore Video'}</span>
          </button>
        </div>
      </div>

      {/* Streaming / Analysis Notice */}
      {(isJobRunning || streamingNotice) && (
        <div className="flex items-center gap-3 p-3.5 rounded-xl bg-purple-950/40 border border-purple-500/30 text-xs text-purple-200 animate-pulse">
          <div className="w-2 h-2 rounded-full bg-purple-400 animate-ping" />
          <span>{streamingNotice || 'Pipeline running: Analyzing audio acoustics & scoring viral hooks...'}</span>
        </div>
      )}

      {/* Empty State */}
      {filteredMoments.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-16 rounded-2xl bg-[#111420]/40 border border-white/5 text-center space-y-3">
          <div className="p-4 rounded-full bg-purple-600/10 text-purple-400 border border-purple-500/20">
            <svg className="w-8 h-8" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18" />
              <line x1="7" y1="2" x2="7" y2="22" />
              <line x1="17" y1="2" x2="17" y2="22" />
              <line x1="2" y1="12" x2="22" y2="12" />
            </svg>
          </div>
          <h4 className="text-zinc-200 font-semibold">No clips found matching your filters</h4>
          <p className="text-zinc-400 text-xs max-w-sm">
            Try adjusting your score filter or click &quot;Rescore Video&quot; to recalculate clips with updated model weights.
          </p>
        </div>
      ) : (
        /* Clips Grid */
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredMoments.map((moment) => (
            <ClipCard
              key={moment.id}
              moment={moment}
              proxyUrl={proxyUrl}
              onSeek={onSeek}
              onFeedback={handleFeedback}
              onDeleteFeedback={handleDeleteFeedback}
            />
          ))}
        </div>
      )}
    </div>
  );
};
