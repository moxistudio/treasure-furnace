from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

try:
    from openai import AsyncOpenAI
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    AsyncOpenAI = None  # type: ignore[assignment]

try:
    from storage import get_long_memories, get_work_logs
except ModuleNotFoundError:  # pragma: no cover - standalone fallback
    def get_long_memories(*args, **kwargs):
        return []

    def get_work_logs(*args, **kwargs):
        return []

from .agent_runtime import RuntimePlan, RuntimeStep


@dataclass
class RuntimeExecutionResult:
    ok: bool
    final_output: str
    step_results: dict[str, str] = field(default_factory=dict)
    sent_messages: list[str] = field(default_factory=list)
    total_tokens: int = 0
    error: str = ""


class RuntimePlanExecutor:
    """Minimal executor for RuntimePlan (T7).

    Supported actions:
    - query_work_logs
    - query_long_memory
    - web_search / web_fetch / code_interpreter (via injected tool runner)
    - browser_open / browser_read / browser_click / browser_screenshot (via injected tool runner)
    - feishu_user_send / feishu_doc_meta (via injected tool runner)
    - delegate_treasure / run_helper_treasure / run_treasure (via injected delegate runner)
    - llm_call
    - send_to_user
    """

    MAX_STEP_TIMEOUT = 60
    MAX_TOKENS_PER_RUN = 20000

    def __init__(
        self,
        llm_caller: Callable[[str, RuntimeStep, RuntimePlan], Awaitable[tuple[str, int]]] | None = None,
        sender: Callable[[str], Awaitable[None]] | None = None,
        tool_runner: Callable[[str, dict[str, Any]], Awaitable[str]] | None = None,
        delegate_runner: Callable[[str, dict[str, Any]], Awaitable[str]] | None = None,
    ):
        self._llm_caller = llm_caller or self._default_llm_call
        self._sender = sender
        self._tool_runner = tool_runner
        self._delegate_runner = delegate_runner
        api_key = os.getenv("LLM_API_KEY", "").strip()
        base_url = os.getenv("LLM_BASE_URL", "https://api.deepseek.com/v1").strip() or "https://api.deepseek.com/v1"
        self._llm_model = os.getenv("LLM_MODEL", "kimi-k2-250905").strip() or "kimi-k2-250905"
        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url) if api_key and AsyncOpenAI else None

    def set_tool_runner(self, tool_runner: Callable[[str, dict[str, Any]], Awaitable[str]] | None) -> None:
        self._tool_runner = tool_runner

    def set_delegate_runner(self, delegate_runner: Callable[[str, dict[str, Any]], Awaitable[str]] | None) -> None:
        self._delegate_runner = delegate_runner

    async def run(
        self,
        plan: RuntimePlan,
        user_id: str,
        inputs: dict[str, Any] | None = None,
    ) -> RuntimeExecutionResult:
        inputs = inputs or {}
        ctx = {
            "user_id": user_id,
            "input": str(inputs.get("input", "")),
        }
        for key, value in inputs.items():
            if key in ctx:
                continue
            if isinstance(value, (dict, list)):
                ctx[key] = value
            elif isinstance(value, (str, int, float, bool)):
                ctx[key] = str(value)
        step_results: dict[str, str] = {}
        sent_messages: list[str] = []
        total_tokens = 0

        if not plan.steps:
            return RuntimeExecutionResult(ok=False, final_output="", error="RuntimePlan has no steps")

        for step in plan.steps:
            if total_tokens > self.MAX_TOKENS_PER_RUN:
                return RuntimeExecutionResult(
                    ok=False,
                    final_output="",
                    step_results=step_results,
                    sent_messages=sent_messages,
                    total_tokens=total_tokens,
                    error=f"token budget exceeded: {total_tokens}",
                )
            try:
                result, used_tokens = await asyncio.wait_for(
                    self._execute_step(step, plan, ctx, step_results),
                    timeout=self.MAX_STEP_TIMEOUT,
                )
            except asyncio.TimeoutError:
                return RuntimeExecutionResult(
                    ok=False,
                    final_output="",
                    step_results=step_results,
                    sent_messages=sent_messages,
                    total_tokens=total_tokens,
                    error=f"step timeout: {step.id}",
                )
            except Exception as e:
                return RuntimeExecutionResult(
                    ok=False,
                    final_output="",
                    step_results=step_results,
                    sent_messages=sent_messages,
                    total_tokens=total_tokens,
                    error=f"step failed ({step.id}): {e}",
                )

            step_results[step.id] = result
            total_tokens += int(used_tokens or 0)

            if step.action == "send_to_user":
                sent_messages.append(result)
                if self._sender:
                    await self._sender(result)

            on_empty = step.params.get("on_empty")
            if not result and isinstance(on_empty, dict) and on_empty.get("stop"):
                final = str(on_empty.get("reply") or "")
                return RuntimeExecutionResult(
                    ok=True,
                    final_output=final,
                    step_results=step_results,
                    sent_messages=sent_messages,
                    total_tokens=total_tokens,
                )

        last_id = plan.steps[-1].id
        final_output = step_results.get(last_id, "")
        return RuntimeExecutionResult(
            ok=True,
            final_output=final_output,
            step_results=step_results,
            sent_messages=sent_messages,
            total_tokens=total_tokens,
        )

    async def _execute_step(
        self,
        step: RuntimeStep,
        plan: RuntimePlan,
        ctx: dict[str, Any],
        step_results: dict[str, str],
    ) -> tuple[str, int]:
        action = step.action
        if action == "query_work_logs":
            return self._do_query_work_logs(ctx["user_id"], step.params), 0
        if action == "query_long_memory":
            return self._do_query_long_memory(ctx["user_id"], step.params), 0
        if action in {"web_search", "web_fetch", "file_read", "code_interpreter", "browser_open", "browser_read", "browser_click", "browser_screenshot", "feishu_user_send", "feishu_doc_meta"}:
            if not self._tool_runner:
                return f"[系统提示] 未配置 tool_runner，无法执行 {action}。", 0
            params = self._render_params(step.params, ctx=ctx, step_results=step_results)
            return await self._tool_runner(action, params), 0
        if action in {"delegate_treasure", "run_helper_treasure", "run_treasure"}:
            if not self._delegate_runner:
                return f"[系统提示] 未配置 delegate_runner，无法执行 {action}。", 0
            params = self._render_params(step.params, ctx=ctx, step_results=step_results)
            return await self._delegate_runner(str(ctx["user_id"]), params), 0
        if action == "llm_call":
            prompt = self._render_template(
                str(step.params.get("prompt", "")),
                ctx=ctx,
                step_results=step_results,
            )
            return await self._llm_caller(prompt, step, plan)
        if action == "send_to_user":
            message = str(step.params.get("message") or "").strip()
            if not message:
                message = self._latest_step_result(step.id, plan, step_results)
            message = self._render_template(message, ctx=ctx, step_results=step_results)
            return message, 0
        return "", 0

    @staticmethod
    def _do_query_work_logs(user_id: str, params: dict[str, Any]) -> str:
        week = params.get("week") if isinstance(params.get("week"), str) else None
        rows = get_work_logs(user_id, week=week)
        if not rows:
            return ""
        return "\n".join(f"[{r[2]}] [{r[1]}] {r[0]}" for r in rows)

    @staticmethod
    def _do_query_long_memory(user_id: str, params: dict[str, Any]) -> str:
        limit = int(params.get("limit") or 5)
        rows = get_long_memories(user_id, limit=max(1, min(limit, 20)))
        if not rows:
            return ""
        return "\n".join(f"- {r}" for r in rows)

    @staticmethod
    def _latest_step_result(current_step_id: str, plan: RuntimePlan, step_results: dict[str, str]) -> str:
        prev_ids = [s.id for s in plan.steps if s.id != current_step_id and s.id in step_results]
        if not prev_ids:
            return ""
        return step_results.get(prev_ids[-1], "") or ""

    @staticmethod
    def _render_template(text: str, ctx: dict[str, Any], step_results: dict[str, str]) -> str:
        out = text or ""
        for key, value in ctx.items():
            if isinstance(value, (dict, list)):
                rendered_value = json.dumps(value, ensure_ascii=False)
            else:
                rendered_value = str(value)
            out = out.replace(f"{{{{{key}}}}}", rendered_value)

        def _json_path_lookup(raw: Any, path: list[str]) -> str:
            if not path or path == ["result"]:
                if isinstance(raw, (dict, list)):
                    return json.dumps(raw, ensure_ascii=False)
                return "" if raw is None else str(raw)
            try:
                current: Any = raw if not isinstance(raw, str) else json.loads(raw)
            except Exception:
                return str(raw) if path == ["result"] else ""
            for part in path:
                if part == "result":
                    continue
                if isinstance(current, dict):
                    current = current.get(part)
                elif isinstance(current, list) and part.isdigit():
                    index = int(part)
                    current = current[index] if 0 <= index < len(current) else None
                else:
                    current = None
                if current is None:
                    return ""
            if isinstance(current, (dict, list)):
                return json.dumps(current, ensure_ascii=False)
            return "" if current is None else str(current)

        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            path = [part for part in match.group(2).split(".") if part]
            if key in ctx:
                return _json_path_lookup(ctx.get(key), path)
            return _json_path_lookup(step_results.get(key, ""), path)

        return re.sub(r"\{\{([a-zA-Z0-9_\-]+)\.([a-zA-Z0-9_\-\.]+)\}\}", repl, out)

    def _render_params(self, params: dict[str, Any], ctx: dict[str, Any], step_results: dict[str, str]) -> dict[str, Any]:
        rendered: dict[str, Any] = {}
        for k, v in (params or {}).items():
            if isinstance(v, str):
                rendered[k] = self._render_template(v, ctx=ctx, step_results=step_results)
            else:
                rendered[k] = v
        return rendered

    async def _default_llm_call(self, prompt: str, step: RuntimeStep, plan: RuntimePlan) -> tuple[str, int]:
        if not self._client:
            return "[系统提示] 未配置 LLM_API_KEY，无法执行 llm_call。", 0

        system_prompt = plan.system_prompt.strip()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        resp = await self._client.chat.completions.create(
            model=str(step.params.get("model") or self._llm_model),
            messages=messages,
            max_tokens=int(step.params.get("max_tokens") or 1000),
            temperature=float(step.params.get("temperature") or 0.4),
        )
        text = (resp.choices[0].message.content or "").strip()
        tokens = int(resp.usage.total_tokens) if resp.usage else 0
        return text, tokens
