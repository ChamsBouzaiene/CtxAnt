import asyncio
import base64
import json
import logging
from typing import Any

import anthropic
from openai import AsyncOpenAI

import browser_bridge
import machine_tools
import usage
from config import AI_PROVIDER, ANTHROPIC_API_KEY, XAI_API_KEY, XAI_MODEL

logger = logging.getLogger(__name__)

# Conversation history keyed by (chat_id, agent_slug).
# Non-agent / hub messages use agent_slug = HUB_KEY.
HUB_KEY = "__hub__"
_histories: dict[tuple[int, str], list[dict]] = {}

# Cancellation flags keyed by (chat_id, agent_slug). Set True to abort an in-flight loop.
_cancel_flags: dict[tuple[int, str], bool] = {}

# Global browser lock — only one browser run can touch Chrome at a time across
# *all* agents / bots sharing this process. Populated lazily so we don't bind
# to an event loop at import time.
_browser_lock: asyncio.Lock | None = None


def _get_browser_lock() -> asyncio.Lock:
    global _browser_lock
    if _browser_lock is None:
        _browser_lock = asyncio.Lock()
    return _browser_lock


def browser_busy() -> bool:
    """True if another agent run currently holds the browser lock."""
    return _browser_lock is not None and _browser_lock.locked()

# Keep at most this many turns before pruning.
MAX_HISTORY_TURNS = 40
# Cap on tool-call rounds inside a single user turn. Bumped from 20 → 50:
# multi-site sweeps (scan 5–10 subreddits, summarise each) routinely need
# ~5 tool calls per site, so 20 was bailing partway through. 50 covers most
# realistic "go visit N pages and report back" jobs without exploding cost
# (the model still stops as soon as it has the answer).
MAX_TOOL_ITERATIONS = 50

CLAUDE_MODEL = "claude-sonnet-4-6"
GROK_VISION_MODEL = "grok-2-vision-latest"

# ── Tool definitions (OpenAI/Grok format — also converted for Claude) ────────

