"""
Evaluation harness for the agent assistant.

    python eval.py             # single-model eval (retrieval accuracy)
    python eval.py --compare   # 3-model comparison (Haiku/Sonnet/Opus)

Retrieval is evaluated separately from generation quality: retrieval is
deterministic (no model call — see assistant.py's retrieve_kb_article), so
its accuracy is measured directly against test_cases.json's expected_kb_id.
Generation quality (are the 3 tone variants actually different, is the
summary accurate) is not auto-scored here — see README.md for why this is
a conscious tradeoff, and cost_analysis.md / model_comparison.md for what
IS measured automatically (latency, cost, whether the model followed the
JSON schema, whether it correctly declined to force a KB match).
"""

import json
import argparse
from pathlib import Path

from anthropic import Anthropic
from assistant import (
    generate_response, retrieve_kb_article, load_kb,
    MODEL_HAIKU, MODEL_SONNET, MODEL_OPUS, DEFAULT_MODEL,
)

TEST_CASES_PATH = Path(__file__).parent / "test_cases.json"

PRICING = {
    MODEL_HAIKU: (1.00, 5.00),
    MODEL_SONNET: (3.00, 15.00),
    MODEL_OPUS: (5.00, 25.00),
}


def load_test_cases():
    with open(TEST_CASES_PATH, encoding="utf-8") as f:
        return json.load(f)


def run_retrieval_eval(verbose: bool = True):
    """Retrieval is deterministic and free — evaluate it directly, no API calls."""
    cases = load_test_cases()
    kb = load_kb()
    rows = []
    correct = 0

    for case in cases:
        matched = retrieve_kb_article(case["text"], kb)
        matched_id = matched["id"] if matched else None
        is_correct = matched_id == case["expected_kb_id"]
        if is_correct:
            correct += 1
        rows.append({
            "id": case["id"],
            "expected_kb_id": case["expected_kb_id"],
            "matched_kb_id": matched_id,
            "correct": is_correct,
        })

    accuracy = correct / len(cases)
    if verbose:
        print(f"\n=== Retrieval eval ({len(cases)} cases) ===")
        for r in rows:
            status = "PASS" if r["correct"] else "FAIL"
            print(f"[{status}] {r['id']}: expected={r['expected_kb_id']} matched={r['matched_kb_id']}")
        print(f"\nRetrieval accuracy: {accuracy:.1%} ({correct}/{len(cases)})")

    return {"rows": rows, "accuracy": accuracy}


def run_generation_eval(model: str = DEFAULT_MODEL, verbose: bool = True):
    """Runs full generation (summary + variants) for each case and records
    schema-validity, flag_for_review correctness, and latency/cost — but
    NOT variant quality, which needs human judgment (see README.md)."""
    client = Anthropic()
    cases = load_test_cases()
    rows = []
    schema_ok_count = 0

    for case in cases:
        result = generate_response(case["text"], model=model, client=client)
        schema_ok = result.error is None
        if schema_ok:
            schema_ok_count += 1
        rows.append({
            "id": case["id"],
            "input": case["text"][:70] + ("..." if len(case["text"]) > 70 else ""),
            "expected_kb_id": case["expected_kb_id"],
            "kb_article_id": result.kb_article_id,
            "schema_ok": schema_ok,
            "num_variants": len(result.variants),
            "flag_for_review": result.flag_for_review,
            "confidence": result.confidence,
            "latency_ms": result.latency_ms,
            "error": result.error,
        })

    schema_accuracy = schema_ok_count / len(cases)
    if verbose:
        print(f"\n=== Generation eval for {model} ===")
        for r in rows:
            status = "OK" if r["schema_ok"] else "FAIL"
            print(f"[{status}] {r['id']}: variants={r['num_variants']} flag={r['flag_for_review']} conf={r['confidence']}")
        print(f"\nSchema-valid responses: {schema_accuracy:.1%} ({schema_ok_count}/{len(cases)})")

    return {"model": model, "rows": rows, "schema_accuracy": schema_accuracy}


def run_comparison():
    client = Anthropic()
    cases = load_test_cases()
    models = [MODEL_HAIKU, MODEL_SONNET, MODEL_OPUS]
    summary = {}

    for model in models:
        print(f"\nRunning {model}...")
        schema_ok = 0
        total_latency = 0.0
        total_input_tok = 0
        total_output_tok = 0
        correct_flags = 0

        for case in cases:
            result = generate_response(case["text"], model=model, client=client)
            if result.error is None:
                schema_ok += 1
            total_latency += result.latency_ms or 0
            total_input_tok += result.input_tokens or 0
            total_output_tok += result.output_tokens or 0
            # A case "should" flag for review if it has no expected KB match
            # (ambiguous) or involves security/misconduct (A04, A07)
            should_flag = case["expected_kb_id"] is None or case["id"] in ("A04", "A07")
            if result.flag_for_review == should_flag:
                correct_flags += 1

        n = len(cases)
        in_price, out_price = PRICING[model]
        avg_cost = (
            (total_input_tok / n) * in_price / 1_000_000
            + (total_output_tok / n) * out_price / 1_000_000
        )

        summary[model] = {
            "schema_valid_rate": round(schema_ok / n, 4),
            "flag_accuracy": round(correct_flags / n, 4),
            "avg_latency_ms": round(total_latency / n, 1),
            "avg_input_tokens": round(total_input_tok / n, 1),
            "avg_output_tokens": round(total_output_tok / n, 1),
            "avg_cost_per_ticket_usd": round(avg_cost, 6),
            "projected_cost_10k_tickets_usd": round(avg_cost * 10_000, 2),
        }

    print("\n=== Model comparison ===")
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--retrieval-only", action="store_true", help="Only run the free retrieval eval, no API calls")
    args = parser.parse_args()

    if args.retrieval_only:
        run_retrieval_eval()
    elif args.compare:
        run_retrieval_eval()
        run_comparison()
    else:
        run_retrieval_eval()
        run_generation_eval(model=args.model)
