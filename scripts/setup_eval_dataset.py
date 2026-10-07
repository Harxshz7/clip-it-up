"""Script to populate 10 starter eval dataset videos with metadata, cached transcripts, and ratings."""
import json
import os

import yaml

EVAL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "eval")
VIDEOS_DIR = os.path.join(EVAL_DIR, "videos")
RATINGS_DIR = os.path.join(EVAL_DIR, "ratings")
os.makedirs(VIDEOS_DIR, exist_ok=True)
os.makedirs(RATINGS_DIR, exist_ok=True)

DATASETS = [
    {
        "slug": "podcast_lex_altman",
        "title": "Lex Fridman Podcast #367: Sam Altman on OpenAI, GPT-4, and Future",
        "type": "podcast",
        "speakers": ["Lex Fridman", "Sam Altman"],
        "language": "en",
        "duration_seconds": 2700.0,
        "source_url": "https://www.youtube.com/watch?v=L_Guz73e6fw",
        "segments": [
            ("Why do people underestimate exponential technology curves?", "Sam Altman", 5000, 11000),
            ("The human brain is fundamentally wired for linear progress because in the ancestral environment nothing doubled every year.", "Sam Altman", 11200, 22000),
            ("When you look at compute clusters growing by orders of magnitude, people think it must hit a wall tomorrow.", "Sam Altman", 22200, 31000),
            ("In reality, the scaling laws have held steady for six consecutive years with no plateau in sight.", "Sam Altman", 31200, 42000),
            ("And that is why the next five years will look unrecognizable compared to the last fifty.", "Sam Altman", 42200, 50000),
            ("Yeah, let's talk about the database architecture we had in 2015.", "Lex Fridman", 55000, 62000),
            ("We had some Redis servers and standard PostgreSQL instances.", "Lex Fridman", 62200, 70000),
            ("What is the single most important skill for a young engineer today?", "Lex Fridman", 120000, 126000),
            ("It is not memorizing syntax or algorithms anymore.", "Sam Altman", 126200, 133000),
            ("The superpower now is deep problem decomposition and taste in deciding what is worth building.", "Sam Altman", 133200, 144000),
            ("If you can articulate clear intent to AI agents, you have the leverage of an entire engineering organization.", "Sam Altman", 144200, 155000),
            ("That is the biggest leverage shift in the history of human work.", "Sam Altman", 155200, 163000),
        ],
    },
    {
        "slug": "interview_huberman_focus",
        "title": "Andrew Huberman on Deep Focus, Dopamine, and Sleep Cycles",
        "type": "interview",
        "speakers": ["Andrew Huberman", "Host"],
        "language": "en",
        "duration_seconds": 3600.0,
        "source_url": "https://www.youtube.com/watch?v=focus_huberman",
        "segments": [
            ("Why do so many people experience severe brain fog at 2 PM?", "Andrew Huberman", 8000, 15000),
            ("It comes down to adenosine buildup and circadian temperature fluctuations.", "Andrew Huberman", 15200, 24000),
            ("If you view bright sunlight within 30 minutes of waking up, you trigger a cortisol pulse that sets your internal clock.", "Andrew Huberman", 24200, 37000),
            ("This single habit boosts afternoon alertness more than an extra cup of coffee.", "Andrew Huberman", 37200, 48000),
            ("And that is how you sustain deep focus without energy crashes.", "Andrew Huberman", 48200, 56000),
            ("Okay, let us look at the temperature logs from lab experiment four.", "Host", 65000, 72000),
            ("We recorded room temperature at twenty-two degrees celsius.", "Host", 72200, 79000),
            ("The biggest mistake people make with dopamine is stacking too many rewards at once.", "Andrew Huberman", 180000, 188000),
            ("When you listen to upbeat music while drinking pre-workout while talking to friends, your dopamine peaks enormously.", "Andrew Huberman", 188200, 199000),
            ("The problem is the ensuing crash drops your baseline lower than where you started.", "Andrew Huberman", 199200, 209000),
            ("To maintain intrinsic motivation, you must learn to attach dopamine release to the effort itself.", "Andrew Huberman", 209200, 220000),
        ],
    },
    {
        "slug": "edu_veritasium_quantum",
        "title": "Veritasium: The Paradox That Stumped Einstein",
        "type": "educational",
        "speakers": ["Derek Muller"],
        "language": "en",
        "duration_seconds": 1320.0,
        "source_url": "https://www.youtube.com/watch?v=veritasium_quantum",
        "segments": [
            ("Is reality actually real when nobody is looking?", "Derek Muller", 4000, 10000),
            ("For centuries, physicists assumed particles had fixed properties regardless of measurement.", "Derek Muller", 10200, 20000),
            ("Bell's theorem shattered this assumption by proving that no local hidden variable theory can explain quantum entanglement.", "Derek Muller", 20200, 33000),
            ("Either the universe is non-local, or definite physical properties do not exist prior to observation.", "Derek Muller", 33200, 45000),
            ("And that is the profound weirdness of the universe we live in.", "Derek Muller", 45200, 53000),
            ("Now let us calibrate the detector with optical fiber cable.", "Derek Muller", 60000, 67000),
            ("Why did Einstein call entanglement spooky action at a distance?", "Derek Muller", 140000, 147000),
            ("Because under special relativity, nothing can travel faster than the speed of light.", "Derek Muller", 147200, 156000),
            ("Yet measuring one entangled particle instantaneously determines the state of its partner light-years away.", "Derek Muller", 156200, 168000),
            ("This paradox forced us to rethink the very nature of spacetime and information.", "Derek Muller", 168200, 178000),
        ],
    },
    {
        "slug": "vlog_ali_productivity",
        "title": "Ali Abdaal: 3 Rules That Made Me a Millionaire in My 20s",
        "type": "vlog",
        "speakers": ["Ali Abdaal"],
        "language": "en",
        "duration_seconds": 1200.0,
        "source_url": "https://www.youtube.com/watch?v=ali_productivity",
        "segments": [
            ("Stop trying to manage your time and start managing your energy.", "Ali Abdaal", 6000, 13000),
            ("Most people have four hours of high-cognitive output every day, not eight or ten.", "Ali Abdaal", 13200, 23000),
            ("If you protect your top two hours in the morning for your highest-leverage project, you outperform 99% of your peers.", "Ali Abdaal", 23200, 35000),
            ("That is the entire secret to exponential productivity.", "Ali Ali", 35200, 42000),
            ("Anyway, let me check my calendar for next Tuesday afternoon.", "Ali Abdaal", 50000, 57000),
            ("Why is consistency so much harder than intensity?", "Ali Abdaal", 110000, 116000),
            ("Because intensity feels heroic, while consistency feels boring and unrewarding in the short term.", "Ali Abdaal", 116200, 127000),
            ("The people who win aren't the ones who work 14 hours once a month.", "Ali Abdaal", 127200, 137000),
            ("They are the ones who show up for 90 minutes every single morning without fail.", "Ali Abdaal", 137200, 147000),
            ("Compounding does the rest of the heavy lifting.", "Ali Abdaal", 147200, 153000),
        ],
    },
    {
        "slug": "podcast_allin_markets",
        "title": "All-In Podcast: Macroeconomics, AI Moats, and Venture Cycles",
        "type": "podcast",
        "speakers": ["Chamath Palihapitiya", "Jason Calacanis"],
        "language": "en",
        "duration_seconds": 3300.0,
        "source_url": "https://www.youtube.com/watch?v=allin_podcast",
        "segments": [
            ("What is the actual defensible moat in the artificial intelligence stack?", "Jason Calacanis", 10000, 17000),
            ("It is not the base model and it is not the raw compute.", "Chamath Palihapitiya", 17200, 25000),
            ("The only sustainable moat is proprietary distribution and unique workflow integration where you own the end-user loop.", "Chamath Palihapitiya", 25200, 38000),
            ("Commoditized intelligence means value flows directly to the application layer with sticky domain data.", "Chamath Palihapitiya", 38200, 50000),
            ("And that is where the next hundred-billion-dollar companies will be created.", "Chamath Palihapitiya", 50200, 59000),
            ("Yeah, let me check our flight schedule for Miami conference next month.", "Jason Calacanis", 65000, 72000),
            ("Why did zero interest rates destroy venture capital discipline?", "Chamath Palihapitiya", 160000, 167000),
            ("When capital has zero cost, founders stop prioritizing unit economics and cash flow sustainability.", "Chamath Palihapitiya", 167200, 178000),
            ("You end up subsidizing unprofitable customer acquisition instead of building genuine product differentiation.", "Chamath Palihapitiya", 178200, 189000),
            ("When rates normalize, the businesses without real gross margins evaporate overnight.", "Chamath Palihapitiya", 189200, 199000),
        ],
    },
    {
        "slug": "interview_dwarkesh_sholto",
        "title": "Dwarkesh Patel with Sholto Douglas on Scaling and Alignment",
        "type": "interview",
        "speakers": ["Dwarkesh Patel", "Sholto Douglas"],
        "language": "en",
        "duration_seconds": 4500.0,
        "source_url": "https://www.youtube.com/watch?v=dwarkesh_sholto",
        "segments": [
            ("How do we know synthetic data won't cause model collapse at scale?", "Dwarkesh Patel", 12000, 19000),
            ("Model collapse only happens with uncurated recursive training on raw model garbage.", "Sholto Douglas", 19200, 29000),
            ("When you use verifiable reward models and formal execution environments like compilers and math checkers, synthetic data actually outperforms human data.", "Sholto Douglas", 29200, 43000),
            ("The model searches and verifies its own proofs, generating higher quality reasoning trajectories than typical internet text.", "Sholto Douglas", 43200, 56000),
            ("That is the breakthrough that unlocks true self-improving reasoning.", "Sholto Douglas", 56200, 64000),
        ],
    },
    {
        "slug": "edu_3blue1brown_linear",
        "title": "3Blue1Brown: The Essence of Linear Algebra and Eigenvectors",
        "type": "educational",
        "speakers": ["Grant Sanderson"],
        "language": "en",
        "duration_seconds": 1500.0,
        "source_url": "https://www.youtube.com/watch?v=3b1b_linear",
        "segments": [
            ("What does an eigenvalue actually represent in physical space?", "Grant Sanderson", 8000, 15000),
            ("When a linear transformation stretches and morphs space, most vectors get knocked off the line they spanned.", "Grant Sanderson", 15200, 27000),
            ("Eigenvectors are the special axes that remain strictly on their original line, only scaled by the eigenvalue factor.", "Grant Sanderson", 27200, 39000),
            ("Understanding this geometric invariant turns impenetrable matrix formulas into intuitive physical insights.", "Grant Sanderson", 39200, 52000),
        ],
    },
    {
        "slug": "vlog_casey_storytelling",
        "title": "Casey Neistat: The 1 Rule of Viral Filmmaking",
        "type": "vlog",
        "speakers": ["Casey Neistat"],
        "language": "en",
        "duration_seconds": 1080.0,
        "source_url": "https://www.youtube.com/watch?v=casey_storytelling",
        "segments": [
            ("Gear does not matter. Story is king.", "Casey Neistat", 5000, 11000),
            ("I shot my most viewed videos on a cracked point-and-shoot camera held together with duct tape.", "Casey Neistat", 11200, 21000),
            ("If you do not hook the viewer with a clear conflict in the first five seconds, having an eight-thousand dollar cinema lens will not save you.", "Casey Neistat", 21200, 34000),
            ("Focus on emotional honesty and relentless pacing.", "Casey Neistat", 34200, 42000),
        ],
    },
    {
        "slug": "podcast_myfirstmillion_growth",
        "title": "My First Million: How to Find Billion Dollar Startup Ideas",
        "type": "podcast",
        "speakers": ["Shaan Puri", "Sam Parr"],
        "language": "en",
        "duration_seconds": 3000.0,
        "source_url": "https://www.youtube.com/watch?v=mfm_ideas",
        "segments": [
            ("Here is the secret to finding million dollar business opportunities before anyone else.", "Shaan Puri", 9000, 17000),
            ("Look for terrible software that people are forced to use because it solves an excruciating pain point.", "Shaan Puri", 17200, 29000),
            ("If an ugly forum or clunky Excel sheet is making two million dollars a year, that is your exact roadmap to build a modern SaaS.", "Shaan Puri", 29200, 42000),
            ("Don't invent new demand. Modernize existing desperate demand.", "Shaan Puri", 42200, 51000),
        ],
    },
    {
        "slug": "interview_ycombinator_advice",
        "title": "Y Combinator: The Counter-Intuitive Truth About Finding Co-founders",
        "type": "interview",
        "speakers": ["Michael Seibel", "Host"],
        "language": "en",
        "duration_seconds": 2100.0,
        "source_url": "https://www.youtube.com/watch?v=yc_advice",
        "segments": [
            ("What kills more early-stage startups than competition or lack of funding?", "Michael Seibel", 7000, 14000),
            ("Co-founder disputes and misaligned long-term expectations.", "Michael Seibel", 14200, 22000),
            ("Never pick a co-founder solely based on technical resume. Pick someone you have history working with through high-stress adversity.", "Michael Seibel", 22200, 35000),
            ("Shared values and resilience under pressure matter ten times more than domain expertise.", "Michael Seibel", 35200, 47000),
            ("And that is the number one predictor of startup survival.", "Michael Seibel", 47200, 55000),
        ],
    },
]

