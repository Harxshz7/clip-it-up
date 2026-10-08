import asyncio
import os
import sys

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from eval.gate import generate_gate_report


async def main():
    print("=" * 70)
    print("CLIP-IT-UP: CREATOR REALITY CHECK (PHASE 2.5 GATE EVALUATION)")
    print("=" * 70)

    fixtures_arg = sys.argv[1] if len(sys.argv) > 1 else None

    # Run report generator
    report = await generate_gate_report(fixtures_path=fixtures_arg)

    print(f"\n[+] Gate Report Generated: {report['report_id']}")
    print(f"[+] Markdown: {report.get('markdown_path')}")
    print(f"[+] JSON:     {report.get('json_path')}")
    print(f"\n{'='*70}")
    print(f"DECISION: {report['overall_verdict']}")
    print(f"{'='*70}\n")

    for c in report["checks"]:
        icon = "[PASS]" if c["status"] == "PASS" else "[FAIL]"
        print(f"  {icon:<7} {c['name']:<50} (Actual: {c['actual']}, Target: {c['target']})")

    print(f"\nKey Metrics:")
    m = report["metrics"]
    print(f"  - Usable Rate:              {round(m['usable_rate']*100, 1)}%")
    print(f"  - Strict Usable Rate:       {round(m['strict_usable_rate']*100, 1)}%")
    print(f"  - Top-3 vs Top-8 Usable:    {round(m['top3_usable_rate']*100, 1)}% vs {round(m['top8_usable_rate']*100, 1)}%")
    print(f"  - Score-Verdict Correlation:r = {m['score_verdict_correlation']}")
    print(f"  - Median Willingness-to-Pay:₹{int(m['median_open_price_inr']):,}/mo")
    print(f"  - Committed to Next Upload: {m['commit_upload_pct']}%")

    print(f"\nTop Recommendations:")
    for i, rec in enumerate(report["recommendations"], 1):
        print(f"  {i}. {rec}")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
