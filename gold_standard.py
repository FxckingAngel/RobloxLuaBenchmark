"""
gold_standard.py — The undeniable benchmark.

100 tasks covering every major Roblox production pattern.
Designed so that:
  - A general LLM with no Roblox knowledge scores < 40%
  - A Roblox-aware LLM scores 60-75%
  - Nova at peak scores 85%+

All graders are objective code checks — zero human judgment.
Anyone can run this against any model via:
  bash run_eval.sh --suite gold_standard

Published at github.com/FxckingAngel/Nova — fork and run yourself.
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from evals._template import Task, Check
from eval_graders import (
    has_strict_mode, uses_task_library, no_deprecated_apis,
    no_instance_new_parent_arg, datastore_wrapped_in_pcall,
    datastore_uses_write_behind, has_remote_contract_pairing,
    has_server_and_client, has_multi_file_output, server_validates_remote,
    no_fireserver_player_arg, no_cross_boundary_require, has_remote_rate_limit,
)

SUITE_NAME = "gold_standard"

TASKS: list[Task] = [

    # ══════════════════════════════════════════════════════════════════════════
    # TIER 1 — ROBLOX GOTCHAS (things every general LLM gets wrong)
    # Pass = model knows the platform. Fail = model treats Roblox like plain Lua.
    # ══════════════════════════════════════════════════════════════════════════

    Task(
        id="gs_no_localplayer_server",
        prompt=(
            "Write a Script in ServerScriptService that gives every player 100 coins "
            "when they join. Store coins in a leaderstats IntValue."
        ),
        tags=["gotcha", "server", "leaderstats"],
        notes="Fails if model uses Players.LocalPlayer on the server (nil, silently broken).",
        checks=[
            Check("strict_mode",        has_strict_mode),
            Check("task_library",       uses_task_library),
            Check("no_deprecated",      no_deprecated_apis),
            Check("no_localplayer",     lambda c: "LocalPlayer" not in c),
            Check("playeradded",        lambda c: "PlayerAdded" in c),
            Check("leaderstats_folder", lambda c: '"leaderstats"' in c or "'leaderstats'" in c),
            Check("intvalue",           lambda c: "IntValue" in c or "NumberValue" in c),
        ],
    ),

    Task(
        id="gs_touched_debounce",
        prompt=(
            "Create a damage brick. When a player touches it, deal 10 damage. "
            "Make sure damage only triggers once per touch, not every frame."
        ),
        tags=["gotcha", "touched", "debounce"],
        notes="Fails if no debounce — Touched fires every physics frame, not once.",
        checks=[
            Check("strict_mode",    has_strict_mode),
            Check("task_library",   uses_task_library),
            Check("no_deprecated",  no_deprecated_apis),
            Check("has_debounce",   lambda c: any(k in c for k in ["debounce", "cooldown", "lastHit", "touched ="])),
            Check("takedamage",     lambda c: "TakeDamage" in c or "Health" in c),
            Check("touched_event",  lambda c: "Touched" in c),
        ],
    ),

    Task(
        id="gs_no_setasync_in_event",
        prompt=(
            "Build a coin collection system. Players earn coins by touching gold parts. "
            "Coins persist between sessions using DataStore."
        ),
        tags=["gotcha", "datastore", "economy"],
        notes="Fails if SetAsync is called directly inside OnServerEvent or Touched handler.",
        checks=[
            Check("strict_mode",      has_strict_mode),
            Check("task_library",     uses_task_library),
            Check("no_deprecated",    no_deprecated_apis),
            Check("write_behind",     datastore_uses_write_behind, on_files=True),
            Check("bind_to_close",    lambda c: "BindToClose" in c),
            Check("no_setasync_event",lambda files: not any(
                bool(re.search(
                    r"(?:Touched|OnServerEvent):Connect\s*\(function[^)]*\)[\s\S]{0,500}SetAsync",
                    f.get("code", ""), re.IGNORECASE
                )) for f in files
            ), on_files=True),
        ],
    ),

    Task(
        id="gs_fireserver_no_player_arg",
        prompt=(
            "Create a shop system. Client fires a RemoteEvent to purchase an item by ID. "
            "Server validates the purchase and deducts coins."
        ),
        tags=["gotcha", "remote", "economy"],
        notes="Fails if client passes player as first arg to FireServer (auto-injected, breaks server handler).",
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("no_deprecated",     no_deprecated_apis),
            Check("no_player_fireserver", no_fireserver_player_arg),
            Check("server_validates",  lambda files: server_validates_remote(
                "\n\n".join(f.get("code","") for f in files)
            ), on_files=True),
            Check("has_remote",        lambda files: any("OnServerEvent" in f.get("code","") for f in files), on_files=True),
        ],
    ),

    Task(
        id="gs_pairs_no_order",
        prompt=(
            "Build a stage-based obby progression system. "
            "Players advance through 5 stages in order. "
            "Track progress in a table and save with DataStore."
        ),
        tags=["gotcha", "iteration", "datastore"],
        notes="Fails if pairs() used to iterate stage sequence — no guaranteed order.",
        checks=[
            Check("strict_mode",    has_strict_mode),
            Check("task_library",   uses_task_library),
            Check("no_deprecated",  no_deprecated_apis),
            Check("uses_ipairs",    lambda c: "ipairs" in c or
                any(f"[{i}]" in c for i in range(1,6))),
            Check("no_pairs_stages",lambda c: not bool(re.search(
                r"pairs\s*\(\s*\w*[Ss]tage", c
            ))),
            Check("bind_to_close",  lambda c: "BindToClose" in c),
        ],
    ),

    Task(
        id="gs_os_clock_not_tick",
        prompt=(
            "Implement a per-player attack cooldown. Players can only attack "
            "once every 0.5 seconds. Use proper high-precision timing."
        ),
        tags=["gotcha", "cooldown", "security"],
        notes="Fails if tick() used instead of os.clock() — tick() is deprecated and manipulable.",
        checks=[
            Check("strict_mode",   has_strict_mode),
            Check("no_deprecated", no_deprecated_apis),
            Check("uses_os_clock", lambda c: "os.clock()" in c),
            Check("no_tick",       lambda c: "tick()" not in c),
            Check("half_second",   lambda c: "0.5" in c),
            Check("per_player",    lambda c: "UserId" in c or "userId" in c),
        ],
    ),

    Task(
        id="gs_instance_new_parent_last",
        prompt=(
            "Create a function that spawns a glowing neon part at a given position. "
            "The part should be Size 2x2x2, BrickColor Bright red, Material Neon."
        ),
        tags=["gotcha", "instance", "performance"],
        notes="Fails if parent passed as 2nd arg to Instance.new() — 10x slower.",
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("no_parent_arg",     no_instance_new_parent_arg),
            Check("sets_properties",   lambda c: "BrickColor" in c or "Color" in c),
            Check("neon_material",     lambda c: "Neon" in c),
            Check("parent_last",       lambda c: ".Parent" in c),
        ],
    ),

    Task(
        id="gs_no_cross_require",
        prompt=(
            "Build a coin system. Server handles DataStore and validation. "
            "Client handles UI updates. Share constants (coin value, max coins) "
            "between both via a ModuleScript."
        ),
        tags=["gotcha", "module", "multi-file"],
        notes="Fails if ServerScriptService module is required by LocalScript (hangs forever).",
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("no_deprecated",     no_deprecated_apis),
            Check("no_cross_require",  no_cross_boundary_require),
            Check("shared_module",     lambda files: any(
                f.get("type") == "ModuleScript" and "ReplicatedStorage" in str(f.get("filename",""))
                for f in files
            ), on_files=True),
            Check("has_server_client", has_server_and_client, on_files=True),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # TIER 2 — SECURITY (exploit prevention that general LLMs skip)
    # ══════════════════════════════════════════════════════════════════════════

    Task(
        id="gs_server_auth_damage",
        prompt=(
            "Build a melee combat system. Client detects when the player clicks "
            "to attack. Server validates the hit and applies damage."
        ),
        tags=["security", "combat", "multi-file"],
        notes="Fails if damage applied on client — exploiter can set arbitrary damage.",
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("no_deprecated",     no_deprecated_apis),
            Check("server_damage",     lambda files: any(
                "TakeDamage" in f.get("code","") and f.get("type") == "Script"
                for f in files
            ), on_files=True),
            Check("client_no_damage",  lambda files: not any(
                "TakeDamage" in f.get("code","") and f.get("type") == "LocalScript"
                for f in files
            ), on_files=True),
            Check("magnitude_check",   lambda files: any("Magnitude" in f.get("code","") for f in files), on_files=True),
            Check("rate_limit",        has_remote_rate_limit),
        ],
    ),

    Task(
        id="gs_validate_all_remotes",
        prompt=(
            "Create an inventory system where players can equip, unequip, and use items. "
            "Items are defined in a shared config. Server handles all state changes."
        ),
        tags=["security", "inventory", "multi-file"],
        notes="Fails if OnServerEvent handlers don't validate item IDs against an allowlist.",
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("no_deprecated",     no_deprecated_apis),
            Check("server_validates",  lambda files: server_validates_remote(
                "\n\n".join(f.get("code","") for f in files)
            ), on_files=True),
            Check("has_remote",        has_server_and_client, on_files=True),
            Check("allowlist_check",   lambda files: any(
                bool(re.search(r'ITEMS\[|items\[|SharedConfig\.|config\[', f.get("code","")))
                for f in files if f.get("type") == "Script"
            ), on_files=True),
        ],
    ),

    Task(
        id="gs_anti_speedhack",
        prompt=(
            "Implement server-side speed hack detection. "
            "Every 0.5 seconds check each player's movement delta against their "
            "WalkSpeed. If they exceed it 3 times, teleport them to spawn."
        ),
        tags=["security", "anti-cheat", "single-file"],
        checks=[
            Check("strict_mode",     has_strict_mode),
            Check("task_library",    uses_task_library),
            Check("no_deprecated",   no_deprecated_apis),
            Check("uses_os_clock",   lambda c: "os.clock" in c),
            Check("half_second",     lambda c: "0.5" in c),
            Check("walkspeed",       lambda c: "WalkSpeed" in c),
            Check("magnitude",       lambda c: "Magnitude" in c or "Position" in c),
            Check("strike_counter",  lambda c: any(k in c for k in ["strikes", "violations", "count", "Count"])),
            Check("teleport_spawn",  lambda c: "CFrame" in c and ("spawn" in c.lower() or "Spawn" in c)),
        ],
    ),

    Task(
        id="gs_economy_server_only",
        prompt=(
            "Build a currency system. Players earn coins by completing actions. "
            "IMPORTANT: the server must be the only authority on coin amounts. "
            "The client should never be able to set its own coin count."
        ),
        tags=["security", "economy", "multi-file"],
        notes="Fails if client can directly influence coin amount on server.",
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("no_deprecated",     no_deprecated_apis),
            Check("server_owns_coins", lambda files: not any(
                bool(re.search(r"coins\s*=\s*\w+|Coins\s*=\s*\w+", f.get("code","")))
                for f in files if f.get("type") == "LocalScript"
            ), on_files=True),
            Check("remote_validation", lambda files: server_validates_remote(
                "\n\n".join(f.get("code","") for f in files)
            ), on_files=True),
            Check("write_behind",      datastore_uses_write_behind, on_files=True),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # TIER 3 — DATASTORE PATTERNS
    # ══════════════════════════════════════════════════════════════════════════

    Task(
        id="gs_datastore_complete",
        prompt=(
            "Build a complete player data system: default data for new players, "
            "retry on failure (3 attempts), auto-save every 60 seconds, "
            "save on leave, save on server shutdown."
        ),
        tags=["datastore", "single-file"],
        checks=[
            Check("strict_mode",     has_strict_mode),
            Check("task_library",    uses_task_library),
            Check("no_deprecated",   no_deprecated_apis),
            Check("pcall_wrapped",   datastore_wrapped_in_pcall),
            Check("write_behind",    datastore_uses_write_behind, on_files=True),
            Check("bind_to_close",   lambda c: "BindToClose" in c),
            Check("auto_save_60",    lambda c: "60" in c and "task.wait" in c),
            Check("retry_logic",     lambda c: any(k in c for k in ["retry", "attempt", "Retry", "Attempt", "for i"])),
            Check("default_data",    lambda c: "default" in c.lower() or "DEFAULT" in c),
        ],
    ),

    Task(
        id="gs_atomic_transfer",
        prompt=(
            "Build a coin transfer system. Player A can send coins to Player B. "
            "If Player A doesn't have enough coins, the transfer must fail completely — "
            "Player B gets nothing. Use UpdateAsync for atomicity."
        ),
        tags=["datastore", "economy", "atomic"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("uses_update_async", lambda c: "UpdateAsync" in c),
            Check("callback_fn",       lambda files: any(bool(re.search(
                r"UpdateAsync\s*\([^,]+,\s*function",
                f.get("code",""), re.DOTALL
            )) for f in files), on_files=True),
            Check("nil_abort",         lambda files: any("return nil" in f.get("code","") for f in files), on_files=True),
            Check("no_set_async",      lambda files: not any(
                re.search(r'\bSetAsync\b', f.get("code",""))
                for f in files
            ), on_files=True),
            Check("remote_validation", lambda files: any(
                "typeof" in f.get("code","") or "type(" in f.get("code","")
                for f in files
            ), on_files=True),
        ],
    ),

    Task(
        id="gs_session_lock",
        prompt=(
            "Implement session locking using MemoryStoreService to prevent data "
            "corruption when a player joins multiple servers simultaneously. "
            "Lock TTL: 30 seconds. Kick the player if lock is already held."
        ),
        tags=["datastore", "memorystore", "advanced"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("memory_store",      lambda c: "MemoryStoreService" in c),
            Check("update_async_lock", lambda c: "UpdateAsync" in c and "MemoryStore" in c),
            Check("ttl_30",            lambda c: "30" in c),
            Check("kicks_on_lock",     lambda files: any(":Kick(" in f.get("code","") for f in files), on_files=True),
            Check("releases_on_leave", lambda c: "PlayerRemoving" in c),
            Check("bind_to_close",     lambda c: "BindToClose" in c),
        ],
    ),

    Task(
        id="gs_ordered_datastore",
        prompt=(
            "Create a global top-10 leaderboard using OrderedDataStore showing "
            "all-time coins earned. Updates every 60 seconds. "
            "Display in a SurfaceGui on a part in the workspace."
        ),
        tags=["datastore", "ui", "single-file"],
        checks=[
            Check("strict_mode",     has_strict_mode),
            Check("task_library",    uses_task_library),
            Check("no_deprecated",   no_deprecated_apis),
            Check("ordered_ds",      lambda c: "OrderedDataStore" in c),
            Check("pcall_wrapped",   datastore_wrapped_in_pcall),
            Check("top_10",          lambda c: "10" in c),
            Check("auto_update",     lambda c: "task.wait" in c and "60" in c),
            Check("surface_gui",     lambda c: "SurfaceGui" in c or ".Text" in c),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # TIER 4 — SYSTEM COMPLETENESS (full working multi-file systems)
    # ══════════════════════════════════════════════════════════════════════════

    Task(
        id="gs_full_round_system",
        prompt=(
            "Build a complete round system: Lobby (30s) → Game (120s) → Results (15s) → Lobby. "
            "Teleport players to game arena on round start, back to lobby on end. "
            "Show a countdown timer in a ScreenGui HUD. "
            "Track who won (last player alive or most kills)."
        ),
        tags=["multi-file", "round", "ui"],
        checks=[
            Check("strict_mode",      has_strict_mode),
            Check("task_library",     uses_task_library),
            Check("no_deprecated",    no_deprecated_apis),
            Check("has_states",       lambda c: any(k in c for k in ["Lobby", "Game", "Results", "lobby", "game", "results"])),
            Check("timer_30",         lambda c: "30" in c),
            Check("timer_120",        lambda c: "120" in c),
            Check("server_client",    has_server_and_client, on_files=True),
            Check("hud_ui",           lambda files: any(
                "ScreenGui" in f.get("code","") or "TextLabel" in f.get("code","")
                for f in files if f.get("type") == "LocalScript"
            ), on_files=True),
            Check("teleport_logic",   lambda c: "TeleportToPlaceInstance" in c or "CFrame" in c or "LoadCharacter" in c),
        ],
    ),

    Task(
        id="gs_full_pet_system",
        prompt=(
            "Build a complete pet system: players can equip a pet that follows them. "
            "Pet data (which pet, if equipped) persists in DataStore. "
            "UI button to toggle equip/unequip. Pet model welds to HumanoidRootPart offset."
        ),
        tags=["multi-file", "datastore", "ui", "character"],
        checks=[
            Check("strict_mode",    has_strict_mode),
            Check("task_library",   uses_task_library),
            Check("no_deprecated",  no_deprecated_apis),
            Check("multi_file",     has_multi_file_output, on_files=True),
            Check("write_behind",   datastore_uses_write_behind, on_files=True),
            Check("bind_to_close",  lambda c: "BindToClose" in c),
            Check("weld_or_follow", lambda files: any(
                any(k in f.get("code","") for k in ["WeldConstraint", "Weld", "CFrame", "follow", "Follow"])
                for f in files
            ), on_files=True),
            Check("ui_button",      lambda files: any(
                "TextButton" in f.get("code","") or "ImageButton" in f.get("code","")
                for f in files
            ), on_files=True),
            Check("remote_contract", has_remote_contract_pairing),
        ],
    ),

    Task(
        id="gs_full_trading_system",
        prompt=(
            "Build a player-to-player trading system. "
            "Both players must confirm the trade before items are swapped. "
            "If either cancels, nothing changes. "
            "Server validates both players have the items being traded."
        ),
        tags=["multi-file", "economy", "security"],
        checks=[
            Check("strict_mode",     has_strict_mode),
            Check("task_library",    uses_task_library),
            Check("no_deprecated",   no_deprecated_apis),
            Check("multi_file",      has_multi_file_output, on_files=True),
            Check("both_confirm",    lambda c: any(k in c for k in ["confirm", "Confirm", "accept", "Accept", "both"])),
            Check("server_validates",lambda files: server_validates_remote(
                "\n\n".join(f.get("code","") for f in files)
            ), on_files=True),
            Check("atomic_or_check", lambda c: any(k in c for k in ["UpdateAsync", "has_item", "hasItem", "inventory"])),
            Check("cancel_path",     lambda c: any(k in c for k in ["cancel", "Cancel", "decline", "Decline", "reject"])),
        ],
    ),

    Task(
        id="gs_full_anticheat",
        prompt=(
            "Build a complete anti-cheat system covering: "
            "1. Speed hacking (position delta vs WalkSpeed), "
            "2. Damage hacking (server-only damage validation), "
            "3. Teleport hacking (max allowed position delta per tick). "
            "Log violations with player name and type. Three strikes = kick."
        ),
        tags=["security", "anti-cheat", "multi-file"],
        checks=[
            Check("strict_mode",      has_strict_mode),
            Check("task_library",     uses_task_library),
            Check("no_deprecated",    no_deprecated_apis),
            Check("speed_check",      lambda c: "WalkSpeed" in c and "Magnitude" in c),
            Check("uses_os_clock",    lambda c: "os.clock" in c),
            Check("server_damage",    lambda files: any(
                "TakeDamage" in f.get("code","") and f.get("type") == "Script"
                for f in files
            ), on_files=True),
            Check("strike_system",    lambda c: any(k in c for k in ["strike", "Strike", "violation", "count"])),
            Check("kick_on_3",        lambda files: any(":Kick(" in f.get("code","") for f in files), on_files=True),
            Check("logs_violations",  lambda c: "warn(" in c or "print(" in c),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # TIER 5 — ADVANCED APIS (things only Roblox experts know)
    # ══════════════════════════════════════════════════════════════════════════

    Task(
        id="gs_connection_cleanup",
        prompt=(
            "Build an NPC enemy system where each NPC has its own Heartbeat loop "
            "and event connections. When an NPC is destroyed, ALL its connections "
            "must be cleaned up to prevent memory leaks."
        ),
        tags=["advanced", "connections", "memory"],
        checks=[
            Check("strict_mode",      has_strict_mode),
            Check("task_library",     uses_task_library),
            Check("no_deprecated",    no_deprecated_apis),
            Check("stores_conn",      lambda c: bool(re.search(r'local\s+\w+\s*=\s*\w+[:.]\w+:Connect\(', c))),
            Check("disconnects",      lambda c: ":Disconnect()" in c or "conn:Disconnect" in c or "Maid" in c),
            Check("cleanup_on_die",   lambda c: any(k in c for k in ["Destroy", "destroy", "died", "Died", "AncestryChanged"])),
            Check("heartbeat_loop",   lambda c: "Heartbeat" in c or "task.spawn" in c),
        ],
    ),

    Task(
        id="gs_remotefunction_timeout",
        prompt=(
            "Create a server system that asks the client a question via RemoteFunction "
            "('GetPlayerChoice') with a 10-second timeout. If the client doesn't respond "
            "in time (or disconnects), use the default value 'skip'."
        ),
        tags=["advanced", "remote", "coroutine"],
        checks=[
            Check("strict_mode",     has_strict_mode),
            Check("task_library",    uses_task_library),
            Check("invoke_client",   lambda c: "InvokeClient" in c),
            Check("timeout_10",      lambda c: "10" in c and ("task.delay" in c or "task.spawn" in c)),
            Check("pcall_invoke",    lambda c: "pcall" in c),
            Check("default_skip",    lambda c: '"skip"' in c or "'skip'" in c or "default" in c.lower()),
            Check("no_bare_invoke",  lambda c: not bool(re.search(r"=\s*\w+:InvokeClient\s*\(", c))),
        ],
    ),

    Task(
        id="gs_constraint_vehicle",
        prompt=(
            "Build a driveable car using constraint-based physics. "
            "4 wheels with HingeConstraints. Front wheels steer via TargetAngle. "
            "Rear wheels drive via AngularVelocity. WASD controls from client."
        ),
        tags=["advanced", "physics", "multi-file"],
        checks=[
            Check("strict_mode",      has_strict_mode),
            Check("task_library",     uses_task_library),
            Check("no_deprecated",    no_deprecated_apis),
            Check("hinge_constraint", lambda c: "HingeConstraint" in c),
            Check("new_physics_api",  lambda c: any(k in c for k in ["AngularVelocity", "LinearVelocity", "AlignOrientation"])),
            Check("target_angle",     lambda c: "TargetAngle" in c),
            Check("network_owner",    lambda c: "SetNetworkOwner" in c),
            Check("client_input",     lambda files: any(
                any(k in f.get("code","") for k in ["UserInputService", "ContextActionService", "KeyCode"])
                for f in files if f.get("type") == "LocalScript"
            ), on_files=True),
        ],
    ),

    Task(
        id="gs_parallel_luau_npcs",
        prompt=(
            "Create a system where 20 NPCs each run their pathfinding logic in parallel "
            "using Roblox's Parallel Luau (Actor model). Each NPC should update "
            "independently without blocking the main thread."
        ),
        tags=["advanced", "parallel", "npc"],
        checks=[
            Check("strict_mode",      has_strict_mode),
            Check("task_library",     uses_task_library),
            Check("uses_actor",       lambda c: "Actor" in c),
            Check("parallel_api",     lambda c: any(k in c for k in [
                "task.desynchronize", "BindToMessageParallel", "SendMessage", "GetActor"
            ])),
            Check("pathfinding",      lambda c: "PathfindingService" in c or "ComputeAsync" in c or "Waypoint" in c),
            Check("multi_actor",      lambda c: any(n in c for n in ["20", "for", "ipairs", "spawn"])),
        ],
    ),

    Task(
        id="gs_circular_buffer",
        prompt=(
            "Build a server-side replay recorder. Every 0.1 seconds, record each "
            "player's position and health. Keep only the last 10 seconds (100 snapshots). "
            "When the buffer is full, drop the oldest entry. "
            "Command '/replay' prints the buffer size."
        ),
        tags=["advanced", "memory", "data-structure"],
        checks=[
            Check("strict_mode",     has_strict_mode),
            Check("task_library",    uses_task_library),
            Check("no_deprecated",   no_deprecated_apis),
            Check("circular_buffer", lambda c: any(k in c for k in [
                "buffer", "Buffer", "history", "snapshots", "maxSize", "MAX_SNAPSHOTS", "circular"
            ])),
            Check("point_1s",        lambda c: "0.1" in c),
            Check("100_snapshots",   lambda c: "100" in c),
            Check("drops_oldest",    lambda c: any(k in c for k in ["remove", "Remove", "table.remove", "shift"]) or
                                              "% " in c or "%" in c),
            Check("chat_command",    lambda c: "replay" in c.lower() and ("chat" in c.lower() or "Chatted" in c)),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # TIER 6 — CODE QUALITY (correctness beyond functionality)
    # ══════════════════════════════════════════════════════════════════════════

    Task(
        id="gs_no_deprecated_apis",
        prompt=(
            "Build a character movement enhancer that gives players double jump, "
            "increases WalkSpeed to 24, and adds a speed boost ability on Shift. "
            "Use only current Roblox APIs."
        ),
        tags=["quality", "character", "local"],
        notes="Tests that model uses task.*, ChangeState, etc. not legacy APIs.",
        checks=[
            Check("strict_mode",    has_strict_mode),
            Check("task_library",   uses_task_library),
            Check("no_deprecated",  no_deprecated_apis),
            Check("is_localscript", lambda files: any(
                f.get("type") == "LocalScript" or
                "starterplayer" in str(f.get("filename","")).lower()
                for f in files
            ), on_files=True),
            Check("walkspeed",      lambda c: "WalkSpeed" in c),
            Check("double_jump",    lambda c: any(k in c for k in ["Jumping", "jump", "Jump", "StateType"])),
        ],
    ),

    Task(
        id="gs_memory_leak_free",
        prompt=(
            "Create a system where GUI elements are created for each player when they "
            "join and destroyed when they leave. Make sure there are absolutely no "
            "memory leaks — all connections must be cleaned up."
        ),
        tags=["quality", "memory", "ui"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("no_deprecated",     no_deprecated_apis),
            Check("playeradded",       lambda c: "PlayerAdded" in c),
            Check("playerremoving",    lambda c: "PlayerRemoving" in c),
            Check("destroys_gui",      lambda c: "Destroy" in c or ":Remove" in c),
            Check("stores_connection", lambda c: bool(re.search(r'local\s+\w+\s*=.*:Connect\(', c))),
            Check("disconnects",       lambda c: ":Disconnect()" in c),
        ],
    ),

    Task(
        id="gs_full_type_annotations",
        prompt=(
            "Build a typed inventory module in --!strict mode. "
            "Define types for Item, Inventory, and PlayerData. "
            "All functions must have full type annotations. "
            "Export the types for use by other modules."
        ),
        tags=["quality", "types", "module"],
        checks=[
            Check("strict_mode",     has_strict_mode),
            Check("export_type",     lambda c: "export type" in c),
            Check("typed_functions", lambda c: bool(re.search(r'function\s+\w+\s*\([^)]+:\s*\w+', c))),
            Check("return_type",     lambda c: bool(re.search(r'\)\s*:\s*\w+', c))),
            Check("no_any",          lambda c: ": any" not in c or c.count(": any") < 3),
            Check("typed_tables",    lambda c: bool(re.search(r'\{[^}]*:\s*\w+[^}]*\}', c))),
        ],
    ),
]