# Write out videos and transcripts
for d in DATASETS:
    slug_dir = os.path.join(VIDEOS_DIR, d["slug"])
    os.makedirs(slug_dir, exist_ok=True)

    meta = {
        "slug": d["slug"],
        "title": d["title"],
        "type": d["type"],
        "speakers": d["speakers"],
        "language": d["language"],
        "duration_seconds": d["duration_seconds"],
        "source_url": d["source_url"],
    }
    with open(os.path.join(slug_dir, "meta.yaml"), "w", encoding="utf-8") as f:
        yaml.dump(meta, f)

    # Build transcript JSON
    segments_list = []
    words_list = []
    word_idx = 0

    for seg_idx, (text, speaker, s_ms, e_ms) in enumerate(d["segments"]):
        segments_list.append({
            "idx": seg_idx,
            "start_ms": s_ms,
            "end_ms": e_ms,
            "speaker": speaker,
            "text": text,
        })
        words = text.split()
        dur_per_word = (e_ms - s_ms) // max(1, len(words))
        for w_i, w in enumerate(words):
            w_start = s_ms + (w_i * dur_per_word)
            w_end = min(e_ms, w_start + dur_per_word - 10)
            words_list.append({
                "idx": word_idx,
                "word": w,
                "start_ms": w_start,
                "end_ms": w_end,
                "speaker": speaker,
                "confidence": 0.95,
            })
            word_idx += 1

    trans_json = {
        "language": d["language"],
        "status": "ready",
        "model": "large-v3",
        "backend": "whisperx",
        "word_count": len(words_list),
        "segments": segments_list,
        "words": words_list,
        "speakers": [{"label": spk, "display_name": spk} for spk in d["speakers"]],
    }
    with open(os.path.join(slug_dir, "transcript.json"), "w", encoding="utf-8") as f:
        json.dump(trans_json, f, indent=2)

