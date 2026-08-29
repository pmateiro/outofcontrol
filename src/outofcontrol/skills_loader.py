from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Skill:
    name: str
    description: str
    body: str
    path: Path

    @property
    def summary(self) -> str:
        return f"- {self.name}: {self.description}"


_FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    m = _FRONTMATTER.match(text)
    if not m:
        return {}, text.strip()
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        meta[key.strip()] = val.strip().strip("\"'")
    return meta, m.group(2).strip()


class SkillLoader:
    def __init__(self, skills_dir: Path) -> None:
        self.skills_dir = skills_dir
        self._cache: dict[str, Skill] | None = None

    def _discover(self) -> dict[str, Skill]:
        found: dict[str, Skill] = {}
        if not self.skills_dir.exists():
            return found
        for path in sorted(self.skills_dir.rglob("SKILL.md")):
            text = path.read_text(encoding="utf-8")
            meta, body = _parse_frontmatter(text)
            name = meta.get("name") or path.parent.name
            description = meta.get("description") or "(no description)"
            found[name] = Skill(name=name, description=description, body=body, path=path)
        return found

    def all(self) -> list[Skill]:
        if self._cache is None:
            self._cache = self._discover()
        return list(self._cache.values())

    def get(self, name: str) -> Skill | None:
        if self._cache is None:
            self._cache = self._discover()
        return self._cache.get(name)

    def reload(self) -> None:
        self._cache = None

    def inventory_text(self) -> str:
        skills = self.all()
        if not skills:
            return "(no skills installed)"
        return "\n".join(s.summary for s in skills)
