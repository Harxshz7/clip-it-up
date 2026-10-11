import type { KeepSegment } from './types.js';

export interface Removal {
  id?: string;
  start_ms: number;
  end_ms: number;
  kind?: string;
  text?: string | null;
  enabled?: boolean;
}

export class EditDecisionList {
  readonly clip_start_ms: number;
  readonly clip_end_ms: number;
  readonly removals: Removal[];
  readonly keep_segments: KeepSegment[];
  readonly total_src_duration_ms: number;
  readonly total_out_duration_ms: number;

  constructor(
    clip_start_ms: number,
    clip_end_ms: number,
    removals: Removal[],
    keep_segments: KeepSegment[],
    total_src_duration_ms: number,
    total_out_duration_ms: number
  ) {
    this.clip_start_ms = clip_start_ms;
    this.clip_end_ms = clip_end_ms;
    this.removals = removals;
    this.keep_segments = keep_segments;
    this.total_src_duration_ms = total_src_duration_ms;
    this.total_out_duration_ms = total_out_duration_ms;
  }

  get removed_duration_ms(): number {
    return this.total_src_duration_ms - this.total_out_duration_ms;
  }

  static create(
    clip_start_ms: number,
    clip_end_ms: number,
    removals?: Removal[] | null
  ): EditDecisionList {
    if (clip_start_ms < 0) {
      throw new Error(`clip_start_ms must be >= 0, got ${clip_start_ms}`);
    }
    if (clip_end_ms <= clip_start_ms) {
      throw new Error(
        `clip_end_ms (${clip_end_ms}) must be > clip_start_ms (${clip_start_ms})`
      );
    }

    const total_src_dur = clip_end_ms - clip_start_ms;
    const raw_removals: Removal[] = [];

    if (removals) {
      for (const r of removals) {
        if (r.enabled === false) {
          continue;
        }
        const clamped_start = Math.max(
          clip_start_ms,
          Math.min(clip_end_ms, Math.round(r.start_ms))
        );
        const clamped_end = Math.max(
          clip_start_ms,
          Math.min(clip_end_ms, Math.round(r.end_ms))
        );
        if (clamped_end > clamped_start) {
          raw_removals.push({
            id: r.id,
            start_ms: clamped_start,
            end_ms: clamped_end,
            kind: r.kind || 'manual',
            text: r.text || null,
            enabled: true,
          });
        }
      }
    }

    // Sort by start_ms, then end_ms
    raw_removals.sort((a, b) => {
      if (a.start_ms !== b.start_ms) return a.start_ms - b.start_ms;
      return a.end_ms - b.end_ms;
    });

    // Merge overlapping / touching removals
    const merged_removals: Removal[] = [];
    for (const r of raw_removals) {
      if (merged_removals.length === 0) {
        merged_removals.push({ ...r });
        continue;
      }

      const last = merged_removals[merged_removals.length - 1];
      if (r.start_ms <= last.end_ms) {
        // Merge
        const new_end = Math.max(last.end_ms, r.end_ms);
        const combined_kind = last.kind === r.kind ? last.kind : 'mixed';
        let combined_text: string | null = null;
        if (last.text && r.text) {
          combined_text = `${last.text} ${r.text}`;
        } else {
          combined_text = last.text || r.text || null;
        }
        last.end_ms = new_end;
        last.kind = combined_kind;
        last.text = combined_text;
      } else {
        merged_removals.push({ ...r });
      }
    }

    // Compute keep segments
    const keep_segments: KeepSegment[] = [];
    let curr_src = clip_start_ms;
    let curr_out = 0;

    for (const r of merged_removals) {
      if (r.start_ms > curr_src) {
        const seg_dur = r.start_ms - curr_src;
        keep_segments.push({
          src_start_ms: curr_src,
          src_end_ms: r.start_ms,
          out_start_ms: curr_out,
          out_end_ms: curr_out + seg_dur,
        });
        curr_out += seg_dur;
      }
      curr_src = Math.max(curr_src, r.end_ms);
    }

    if (curr_src < clip_end_ms) {
      const seg_dur = clip_end_ms - curr_src;
      keep_segments.push({
        src_start_ms: curr_src,
        src_end_ms: clip_end_ms,
        out_start_ms: curr_out,
        out_end_ms: curr_out + seg_dur,
      });
      curr_out += seg_dur;
    }

    return new EditDecisionList(
      clip_start_ms,
      clip_end_ms,
      merged_removals,
      keep_segments,
      total_src_dur,
      curr_out
    );
  }

  src_to_out(src_ms: number): number | null {
    if (src_ms < this.clip_start_ms || src_ms > this.clip_end_ms) {
      return null;
    }
    if (src_ms === this.clip_end_ms) {
      return this.total_out_duration_ms;
    }
    for (const seg of this.keep_segments) {
      if (seg.src_start_ms <= src_ms && src_ms < seg.src_end_ms) {
        return seg.out_start_ms + (src_ms - seg.src_start_ms);
      }
    }
    return null;
  }

