"""Edit Decision List (EDL) and Timeline Mapping.

Pure, deterministic module that maps source video time to rendered output timeline.
Handles arbitrary silence and filler cuts, maintains exact A/V alignment,
and provides bidirectional time remapping for captions, crop keyframes, and audio.
"""
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class Removal:
    """A time interval cut out from the source video."""
    start_ms: int
    end_ms: int
    kind: str = "manual"  # filler | silence | manual
    text: str | None = None

    def __post_init__(self):
        if self.start_ms > self.end_ms:
            raise ValueError(f"Invalid removal interval: start_ms ({self.start_ms}) > end_ms ({self.end_ms})")

    @property
    def duration_ms(self) -> int:
        return max(0, self.end_ms - self.start_ms)


@dataclass(frozen=True)
class KeepSegment:
    """A contiguous segment preserved from the source video onto the output timeline."""
    src_start_ms: int
    src_end_ms: int
    out_start_ms: int
    out_end_ms: int

    def __post_init__(self):
        src_dur = self.src_end_ms - self.src_start_ms
        out_dur = self.out_end_ms - self.out_start_ms
        if src_dur != out_dur:
            raise ValueError(f"KeepSegment duration mismatch: src {src_dur}ms != out {out_dur}ms")
        if src_dur < 0:
            raise ValueError(f"KeepSegment duration negative: {src_dur}ms")

    @property
    def duration_ms(self) -> int:
        return self.src_end_ms - self.src_start_ms


