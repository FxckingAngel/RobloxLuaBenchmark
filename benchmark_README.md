# Roblox Lua Benchmark

An objective benchmark for evaluating AI coding assistants on Roblox/Luau tasks.

All 196 checks are **fully automated** — zero human judgment. Fork it, point it at any model, get a score.

## Results

| Model | Pass Rate | Avg Score |
|-------|-----------|-----------|
| **Nova** | **TBD** | **TBD** |
| Claude Sonnet 4.6 | — | — |
| GPT-4o | — | — |

*Run the benchmark yourself and submit a PR with your results.*

## Why this is hard for general models

General LLMs trained on internet data treat Roblox like plain Lua. They consistently fail on platform-specific patterns:

| Pattern | What general models do | What's correct |
|---------|----------------------|----------------|
| `Players.LocalPlayer` | Use it anywhere | **nil on server** — LocalScript only |
| `Touched` event | Connect without debounce | Fires **every physics frame** — needs debounce |
| `tick()` | Use for timing | **Deprecated and exploitable** — use `os.clock()` |
| `FireServer(player, ...)` | Pass player manually | **Auto-injected** — passing it shifts all args |
| `pairs()` on stages | Iterate stage order | **No guaranteed order** — use `ipairs()` |
| `SetAsync` in `OnServerEvent` | Write on every event | **Hits rate limits** — write-behind cache only |
| `UpdateAsync` | Use `SetAsync` instead | **Required for atomicity** — callback returns nil to abort |
| `Instance.new("Part", parent)` | Pass parent as 2nd arg | **10x slower** — set `.Parent` last |

## Benchmark structure

28 tasks across 6 tiers:

**Tier 1 — Roblox Gotchas** (8 tasks)
Things every general LLM gets wrong about the platform. A model that knows Lua but not Roblox fails these.

**Tier 2 — Security** (4 tasks)
Exploit prevention. Server-authoritative damage, remote validation, anti-speedhack, economy authority.

**Tier 3 — DataStore Patterns** (4 tasks)
Correct persistence. Write-behind cache, atomic `UpdateAsync`, session locking, `OrderedDataStore`.

**Tier 4 — Full Systems** (4 tasks)
Complete working multi-file systems: round system, pet system, trading, anti-cheat stack.

**Tier 5 — Advanced APIs** (5 tasks)
Parallel Luau Actors, `RemoteFunction` timeouts, constraint-based vehicles, circular buffers.

**Tier 6 — Code Quality** (3 tasks)
No deprecated APIs, zero memory leaks, full Luau type annotations.

## How to run

```bash
git clone https://github.com/FxckingAngel/RobloxLuaBenchmark
cd RobloxLuaBenchmark
pip install asyncio
```

Open `runner.py` and implement the `generate()` function for your model:

```python
async def generate(prompt: str, model: str) -> str:
    # OpenAI example:
    from openai import AsyncOpenAI
    client = AsyncOpenAI()
    resp = await client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}]
    )
    return resp.choices[0].message.content
```

Then run:

```bash
# Single trial (quick check)
python runner.py --model gpt-4o --trials 1

# Full benchmark (3 trials per task — matches official scoring)
python runner.py --model gpt-4o --trials 3

# Single task for debugging
python runner.py --model gpt-4o --task gs_touched_debounce
```

Results are saved to `results_<model>.json`.

## Submitting results

Run with `--trials 3` and open a PR adding your row to the results table above.
Include the `results_<model>.json` file.

## Notes

- The benchmark uses single-file evaluation. Multi-file tasks (`on_files=True` checks) evaluate the combined output.
- A model with a strong Roblox-specific system prompt will score higher than a vanilla API call.
- That's intentional — knowing the platform is the point.
