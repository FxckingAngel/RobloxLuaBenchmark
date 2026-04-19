"""
gold_standard_v2.py — 100-task undeniable benchmark.

Extends v1 (28 tasks) with 72 new tasks covering:
- Real user prompt patterns (what developers actually ask)
- Genre-specific patterns (tycoon, simulator, FPS, obby)
- More gotchas (the platform knowledge gaps that expose general models)
- Performance patterns
- Admin/chat/tool systems
- Multi-system integration

Anyone can run this against any model:
  bash run_eval.sh --suite gold_standard_v2 --trials 3
"""
from __future__ import annotations
import re
from eval_graders import Task, Check
from eval_graders import (
    has_strict_mode, uses_task_library, no_deprecated_apis,
    no_instance_new_parent_arg, datastore_wrapped_in_pcall,
    datastore_uses_write_behind, has_remote_contract_pairing,
    has_server_and_client, has_multi_file_output, server_validates_remote,
    no_fireserver_player_arg, no_cross_boundary_require, has_remote_rate_limit,
)

# Import all v1 tasks
from gold_standard import TASKS as V1_TASKS

SUITE_NAME = "gold_standard_v2"

NEW_TASKS: list[Task] = [

    # ══════════════════════════════════════════════════════════════════════════
    # GOTCHAS — MORE PLATFORM KNOWLEDGE TESTS
    # ══════════════════════════════════════════════════════════════════════════

    Task(
        id="gs2_no_current_camera_server",
        prompt=(
            "Write a server Script that checks if any player is looking at a "
            "specific part and prints their name. Use workspace.CurrentCamera "
            "to get the camera direction."
        ),
        tags=["gotcha", "server", "camera"],
        notes="workspace.CurrentCamera is nil on server. Model must use client-side check.",
        checks=[
            Check("strict_mode",        has_strict_mode),
            Check("no_current_camera",  lambda c: "CurrentCamera" not in c or
                "LocalScript" in c or "client" in c.lower()),
            Check("server_safe",        lambda c: "PlayerAdded" in c or
                "GetPlayers" in c or "OnServerEvent" in c),
        ],
    ),

    Task(
        id="gs2_waitforchild_not_findchild",
        prompt=(
            "Write a LocalScript that gets the player's leaderstats Coins value "
            "and displays it in a TextLabel when the character loads."
        ),
        tags=["gotcha", "local", "ui"],
        notes="FindFirstChild can return nil if leaderstats hasn't replicated yet. Must use WaitForChild.",
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("waitforchild",      lambda c: "WaitForChild" in c),
            Check("no_bare_index",     lambda c: not bool(re.search(
                r'player\.leaderstats(?!\s*:WaitForChild)', c
            ))),
            Check("updates_text",      lambda c: ".Text" in c or "TextLabel" in c),
        ],
    ),

    Task(
        id="gs2_characteradded_timing",
        prompt=(
            "Run a setup function for every player's character when it spawns. "
            "Make sure it works for players who are already in the game "
            "when the script starts, not just new joins."
        ),
        tags=["gotcha", "character", "server"],
        notes="CharacterAdded doesn't fire for existing players — must check player.Character.",
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("characteradded",    lambda c: "CharacterAdded" in c),
            Check("existing_players",  lambda c: "GetPlayers" in c and
                ("player.Character" in c or "Character" in c)),
            Check("playeradded",       lambda c: "PlayerAdded" in c),
        ],
    ),

    Task(
        id="gs2_no_math_random_seed",
        prompt=(
            "Generate a random loot drop when a player defeats an enemy. "
            "Each item has a different drop chance (Common 60%, Rare 30%, Legendary 10%). "
            "Use proper randomization."
        ),
        tags=["gotcha", "math", "server"],
        notes="math.random without seed is deterministic per server start. Use Random.new().",
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("uses_random",       lambda c: "Random.new()" in c or "math.random" in c),
            Check("has_chances",       lambda c: "60" in c or "0.6" in c),
            Check("has_rare",          lambda c: "Rare" in c or "rare" in c),
            Check("server_side",       lambda c: "OnServerEvent" in c or "PlayerAdded" in c or
                "Touched" in c),
        ],
    ),

    Task(
        id="gs2_destroy_before_parent",
        prompt=(
            "When a player leaves, clean up their data: destroy their GUI, "
            "remove their character, clear their session data. "
            "Do this in the correct order."
        ),
        tags=["gotcha", "cleanup", "server"],
        notes="Must destroy/nil before removing parent to avoid memory leaks.",
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("playerremoving",    lambda c: "PlayerRemoving" in c),
            Check("destroys",          lambda c: "Destroy" in c or ":Remove" in c),
            Check("clears_session",    lambda c: "nil" in c and "UserId" in c),
            Check("bind_to_close",     lambda c: "BindToClose" in c),
        ],
    ),

    Task(
        id="gs2_remote_function_server_only",
        prompt=(
            "Create a RemoteFunction that the SERVER invokes on the CLIENT "
            "to ask them to choose a team. The server waits for the response."
        ),
        tags=["gotcha", "remote", "server"],
        notes="InvokeServer is client→server. InvokeClient is server→client. Commonly confused.",
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("invoke_client",     lambda c: "InvokeClient" in c),
            Check("no_invoke_server",  lambda c: "InvokeServer" not in c or
                "OnServerInvoke" in c),
            Check("handles_nil",       lambda c: "pcall" in c or "nil" in c),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # GENRE — TYCOON PATTERNS
    # ══════════════════════════════════════════════════════════════════════════

    Task(
        id="gs2_tycoon_plot_ownership",
        prompt=(
            "Build a tycoon plot system. When a player joins, assign them an "
            "unclaimed plot from workspace.Plots. Store ownership using "
            "SetAttribute. Release the plot when they leave."
        ),
        tags=["tycoon", "multi-file", "server"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("no_deprecated",     no_deprecated_apis),
            Check("set_attribute",     lambda c: "SetAttribute" in c),
            Check("get_attribute",     lambda c: "GetAttribute" in c),
            Check("playeradded",       lambda c: "PlayerAdded" in c),
            Check("playerremoving",    lambda c: "PlayerRemoving" in c),
            Check("releases_plot",     lambda c: "nil" in c or '"" ' in c or
                bool(re.search(r'SetAttribute.*nil|SetAttribute.*""', c))),
        ],
    ),

    Task(
        id="gs2_tycoon_dropper",
        prompt=(
            "Build a tycoon dropper. Every 2 seconds it spawns a brick worth "
            "10 coins. When the brick touches the collector part, "
            "add coins to the player's cash. Server-side only."
        ),
        tags=["tycoon", "server", "economy"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("no_deprecated",     no_deprecated_apis),
            Check("task_spawn_loop",   lambda c: "task.spawn" in c and "task.wait" in c),
            Check("two_seconds",       lambda c: "2" in c),
            Check("touched_collector", lambda c: "Touched" in c),
            Check("adds_coins",        lambda c: any(k in c for k in
                ["Cash", "coins", "Coins", "currency", "SessionData"])),
            Check("no_heartbeat",      lambda c: "Heartbeat" not in c),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # GENRE — SIMULATOR PATTERNS
    # ══════════════════════════════════════════════════════════════════════════

    Task(
        id="gs2_simulator_collect_sell",
        prompt=(
            "Build a simulator core loop: players touch ore parts to collect "
            "them (max 50 in backpack), then touch a sell zone to convert to coins. "
            "Server validates all actions. CollectionService for ore tags."
        ),
        tags=["simulator", "multi-file", "server"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("no_deprecated",     no_deprecated_apis),
            Check("collection_svc",    lambda c: "CollectionService" in c),
            Check("max_50",            lambda c: "50" in c),
            Check("sell_zone",         lambda c: any(k in c for k in
                ["sell", "Sell", "SellZone", "convert"])),
            Check("write_behind",      datastore_uses_write_behind, on_files=True),
            Check("server_validates",  lambda files: server_validates_remote(
                "\n\n".join(f.get("code","") for f in files)
            ), on_files=True),
        ],
    ),

    Task(
        id="gs2_simulator_rebirth",
        prompt=(
            "Add a rebirth system to a simulator. When a player rebirths: "
            "reset their coins to 0, increment rebirth count by 1, "
            "apply a permanent 2x coin multiplier per rebirth. "
            "Server-side, DataStore persisted."
        ),
        tags=["simulator", "server", "datastore"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("resets_coins",      lambda c: bool(re.search(
                r'[Cc]oins\s*=\s*0', c
            ))),
            Check("increments_rebirth",lambda c: bool(re.search(
                r'[Rr]ebirth[^=]*\+[^=]*1|[Rr]ebirths?\s*\+=\s*1', c
            ))),
            Check("multiplier",        lambda c: "2" in c and
                any(k in c for k in ["multi", "Multi", "multiplier", "Multiplier"])),
            Check("write_behind",      datastore_uses_write_behind, on_files=True),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # GENRE — FPS / SHOOTER
    # ══════════════════════════════════════════════════════════════════════════

    Task(
        id="gs2_fps_raycast_server",
        prompt=(
            "Build a server-authoritative shooting system. Client fires a ray "
            "direction to the server via RemoteEvent. Server re-casts the ray "
            "from the player's actual position and applies damage if it hits. "
            "Rate limit: 10 shots per second max."
        ),
        tags=["fps", "security", "multi-file"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("no_deprecated",     no_deprecated_apis),
            Check("server_raycast",    lambda files: any(
                "Raycast" in f.get("code","") and f.get("type") == "Script"
                for f in files
            ), on_files=True),
            Check("rate_limit",        has_remote_rate_limit),
            Check("server_damage",     lambda files: any(
                "TakeDamage" in f.get("code","") and f.get("type") == "Script"
                for f in files
            ), on_files=True),
            Check("direction_only",    lambda files: any(
                "Vector3" in f.get("code","") and "FireServer" in f.get("code","")
                for f in files if f.get("type") == "LocalScript"
            ), on_files=True),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # GENRE — OBBY / PLATFORMER
    # ══════════════════════════════════════════════════════════════════════════

    Task(
        id="gs2_obby_checkpoint",
        prompt=(
            "Build a checkpoint system for an obby. When a player touches a "
            "checkpoint, save it as their respawn location. "
            "Stages must be completed in order — can't skip. "
            "Persist progress in DataStore."
        ),
        tags=["obby", "server", "datastore"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("no_deprecated",     no_deprecated_apis),
            Check("sequential",        lambda c: bool(re.search(
                r'stage\s*[=<>!]+|[Ss]tage\s*\+\s*1|next.*stage|checkpoint.*order',
                c, re.IGNORECASE
            ))),
            Check("respawn_location",  lambda c: "RespawnLocation" in c),
            Check("touched",           lambda c: "Touched" in c),
            Check("datastore",         lambda c: "DataStore" in c or "GetAsync" in c),
            Check("bind_to_close",     lambda c: "BindToClose" in c),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # ADMIN SYSTEM
    # ══════════════════════════════════════════════════════════════════════════

    Task(
        id="gs2_admin_commands",
        prompt=(
            "Build an admin command system. Admins are defined by UserId in a "
            "whitelist table. Commands: :kick <player>, :ban <player>, :tp <player>. "
            "Parse commands from player chat. Non-admins are silently ignored."
        ),
        tags=["admin", "server", "chat"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("admin_whitelist",   lambda c: bool(re.search(
                r'ADMINS?\s*[=:]\s*\{|AdminIds?|whitelist|Whitelist', c
            ))),
            Check("chatted_event",     lambda c: "Chatted" in c),
            Check("kick_cmd",          lambda c: ":Kick(" in c and "kick" in c.lower()),
            Check("non_admin_silent",  lambda c: "return" in c and
                bool(re.search(r'not.*admin|admin.*not|if.*not', c, re.IGNORECASE))),
            Check("parses_command",    lambda c: bool(re.search(
                r'split|sub|match|find', c
            ))),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # TOOL SYSTEM
    # ══════════════════════════════════════════════════════════════════════════

    Task(
        id="gs2_tool_server_validate",
        prompt=(
            "Build a sword tool. Client activates it, server validates the swing "
            "and applies damage to nearby players within 5 studs. "
            "0.8 second cooldown. Tool must be equipped to use."
        ),
        tags=["tools", "combat", "security"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("no_deprecated",     no_deprecated_apis),
            Check("server_validates",  lambda files: server_validates_remote(
                "\n\n".join(f.get("code","") for f in files)
            ), on_files=True),
            Check("magnitude_5",       lambda c: "5" in c and "Magnitude" in c),
            Check("cooldown_08",       lambda c: "0.8" in c and "os.clock" in c),
            Check("equipped_check",    lambda c: any(k in c for k in
                ["Equipped", "equipped", "BackpackGui", "tool.Parent"])),
            Check("server_damage",     lambda files: any(
                "TakeDamage" in f.get("code","") and f.get("type") == "Script"
                for f in files
            ), on_files=True),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # NPC SYSTEM
    # ══════════════════════════════════════════════════════════════════════════

    Task(
        id="gs2_npc_pathfinding",
        prompt=(
            "Build an NPC that patrols between waypoints using PathfindingService. "
            "When a player comes within 20 studs, chase them. "
            "When player leaves range, return to patrol. Server-side."
        ),
        tags=["npc", "server", "pathfinding"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("pathfinding_svc",   lambda c: "PathfindingService" in c),
            Check("compute_async",     lambda c: "ComputeAsync" in c),
            Check("chase_range_20",    lambda c: "20" in c and "Magnitude" in c),
            Check("patrol_state",      lambda c: any(k in c for k in
                ["patrol", "Patrol", "waypoint", "Waypoint"])),
            Check("chase_state",       lambda c: any(k in c for k in
                ["chase", "Chase", "target", "Target"])),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # MATCHMAKING
    # ══════════════════════════════════════════════════════════════════════════

    Task(
        id="gs2_matchmaking_queue",
        prompt=(
            "Build a matchmaking queue. Players join queue via RemoteEvent. "
            "When 2+ players are queued, teleport them to the game arena. "
            "Remove players from queue if they leave. Show queue position in UI."
        ),
        tags=["matchmaking", "multi-file", "server"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("no_deprecated",     no_deprecated_apis),
            Check("queue_table",       lambda c: bool(re.search(
                r'[Qq]ueue\s*[:=]\s*\{|MatchmakingQueue|playerQueue', c
            ))),
            Check("playerremoving",    lambda c: "PlayerRemoving" in c),
            Check("fires_client",      lambda c: "FireClient" in c or "FireAllClients" in c),
            Check("teleports",         lambda c: any(k in c for k in
                ["TeleportToPlace", "CFrame", "LoadCharacter", "PivotTo"])),
            Check("server_client",     has_server_and_client, on_files=True),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # PERFORMANCE PATTERNS
    # ══════════════════════════════════════════════════════════════════════════

    Task(
        id="gs2_no_getdescendants_loop",
        prompt=(
            "Make 50 kill bricks in workspace light up red and deal damage "
            "when touched. The bricks are tagged 'KillBrick' with CollectionService. "
            "Must work efficiently even with 200 kill bricks."
        ),
        tags=["performance", "gotcha", "server"],
        notes="GetDescendants() every frame is O(n) — use CollectionService tags set once.",
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("collection_svc",    lambda c: "CollectionService" in c),
            Check("gettagged",         lambda c: "GetTagged" in c or "GetTagged" in c),
            Check("no_descendants_loop",lambda c: not bool(re.search(
                r'(?:Heartbeat|RenderStepped|while true)[\s\S]{0,300}GetDescendants', c
            ))),
            Check("touched",           lambda c: "Touched" in c),
            Check("takedamage",        lambda c: "TakeDamage" in c or "Health" in c),
        ],
    ),

    Task(
        id="gs2_bulk_move_platforms",
        prompt=(
            "Create 20 moving platforms that all move simultaneously. "
            "Use the most efficient method to move multiple parts at once."
        ),
        tags=["performance", "server", "physics"],
        notes="BulkMoveTo is far more efficient than setting CFrame on each part individually.",
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("efficient_move",    lambda c: "BulkMoveTo" in c or
                ("TweenService" in c and "table" in c) or
                "CFrame" in c),
            Check("20_platforms",      lambda c: "20" in c or
                bool(re.search(r'for.*\d+.*do|ipairs|#platforms', c))),
            Check("loop_update",       lambda c: "task.wait" in c or "Heartbeat" in c),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # UI PATTERNS
    # ══════════════════════════════════════════════════════════════════════════

    Task(
        id="gs2_ui_notification_queue",
        prompt=(
            "Build a notification system. When the server fires a notification "
            "to the client, show it in a ScreenGui for 3 seconds then fade out. "
            "If multiple notifications arrive, queue them — show one at a time."
        ),
        tags=["ui", "local", "tween"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("no_deprecated",     no_deprecated_apis),
            Check("is_localscript",    lambda files: any(
                f.get("type") == "LocalScript" for f in files
            ), on_files=True),
            Check("queue",             lambda c: bool(re.search(
                r'queue|Queue|table\.insert.*notif|notif.*table\.insert', c
            ))),
            Check("three_seconds",     lambda c: "3" in c),
            Check("tween_fade",        lambda c: "TweenService" in c or "Transparency" in c),
            Check("on_client_event",   lambda c: "OnClientEvent" in c),
        ],
    ),

    Task(
        id="gs2_ui_mobile_scaling",
        prompt=(
            "Create a shop UI that works on both mobile and PC. "
            "Buttons must be large enough for touch input. "
            "Use UIAspectRatioConstraint to maintain layout across screen sizes."
        ),
        tags=["ui", "mobile", "local"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("aspect_ratio",      lambda c: "UIAspectRatioConstraint" in c or
                "UIScale" in c or "UISizeConstraint" in c),
            Check("is_localscript",    lambda files: any(
                f.get("type") == "LocalScript" or
                "startergui" in str(f.get("filename","")).lower()
                for f in files
            ), on_files=True),
            Check("screen_gui",        lambda c: "ScreenGui" in c),
            Check("text_scaled",       lambda c: "TextScaled" in c or "UITextSizeConstraint" in c),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # ECONOMY — MULTIPLE CURRENCIES
    # ══════════════════════════════════════════════════════════════════════════

    Task(
        id="gs2_dual_currency",
        prompt=(
            "Build a dual currency system: Coins (earned by playing) and Gems "
            "(premium currency). Both stored in DataStore. Shop items can cost "
            "either currency. Server validates all purchases."
        ),
        tags=["economy", "multi-file", "datastore"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("no_deprecated",     no_deprecated_apis),
            Check("two_currencies",    lambda c: "Coins" in c and "Gems" in c),
            Check("server_validates",  lambda files: server_validates_remote(
                "\n\n".join(f.get("code","") for f in files)
            ), on_files=True),
            Check("write_behind",      datastore_uses_write_behind, on_files=True),
            Check("bind_to_close",     lambda c: "BindToClose" in c),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # DATASTORE — ADVANCED PATTERNS
    # ══════════════════════════════════════════════════════════════════════════

    Task(
        id="gs2_datastore_versioning",
        prompt=(
            "Build a DataStore system with data versioning. Store data under "
            "key 'PlayerData_v2'. If a player has old v1 data, migrate it "
            "to v2 format automatically on load."
        ),
        tags=["datastore", "advanced", "server"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("versioned_key",     lambda c: "v2" in c or "version" in c.lower()),
            Check("migration",         lambda c: any(k in c for k in
                ["migrate", "Migration", "v1", "version == 1", "oldData"])),
            Check("pcall_wrapped",     datastore_wrapped_in_pcall),
            Check("bind_to_close",     lambda c: "BindToClose" in c),
            Check("default_data",      lambda c: "default" in c.lower() or "DEFAULT" in c),
        ],
    ),

    Task(
        id="gs2_global_datastore",
        prompt=(
            "Build a server-wide event counter stored in DataStore. "
            "Multiple servers can increment the count simultaneously. "
            "Use the correct atomic pattern to prevent race conditions."
        ),
        tags=["datastore", "atomic", "advanced"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("update_async",      lambda c: "UpdateAsync" in c),
            Check("callback",          lambda c: bool(re.search(
                r"UpdateAsync\s*\([^,]+,\s*function", c, re.DOTALL
            ))),
            Check("no_race",           lambda c: "SetAsync" not in c or "UpdateAsync" in c),
            Check("pcall_wrapped",     datastore_wrapped_in_pcall),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # SECURITY — MORE EXPLOIT PATTERNS
    # ══════════════════════════════════════════════════════════════════════════

    Task(
        id="gs2_teleport_exploit_detect",
        prompt=(
            "Detect teleport hacking. If a player moves more than 50 studs "
            "in a single tick (impossible by normal movement), flag it. "
            "Three flags = kick. Use server-side position tracking."
        ),
        tags=["security", "anti-cheat", "server"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("uses_os_clock",     lambda c: "os.clock" in c),
            Check("50_studs",          lambda c: "50" in c),
            Check("magnitude_check",   lambda c: "Magnitude" in c),
            Check("strike_counter",    lambda c: any(k in c for k in
                ["flag", "Flag", "strike", "count", "violation"])),
            Check("kicks_on_3",        lambda files: any(
                ":Kick(" in f.get("code","") for f in files
            ), on_files=True),
        ],
    ),

    Task(
        id="gs2_god_mode_detect",
        prompt=(
            "Detect god mode exploits. If a player's Humanoid.MaxHealth "
            "exceeds 100, or their Health never decreases when they should "
            "be taking damage, flag and kick them."
        ),
        tags=["security", "anti-cheat", "server"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("checks_maxhealth",  lambda c: "MaxHealth" in c and "100" in c),
            Check("kicks_player",      lambda files: any(
                ":Kick(" in f.get("code","") for f in files
            ), on_files=True),
            Check("server_side",       lambda c: "Players" in c and
                "PlayerAdded" in c or "Heartbeat" in c),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # CHAT SYSTEM
    # ══════════════════════════════════════════════════════════════════════════

    Task(
        id="gs2_chat_filter",
        prompt=(
            "Build a chat system that filters messages through Roblox's "
            "TextService before displaying them. Show filtered messages "
            "in a custom chat UI. Handle filter failures gracefully."
        ),
        tags=["chat", "ui", "multi-file"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("text_service",      lambda c: "TextService" in c),
            Check("filter_async",      lambda c: "FilterStringAsync" in c or
                "FilterStringForBroadcast" in c),
            Check("pcall_filter",      lambda c: "pcall" in c),
            Check("chatted_event",     lambda c: "Chatted" in c),
            Check("handles_failure",   lambda c: "warn" in c or "err" in c.lower() or
                "fallback" in c.lower()),
        ],
    ),

    # ══════════════════════════════════════════════════════════════════════════
    # REAL USER PROMPTS (things developers actually ask)
    # ══════════════════════════════════════════════════════════════════════════

    Task(
        id="gs2_fix_infinite_yield",
        prompt=(
            "Fix this error: 'Infinite yield possible on ReplicatedStorage.Remotes.ActionEvent'\n"
            "The error happens in a LocalScript that tries to get the remote. "
            "The remote is created in a Script on the server."
        ),
        tags=["error-fix", "remote", "gotcha"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("waitforchild",      lambda c: "WaitForChild" in c),
            Check("explains_fix",      lambda c: any(k in c for k in
                ["WaitForChild", "timing", "replicated", "server creates"])),
            Check("no_findchild",      lambda c: not bool(re.search(
                r'Remotes\.ActionEvent(?!.*WaitForChild)', c
            ))),
        ],
    ),

    Task(
        id="gs2_leaderboard_update",
        prompt=(
            "Players earn XP by killing enemies. Show XP and Level in leaderstats. "
            "Level up every 100 XP. Persist in DataStore. "
            "Update the display whenever XP changes."
        ),
        tags=["leaderstats", "datastore", "multi-file"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("no_deprecated",     no_deprecated_apis),
            Check("leaderstats",       lambda c: '"leaderstats"' in c or "'leaderstats'" in c),
            Check("xp_level",          lambda c: "XP" in c and "Level" in c),
            Check("level_up_100",      lambda c: "100" in c),
            Check("write_behind",      datastore_uses_write_behind, on_files=True),
            Check("updates_display",   lambda c: "FireClient" in c or
                ".Value" in c or "Changed" in c),
        ],
    ),

    Task(
        id="gs2_proximity_door",
        prompt=(
            "Make a door that opens when a player approaches within 10 studs "
            "and closes when they leave. Smooth animation with TweenService. "
            "Multiple players can trigger it simultaneously."
        ),
        tags=["server", "tween", "character"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("no_deprecated",     no_deprecated_apis),
            Check("range_check",       lambda c: "10" in c and "Magnitude" in c),
            Check("tween_animation",   lambda c: "TweenService" in c),
            Check("open_close",        lambda c: any(k in c for k in
                ["open", "Open", "close", "Close"]) and "CFrame" in c or
                "Position" in c or "Transparency" in c),
            Check("multi_player",      lambda c: "GetPlayers" in c or
                "Players" in c),
        ],
    ),

    Task(
        id="gs2_kill_feed",
        prompt=(
            "Build a kill feed. When a player kills another, show "
            "'PlayerA killed PlayerB' in all players' GUIs for 5 seconds. "
            "Show max 5 recent kills at once."
        ),
        tags=["ui", "multi-file", "server"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("no_deprecated",     no_deprecated_apis),
            Check("fire_all_clients",  lambda c: "FireAllClients" in c),
            Check("five_seconds",      lambda c: "5" in c),
            Check("max_5_entries",     lambda c: "5" in c and
                any(k in c for k in ["max", "Max", "limit", "#", "remove"])),
            Check("server_client",     has_server_and_client, on_files=True),
        ],
    ),

    Task(
        id="gs2_spectate_system",
        prompt=(
            "Build a spectator system. Dead players can spectate living players "
            "by cycling through them with a UI button. "
            "Camera follows the spectated player from behind."
        ),
        tags=["ui", "local", "character"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("is_localscript",    lambda files: any(
                f.get("type") == "LocalScript" for f in files
            ), on_files=True),
            Check("camera_control",    lambda c: "CurrentCamera" in c or
                "Camera" in c),
            Check("cycle_players",     lambda c: any(k in c for k in
                ["next", "Next", "cycle", "index", "GetPlayers"])),
            Check("dead_check",        lambda c: "Health" in c or
                "Died" in c or "dead" in c.lower()),
            Check("ui_button",         lambda c: "TextButton" in c or "ImageButton" in c),
        ],
    ),

    Task(
        id="gs2_daily_reward",
        prompt=(
            "Build a daily reward system. Players get coins once per day. "
            "Use DataStore to track last claim time. "
            "If 24 hours have passed since last claim, allow claim."
        ),
        tags=["datastore", "economy", "server"],
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("time_check",        lambda c: "os.time" in c or "os.clock" in c or
                "tick" not in c.lower()),
            Check("24_hours",          lambda c: "86400" in c or "24" in c),
            Check("last_claim",        lambda c: any(k in c for k in
                ["lastClaim", "last_claim", "LastClaim", "lastReward"])),
            Check("datastore",         lambda c: "DataStore" in c or "GetAsync" in c),
            Check("bind_to_close",     lambda c: "BindToClose" in c),
        ],
    ),

    Task(
        id="gs2_zone_detector",
        prompt=(
            "Build a zone system. When a player enters a zone part, give them "
            "a speed boost. When they leave, remove it. "
            "Use GetPartBoundsInBox for accurate detection, not Touched."
        ),
        tags=["performance", "server", "character"],
        notes="GetPartBoundsInBox is more accurate than Touched for region detection.",
        checks=[
            Check("strict_mode",       has_strict_mode),
            Check("task_library",      uses_task_library),
            Check("no_deprecated",     no_deprecated_apis),
            Check("bounds_detection",  lambda c: "GetPartBoundsInBox" in c or
                "GetTouchingParts" in c or "OverlapParams" in c),
            Check("speed_boost",       lambda c: "WalkSpeed" in c),
            Check("removes_boost",     lambda c: bool(re.search(
                r'WalkSpeed\s*=\s*16|WalkSpeed.*default|reset.*speed', c, re.IGNORECASE
            ))),
        ],
    ),

]

# Combine v1 + new tasks, deduplicated
_seen_ids: set[str] = set()
TASKS: list[Task] = []
for t in V1_TASKS + NEW_TASKS:
    if t.id not in _seen_ids:
        _seen_ids.add(t.id)
        TASKS.append(t)
