from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .agent_runtime import AgentCompiler, RuntimePlan


@dataclass
class LoadedAgent:
    agent_id: str
    source_path: str
    spec: dict[str, Any]
    plan: RuntimePlan
    pack_path: str = ""
    pack_spec: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentRegistryLoadResult:
    agents: dict[str, LoadedAgent] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    scanned_files: list[str] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        return {
            "agents": sorted(self.agents.keys()),
            "count": len(self.agents),
            "errors": list(self.errors),
            "scanned_files": list(self.scanned_files),
        }


class AgentRegistry:
    """Load runtime capability packages from runtime_assets only."""

    def __init__(
        self,
        agents_dir: str | Path = "agents",
        compiler: AgentCompiler | None = None,
        runtime_assets_dir: str | Path | None = None,
    ):
        self.agents_dir = Path(agents_dir)
        self.runtime_assets_dir = (
            Path(runtime_assets_dir) if runtime_assets_dir is not None else self.agents_dir.parent / "runtime_assets"
        )
        self.compiler = compiler or AgentCompiler()
        self._agents: dict[str, LoadedAgent] = {}

    def load_all(self) -> AgentRegistryLoadResult:
        result = AgentRegistryLoadResult()
        self._agents = {}

        self._load_pack_entries(result)

        return result

    def get(self, agent_id: str) -> LoadedAgent | None:
        return self._agents.get(agent_id)

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError("root YAML must be a mapping/object")
        return raw

    def _load_pack_entries(self, result: AgentRegistryLoadResult) -> None:
        root = self.runtime_assets_dir
        if not root.exists():
            return
        for pack_path in sorted(root.glob("*/pack.yaml")):
            result.scanned_files.append(str(pack_path))
            try:
                loaded = self._load_pack_only(pack_path)
            except Exception as e:
                result.errors.append(f"{pack_path}: {e}")
                continue

            if loaded.agent_id in self._agents:
                continue

            self._agents[loaded.agent_id] = loaded
            result.agents[loaded.agent_id] = loaded

    def _load_pack_only(self, pack_path: Path) -> LoadedAgent:
        pack_spec = self._read_yaml(pack_path)
        skill_md_path = pack_path.parent / "SKILL.md"
        skill_markdown = skill_md_path.read_text(encoding="utf-8") if skill_md_path.exists() else ""
        plan = self.compiler.compile_pack(pack_spec, skill_markdown=skill_markdown)
        agent_id = plan.agent_name.strip() or pack_path.parent.name
        spec = self.compiler.pack_to_agent_spec(pack_spec, skill_markdown=skill_markdown)
        return LoadedAgent(
            agent_id=agent_id,
            source_path=str(pack_path),
            spec=spec,
            plan=plan,
            pack_path=str(pack_path),
            pack_spec=pack_spec,
        )


def load_agents_registry(agents_dir: str | Path = "agents") -> AgentRegistryLoadResult:
    return AgentRegistry(agents_dir=agents_dir).load_all()
