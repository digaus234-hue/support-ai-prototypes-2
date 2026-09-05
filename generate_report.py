"""
Runs retrieval eval + generation eval + 3-model comparison and writes
formatted markdown into eval_results.md and model_comparison.md.

    export ANTHROPIC_API_KEY=sk-ant-...
    python generate_report.py
"""

import json
from pathlib import Path
from datetime import datetime, timezone

from eval import run_retrieval_eval, run_generation_eval, run_comparison
from assistant import DEFAULT_MODEL

OUT_DIR = Path(__file__).parent


def write_eval_results(retrieval_data: dict, gen_data: dict):
    lines = [
        f"# Eval Results — model: `{gen_data['model']}`",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Retrieval accuracy (deterministic, no API calls)",
        "",
        f"**{retrieval_data['accuracy']:.1%}** "
        f"({sum(1 for r in retrieval_data['rows'] if r['correct'])}/{len(retrieval_data['rows'])})",
        "",
        "| ID | Expected KB | Matched KB | Correct |",
        "|----|--------------|-------------|---------|",
    ]
    for r in retrieval_data["rows"]:
        lines.append(
            f"| {r['id']} | {r['expected_kb_id'] or '(none)'} | {r['matched_kb_id'] or '(none)'} | "
            f"{'✅' if r['correct'] else '❌'} |"
        )

    lines += [
        "",
        "## Generation eval (schema validity + flagging behavior)",
        "",
        f"**Schema-valid responses: {gen_data['schema_accuracy']:.1%}**",
        "",
        "| ID | Input (truncated) | Variants Returned | Flag for Review | Confidence | Latency (ms) |",
        "|----|---------------------|----------------------|--------------------|--------------|---------------|",
    ]
    for r in gen_data["rows"]:
        lines.append(
            f"| {r['id']} | {r['input']} | {r['num_variants']} | {r['flag_for_review']} | "
            f"{r['confidence']} | {r['latency_ms']} |"
        )

    (OUT_DIR / "eval_results.md").write_text("\n".join(lines), encoding="utf-8")
    print("Wrote eval_results.md")


def write_model_comparison(summary: dict):
    lines = [
        "# Model Comparison — Haiku vs Sonnet vs Opus",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "All three models run against the same 10-case test set with identical",
        "system prompt and KB retrieval (retrieval itself is not model-dependent —",
        "see `eval_results.md`). `flag_accuracy` measures whether the model correctly",
        "set `flag_for_review` on the cases that should require human judgment",
        "(A04 expert misconduct, A07 account security, and the two no-KB-match edge cases).",
        "",
        "| Model | Schema Valid | Flag Accuracy | Avg Latency (ms) | Avg Input Tok | Avg Output Tok | Avg Cost/Ticket | Projected Cost / 10k Tickets |",
        "|-------|----------------|-----------------|--------------------|-----------------|-------------------|--------------------|--------------------------------|",
    ]
    for model, s in summary.items():
        lines.append(
            f"| {model} | {s['schema_valid_rate']:.1%} | {s['flag_accuracy']:.1%} | {s['avg_latency_ms']} | "
            f"{s['avg_input_tokens']} | {s['avg_output_tokens']} | ${s['avg_cost_per_ticket_usd']:.6f} | "
            f"${s['projected_cost_10k_tickets_usd']:.2f} |"
        )

    lines += [
        "",
        "## Why this task defaults to Sonnet, not Haiku",
        "",
        "Unlike Task 1's classification (a bounded, single-label decision), this task",
        "generates open-ended prose that a support agent will read and possibly send",
        "to a real customer with minimal editing. Quality of the writing itself — does",
        "the empathetic variant actually sound empathetic and not just \"formal with a",
        "sorry\", does the short variant stay genuinely short, is the summary accurate —",
        "matters more here than in a closed classification task, and is harder to",
        "verify automatically (this eval only checks schema validity and flagging",
        "logic, not prose quality — see README.md for why that's a conscious tradeoff).",
        "Given the output is customer-facing, the cost difference between Sonnet and",
        "Haiku (see table above) is worth paying for the more reliable writing quality,",
        "unlike Task 1 where Haiku's cost advantage was decisive for a bounded task.",
    ]

    (OUT_DIR / "model_comparison.md").write_text("\n".join(lines), encoding="utf-8")
    print("Wrote model_comparison.md")


if __name__ == "__main__":
    print("Running retrieval eval (no API calls)...")
    retrieval_data = run_retrieval_eval(verbose=False)

    print("Running single-model generation eval...")
    gen_data = run_generation_eval(model=DEFAULT_MODEL, verbose=False)
    write_eval_results(retrieval_data, gen_data)

    print("\nRunning 3-model comparison (this calls the API 3x10 = 30 times)...")
    summary = run_comparison()
    write_model_comparison(summary)

    print("\nDone. Review eval_results.md and model_comparison.md.")