TOOLS_OPENAI = [
    {
        "type": "function",
        "function": {
            "name": "browser_screenshot",
            "description": "Capture a screenshot of the current browser tab. Always do this first to see what's on screen.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_navigate",
            "description": "Navigate the current tab to a URL.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "Full URL including https://"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_click",
            "description": "Click an element by CSS selector or by (x, y) pixel coordinates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of the element to click"},
                    "x": {"type": "number", "description": "X coordinate (if no selector)"},
                    "y": {"type": "number", "description": "Y coordinate (if no selector)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_type",
            "description": "Clear an input field and type text into it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "CSS selector of the input"},
                    "text": {"type": "string", "description": "Text to type"},
                },
                "required": ["selector", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_scroll",
            "description": "Scroll the page up or down.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["up", "down", "left", "right"]},
                    "pixels": {"type": "number", "description": "Pixels to scroll (default 500)"},
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_get_page_content",
            "description": "Get the visible text content, title, and URL of the current tab.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_list_tabs",
            "description": "List all open browser tabs with their id, title, and URL.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_switch_tab",
            "description": "Switch focus to a different tab.",
            "parameters": {
                "type": "object",
                "properties": {"tab_id": {"type": "integer", "description": "Tab ID from browser_list_tabs"}},
                "required": ["tab_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_new_tab",
            "description": "Open a new browser tab, optionally at a URL.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "URL to open (optional)"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "browser_close_tab",
            "description": "Close the current active tab.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command on the local machine and return stdout/stderr.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to run"},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)"},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file on the local machine.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "File path (~ supported)"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file on the local machine (creates or overwrites).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                    "content": {"type": "string", "description": "Content to write"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and directories at a given path.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Directory path (default: current dir)"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_working_directory",
            "description": "Get the current working directory of the backend server.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]

# Convert OpenAI tool format → Anthropic format
TOOLS_ANTHROPIC = [
    {
        "name": t["function"]["name"],
        "description": t["function"]["description"],
        "input_schema": t["function"]["parameters"],
    }
    for t in TOOLS_OPENAI
]

SYSTEM_PROMPT = (
    "You are a browser-control AI assistant. The user communicates with you via Telegram. "
    "You have tools to control their Chrome browser remotely and to run commands on their local machine. "
    "When given a task, use tools step by step. Always take a screenshot first to see the current state of the browser. "
    "After completing a task, describe briefly what you did."
)

# Appended to every system prompt (agent or hub). Keep this short — it's spent on
# every turn. The goal: when the AI hits a blocker (login wall, CAPTCHA, missing
# info, ambiguous request) it must give the user a CONCRETE, ACTIONABLE next step
# rather than a dead-end "I couldn't do it" summary.
BLOCKER_GUIDANCE = (
    "\n\n"
    "─── When something blocks you ───\n"
    "If you hit an auth wall, CAPTCHA, 2FA prompt, missing info, or any other "
    "blocker, DO NOT silently give up with a one-liner. Instead:\n"
    "  1. Say exactly what's blocking you (e.g. 'Gmail wants me to sign in').\n"
    "  2. Give the user step-by-step unblock instructions, including the exact "
    "URL to open in their Chrome and what to do there (e.g. 'Open "
    "https://mail.google.com in the Chrome I'm driving and sign in — I share "
    "that browser session, so after you log in I'll see it too').\n"
    "  3. Tell them the exact command to reply with so you resume (e.g. "
    "'Once you're signed in, reply /run and I'll pick up where I left off').\n"
    "  4. If the user just sent you a follow-up message trying to help, TREAT "
    "IT AS A FRESH ATTEMPT — take a new screenshot, re-check the state of the "
    "page, and try the task again. Do not just repeat your prior failure "
    "summary.\n"
    "Always prefer action over apologies. Your job is to get the user unstuck, "
    "not to narrate the stuck state."
)


# ── Tool execution ────────────────────────────────────────────────────────────

async def _execute_tool(name: str, args: dict) -> tuple[Any, bytes | None]:
    """Returns (result_dict, screenshot_bytes_or_None)."""
    screenshot_bytes = None

    if name == "browser_screenshot":
        result = await browser_bridge.send_command("screenshot")
        if result.get("success") and result.get("data"):
            screenshot_bytes = base64.b64decode(result["data"])
            return {"status": "screenshot captured"}, screenshot_bytes
        return result, None

    elif name == "browser_navigate":
        result = await browser_bridge.send_command("navigate", url=args["url"])
        await asyncio.sleep(1.5)  # let page load
        return result, None

    elif name == "browser_click":
        result = await browser_bridge.send_command(
            "click",
            selector=args.get("selector"),
            x=args.get("x"),
            y=args.get("y"),
        )
        return result, None

    elif name == "browser_type":
        result = await browser_bridge.send_command(
            "type", selector=args["selector"], text=args["text"]
        )
        return result, None

    elif name == "browser_scroll":
        result = await browser_bridge.send_command(
            "scroll", direction=args["direction"], pixels=args.get("pixels", 500)
        )
        return result, None

    elif name == "browser_get_page_content":
        result = await browser_bridge.send_command("get_content")
        return result, None

    elif name == "browser_list_tabs":
        result = await browser_bridge.send_command("list_tabs")
        return result, None

    elif name == "browser_switch_tab":
        result = await browser_bridge.send_command("switch_tab", tabId=args["tab_id"])
        return result, None

    elif name == "browser_new_tab":
        result = await browser_bridge.send_command("new_tab", url=args.get("url", ""))
        return result, None

    elif name == "browser_close_tab":
        result = await browser_bridge.send_command("close_tab")
        return result, None

    elif name == "run_command":
        result = await machine_tools.run_command(
            args["command"], timeout=args.get("timeout", 30)
        )
        return result, None

    elif name == "read_file":
        result = machine_tools.read_file(args["path"])
        return result, None

    elif name == "write_file":
        result = machine_tools.write_file(args["path"], args["content"])
        return result, None

    elif name == "list_directory":
        result = machine_tools.list_directory(args.get("path", "."))
        return result, None

    elif name == "get_working_directory":
        result = machine_tools.get_working_directory()
        return result, None

    return {"error": f"Unknown tool: {name}"}, None


# ── History management ───────────────────────────────────────────────────────

def _trim_history(history: list[dict]) -> None:
    """Keep only the last MAX_HISTORY_TURNS messages. Mutates in place."""
    if len(history) > MAX_HISTORY_TURNS:
        del history[: len(history) - MAX_HISTORY_TURNS]


def _hist_key(chat_id: int, agent_slug: str | None) -> tuple[int, str]:
    return (chat_id, agent_slug or HUB_KEY)


def _check_cancelled(chat_id: int, agent_slug: str | None) -> bool:
    return _cancel_flags.get(_hist_key(chat_id, agent_slug), False)


# ── Message building (supports text + optional image) ────────────────────────

def _build_grok_user_message(text: str, image_bytes: bytes | None) -> dict:
    if not image_bytes:
        return {"role": "user", "content": text}
    # OpenAI-compatible multimodal format
    b64 = base64.b64encode(image_bytes).decode()
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": text or "Please look at this image."},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ],
    }


def _build_claude_user_message(text: str, image_bytes: bytes | None) -> dict:
    if not image_bytes:
        return {"role": "user", "content": text}
    b64 = base64.b64encode(image_bytes).decode()
    return {
        "role": "user",
        "content": [
            {"type": "text", "text": text or "Please look at this image."},
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": b64},
            },
        ],
    }


# ── Provider implementations ─────────────────────────────────────────────────

async def _run_grok(
    chat_id: int,
    user_text: str,
    image: bytes | None = None,
    agent_slug: str | None = None,
    system_prompt: str | None = None,
) -> tuple[str, list[bytes]]:
    client = AsyncOpenAI(api_key=XAI_API_KEY, base_url="https://api.x.ai/v1")
    history = _histories.setdefault(_hist_key(chat_id, agent_slug), [])
    history.append(_build_grok_user_message(user_text, image))

    # Vision model if an image was included in the LAST user turn
    model = GROK_VISION_MODEL if image else XAI_MODEL
    screenshots: list[bytes] = []
    iterations = 0
    system = system_prompt or SYSTEM_PROMPT

    while True:
        if _check_cancelled(chat_id, agent_slug):
            _cancel_flags[_hist_key(chat_id, agent_slug)] = False
            return "⏹ Cancelled.", screenshots
        if iterations >= MAX_TOOL_ITERATIONS:
            return "(stopped — too many tool iterations)", screenshots

        response = await client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": system}] + history,
            tools=TOOLS_OPENAI,
            tool_choice="auto",
        )

        # Track usage (per-agent slug so /usage can break down by agent)
        if response.usage:
            usage.record(
                chat_id, "grok", model,
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
                agent_slug=agent_slug,
            )

        choice = response.choices[0]
        msg = choice.message
        history.append(msg.model_dump(exclude_none=True))
        # After the first turn, switch back to text model unless explicitly vision
        model = XAI_MODEL

        if choice.finish_reason == "tool_calls" and msg.tool_calls:
            iterations += 1
            for tc in msg.tool_calls:
                name = tc.function.name
                args = json.loads(tc.function.arguments or "{}")
                logger.info(f"Tool call: {name}({args})")
                result, screenshot = await _execute_tool(name, args)
                if screenshot:
                    screenshots.append(screenshot)
                history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result)[:8000],  # cap to keep tokens in check
                })
        else:
            _trim_history(history)
            return msg.content or "", screenshots


