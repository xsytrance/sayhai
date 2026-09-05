"""Deeper memory (Phase 7).

Graduates from "no memory" to flat-but-persistent notes: the creature learns your
**name** and remembers **facts** you tell it, and injects the relevant ones back
into the brain's context so it actually recalls your name, your dog, the inside
joke. Stored in ``data/memory.json``.

Extraction is deliberately simple (name patterns + "remember ..."); smarter recall
(embeddings/semantic search) is a future upgrade behind the same ``context_for``.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_NAME_EXPLICIT = re.compile(r"\b(?:my name is|call me|name's)\s+([A-Za-z][\w'-]{1,20})", re.I)
_NAME_IM = re.compile(r"\b(?i:i'm|i am)\s+([A-Z][a-z]{1,20})\b")   # capitalized => a name, not "i'm tired"
_REMEMBER = re.compile(r"\bremember(?:\s+that|\s+this)?[:,]?\s+(.+)", re.I)
_STOP = {"not", "so", "just", "really", "very", "still", "also", "fine", "good", "ok",
         "okay", "here", "back", "done", "sorry", "tired", "happy", "sad", "hungry",
         "bored", "busy", "sure", "the", "a", "an", "your", "you"}
_MAX_FACTS = 60


class Memory:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.name: str = ""
        self.facts: list[str] = []
        self.load()

    # --- persistence -------------------------------------------------------
    def load(self) -> None:
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            self.name = str(d.get("name", "") or "")
            self.facts = [str(f) for f in d.get("facts", []) if str(f).strip()]
        except Exception:
            pass

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({"name": self.name, "facts": self.facts}), encoding="utf-8")
        except Exception:
            pass

    # --- writing -----------------------------------------------------------
    def set_name(self, name: str) -> None:
        name = name.strip().strip(".!,").capitalize()
        if name and name.lower() not in _STOP and name != self.name:
            self.name = name
            self.save()

    def add_fact(self, fact: str) -> None:
        fact = " ".join(fact.split()).strip().strip(".")
        if len(fact) < 3:
            return
        low = fact.lower()
        if any(f.lower() == low for f in self.facts):
            return
        self.facts.append(fact)
        del self.facts[: max(0, len(self.facts) - _MAX_FACTS)]
        self.save()

    def extract(self, text: str) -> bool:
        """Learn name/facts from a user message. Returns True if anything stuck."""
        changed = False
        m = _NAME_EXPLICIT.search(text) or _NAME_IM.search(text)
        if m:
            before = self.name
            self.set_name(m.group(1))
            changed = changed or self.name != before
        for rm in _REMEMBER.finditer(text):
            before = len(self.facts)
            self.add_fact(rm.group(1))
            changed = changed or len(self.facts) != before
        return changed

    # --- reading -----------------------------------------------------------
    def _relevant(self, text: str, k: int = 5) -> list[str]:
        words = set(re.findall(r"[a-z]{4,}", text.lower()))
        rel = [f for f in self.facts if any(w in f.lower() for w in words)]
        rest = [f for f in reversed(self.facts) if f not in rel]
        return (rel + rest)[:k]

    def context_for(self, text: str) -> str:
        bits = []
        if self.name:
            bits.append(f"your human is named {self.name}")
        rel = self._relevant(text)
        if rel:
            bits.append("you remember: " + "; ".join(rel))
        return ("WHAT YOU KNOW — " + ". ".join(bits) + ".") if bits else ""

    def public(self) -> dict:
        return {"name": self.name, "facts": self.facts}
