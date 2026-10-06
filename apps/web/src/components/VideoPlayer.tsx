"use client";

import React, { useRef, useEffect, useState, forwardRef, useImperativeHandle } from "react";
import { Play, Pause, RotateCcw, RotateCw, Volume2, VolumeX, Maximize, Settings } from "lucide-react";
import { formatDuration } from "@/lib/utils";

export interface VideoPlayerRef {
  seekTo: (seconds: number) => void;
  play: () => void;
  pause: () => void;
  togglePlay: () => void;
  getCurrentTime: () => number;
}

interface VideoPlayerProps {
  src: string;
  onTimeUpdate?: (currentMs: number, currentTimeSeconds: number) => void;
  onDurationChange?: (durationSeconds: number) => void;
  poster?: string;
  title?: string;
}

export const VideoPlayer = forwardRef<VideoPlayerRef, VideoPlayerProps>(
  ({ src, onTimeUpdate, onDurationChange, poster, title }, ref) => {
    const videoRef = useRef<HTMLVideoElement | null>(null);
    const containerRef = useRef<HTMLDivElement | null>(null);

    const [isPlaying, setIsPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [volume, setVolume] = useState(1);
    const [isMuted, setIsMuted] = useState(false);
    const [playbackRate, setPlaybackRate] = useState(1);
    const [showControls, setShowControls] = useState(true);

    useImperativeHandle(ref, () => ({
      seekTo: (seconds: number) => {
        if (videoRef.current) {
          const clamped = Math.max(0, Math.min(seconds, duration || 999999));
          videoRef.current.currentTime = clamped;
          setCurrentTime(clamped);
          onTimeUpdate?.(Math.round(clamped * 1000), clamped);
        }
      },
      play: () => {
        videoRef.current?.play().catch(() => {});
      },
      pause: () => {
        videoRef.current?.pause();
      },
      togglePlay: () => {
        if (videoRef.current) {
          if (videoRef.current.paused) {
            videoRef.current.play().catch(() => {});
          } else {
            videoRef.current.pause();
          }
        }
      },
      getCurrentTime: () => videoRef.current?.currentTime || 0,
    }));

    // Keyboard controls (Space, J/K/L, Left/Right arrows)
    useEffect(() => {
      const handleKeyDown = (e: KeyboardEvent) => {
        // Ignore shortcuts if typing in an input/textarea/contenteditable
        const target = e.target as HTMLElement | null;
        if (
          target &&
          (target.tagName === "INPUT" ||
            target.tagName === "TEXTAREA" ||
            target.isContentEditable)
        ) {
          return;
        }

        const video = videoRef.current;
        if (!video) return;

        switch (e.key) {
          case " ":
            e.preventDefault();
            if (video.paused) video.play().catch(() => {});
            else video.pause();
            break;
          case "k":
          case "K":
            e.preventDefault();
            if (video.paused) video.play().catch(() => {});
            else video.pause();
            break;
          case "j":
          case "J":
            e.preventDefault();
            video.currentTime = Math.max(0, video.currentTime - 10);
            break;
          case "l":
          case "L":
            e.preventDefault();
            video.currentTime = Math.min(video.duration || 999999, video.currentTime + 10);
            break;
          case "ArrowLeft":
            e.preventDefault();
            video.currentTime = Math.max(0, video.currentTime - 5);
            break;
          case "ArrowRight":
            e.preventDefault();
            video.currentTime = Math.min(video.duration || 999999, video.currentTime + 5);
            break;
        }
      };

      window.addEventListener("keydown", handleKeyDown);
      return () => window.removeEventListener("keydown", handleKeyDown);
    }, [duration]);

    const handleTimeUpdate = () => {
      if (videoRef.current) {
        const cur = videoRef.current.currentTime;
        setCurrentTime(cur);
        onTimeUpdate?.(Math.round(cur * 1000), cur);
      }
    };

    const handleLoadedMetadata = () => {
      if (videoRef.current) {
        const dur = videoRef.current.duration || 0;
        setDuration(dur);
        onDurationChange?.(dur);
      }
    };

    const handlePlayPause = () => {
      if (!videoRef.current) return;
      if (videoRef.current.paused) {
        videoRef.current.play().catch(() => {});
      } else {
        videoRef.current.pause();
      }
    };

    const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
      const targetTime = parseFloat(e.target.value);
      if (videoRef.current) {
        videoRef.current.currentTime = targetTime;
        setCurrentTime(targetTime);
        onTimeUpdate?.(Math.round(targetTime * 1000), targetTime);
      }
    };

    const handleVolumeToggle = () => {
      if (!videoRef.current) return;
      if (isMuted) {
        videoRef.current.muted = false;
        setIsMuted(false);
      } else {
        videoRef.current.muted = true;
        setIsMuted(true);
      }
    };

    const handleRateChange = (rate: number) => {
      if (!videoRef.current) return;
      videoRef.current.playbackRate = rate;
      setPlaybackRate(rate);
    };

    const toggleFullscreen = () => {
      if (!containerRef.current) return;
      if (!document.fullscreenElement) {
        containerRef.current.requestFullscreen().catch(() => {});
      } else {
        document.exitFullscreen().catch(() => {});
      }
    };

    return (
      <div
        ref={containerRef}
        className="relative group rounded-2xl overflow-hidden bg-black border border-white/10 shadow-2xl flex flex-col justify-between aspect-video select-none"
        onMouseEnter={() => setShowControls(true)}
        onMouseLeave={() => isPlaying && setShowControls(false)}
      >
        <video
          ref={videoRef}
          src={src}
          poster={poster}
          className="w-full h-full object-contain cursor-pointer"
          playsInline
          onClick={handlePlayPause}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={handleLoadedMetadata}
        />

        {/* Center Big Play Button Overlay on Pause */}
        {!isPlaying && (
          <button
            onClick={handlePlayPause}
            className="absolute inset-0 m-auto w-16 h-16 rounded-full bg-purple-600/90 hover:bg-purple-500 text-white flex items-center justify-center shadow-lg transition-transform transform active:scale-95 hover:scale-105 backdrop-blur-sm"
            aria-label="Play video"
          >
            <Play className="w-8 h-8 fill-current translate-x-0.5" />
          </button>
        )}

        {/* Custom Video Control Overlay */}
        <div
          className={`absolute bottom-0 inset-x-0 bg-gradient-to-t from-black/90 via-black/50 to-transparent p-4 transition-opacity duration-300 ${
            showControls || !isPlaying ? "opacity-100" : "opacity-0 pointer-events-none"
          }`}
        >
          {/* Seek Bar */}
          <div className="relative flex items-center mb-3">
            <input
              type="range"
              min={0}
              max={duration || 100}
              step={0.1}
              value={currentTime}
              onChange={handleSeek}
              className="w-full h-1.5 bg-white/20 rounded-lg appearance-none cursor-pointer accent-purple-500 hover:h-2 transition-all"
            />
          </div>

          <div className="flex items-center justify-between text-white text-xs">
            <div className="flex items-center gap-3">
              {/* Play/Pause */}
              <button
                onClick={handlePlayPause}
                className="p-1.5 rounded-lg hover:bg-white/10 transition-colors"
                title={isPlaying ? "Pause (Space/K)" : "Play (Space/K)"}
              >
                {isPlaying ? <Pause className="w-5 h-5 fill-current" /> : <Play className="w-5 h-5 fill-current" />}
              </button>

              {/* Seek -5s */}
              <button
                onClick={() => {
                  if (videoRef.current) videoRef.current.currentTime = Math.max(0, currentTime - 5);
                }}
                className="p-1 rounded-lg hover:bg-white/10 transition-colors text-zinc-300 hover:text-white"
                title="Rewind 5s (Left Arrow)"
              >
                <RotateCcw className="w-4 h-4" />
              </button>

              {/* Seek +5s */}
              <button
                onClick={() => {
                  if (videoRef.current) videoRef.current.currentTime = Math.min(duration, currentTime + 5);
                }}
                className="p-1 rounded-lg hover:bg-white/10 transition-colors text-zinc-300 hover:text-white"
                title="Forward 5s (Right Arrow)"
              >
                <RotateCw className="w-4 h-4" />
              </button>

              {/* Mute/Volume */}
              <button
                onClick={handleVolumeToggle}
                className="p-1 rounded-lg hover:bg-white/10 transition-colors text-zinc-300 hover:text-white"
                title="Mute / Unmute"
              >
                {isMuted ? <VolumeX className="w-4 h-4 text-red-400" /> : <Volume2 className="w-4 h-4" />}
              </button>

              {/* Timestamp */}
              <span className="font-mono text-zinc-300 select-none">
                {formatDuration(currentTime)} / {formatDuration(duration)}
              </span>
            </div>

            <div className="flex items-center gap-3">
              {/* Playback speed selector */}
              <div className="flex items-center gap-1 bg-white/10 rounded-lg px-2 py-0.5">
                {[1, 1.25, 1.5, 2].map((rate) => (
                  <button
                    key={rate}
                    onClick={() => handleRateChange(rate)}
                    className={`px-1.5 py-0.5 rounded text-[11px] font-medium transition-colors ${
                      playbackRate === rate ? "bg-purple-600 text-white" : "text-zinc-400 hover:text-white"
                    }`}
                  >
                    {rate}x
                  </button>
                ))}
              </div>

              {/* Fullscreen */}
              <button
                onClick={toggleFullscreen}
                className="p-1.5 rounded-lg hover:bg-white/10 transition-colors text-zinc-300 hover:text-white"
                title="Fullscreen"
              >
                <Maximize className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }
);

VideoPlayer.displayName = "VideoPlayer";