async def _run_claude(
    chat_id: int,
    user_text: str,
    image: bytes | None = None,
    agent_slug: str | None = None,
    system_prompt: str | None = None,
) -> tuple[str, list[bytes]]:
    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    history = _histories.setdefault(_hist_key(chat_id, agent_slug), [])
    history.append(_build_claude_user_message(user_text, image))

    screenshots: list[bytes] = []
    iterations = 0
    system = system_prompt or SYSTEM_PROMPT

    while True:
        if _check_cancelled(chat_id, agent_slug):
            _cancel_flags[_hist_key(chat_id, agent_slug)] = False
            return "⏹ Cancelled.", screenshots
        if iterations >= MAX_TOOL_ITERATIONS:
            return "(stopped — too many tool iterations)", screenshots

        response = await client.messages.create(
            model=CLAUDE_MODEL,
            # Bumped from 4096 → 8192 so long, structured answers (e.g. "list
            # 10 candidates with summary + reasoning") don't get truncated
            # mid-word. Sonnet supports up to 64K output tokens; 8K is the
            # sweet spot between "won't truncate" and "won't waste".
            max_tokens=8192,
            system=system,
            tools=TOOLS_ANTHROPIC,
            messages=history,
        )

        if response.usage:
            usage.record(
                chat_id, "claude", CLAUDE_MODEL,
                response.usage.input_tokens,
                response.usage.output_tokens,
                agent_slug=agent_slug,
            )

        assistant_content = []
        tool_calls_found = []
        for block in response.content:
            if block.type == "text":
                assistant_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                assistant_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
                tool_calls_found.append(block)
        history.append({"role": "assistant", "content": assistant_content})

        if response.stop_reason == "tool_use" and tool_calls_found:
            iterations += 1
            tool_results = []
            for block in tool_calls_found:
                logger.info(f"Tool call: {block.name}({block.input})")
                result, screenshot = await _execute_tool(block.name, block.input)
                if screenshot:
                    screenshots.append(screenshot)

                content: list[dict] = [{"type": "text", "text": json.dumps(result)[:8000]}]
                if screenshot:
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": base64.b64encode(screenshot).decode(),
                        },
                    })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": content,
                })
            history.append({"role": "user", "content": tool_results})
        else:
            text = " ".join(
                b["text"] for b in assistant_content if b.get("type") == "text"
            )
            _trim_history(history)
            return text, screenshots


