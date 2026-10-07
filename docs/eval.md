# Evaluation Harness, Scoring Rubric & Benchmark Methodology

> Comprehensive guide for evaluating clip quality, rater guidelines, metric definitions, and weight tuning.

---

## 1. Core Evaluation Philosophy

At clip-it-up, clip discovery and virality scoring is treated as an ML-assisted ranking product:
**Every prompt update, feature addition, and weight shift is judged by measured precision, not intuition.**

### Primary Target Metric:
- **Precision@5 (Top-5 Usable Rate) $\ge 60\%$ across benchmark datasets.**

---

## 2. Human Scoring Rubric

Human raters evaluate prospective clips on a **1 to 5 scale**:

| Score | Rating | Definition & Criteria |
| :--- | :--- | :--- |
| **5** | **Exceptional** | Immediate curiosity-driven hook in the first 3 seconds, high emotional conviction, 100% standalone coherence (no missing context), clean punchline / resolution, ready to post immediately. |
| **4** | **Usable** | Clear hook, coherent narrative, strong insight, delivers on the hook. Would post as-is or with minor trim. |
| **3** | **Borderline** | Interesting discussion but weak/slow start (takes >8 seconds to get to the point) or ends abruptly. |
| **2** | **Poor** | Starts on a dangling pronoun ("and that's why he did it..."), requires external context, or rambles off-topic. |
| **1** | **Unusable** | Cut off mid-word or mid-sentence, pure filler words, or incoherent noise. |

### The "Usable" Label Rule:
A candidate clip is considered **"Usable" (Binary 1)** if **at least 2 of 3 independent human raters rate it $\ge 4/5$**.

### Time Overlap Matching:
Human ratings are tied to time ranges $[start\_ms, end\_ms]$. When rescoring with new prompts or weights, candidate clips are matched to ground-truth ratings if temporal $\text{IoU} \ge 0.60$. This guarantees historical ratings survive prompt and algorithm changes.

---

## 3. Metrics Computed

Each evaluation run computes and logs:

1. **Precision@5**: Fraction of the top 5 ranked moments per video that meet the usable threshold. Target: $\ge 60\%$.
2. **Precision@10**: Fraction of top 10 moments that are usable.
3. **Mean Score of Usable vs. Unusable**: Verifies that the model assigns systematically higher scores to usable clips ($\text{Mean}_{\text{usable}} > \text{Mean}_{\text{unusable}}$).
4. **AUC-ROC (Area Under ROC Curve)**: Measures ranking quality and discriminative ability across all candidate thresholds. Target: $\ge 0.75$.
5. **Per-Signal Correlation ($r$)**: Pearson and Spearman correlation between individual scoring dimensions (`hook`, `emotion`, `coherence`, `payoff`, `novelty`, `audio_energy`, `laughter`, `pause_penalty`) and human ground-truth labels.
6. **Inter-Rater Agreement**: Pairwise percentage agreement and mean score discrepancy across raters.
7. **Cost per Source Hour**: LLM token consumption in ₹ INR and $ USD.
8. **Wall Time per Source Hour**: Processing speed in seconds.

---

## 4. Evaluation CLI Commands

### Run Full Benchmark Suite:
```bash
make eval
# Or directly:
python -m eval.run
```
Runs candidate generation and two-pass scoring across all 10 benchmark videos, generates a timestamped report at `eval/reports/<timestamp>.md`, and prints a diff against the previous run.

### Tune Signal Weights:
```bash
make tune
# Or directly:
python -m eval.tune
```
Performs coordinate search over signal weights against the ground-truth ratings, outputs optimal weights, and saves candidate configuration to `eval/tuned_weights.yaml` for review.

### Add New Evaluation Video:
```bash
python scripts/add_eval_video.py --slug podcast_new_interview --title "Founder Story" --type podcast
```

---

## 5. Starter Benchmark Dataset (10 Videos)

The evaluation suite contains 10 diverse long-form videos spanning podcasts, interviews, solo vlogs, and educational talking heads:

1. `podcast_lex_altman` (Podcast, 2 speakers, technology/AI)
2. `interview_huberman_focus` (Interview, 2 speakers, science/health)
3. `edu_veritasium_quantum` (Educational talking-head, 1 speaker, physics)
4. `vlog_ali_productivity` (Solo vlog, 1 speaker, productivity)
5. `podcast_allin_markets` (Panel/Podcast, 2 speakers, business/macro)
6. `interview_dwarkesh_sholto` (Interview, 2 speakers, AI research)
7. `edu_3blue1brown_linear` (Educational, 1 speaker, mathematics)
8. `vlog_casey_storytelling` (Solo vlog, 1 speaker, filmmaking)
9. `podcast_myfirstmillion_growth` (Podcast, 2 speakers, startups)
10. `interview_ycombinator_advice` (Interview, 2 speakers, venture capital)
