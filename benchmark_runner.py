"""
runner.py — Roblox Lua Benchmark runner.

Point this at any model that can generate Luau code and get a score.

Usage:
    python runner.py --model gpt-4o --trials 3
    python runner.py --model claude-sonnet-4-6 --trials 1
    python runner.py --task gs_touched_debounce --model gpt-4o

Implement the generate() function below for your model.
"""
import asyncio
import argparse
import json
import re
import sys
import time
from pathlib import Path


# ── Implement this for your model ─────────────────────────────────────────────
async def generate(prompt: str, model: str) -> str:
    """
    Call your model and return the generated Luau code.

    Example — OpenAI:
        from openai import AsyncOpenAI
        client = AsyncOpenAI()
        resp = await client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.choices[0].message.content

    Example — Anthropic:
        import anthropic
        client = anthropic.AsyncAnthropic()
        resp = await client.messages.create(
            model=model, max_tokens=4096,
            messages=[{"role": "user", "content": prompt}]
        )
        return resp.content[0].text
    """
    raise NotImplementedError(
        "Implement generate() with your model's API call.\n"
        "See the docstring above for OpenAI and Anthropic examples."
    )


# ── Load tasks and graders ─────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from gold_standard import TASKS
from eval_graders import (
    has_strict_mode, uses_task_library, no_deprecated_apis,
    no_instance_new_parent_arg, datastore_wrapped_in_pcall,
    datastore_uses_write_behind, has_remote_contract_pairing,
    has_server_and_client, has_multi_file_output, server_validates_remote,
    no_fireserver_player_arg, no_cross_boundary_require, has_remote_rate_limit,
)


# ── Per-task runner ────────────────────────────────────────────────────────────
async def run_task(task, model: str, trial: int) -> dict:
    t0 = time.monotonic()
    code = ""
    error = ""

    try:
        code = await generate(task.prompt, model)
        # Strip markdown fences if model wraps code
        code = re.sub(r"^```(?:lua|luau)?\s*\n?", "", code, flags=re.MULTILINE)
        code = re.sub(r"\n?```\s*$", "", code, flags=re.MULTILINE).strip()
    except NotImplementedError:
        raise
    except Exception as e:
        error = str(e)

    latency_ms = int((time.monotonic() - t0) * 1000)

    # Build a single-file context for on_files checks
    files = [{"code": code, "type": "Script", "filename": "MainServer"}]

    results: dict[str, bool] = {}
    for check in task.checks:
        try:
            on_files = getattr(check, "on_files", False)
            results[check.name] = bool(check.fn(files) if on_files else check.fn(code))
        except Exception:
            results[check.name] = False

    passed = all(results.values())
    score  = sum(results.values()) / len(results) if results else 0.0

    status = "PASS" if passed else "FAIL"
    print(f"  {status}  {task.id}  (trial {trial})  score={score:.0%}  {latency_ms}ms")
    if error:
        print(f"    ERROR: {error}")
    for name, ok in results.items():
        print(f"    [{'PASS' if ok else 'FAIL'}]  {name}")

    return {
        "task_id":      task.id,
        "trial":        trial,
        "passed":       passed,
        "score":        score,
        "check_results": results,
        "latency_ms":   latency_ms,
        "error":        error,
    }


# ── Main ───────────────────────────────────────────────────────────────────────
async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Roblox Lua Benchmark — evaluate any LLM on Roblox/Luau tasks"
    )
    parser.add_argument("--model",  default="your-model", help="Model name passed to generate()")
    parser.add_argument("--trials", type=int, default=1,  help="Trials per task (default: 1)")
    parser.add_argument("--task",   default="",           help="Run a single task by ID")
    args = parser.parse_args()

    tasks = [t for t in TASKS if not args.task or t.id == args.task]
    if not tasks:
        print(f"Task '{args.task}' not found. Available: {[t.id for t in TASKS]}")
        return

    all_results: list[dict] = []
    print(f"\nRoblox Lua Benchmark")
    print(f"Model:  {args.model}")
    print(f"Tasks:  {len(tasks)}  ×  {args.trials} trial(s)")
    print(f"{'='*60}")

    for task in tasks:
        print(f"\n[{task.id}]")
        print(f"  {task.prompt[:100]}...")
        for trial in range(1, args.trials + 1):
            result = await run_task(task, args.model, trial)
            all_results.append(result)

    # ── Summary ────────────────────────────────────────────────────────────────
    total  = len(all_results)
    passed = sum(1 for r in all_results if r["passed"])
    avg    = sum(r["score"] for r in all_results) / total if total else 0.0

    print(f"\n{'='*60}")
    print(f"  Model:      {args.model}")
    print(f"  Pass rate:  {passed}/{total}  ({passed/total:.0%})")
    print(f"  Avg score:  {avg:.0%}")
    print(f"{'='*60}\n")

    out = Path(f"results_{args.model.replace(':', '_').replace('/', '_')}.json")
    out.write_text(json.dumps(all_results, indent=2))
    print(f"Results saved → {out}")


if __name__ == "__main__":
    asyncio.run(main())