# ── Public interface ─────────────────────────────────────────────────────────

async def process_message(
    chat_id: int,
    user_text: str,
    image: bytes | None = None,
    agent_slug: str | None = None,
    system_prompt: str | None = None,
) -> tuple[str, list[bytes]]:
    """Run an AI turn for this (chat_id, agent_slug) context.

    The browser is a single shared resource, so all runs serialize through a
    global asyncio.Lock. If another agent is already running, this call awaits
    its completion. Callers that want to surface "queued" feedback to the user
    can check `browser_busy()` before calling.
    """
    _cancel_flags[_hist_key(chat_id, agent_slug)] = False
    # Always append the blocker-resolution guidance so every agent, including
    # the hub, tells the user how to unblock instead of silently giving up.
    effective_system = (system_prompt or SYSTEM_PROMPT) + BLOCKER_GUIDANCE
    async with _get_browser_lock():
        if AI_PROVIDER == "claude":
            return await _run_claude(chat_id, user_text, image, agent_slug, effective_system)
        return await _run_grok(chat_id, user_text, image, agent_slug, effective_system)


def cancel(chat_id: int, agent_slug: str | None = None) -> None:
    """Cancel the in-flight run for this (chat_id, agent_slug).

    Pass agent_slug=None to cancel the hub's free-form chat. To cancel
    everything for a chat, use cancel_all(chat_id).
    """
    _cancel_flags[_hist_key(chat_id, agent_slug)] = True


def cancel_all(chat_id: int) -> int:
    """Set the cancel flag for every active run under this chat_id. Returns count."""
    n = 0
    for key in list(_cancel_flags.keys()):
        if key[0] == chat_id:
            _cancel_flags[key] = True
            n += 1
    # Also cover in-flight runs whose flag hasn't been registered yet.
    _cancel_flags[_hist_key(chat_id, None)] = True
    return n


def clear_history(chat_id: int, agent_slug: str | None = None) -> None:
    """Clear conversation history. Pass agent_slug=None to clear everything for this chat."""
    if agent_slug is not None:
        _histories.pop(_hist_key(chat_id, agent_slug), None)
        return
    for key in list(_histories.keys()):
        if key[0] == chat_id:
            _histories.pop(key, None)
