"""Analysis package for scene detection, face tracking, and active speaker association."""
from worker.analysis.active_speaker import AudioVisualSpeakerAssociator, SpeakerTrackAssociation
from worker.analysis.classifier import BaseSceneClassifier, RuleBasedSceneClassifier
from worker.analysis.detector import (
    BaseFaceDetector,
    FaceDetection,
    MediaPipeFaceDetector,
    MockFaceDetector,
    YOLOv8FaceDetector,
    get_face_detector,
)
from worker.analysis.scene import SceneCut, detect_scenes
from worker.analysis.service import run_video_analysis
from worker.analysis.tracker import FaceTrackData, FaceTracker

__all__ = [
    "BaseFaceDetector",
    "FaceDetection",
    "MediaPipeFaceDetector",
    "YOLOv8FaceDetector",
    "MockFaceDetector",
    "get_face_detector",
    "SceneCut",
    "detect_scenes",
    "FaceTrackData",
    "FaceTracker",
    "BaseSceneClassifier",
    "RuleBasedSceneClassifier",
    "AudioVisualSpeakerAssociator",
    "SpeakerTrackAssociation",
    "run_video_analysis",
]
