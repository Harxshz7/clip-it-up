from typing import Dict, Any, Tuple
from clip_shared.prompts.clip_score_v1 import Pass2CandidateScore


def combine_signals(
    llm_score: Pass2CandidateScore,
    audio_features: Dict[str, float],
    weights: Dict[str, float],
    hook_energy_boost: float = 0.15,
) -> Tuple[float, Dict[str, float]]:
    """
    Combine multi-modal LLM quality signals and acoustic features into a single final score [0.0, 1.0].
    
    Formula:
      effective_hook = (1 - boost) * llm_hook + boost * hook_energy
      base_score = w_hook * effective_hook +
                   w_emotion * emotion +
                   w_coherence * coherence +
                   w_payoff * payoff +
                   w_novelty * novelty +
                   w_energy * audio_energy +
                   w_laughter * laughter
      penalties = w_pause * pause_ratio +
                  w_flag * (needs_context + off_topic + profanity + sensitive)
      final_score = clip(base_score - penalties, 0.0, 1.0)
    """
    w_hook = weights.get("hook", 0.30)
    w_emotion = weights.get("emotion", 0.15)
    w_coherence = weights.get("coherence", 0.20)
    w_payoff = weights.get("payoff", 0.20)
    w_novelty = weights.get("novelty", 0.10)
    w_energy = weights.get("audio_energy", 0.10)
    w_laughter = weights.get("laughter", 0.05)
    w_pause = weights.get("pause_penalty", 0.15)
    w_flag = weights.get("flag_penalty", 0.30)

    # Audio metrics
    audio_energy = float(audio_features.get("audio_energy", 0.5))
    laughter = float(audio_features.get("laughter", 0.0))
    hook_energy = float(audio_features.get("hook_energy", 0.5))
    pause_ratio = float(audio_features.get("pause_ratio", 0.0))

    # Blended hook (combining LLM text hook with acoustic onset/energy in the first 3s)
    effective_hook = (1.0 - hook_energy_boost) * llm_score.hook + hook_energy_boost * hook_energy

    # Positive weighted components
    weighted_sum = (
        w_hook * effective_hook
        + w_emotion * llm_score.emotion
        + w_coherence * llm_score.coherence
        + w_payoff * llm_score.payoff
        + w_novelty * llm_score.novelty
        + w_energy * audio_energy
        + w_laughter * laughter
    )

    # Total weight of positive signals for normalization
    total_pos_weight = w_hook + w_emotion + w_coherence + w_payoff + w_novelty + w_energy + w_laughter
    norm_score = weighted_sum / max(0.1, total_pos_weight)

    # Penalties
    pause_penalty = w_pause * pause_ratio

    flags_count = 0
    if llm_score.flags.needs_context:
        flags_count += 1
    if llm_score.flags.off_topic:
        flags_count += 1
    if llm_score.flags.profanity:
        flags_count += 0.5
    if llm_score.flags.sensitive:
        flags_count += 0.5

    flag_penalty = w_flag * min(1.0, flags_count * 0.5)

    final_score = max(0.0, min(1.0, norm_score - pause_penalty - flag_penalty))

    breakdown = {
        "hook": round(float(effective_hook), 3),
        "emotion": round(float(llm_score.emotion), 3),
        "coherence": round(float(llm_score.coherence), 3),
        "payoff": round(float(llm_score.payoff), 3),
        "novelty": round(float(llm_score.novelty), 3),
        "audio_energy": round(float(audio_energy), 3),
        "laughter": round(float(laughter), 3),
        "pause_penalty": round(float(pause_penalty), 3),
        "flag_penalty": round(float(flag_penalty), 3),
        "flags": {
            "needs_context": llm_score.flags.needs_context,
            "off_topic": llm_score.flags.off_topic,
            "profanity": llm_score.flags.profanity,
            "sensitive": llm_score.flags.sensitive,
        },
    }

    return round(final_score, 3), breakdown
