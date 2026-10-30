"""parity.yaml models and preset loading."""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, Field


class Tool(BaseModel):
    label: str
    command: str
    container: Optional[str] = None
    version_command: Optional[str] = None


class Case(BaseModel):
    id: str
    inputs: dict[str, str] = Field(default_factory=dict)
    params: str = ""


class OutputRule(BaseModel):
    pattern: str                                  # glob relative to the reference output dir
    comparator: str = "exact"
    options: dict[str, Any] = Field(default_factory=dict)
    rename: Optional[tuple[str, str]] = None      # (regex, replacement) giving the candidate path
    required: bool = True


class Accepted(BaseModel):
    pattern: str
    reason: str


class Spec(BaseModel):
    name: str = "parity"
    extends: Optional[str] = None                 # preset name
    reference: Optional[Tool] = None
    candidate: Optional[Tool] = None
    cases: list[Case] = Field(default_factory=list)
    outputs: list[OutputRule] = Field(default_factory=list)
    accepted_divergences: list[Accepted] = Field(default_factory=list)
    ignore: list[str] = Field(default_factory=list)


def preset_names() -> list[str]:
    return sorted(p.name[:-5] for p in resources.files("bioparity.presets").iterdir() if p.name.endswith(".yaml"))


def load_preset(name: str) -> dict:
    path = resources.files("bioparity.presets") / f"{name}.yaml"
    if not path.is_file():
        raise ValueError(f"unknown preset '{name}'. available: {', '.join(preset_names())}")
    return yaml.safe_load(path.read_text())


def load_spec(path: Path | None, preset: str | None = None) -> Spec:
    data: dict = yaml.safe_load(path.read_text()) if path else {}
    data = data or {}
    base_name = preset or data.get("extends")
    if base_name:
        base = load_preset(base_name)
        # the user's rules come first so they win; preset rules fill in the rest
        data["outputs"] = list(data.get("outputs", [])) + list(base.get("outputs", []))
        data["accepted_divergences"] = list(data.get("accepted_divergences", [])) + list(base.get("accepted_divergences", []))
        data["ignore"] = list(data.get("ignore", [])) + list(base.get("ignore", []))
        data.setdefault("name", base.get("name", base_name))
    return Spec(**data)
