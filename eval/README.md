# Clip-It-Up Evaluation Benchmark Suite

> Continuous evaluation harness, benchmark datasets, and precision tracking for AI clip discovery.

## 1. Directory Structure

- `videos/<slug>/`: Benchmark test videos with `meta.yaml` and cached `transcript.json`.
  - Starter mix: 10 videos (target growth to 30 videos).
  - Target domains: Podcasts, 1-on-1 interviews, educational talking-head, solo vlogs (1–2 speakers, 20–90 min).
- `ratings/`: Ground-truth human rater ratings (`ground_truth.json` or exported CSVs).
- `reports/`: Timestamped markdown & JSON evaluation reports diffing precision against previous runs.
- `prompts/`: Versioned scoring prompts (`clip_score_v1.md`).
- `metrics.py`: Implementation of Precision@5, Precision@10, AUC-ROC, signal correlations, and inter-rater agreement.
- `run.py`: Full evaluation runner (`make eval`).
- `tune.py`: Coordinate search weight tuner (`make tune`).

## 2. Benchmark Commands

```bash
# Run full evaluation across all videos
make eval

# Tune signal weights to maximize Precision@5
make tune

# Add a new video to the benchmark suite
python scripts/add_eval_video.py --slug <slug> --title "<Title>" --type podcast
```

## 3. Human Rater Tool

A blind rating interface is available at `/eval/rate` in the web application for gathering 1–5 quality ratings from multiple evaluators without exposing model scores.
