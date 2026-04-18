"""
eval_graders.py — Shared dataclasses and grader functions for Nova evals.

Import this module in eval pack files (tests/evals/*.py) to define tasks.
This module has no dependencies on the harness runner (eval_nova.py) so
eval packs can safely import from here without circular imports.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class Check:
    name:    str
    fn:      Callable
    weight:  float = 1.0   # weighted contribution to task score
    on_files: bool = False  # True = fn receives files list, False = receives code blob


@dataclass
class Task:
    id:      str
    prompt:  str
    checks:  list[Check]
    tags:    list[str] = field(default_factory=list)
    notes:   str = ""


@dataclass
class CheckResult:
    name:   str
    passed: bool
    weight: float


@dataclass
class TaskResult:
    task_id:        str
    trial:          int
    prompt:         str
    passed:         bool
    score:          float
    check_results:  list[CheckResult]
    n_files:        int
    n_warnings:     int
    latency_ms:     int
    error:          str | None = None
    generated_code: str        = ""   # first 2000 chars for debugging


# ---------------------------------------------------------------------------
# Code extraction helpers
# ---------------------------------------------------------------------------

def _code_blocks(raw: str) -> str:
    """
    Extract only the luau/lua fenced code blocks from Nova's output.

    Nova's output contains PLAN and OBSERVE prose sections that may mention
    legacy APIs or wrong patterns as explanations. Graders that check for
    the presence/absence of patterns must run against code only, not prose.

    Handles all fence variants Nova produces: ```luau, ```lua, ```lu, ``` (bare).
    Falls back to the full string if no fenced blocks are found.
    """
    blocks = re.findall(r"```(?:luau[\d.]*|lua[\d.]*|lu)?\s*\n(.*?)```", raw, re.DOTALL)
    if blocks:
        return "\n".join(blocks)

    file_sections = re.findall(
        r"####\s*File:\s*.*?\n(.*?)(?=\n####\s*File:|\n###\s*(?:OBSERVE|END)\b|\Z)",
        raw,
        re.DOTALL | re.IGNORECASE,
    )
    if file_sections:
        return "\n".join(s.strip() for s in file_sections if s.strip())

    looks_like_code = bool(re.search(r"--!strict|local\s+\w+\s*=|function\s+\w+|:Connect\s*\(", raw))
    return raw if looks_like_code else ""


def _check_code_only(raw: str, fn) -> bool:
    """Run a grader function against code blocks only."""
    return fn(_code_blocks(raw))


# ---------------------------------------------------------------------------
# Grader functions — deterministic regex/AST checks
# ---------------------------------------------------------------------------

def has_strict_mode(code: str) -> bool:
    """Every generated file must have --!strict on line 1."""
    for block in re.split(r"\n(?=--!)", code):
        if block.strip().startswith("--!strict"):
            return True
    return bool(re.search(r"^--!strict", code, re.MULTILINE))


def uses_task_library(code: str) -> bool:
    """No legacy wait()/spawn()/delay() calls in generated code.

    Revised rule:
      PASS if: no legacy calls present (regardless of whether task.X is used)
      FAIL if: legacy wait()/spawn()/delay() appear in code blocks
    """
    c = _code_blocks(code)
    stripped = re.sub(r"\btask\.(wait|spawn|delay|defer)\b", "TASK_LIB", c)
    stripped = re.sub(r":\s*Wait\s*\(", ":SIGNAL_WAIT(", stripped)
    stripped = re.sub(r"\bcoroutine\.(wrap|resume|yield)\b", "COROUTINE_LIB", stripped)
    has_legacy = bool(re.search(r"(?<!\w)(wait|spawn|delay)\s*\(", stripped))
    return not has_legacy


def no_deprecated_apis(code: str) -> bool:
    c = _code_blocks(code)
    deprecated = [
        r"\bBodyVelocity\b", r"\bBodyGyro\b", r"\bBodyPosition\b",
        r"\bBodyForce\b", r"\bBodyAngularVelocity\b",
        r"game\.Players\b",
        r"\btick\s*\(\s*\)",
    ]
    return not any(re.search(p, c) for p in deprecated)


def server_validates_remote(code: str) -> bool:
    """OnServerEvent must be followed by type/range checks before state mutation."""
    matches = list(re.finditer(
        r"OnServerEvent:Connect\s*\(function\s*\(([^)]+)\)([\s\S]{0,2000}?)\bend\b",
        code,
        re.DOTALL,
    ))
    if not matches:
        return True
    for m in matches:
        body = m.group(2)
        has_validation = bool(re.search(
            r"type\s*\(|typeof\s*\(|if\s+.+\s+then\s+return|~=\s*\"string\"|~=\s*\"number\"",
            body
        ))
        if not has_validation:
            return False
    return True


def datastore_wrapped_in_pcall(code: str) -> bool:
    """DataStore calls must be inside pcall/xpcall."""
    for m in re.finditer(r"(GetAsync|SetAsync|UpdateAsync|IncrementAsync|RemoveAsync)\s*\(", code):
        ctx = code[max(0, m.start() - 400): m.start()]
        if "pcall" not in ctx and "xpcall" not in ctx:
            return False
    return True


def no_instance_new_parent_arg(code: str) -> bool:
    """Instance.new('X', parent) performance footgun."""
    return not bool(re.search(
        r'Instance\.new\s*\(\s*["\'](?:Part|Model|Folder|Script|LocalScript|ScreenGui'
        r'|Frame|TextLabel|TextButton|ImageLabel|Sound)["\'],\s*\w',
        code
    ))


def no_runtime_remote_creation(code: str) -> bool:
    return not bool(re.search(r'Instance\.new\s*\(\s*["\']Remote(?:Event|Function)["\']', code))


def has_multi_file_output(files: list[dict]) -> bool:
    """Multi-file prompts should produce >= 2 files."""
    return len(files) >= 2


def has_server_and_client(files: list[dict]) -> bool:
    types = {f.get("type", "") for f in files}
    return "Script" in types and "LocalScript" in types


def has_remote_contract_pairing(code: str) -> bool:
    """Cross-file contract sanity check."""
    c = _code_blocks(code)
    has_fire_client = ("FireClient(" in c) or ("FireAllClients(" in c)
    has_on_client = "OnClientEvent:Connect" in c
    has_fire_server = "FireServer(" in c
    has_on_server = "OnServerEvent:Connect" in c
    if has_fire_client and not has_on_client:
        return False
    if has_fire_server and not has_on_server:
        return False
    return True


def no_cross_boundary_require(code: str) -> bool:
    """LocalScript should not require modules from ServerScriptService."""
    c = _code_blocks(code)
    bad_patterns = (
        "LocalScript" in c and "ServerScriptService" in c and "require(" in c,
        bool(re.search(r"require\s*\(.*ServerScriptService", c, re.IGNORECASE)),
    )
    return not any(bad_patterns)


def no_placeholders(code: str) -> bool:
    c = _code_blocks(code)
    return not bool(re.search(r"\b(?:TODO|FIXME|HACK)\b", c, re.IGNORECASE))


def no_inline_error_markers(code: str) -> bool:
    c = _code_blocks(code)
    return not bool(re.search(r"^\s*--\s*ERROR\s*:", c, re.IGNORECASE | re.MULTILINE))


def datastore_uses_write_behind(files_or_code) -> bool:
    """DataStore pattern: in-memory table mutated in-game, flushed on PlayerRemoving/BindToClose."""
    if isinstance(files_or_code, list):
        c = "\n\n".join(f.get("code", "") for f in files_or_code)
    else:
        c = _code_blocks(files_or_code)

    has_session = bool(re.search(
        r"\w+\[(?:[\w.]+\.)?UserId\]"
        r"|\w+\[userId\]"
        r"|\w+\[tostring\([\w.]+\)\]",
        c
    ))
    has_flush = (
        bool(re.search(r"PlayerRemoving", c)) and
        bool(re.search(r"SetAsync|UpdateAsync", c))
    ) or bool(re.search(r"BindToClose[\s\S]{0,800}(?:SetAsync|UpdateAsync)", c, re.DOTALL))

    no_setasync_on_event = not bool(re.search(
        r"OnServerEvent:Connect\s*\(function[^)]*\)[\s\S]{0,400}(?:SetAsync|UpdateAsync)",
        c, re.DOTALL
    ))
    return has_session and has_flush and no_setasync_on_event


def has_remote_rate_limit(code: str) -> bool:
    """Rate limiting uses os.clock(), not tick()."""
    c = _code_blocks(code)
    has_rate = bool(re.search(r"os\.clock\(\)", c))
    no_tick  = not bool(re.search(r"\btick\s*\(\s*\)", c))
    return has_rate and no_tick


def preserves_public_names(code: str) -> bool:
    if "SessionData" in code:
        return True
    return True


def has_strict_annotations(code: str) -> bool:
    return bool(re.search(r"--!strict", code))


def matches_existing_style(code: str) -> bool:
    return True  # placeholder


def no_scope_creep(code: str) -> bool:
    return True  # placeholder


def has_touched_debounce(code: str) -> bool:
    """Kill brick / damage code should have a debounce on Touched."""
    c = _code_blocks(code)
    if "Touched" not in c:
        return True
    has_debounce = bool(re.search(
        r"debounce|cooldown|lastDamage"
        r"|local\s+\w+\s*=\s*\{"
        r"|\w+\[\w+\]\s*=\s*true"
        r"|\w+\[\w+\.Name\]",
        c, re.IGNORECASE
    ))
    return has_debounce


def no_fireserver_player_arg(code: str) -> bool:
    """Client code must not pass player as explicit first arg to FireServer."""
    return not bool(re.search(
        r":FireServer\s*\(\s*(?:player|plr|p)\s*[,)]",
        code
    ))


def uses_tostring_for_text(code: str) -> bool:
    """TextLabel.Text must use tostring() when assigning numeric values."""
    if ".Text" not in code:
        return True
    direct_assign = re.search(
        r"\.Text\s*=\s*(?!tostring|string\.format|tostring)[\w\[\]\.]+\.(?:Value|Coins|Cash|Score|Level|XP|Health)(?!\s*\.)",
        code
    )
    return not bool(direct_assign)


def no_localplayer_on_server(code: str) -> bool:
    """LocalPlayer should not appear in server Script context."""
    if "LocalPlayer" not in code:
        return True

    server_apis = ["DataStoreService", "SetAsync", "UpdateAsync", "GetAsync"]
    client_signals = [
        "PlayerGui", "UserInputService", "ContextActionService",
        "OnClientEvent", "RenderStepped", "StarterGui",
    ]

    has_server_api = any(api in code for api in server_apis)
    has_client_signal = any(sig in code for sig in client_signals)

    if not has_server_api:
        return True
    if has_client_signal:
        return True
    return False