  src_to_out_clamped(src_ms: number): number {
    if (this.keep_segments.length === 0) return 0;
    if (src_ms <= this.clip_start_ms) return 0;
    if (src_ms >= this.clip_end_ms) return this.total_out_duration_ms;

    for (const seg of this.keep_segments) {
      if (src_ms < seg.src_start_ms) {
        return seg.out_start_ms;
      }
      if (seg.src_start_ms <= src_ms && src_ms <= seg.src_end_ms) {
        return seg.out_start_ms + (src_ms - seg.src_start_ms);
      }
    }
    return this.total_out_duration_ms;
  }

  out_to_src(out_ms: number): number {
    if (this.keep_segments.length === 0) return this.clip_start_ms;
    if (out_ms <= 0) return this.keep_segments[0].src_start_ms;
    if (out_ms >= this.total_out_duration_ms) {
      return this.keep_segments[this.keep_segments.length - 1].src_end_ms;
    }

    for (let i = 0; i < this.keep_segments.length; i++) {
      const seg = this.keep_segments[i];
      if (i === this.keep_segments.length - 1) {
        if (seg.out_start_ms <= out_ms && out_ms <= seg.out_end_ms) {
          return seg.src_start_ms + (out_ms - seg.out_start_ms);
        }
      } else {
        if (seg.out_start_ms <= out_ms && out_ms < seg.out_end_ms) {
          return seg.src_start_ms + (out_ms - seg.out_start_ms);
        }
      }
    }
    return this.keep_segments[this.keep_segments.length - 1].src_end_ms;
  }

  remap_words<T extends { start_ms: number; end_ms: number; deleted?: boolean }>(
    words: T[]
  ): (T & { src_start_ms: number; src_end_ms: number })[] {
    const remapped: (T & { src_start_ms: number; src_end_ms: number })[] = [];

    for (const w of words) {
      const w_start = Math.round(w.start_ms);
      const w_end = Math.round(w.end_ms);
      if (w.deleted || w_end <= this.clip_start_ms || w_start >= this.clip_end_ms) {
        continue;
      }

      let is_removed = false;
      for (const r of this.removals) {
        if (r.start_ms <= w_start && w_end <= r.end_ms) {
          is_removed = true;
          break;
        }
      }
      if (is_removed) continue;

      const out_start = this.src_to_out_clamped(w_start);
      const out_end = this.src_to_out_clamped(w_end);

      if (out_end > out_start) {
        remapped.push({
          ...w,
          start_ms: out_start,
          end_ms: out_end,
          src_start_ms: w_start,
          src_end_ms: w_end,
        });
      }
    }

    return remapped;
  }

  remap_crop_path(crop_path: {
    keyframes?: Array<{ t_ms: number; [key: string]: any }>;
    [key: string]: any;
  }): {
    keyframes: Array<{ t_ms: number; [key: string]: any }>;
    duration_ms: number;
    [key: string]: any;
  } {
    const raw_kfs = crop_path.keyframes || [];
    if (raw_kfs.length === 0) {
      return {
        ...crop_path,
        keyframes: [],
        duration_ms: this.total_out_duration_ms,
      };
    }

    const first_t = raw_kfs[0].t_ms;
    const is_relative = first_t < this.clip_start_ms && raw_kfs.length > 0;

    const remapped_kfs: Array<{ t_ms: number; [key: string]: any }> = [];
    const seen_times = new Set<number>();

    for (const kf of raw_kfs) {
      const src_t = is_relative ? this.clip_start_ms + kf.t_ms : kf.t_ms;
      const out_t = this.src_to_out_clamped(src_t);

      if (!seen_times.has(out_t)) {
        seen_times.add(out_t);
        remapped_kfs.push({
          ...kf,
          t_ms: out_t,
        });
      }
    }

    remapped_kfs.sort((a, b) => a.t_ms - b.t_ms);

    if (remapped_kfs.length > 0 && remapped_kfs[0].t_ms > 0) {
      remapped_kfs.unshift({
        ...remapped_kfs[0],
        t_ms: 0,
      });
    }

    if (
      remapped_kfs.length > 0 &&
      remapped_kfs[remapped_kfs.length - 1].t_ms < this.total_out_duration_ms
    ) {
      remapped_kfs.push({
        ...remapped_kfs[remapped_kfs.length - 1],
        t_ms: this.total_out_duration_ms,
      });
    }

    return {
      ...crop_path,
      keyframes: remapped_kfs,
      duration_ms: this.total_out_duration_ms,
    };
  }

  to_dict() {
    return {
      clip_start_ms: this.clip_start_ms,
      clip_end_ms: this.clip_end_ms,
      total_src_duration_ms: this.total_src_duration_ms,
      total_out_duration_ms: this.total_out_duration_ms,
      removed_duration_ms: this.removed_duration_ms,
      removals: this.removals,
      keep_segments: this.keep_segments,
    };
  }
}
