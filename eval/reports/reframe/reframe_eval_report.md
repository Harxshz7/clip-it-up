# 📐 Phase 3 Reframe Evaluation Report

> Generated on 2026-10-09T11:21:45.515641+00:00

## 1. Key Performance Metrics

| Metric | Actual | Target | Status |
| :--- | :--- | :--- | :--- |
| **Face Inside Crop Rate** | `100.0%` | `>= 99.0%` | ✅ PASS |
| **Mean Jitter Score** | `0.0` | `< 0.005` | ✅ PASS |
| **Human OK Rate** | `100.0%` | `>= 90.0%` | ✅ PASS |
| **Fallback Rate** | `33.3%` | `< 35.0%` | ✅ |

## 2. Mode Distribution

- **`speaker_track`**: 1 clips
- **`balanced`**: 1 clips
- **`fit_blur`**: 1 clips

## 3. Evaluated Scenarios

- **talking_head_single_speaker** (`speaker_track`): Conf `0.98`, Face Inside `100.0%`, Jitter `0.0`
- **two_person_balanced** (`balanced`): Conf `0.94`, Face Inside `100.0%`, Jitter `0.0`
- **presentation_slides_fallback** (`fit_blur`): Conf `0.9`, Face Inside `100.0%`, Jitter `0.0`
