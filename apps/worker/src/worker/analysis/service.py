"""End-to-end video analysis service orchestrating sampling, scene detection, tracking, and S3/DB persistence."""
from collections.abc import Callable
from typing import Any
import io
import os
import tempfile
import time
import uuid
from decimal import Decimal
import cv2
import numpy as np
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
import structlog

from clip_shared.config import get_settings
from clip_shared.db.base import utc_now
from clip_shared.db.models import FaceTrack, TranscriptSegment, Usage, Video, VideoAnalysis
from clip_shared.rates import StageRateConfig
from worker.analysis.active_speaker import AudioVisualSpeakerAssociator, SpeakerTurn
from worker.analysis.classifier import RuleBasedSceneClassifier
from worker.analysis.detector import get_face_detector
from worker.analysis.mesh import MouthOpennessExtractor
from worker.analysis.scene import detect_scenes
from worker.analysis.tracker import FaceTracker

logger = structlog.get_logger()
settings = get_settings()


def run_video_analysis(
    video_id: uuid.UUID,
    s3_client: Any,
    db_session: Any,
    version: str = "v1",
    fps_sampled: float = 6.0,
    detector_backend: str = "mediapipe",
    on_progress: Callable[[int, str], None] | None = None,
) -> VideoAnalysis:
    """
    Run visual analysis on proxy video.
    Persists scenes, face tracks, speaker associations, raw detections S3 npz, and usage.
    """
    start_time = time.time()

    # 1. Check existing cached analysis
    stmt = select(VideoAnalysis).where(
        VideoAnalysis.video_id == video_id,
        VideoAnalysis.version == version,
    )
    existing = db_session.execute(stmt).scalars().first()
    if existing and existing.status == "ready":
        logger.info("Video analysis already cached and ready", video_id=str(video_id), version=version)
        return existing

    # 2. Fetch video details
    video = db_session.get(Video, video_id)
    if not video:
        raise ValueError(f"Video {video_id} not found")

    # Mark status running
    if not existing:
        analysis_record = VideoAnalysis(
            id=uuid.uuid4(),
            video_id=video_id,
            version=version,
            fps_sampled=fps_sampled,
            scenes=[],
            status="running",
            summary={},
            created_at=utc_now(),
        )
        db_session.add(analysis_record)
        db_session.commit()
    else:
        analysis_record = existing
        analysis_record.status = "running"
        db_session.commit()

    if on_progress:
        on_progress(5, "Downloading proxy video for visual analysis...")

    # 3. Download proxy (or original) to temporary file
    video_key = video.proxy_key or video.storage_key
    with tempfile.TemporaryDirectory() as tmpdir:
        proxy_path = os.path.join(tmpdir, "proxy.mp4")
        s3_client.download_file(settings.S3_BUCKET_NAME, video_key, proxy_path)

        if on_progress:
            on_progress(15, "Detecting scene boundaries...")

        # 4. Detect scene cuts
        scene_cuts = detect_scenes(proxy_path)

        if on_progress:
            on_progress(25, "Sampling frames and detecting faces...")

        # 5. Sample frames and track faces
        cap = cv2.VideoCapture(proxy_path)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video at {proxy_path}")

        src_fps = float(cap.get(cv2.CAP_PROP_FPS) or 25.0)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        frame_interval = max(1, int(round(src_fps / fps_sampled)))

        detector = get_face_detector(detector_backend)
        mesh_extractor = MouthOpennessExtractor()
        tracker = FaceTracker()

        frame_idx = 0
        sampled_count = 0
        raw_detections_log: list[dict] = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                t_ms = int((frame_idx / src_fps) * 1000)

                # Downscale width to ~640 for fast detection
                h, w = frame.shape[:2]
                target_w = min(640, w)
                target_h = int(h * (target_w / float(w)))
                small_frame = cv2.resize(frame, (target_w, target_h)) if target_w < w else frame

                detections = detector.detect(small_frame)

                # If multiple faces, extract mouth openness for speaking variance
                if len(detections) >= 2:
                    for det in detections:
                        # Crop face
                        xmin_px = int(det.xmin * target_w)
                        ymin_px = int(det.ymin * target_h)
                        w_px = int(det.width * target_w)
                        h_px = int(det.height * target_h)
                        crop = small_frame[max(0, ymin_px):min(target_h, ymin_px + h_px), max(0, xmin_px):min(target_w, xmin_px + w_px)]
                        if crop.size > 0:
                            det.mouth_openness = mesh_extractor.compute_mouth_openness(crop)

                tracker.update(frame_idx=frame_idx, t_ms=t_ms, detections=detections)
                sampled_count += 1

                for d in detections:
                    raw_detections_log.append({
                        "t_ms": t_ms,
                        "bbox": list(d.bbox),
                        "conf": d.confidence,
                        "mouth": d.mouth_openness,
                    })

                if on_progress and total_frames > 0 and (sampled_count % 30 == 0):
                    pct = int(25 + (frame_idx / float(total_frames)) * 50)
                    on_progress(min(75, pct), f"Analyzed {sampled_count} frames...")

            frame_idx += 1

        cap.release()
        detector.close()
        mesh_extractor.close()

        if on_progress:
            on_progress(78, "Associating speakers with face trajectories...")

        # 6. Finalize face tracks
        face_tracks_data = tracker.finalize()

        # 7. Active speaker association with transcript
        seg_stmt = select(TranscriptSegment).join(TranscriptSegment.transcript).where(
            TranscriptSegment.transcript.has(video_id=video_id)
        ).order_by(TranscriptSegment.idx)
        segments = db_session.execute(seg_stmt).scalars().all()

        speaker_turns: list[SpeakerTurn] = []
        for s in segments:
            if s.speaker:
                speaker_turns.append(SpeakerTurn(
                    start_ms=s.start_ms,
                    end_ms=s.end_ms,
                    speaker_label=s.speaker,
                ))

        associator = AudioVisualSpeakerAssociator()
        speaker_map = associator.associate_speakers_with_tracks(face_tracks_data, speaker_turns)

        if on_progress:
            on_progress(88, "Classifying scene shots...")

        # 8. Classify scenes
        classifier = RuleBasedSceneClassifier()
        classified_scenes: list[dict] = []
        for cut in scene_cuts:
            item = classifier.classify(cut, face_tracks_data)
            classified_scenes.append(item.model_dump())

        if on_progress:
            on_progress(94, "Persisting visual analysis data...")

        # 9. Upload raw detections to S3 as .npz
        npz_buffer = io.BytesIO()
        np.savez_compressed(
            npz_buffer,
            detections=np.array([d["bbox"] for d in raw_detections_log], dtype=np.float32) if raw_detections_log else np.empty((0, 4)),
            timestamps=np.array([d["t_ms"] for d in raw_detections_log], dtype=np.int64) if raw_detections_log else np.empty((0,)),
        )
        npz_buffer.seek(0)
        frames_key = f"users/{video.user_id}/videos/{video_id}/analysis/{version}.npz"
        s3_client.put_object(
            Bucket=settings.S3_BUCKET_NAME,
            Key=frames_key,
            Body=npz_buffer.getvalue(),
            ContentType="application/octet-stream",
        )

        # 10. Persist VideoAnalysis & FaceTracks in DB
        analysis_summary = {
            "total_sampled_frames": sampled_count,
            "total_face_tracks": len(face_tracks_data),
            "total_scenes": len(classified_scenes),
            "associated_speakers": list(speaker_map.keys()),
        }

        analysis_record.scenes = classified_scenes
        analysis_record.status = "ready"
        analysis_record.frames_key = frames_key
        analysis_record.summary = analysis_summary
        db_session.flush()

        # Insert face tracks
        for trk in face_tracks_data:
            ft = FaceTrack(
                id=uuid.uuid4(),
                analysis_id=analysis_record.id,
                track_id=trk.track_id,
                start_ms=trk.start_ms,
                end_ms=trk.end_ms,
                avg_conf=trk.avg_conf,
                speaker_label=trk.speaker_label,
                summary=trk.summary,
                created_at=utc_now(),
            )
            db_session.add(ft)

        # Record CPU usage
        elapsed_seconds = max(1.0, time.time() - start_time)
        video_duration_s = video.duration_seconds or (frame_idx / src_fps)
        cost_inr = StageRateConfig.calculate_stage_cost("analysis", video_duration_s)

        usage_stmt = pg_insert(Usage).values(
            id=uuid.uuid4(),
            user_id=video.user_id,
            video_id=video.id,
            metric="cpu_seconds",
            quantity=Decimal(str(round(elapsed_seconds, 2))),
            cost_inr=cost_inr,
            created_at=utc_now(),
        ).on_conflict_do_nothing()
        db_session.execute(usage_stmt)

        db_session.commit()

        if on_progress:
            on_progress(100, "Visual analysis complete!")

        logger.info(
            "Video analysis completed successfully",
            video_id=str(video_id),
            version=version,
            tracks=len(face_tracks_data),
            scenes=len(classified_scenes),
            elapsed=round(elapsed_seconds, 2),
        )

        return analysis_record