@dataclass
class EditDecisionList:
    """
    Immutable representation of an edit decision list for a clip.
    Transforms (clip_range + removals) into a list of keep segments and
    provides deterministic bidirectional time mapping.
    """
    clip_start_ms: int
    clip_end_ms: int
    removals: list[Removal] = field(default_factory=list)
    keep_segments: list[KeepSegment] = field(default_factory=list)
    total_src_duration_ms: int = 0
    total_out_duration_ms: int = 0

    @classmethod
    def create(
        cls,
        clip_start_ms: int,
        clip_end_ms: int,
        removals: list[Removal | dict[str, Any]] | None = None,
    ) -> "EditDecisionList":
        """
        Build an EDL by normalizing, merging, and clamping removal intervals,
        then computing the resulting contiguous keep segments.
        """
        if clip_start_ms < 0:
            raise ValueError(f"clip_start_ms must be >= 0, got {clip_start_ms}")
        if clip_end_ms <= clip_start_ms:
            raise ValueError(f"clip_end_ms ({clip_end_ms}) must be > clip_start_ms ({clip_start_ms})")

        total_src_dur = clip_end_ms - clip_start_ms

        # Normalize removals
        raw_removals: list[Removal] = []
        if removals:
            for r in removals:
                if isinstance(r, dict):
                    rem = Removal(
                        start_ms=int(r["start_ms"]),
                        end_ms=int(r["end_ms"]),
                        kind=str(r.get("kind", "manual")),
                        text=r.get("text"),
                    )
                else:
                    rem = r

                # Clamp to clip bounds
                clamped_start = max(clip_start_ms, min(clip_end_ms, rem.start_ms))
                clamped_end = max(clip_start_ms, min(clip_end_ms, rem.end_ms))
                if clamped_end > clamped_start:
                    raw_removals.append(
                        Removal(
                            start_ms=clamped_start,
                            end_ms=clamped_end,
                            kind=rem.kind,
                            text=rem.text,
                        )
                    )

        # Sort by start_ms
        raw_removals.sort(key=lambda x: (x.start_ms, x.end_ms))

        # Merge overlapping / touching removals
        merged_removals: list[Removal] = []
        for r in raw_removals:
            if not merged_removals:
                merged_removals.append(r)
                continue

            last = merged_removals[-1]
            if r.start_ms <= last.end_ms:
                # Merge
                new_end = max(last.end_ms, r.end_ms)
                combined_kind = last.kind if last.kind == r.kind else "mixed"
                combined_text = None
                if last.text and r.text:
                    combined_text = f"{last.text} {r.text}"
                else:
                    combined_text = last.text or r.text
                merged_removals[-1] = Removal(
                    start_ms=last.start_ms,
                    end_ms=new_end,
                    kind=combined_kind,
                    text=combined_text,
                )
            else:
                merged_removals.append(r)

        # Compute keep segments
        keep_segments: list[KeepSegment] = []
        curr_src = clip_start_ms
        curr_out = 0

        for r in merged_removals:
            if r.start_ms > curr_src:
                seg_dur = r.start_ms - curr_src
                keep_segments.append(
                    KeepSegment(
                        src_start_ms=curr_src,
                        src_end_ms=r.start_ms,
                        out_start_ms=curr_out,
                        out_end_ms=curr_out + seg_dur,
                    )
                )
                curr_out += seg_dur
            curr_src = max(curr_src, r.end_ms)

        if curr_src < clip_end_ms:
            seg_dur = clip_end_ms - curr_src
            keep_segments.append(
                KeepSegment(
                    src_start_ms=curr_src,
                    src_end_ms=clip_end_ms,
                    out_start_ms=curr_out,
                    out_end_ms=curr_out + seg_dur,
                )
            )
            curr_out += seg_dur

        return cls(
            clip_start_ms=clip_start_ms,
            clip_end_ms=clip_end_ms,
            removals=merged_removals,
            keep_segments=keep_segments,
            total_src_duration_ms=total_src_dur,
            total_out_duration_ms=curr_out,
        )

    @property
    def removed_duration_ms(self) -> int:
        return self.total_src_duration_ms - self.total_out_duration_ms

    def src_to_out(self, src_ms: int) -> int | None:
        """
        Map a source millisecond timestamp to output timeline millisecond.
        Returns None if src_ms falls outside the clip or inside a removed cut.
        """
        if src_ms < self.clip_start_ms or src_ms > self.clip_end_ms:
            return None

        # Boundary edge case
        if src_ms == self.clip_end_ms:
            return self.total_out_duration_ms

        for seg in self.keep_segments:
            if seg.src_start_ms <= src_ms < seg.src_end_ms:
                return seg.out_start_ms + (src_ms - seg.src_start_ms)

        return None

    def src_to_out_clamped(self, src_ms: int) -> int:
        """
        Map a source millisecond timestamp to the closest valid output timeline position.
        If src_ms falls inside a removal, it maps to the cut point boundary.
        Clamped to [0, total_out_duration_ms].
        """
        if not self.keep_segments:
            return 0

        if src_ms <= self.clip_start_ms:
            return 0
        if src_ms >= self.clip_end_ms:
            return self.total_out_duration_ms

        for seg in self.keep_segments:
            if src_ms < seg.src_start_ms:
                return seg.out_start_ms
            if seg.src_start_ms <= src_ms <= seg.src_end_ms:
                return seg.out_start_ms + (src_ms - seg.src_start_ms)

        return self.total_out_duration_ms

    def out_to_src(self, out_ms: int) -> int:
        """
        Map an output timeline millisecond back to the source timestamp.
        Invertible mapping on all kept segments.
        """
        if not self.keep_segments:
            return self.clip_start_ms

        if out_ms <= 0:
            return self.keep_segments[0].src_start_ms
        if out_ms >= self.total_out_duration_ms:
            return self.keep_segments[-1].src_end_ms

        for i, seg in enumerate(self.keep_segments):
            if i == len(self.keep_segments) - 1:
                if seg.out_start_ms <= out_ms <= seg.out_end_ms:
                    return seg.src_start_ms + (out_ms - seg.out_start_ms)
            else:
                if seg.out_start_ms <= out_ms < seg.out_end_ms:
                    return seg.src_start_ms + (out_ms - seg.out_start_ms)

        return self.keep_segments[-1].src_end_ms

    def remap_words(self, words: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Remap a list of word dictionaries from source time to the output timeline.
        Words in removed intervals are dropped or marked deleted.
        """
        remapped: list[dict[str, Any]] = []

        for w in words:
            w_start = int(w.get("start_ms", 0))
            w_end = int(w.get("end_ms", 0))
            w_text = w.get("text", "")
            is_deleted = bool(w.get("deleted", False))

            # Skip if already deleted or outside clip bounds
            if is_deleted or w_end <= self.clip_start_ms or w_start >= self.clip_end_ms:
                continue

            # Check if word is completely inside any removal
            is_removed = False
            for r in self.removals:
                if r.start_ms <= w_start and w_end <= r.end_ms:
                    is_removed = True
                    break

            if is_removed:
                continue

            out_start = self.src_to_out_clamped(w_start)
            out_end = self.src_to_out_clamped(w_end)

            if out_end > out_start:
                w_copy = dict(w)
                w_copy["start_ms"] = out_start
                w_copy["end_ms"] = out_end
                w_copy["src_start_ms"] = w_start
                w_copy["src_end_ms"] = w_end
                remapped.append(w_copy)

        return remapped

    def remap_crop_path(self, crop_path: dict[str, Any]) -> dict[str, Any]:
        """
        Remap 9:16 crop path keyframes from source time to output timeline.
        Keyframes are positioned on the new contiguous timeline and deduplicated.
        """
        raw_keyframes = crop_path.get("keyframes", [])
        if not raw_keyframes:
            return dict(crop_path)

        # Detect if keyframes are relative to clip start (t_ms in [0, clip_duration]) or absolute
        first_t = raw_keyframes[0].get("t_ms", 0)
        is_relative = first_t < self.clip_start_ms and len(raw_keyframes) > 0

        remapped_kfs = []
        seen_times = set()

        for kf in raw_keyframes:
            src_t = (self.clip_start_ms + kf["t_ms"]) if is_relative else kf["t_ms"]
            out_t = self.src_to_out_clamped(src_t)

            if out_t not in seen_times:
                seen_times.add(out_t)
                new_kf = dict(kf)
                new_kf["t_ms"] = out_t
                remapped_kfs.append(new_kf)

        remapped_kfs.sort(key=lambda k: k["t_ms"])

        # Ensure we have a keyframe at t=0 and t=total_out_duration_ms
        if remapped_kfs and remapped_kfs[0]["t_ms"] > 0:
            first_copy = dict(remapped_kfs[0])
            first_copy["t_ms"] = 0
            remapped_kfs.insert(0, first_copy)

        if remapped_kfs and remapped_kfs[-1]["t_ms"] < self.total_out_duration_ms:
            last_copy = dict(remapped_kfs[-1])
            last_copy["t_ms"] = self.total_out_duration_ms
            remapped_kfs.append(last_copy)

        result = dict(crop_path)
        result["keyframes"] = remapped_kfs
        result["duration_ms"] = self.total_out_duration_ms
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "clip_start_ms": self.clip_start_ms,
            "clip_end_ms": self.clip_end_ms,
            "total_src_duration_ms": self.total_src_duration_ms,
            "total_out_duration_ms": self.total_out_duration_ms,
            "removed_duration_ms": self.removed_duration_ms,
            "removals": [asdict(r) for r in self.removals],
            "keep_segments": [asdict(s) for s in self.keep_segments],
        }