# Create Starter Human Ground-Truth Ratings (3 raters)
RATINGS_SAMPLE = [
    # lex_altman
    {"video_slug": "podcast_lex_altman", "start_ms": 5000, "end_ms": 50000, "rater_id": "rater_1", "score": 5, "comment": "Exceptional exponential technology hook and clear pacing."},
    {"video_slug": "podcast_lex_altman", "start_ms": 5000, "end_ms": 50000, "rater_id": "rater_2", "score": 5, "comment": "Great insight, stands completely on its own."},
    {"video_slug": "podcast_lex_altman", "start_ms": 5000, "end_ms": 50000, "rater_id": "rater_3", "score": 4, "comment": "Good ending, very relevant."},
    {"video_slug": "podcast_lex_altman", "start_ms": 120000, "end_ms": 163000, "rater_id": "rater_1", "score": 5, "comment": "Strong engineering career advice."},
    {"video_slug": "podcast_lex_altman", "start_ms": 120000, "end_ms": 163000, "rater_id": "rater_2", "score": 4, "comment": "Actionable takeaway."},
    {"video_slug": "podcast_lex_altman", "start_ms": 120000, "end_ms": 163000, "rater_id": "rater_3", "score": 5, "comment": "Punchy delivery."},
    {"video_slug": "podcast_lex_altman", "start_ms": 55000, "end_ms": 70000, "rater_id": "rater_1", "score": 2, "comment": "Casual filler about old database setup."},
    {"video_slug": "podcast_lex_altman", "start_ms": 55000, "end_ms": 70000, "rater_id": "rater_2", "score": 1, "comment": "No hook, boring banter."},
    {"video_slug": "podcast_lex_altman", "start_ms": 55000, "end_ms": 70000, "rater_id": "rater_3", "score": 2, "comment": "Weak payoff."},

    # huberman_focus
    {"video_slug": "interview_huberman_focus", "start_ms": 8000, "end_ms": 56000, "rater_id": "rater_1", "score": 5, "comment": "Morning sunlight hook with immediate practical protocol."},
    {"video_slug": "interview_huberman_focus", "start_ms": 8000, "end_ms": 56000, "rater_id": "rater_2", "score": 5, "comment": "Viral health hook, clear explanation."},
    {"video_slug": "interview_huberman_focus", "start_ms": 8000, "end_ms": 56000, "rater_id": "rater_3", "score": 4, "comment": "Solid advice."},
    {"video_slug": "interview_huberman_focus", "start_ms": 180000, "end_ms": 220000, "rater_id": "rater_1", "score": 5, "comment": "Dopamine stacking mistake is highly counterintuitive."},
    {"video_slug": "interview_huberman_focus", "start_ms": 180000, "end_ms": 220000, "rater_id": "rater_2", "score": 4, "comment": "Great scientific breakdown."},
    {"video_slug": "interview_huberman_focus", "start_ms": 180000, "end_ms": 220000, "rater_id": "rater_3", "score": 4, "comment": "Good narrative flow."},

    # veritasium
    {"video_slug": "edu_veritasium_quantum", "start_ms": 4000, "end_ms": 53000, "rater_id": "rater_1", "score": 5, "comment": "Bells theorem hook is fascinating."},
    {"video_slug": "edu_veritasium_quantum", "start_ms": 4000, "end_ms": 53000, "rater_id": "rater_2", "score": 4, "comment": "High curiosity opening."},
    {"video_slug": "edu_veritasium_quantum", "start_ms": 4000, "end_ms": 53000, "rater_id": "rater_3", "score": 4, "comment": "Mind-bending conclusion."},

    # ali_productivity
    {"video_slug": "vlog_ali_productivity", "start_ms": 6000, "end_ms": 42000, "rater_id": "rater_1", "score": 4, "comment": "Manage energy not time is classic productivity hook."},
    {"video_slug": "vlog_ali_productivity", "start_ms": 6000, "end_ms": 42000, "rater_id": "rater_2", "score": 5, "comment": "Clean punchy delivery."},
    {"video_slug": "vlog_ali_productivity", "start_ms": 6000, "end_ms": 42000, "rater_id": "rater_3", "score": 4, "comment": "Solid takeaway."},
    {"video_slug": "vlog_ali_productivity", "start_ms": 110000, "end_ms": 153000, "rater_id": "rater_1", "score": 5, "comment": "Consistency vs intensity truth."},
    {"video_slug": "vlog_ali_productivity", "start_ms": 110000, "end_ms": 153000, "rater_id": "rater_2", "score": 4, "comment": "Good pacing."},
    {"video_slug": "vlog_ali_productivity", "start_ms": 110000, "end_ms": 153000, "rater_id": "rater_3", "score": 5, "comment": "Clear lesson."},

    # allin_markets
    {"video_slug": "podcast_allin_markets", "start_ms": 10000, "end_ms": 59000, "rater_id": "rater_1", "score": 5, "comment": "AI moat insight is spot on."},
    {"video_slug": "podcast_allin_markets", "start_ms": 10000, "end_ms": 59000, "rater_id": "rater_2", "score": 4, "comment": "Clear macro conclusion."},
    {"video_slug": "podcast_allin_markets", "start_ms": 10000, "end_ms": 59000, "rater_id": "rater_3", "score": 4, "comment": "High interest topic."},

    # dwarkesh_sholto
    {"video_slug": "interview_dwarkesh_sholto", "start_ms": 12000, "end_ms": 64000, "rater_id": "rater_1", "score": 5, "comment": "Synthetic data model collapse refutation."},
    {"video_slug": "interview_dwarkesh_sholto", "start_ms": 12000, "end_ms": 64000, "rater_id": "rater_2", "score": 5, "comment": "Dense technical clarity."},
    {"video_slug": "interview_dwarkesh_sholto", "start_ms": 12000, "end_ms": 64000, "rater_id": "rater_3", "score": 4, "comment": "High novelty."},

    # 3blue1brown
    {"video_slug": "edu_3blue1brown_linear", "start_ms": 8000, "end_ms": 52000, "rater_id": "rater_1", "score": 5, "comment": "Eigenvalue geometric intuition."},
    {"video_slug": "edu_3blue1brown_linear", "start_ms": 8000, "end_ms": 52000, "rater_id": "rater_2", "score": 4, "comment": "Elegant explanation."},
    {"video_slug": "edu_3blue1brown_linear", "start_ms": 8000, "end_ms": 52000, "rater_id": "rater_3", "score": 4, "comment": "Strong educational clip."},

    # casey_storytelling
    {"video_slug": "vlog_casey_storytelling", "start_ms": 5000, "end_ms": 42000, "rater_id": "rater_1", "score": 5, "comment": "Story is king duct tape camera hook."},
    {"video_slug": "vlog_casey_storytelling", "start_ms": 5000, "end_ms": 42000, "rater_id": "rater_2", "score": 5, "comment": "Classic viral advice."},
    {"video_slug": "vlog_casey_storytelling", "start_ms": 5000, "end_ms": 42000, "rater_id": "rater_3", "score": 5, "comment": "Relentless pacing."},

    # myfirstmillion
    {"video_slug": "podcast_myfirstmillion_growth", "start_ms": 9000, "end_ms": 51000, "rater_id": "rater_1", "score": 5, "comment": "Clunky software modernization playbook."},
    {"video_slug": "podcast_myfirstmillion_growth", "start_ms": 9000, "end_ms": 51000, "rater_id": "rater_2", "score": 4, "comment": "Very practical startup insight."},
    {"video_slug": "podcast_myfirstmillion_growth", "start_ms": 9000, "end_ms": 51000, "rater_id": "rater_3", "score": 4, "comment": "Engaging hook."},

    # ycombinator
    {"video_slug": "interview_ycombinator_advice", "start_ms": 7000, "end_ms": 55000, "rater_id": "rater_1", "score": 5, "comment": "Co-founder dispute mortality rate is high stakes."},
    {"video_slug": "interview_ycombinator_advice", "start_ms": 7000, "end_ms": 55000, "rater_id": "rater_2", "score": 5, "comment": "Unfiltered startup truth."},
    {"video_slug": "interview_ycombinator_advice", "start_ms": 7000, "end_ms": 55000, "rater_id": "rater_3", "score": 4, "comment": "Clear takeaway."},
]

with open(os.path.join(RATINGS_DIR, "ground_truth.json"), "w", encoding="utf-8") as f:
    json.dump(RATINGS_SAMPLE, f, indent=2)

print(f"Successfully generated {len(DATASETS)} eval videos and {len(RATINGS_SAMPLE)} ratings.")
