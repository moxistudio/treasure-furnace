from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


FOUR_BACKENDS = {"opencode", "qwen_code", "kimi_code", "claude_code"}


@dataclass
class RuntimeStep:
    id: str
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    trust: str = "auto"


@dataclass
class RuntimePlan:
    agent_name: str
    display_name: str
    executor_type: str
    backend_profile: str
    tool_whitelist: list[str] = field(default_factory=list)
    steps: list[RuntimeStep] = field(default_factory=list)
    system_prompt: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "display_name": self.display_name,
            "executor_type": self.executor_type,
            "backend_profile": self.backend_profile,
            "tool_whitelist": list(self.tool_whitelist),
            "steps": [
                {"id": s.id, "action": s.action, "params": dict(s.params), "trust": s.trust}
                for s in self.steps
            ],
            "system_prompt": self.system_prompt,
            "metadata": dict(self.metadata),
            "warnings": list(self.warnings),
        }


class AgentCompiler:
    """Compile HoluBot agent spec (agent.yaml parsed dict) into a backend-agnostic runtime plan.

    Current role:
    - Accept either legacy agent specs or pack-derived specs compiled from runtime_assets.
    - Produce a backend-agnostic runtime plan / prompt bundle for adapters.
    - Keep backend-native config emission out of the default runtime path.
    """

    def compile(self, spec: dict[str, Any]) -> RuntimePlan:
        raw = spec or {}
        meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
        name = str(
            raw.get("name")
            or raw.get("id")
            or meta.get("id")
            or meta.get("name")
            or "unnamed_agent"
        ).strip() or "unnamed_agent"
        display_name = str(raw.get("display_name") or raw.get("title") or meta.get("name") or name).strip()

        executor = raw.get("executor") if isinstance(raw.get("executor"), dict) else {}
        executor_type = str(executor.get("type") or "builtin").strip().lower()
        backend_profile = self._resolve_backend_profile(executor_type, executor)

        tools = self._compile_tools(raw.get("capabilities"))
        steps, step_warnings = self._compile_steps(raw.get("steps"))
        prompt = self._compile_system_prompt(raw)
        personality_meta = self._extract_personality(raw)

        metadata = {
            "memory_policy": raw.get("memory") if isinstance(raw.get("memory"), dict) else {},
            "personality": personality_meta,
            "backend_native_mirror": self._backend_native_mirror_hint(backend_profile),
            "source_version": str(raw.get("version") or meta.get("version") or ""),
            "runtime_hints": executor.get("runtime_hints") if isinstance(executor.get("runtime_hints"), dict) else {},
            "model_strategy": raw.get("model_strategy") if isinstance(raw.get("model_strategy"), dict) else {},
        }

        warnings = step_warnings
        if backend_profile not in FOUR_BACKENDS:
            warnings.append(f"backend_profile={backend_profile} not in first-tier four backends")

        return RuntimePlan(
            agent_name=name,
            display_name=display_name,
            executor_type=executor_type,
            backend_profile=backend_profile,
            tool_whitelist=tools,
            steps=steps,
            system_prompt=prompt,
            metadata=metadata,
            warnings=warnings,
        )

    def compile_pack(self, pack_spec: dict[str, Any], *, skill_markdown: str = "") -> RuntimePlan:
        compat_spec = self.pack_to_agent_spec(pack_spec, skill_markdown=skill_markdown)
        plan = self.compile(compat_spec)
        pack_meta = pack_spec.get("meta") if isinstance(pack_spec.get("meta"), dict) else {}
        plan.metadata["pack_meta"] = {
            "id": str(pack_meta.get("id") or "").strip(),
            "kind": str(pack_meta.get("kind") or "").strip(),
            "version": str(pack_meta.get("version") or "").strip(),
        }
        plan.metadata["pack_source"] = True
        return plan

    def pack_to_agent_spec(self, pack_spec: dict[str, Any], *, skill_markdown: str = "") -> dict[str, Any]:
        raw = pack_spec if isinstance(pack_spec, dict) else {}
        meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
        activation = raw.get("activation") if isinstance(raw.get("activation"), dict) else {}
        tools = raw.get("tools") if isinstance(raw.get("tools"), dict) else {}
        runtime = raw.get("runtime") if isinstance(raw.get("runtime"), dict) else {}
        governance = raw.get("governance") if isinstance(raw.get("governance"), dict) else {}
        knowledge = raw.get("knowledge") if isinstance(raw.get("knowledge"), dict) else {}
        hallucination_policy = raw.get("hallucination_policy") if isinstance(raw.get("hallucination_policy"), dict) else {}
        output_contract = raw.get("output_contract") if isinstance(raw.get("output_contract"), dict) else {}
        model_strategy = raw.get("model_strategy") if isinstance(raw.get("model_strategy"), dict) else {}
        memory = raw.get("memory") if isinstance(raw.get("memory"), dict) else {}
        personality = raw.get("personality") if isinstance(raw.get("personality"), dict) else {}
        soul_care = raw.get("soul_care") if isinstance(raw.get("soul_care"), dict) else {}
        evolution = raw.get("evolution") if isinstance(raw.get("evolution"), dict) else {}

        builtin_tools = self._coerce_pack_tools(tools.get("builtin"))
        forbidden_tools = self._coerce_pack_tools(governance.get("forbidden_tools"))
        executor_type = self._resolve_pack_executor_type(runtime)
        system_prompt = self._extract_skill_markdown_body(skill_markdown).strip()
        if not system_prompt:
            system_prompt = str(meta.get("description") or meta.get("name") or meta.get("id") or "").strip()

        mcp_servers = tools.get("mcp_servers") if isinstance(tools.get("mcp_servers"), dict) else {}
        mcp_required = self._coerce_pack_tools(mcp_servers.get("required"))
        mcp_optional = self._coerce_pack_tools(mcp_servers.get("optional"))
        route_preference = str(activation.get("route_preference") or runtime.get("kind") or "").strip().lower()

        constraints = [str(item).strip() for item in (output_contract.get("rules") or []) if str(item).strip()]
        steps = runtime.get("steps") if isinstance(runtime.get("steps"), list) else []
        if not steps:
            steps = self._build_pack_default_steps(builtin_tools, executor_type)
        compat_meta = dict(meta)
        compat_meta.update(
            {
                "id": str(meta.get("id") or meta.get("name") or "unnamed_pack").strip() or "unnamed_pack",
                "name": str(meta.get("name") or meta.get("id") or "未命名法宝").strip() or "未命名法宝",
                "version": str(meta.get("version") or "").strip(),
                "description": str(meta.get("description") or "").strip(),
                "origin": str(meta.get("origin") or "pack").strip() or "pack",
            }
        )
        compat_spec: dict[str, Any] = {
            "meta": compat_meta,
            "trigger": {
                "keywords": self._coerce_pack_tools(activation.get("trigger_keywords")),
                "negative_keywords": self._coerce_pack_tools(
                    activation.get("negative_keywords") or activation.get("trigger_negative")
                ),
                "intent_types": self._coerce_pack_tools(activation.get("intents")),
            },
            "capabilities": {
                "tools": [{"name": name} for name in builtin_tools],
                "forbidden_tools": forbidden_tools,
            },
            "trust": {
                "default_level": str(governance.get("trust_level") or "confirm").strip().lower() or "confirm",
            },
            "executor": {
                "type": executor_type,
                "runtime_hints": {
                    "pack_runtime_kind": str(runtime.get("kind") or "").strip().lower(),
                    "route_preference": route_preference,
                },
            },
            "system_prompt": system_prompt,
            "constraints": constraints,
            "steps": [dict(item) for item in steps if isinstance(item, dict)],
            "mcp": {
                "enabled": bool(mcp_required or mcp_optional),
                "servers": mcp_required,
                "optional_servers": mcp_optional,
            },
            "import_source": {
                "type": "treasure_pack",
                "name": str(meta.get("name") or meta.get("id") or "").strip(),
            },
        }
        if knowledge:
            compat_spec["knowledge"] = dict(knowledge)
        if hallucination_policy:
            compat_spec["hallucination_policy"] = dict(hallucination_policy)
        if output_contract:
            compat_spec["output_contract"] = dict(output_contract)
        if model_strategy:
            compat_spec["model_strategy"] = dict(model_strategy)
        if memory:
            compat_spec["memory"] = dict(memory)
        if personality:
            compat_spec["personality"] = dict(personality)
        if soul_care:
            compat_spec["soul_care"] = dict(soul_care)
        if evolution:
            compat_spec["evolution"] = dict(evolution)
        if isinstance(raw.get("token_budget"), (int, float)):
            compat_spec["token_budget"] = int(raw.get("token_budget") or 0)
        return compat_spec

    def export_backend_mirror(
        self,
        spec: dict[str, Any],
        backend: str,
        out_dir: str = "generated/agent_mirrors",
        write_files: bool = True,
    ):
        # Local import to avoid circular dependency at module import time.
        from .agent_mirror_exporter import export_backend_mirror

        plan = self.compile(spec)
        return export_backend_mirror(plan=plan, backend=backend, out_dir=out_dir, write_files=write_files)

    def _resolve_backend_profile(self, executor_type: str, executor: dict[str, Any]) -> str:
        if executor_type in FOUR_BACKENDS:
            return executor_type
        backend = str(executor.get("backend") or "").strip().lower()
        if backend in FOUR_BACKENDS:
            return backend
        if executor_type == "builtin":
            # Runtime still compiles; execution may stay in HoluBot.
            return "builtin"
        return executor_type or "builtin"

    @staticmethod
    def _coerce_pack_tools(raw: Any) -> list[str]:
        if isinstance(raw, str):
            return [raw.strip()] if raw.strip() else []
        if not isinstance(raw, list):
            return []
        out: list[str] = []
        for item in raw:
            token = str(item or "").strip()
            if token and token not in out:
                out.append(token)
        return out

    @staticmethod
    def _resolve_pack_executor_type(runtime: dict[str, Any]) -> str:
        kind = AgentCompiler._canonical_pack_runtime_kind(runtime.get("kind"))
        if kind:
            return kind
        return "builtin"

    @staticmethod
    def _canonical_pack_runtime_kind(raw: Any) -> str:
        token = str(raw or "").strip().lower()
        if token == "builtin":
            return "builtin"
        if token == "nimbus":
            return "nimbus"
        if token == "marshal":
            return "marshal"
        return ""

    def _build_pack_default_steps(self, builtin_tools: list[str], executor_type: str) -> list[dict[str, Any]]:
        tools = [str(item).strip() for item in builtin_tools if str(item).strip()]
        if not tools:
            return [
                {
                    "id": "respond",
                    "action": "send_to_user",
                    "params": {"message": "[系统提示] 当前法宝包未声明可执行步骤。"},
                }
            ]

        steps: list[dict[str, Any]] = []
        tool_set = set(tools)

        if "web_search" in tool_set:
            steps.append({"id": "search", "action": "web_search", "params": {"query": "{{input}}"}})
            if "llm_call" in tool_set:
                steps.append(
                    {
                        "id": "compose",
                        "action": "llm_call",
                        "params": {"prompt": "基于以下搜索结果回答用户：\n{{search.result}}\n\n用户问题：{{input}}"},
                    }
                )
                steps.append({"id": "reply", "action": "send_to_user"})
                return steps

        if "browser_open" in tool_set:
            steps.append({"id": "open", "action": "browser_open", "params": {"url": "{{input}}"}})
            if "browser_read" in tool_set:
                steps.append({"id": "read", "action": "browser_read", "params": {"session_id": "{{open.session_id}}"}})
                if "llm_call" in tool_set:
                    steps.append(
                        {
                            "id": "compose",
                            "action": "llm_call",
                            "params": {"prompt": "根据页面内容回答用户：\n{{read.result}}\n\n用户问题：{{input}}"},
                        }
                    )
                else:
                    steps.append(
                        {
                            "id": "reply",
                            "action": "send_to_user",
                            "params": {
                                "message": "页面：{{read.title}}\n链接：{{read.url}}\n摘要：{{read.summary}}"
                            },
                        }
                    )
                    return steps
                steps.append({"id": "reply", "action": "send_to_user"})
                return steps

        if "llm_call" in tool_set:
            steps.append({"id": "respond", "action": "llm_call", "params": {"prompt": "{{input}}"}})
            steps.append({"id": "reply", "action": "send_to_user"})
            return steps

        primary_tool = next((name for name in tools if name != "send_to_user"), tools[0])
        primary_params: dict[str, Any] = {}
        if primary_tool in {"web_fetch", "browser_open"}:
            primary_params["url"] = "{{input}}"
        elif primary_tool == "file_read":
            primary_params["path"] = "{{input}}"
        else:
            primary_params["query"] = "{{input}}"
        steps.append({"id": "run", "action": primary_tool, "params": primary_params})
        if primary_tool != "send_to_user":
            if primary_tool == "browser_open":
                steps.append(
                    {
                        "id": "reply",
                        "action": "send_to_user",
                        "params": {
                            "message": "已打开页面：{{run.title}}\n链接：{{run.url}}\n摘要：{{run.summary}}"
                        },
                    }
                )
            else:
                steps.append({"id": "reply", "action": "send_to_user"})
        return steps

    @staticmethod
    def _extract_skill_markdown_body(markdown_text: str) -> str:
        text = str(markdown_text or "").strip()
        if not text:
            return ""
        if not text.startswith("---"):
            return text
        parts = text.split("\n")
        if not parts or parts[0].strip() != "---":
            return text
        for idx in range(1, len(parts)):
            if parts[idx].strip() == "---":
                return "\n".join(parts[idx + 1 :]).strip()
        return text

    def _compile_tools(self, capabilities: Any) -> list[str]:
        if not isinstance(capabilities, dict):
            return []
        tools = capabilities.get("tools")
        if not isinstance(tools, list):
            return []
        out: list[str] = []
        for item in tools:
            if isinstance(item, str):
                name = item.strip()
            elif isinstance(item, dict):
                name = str(item.get("name") or "").strip()
            else:
                name = ""
            if name and name not in out:
                out.append(name)
        return out

    def _compile_steps(self, raw_steps: Any) -> tuple[list[RuntimeStep], list[str]]:
        if not isinstance(raw_steps, list):
            return [], []
        out: list[RuntimeStep] = []
        warnings: list[str] = []
        for idx, item in enumerate(raw_steps, 1):
            if not isinstance(item, dict):
                warnings.append(f"step[{idx}] ignored: not a dict")
                continue
            action = str(item.get("action") or item.get("type") or "").strip()
            if not action:
                warnings.append(f"step[{idx}] ignored: missing action")
                continue
            sid = str(item.get("id") or f"step_{idx}").strip()
            trust = str(item.get("trust") or item.get("risk") or "auto").strip().lower() or "auto"
            params = {
                k: v
                for k, v in item.items()
                if k not in {"id", "action", "type", "trust", "risk"}
            }
            if isinstance(params.get("params"), dict):
                nested = params.pop("params")
                for k, v in nested.items():
                    params.setdefault(k, v)
            if "trust_level" in params and "trust" not in params:
                trust = str(params.pop("trust_level") or trust).strip().lower() or trust
            out.append(RuntimeStep(id=sid, action=action, params=params, trust=trust))
        return out, warnings

    def _extract_personality(self, raw: dict[str, Any]) -> dict[str, Any]:
        p = raw.get("personality") if isinstance(raw.get("personality"), dict) else {}
        if not p:
            return {}
        ocean_keys = ["openness", "conscientiousness", "extraversion", "agreeableness", "stability"]
        if "ocean" in p and isinstance(p.get("ocean"), dict):
            return p
        if any(k in p for k in ocean_keys):
            ocean = {k: p[k] for k in ocean_keys if k in p}
            rest = {k: v for k, v in p.items() if k not in ocean_keys}
            return {"ocean": ocean, **rest}
        return p

    def _compile_system_prompt(self, raw: dict[str, Any]) -> str:
        lines: list[str] = []
        role = raw.get("role") if isinstance(raw.get("role"), dict) else {}
        personality = self._extract_personality(raw)

        if isinstance(role, dict):
            goal = str(role.get("goal") or "").strip()
            if goal:
                lines.append(f"Agent goal: {goal}")
            style = str(role.get("style") or "").strip()
            if style:
                lines.append(f"Interaction style: {style}")

        if personality:
            ocean = personality.get("ocean") if isinstance(personality.get("ocean"), dict) else {}
            if ocean:
                kv = ", ".join(f"{k}={v}" for k, v in ocean.items())
                lines.append(f"OCEAN profile: {kv}")
            persona_text = str(personality.get("prompt") or personality.get("description") or "").strip()
            if persona_text:
                lines.append(f"Persona: {persona_text}")

        instruction = str(raw.get("system_prompt") or raw.get("instruction") or "").strip()
        if instruction:
            lines.append(instruction)

        constraints_block = self._compile_constraints(raw.get("constraints"))
        if constraints_block:
            lines.append(constraints_block)

        return "\n".join(lines).strip()

    @staticmethod
    def _compile_constraints(raw_constraints: Any) -> str:
        if not isinstance(raw_constraints, list):
            return ""
        items: list[str] = []
        seen: set[str] = set()
        for item in raw_constraints:
            text = str(item or "").strip()
            if not text or text in seen:
                continue
            seen.add(text)
            items.append(text)
        if not items:
            return ""
        return "关键约束：\n" + "\n".join(f"- {item}" for item in items)

    def _backend_native_mirror_hint(self, backend_profile: str) -> dict[str, Any]:
        if backend_profile == "opencode":
            return {"supported": True, "agent_native": True, "skills_native": True}
        if backend_profile == "qwen_code":
            return {"supported": True, "agent_native": True, "skills_native": True}
        if backend_profile == "kimi_code":
            return {"supported": True, "agent_native": True, "skills_native": True}
        if backend_profile == "claude_code":
            return {"supported": True, "agent_native": "subagents", "skills_native": "mcp/subagents"}
        return {"supported": False}


def compile_agent_spec(spec: dict[str, Any]) -> RuntimePlan:
    return AgentCompiler().compile(spec)
