"""The Life — the Tamagotchi layer (Phase 5).

Stats (hunger, energy, bond), XP & levels, and feeding. The **critical** rule:
this must feed the emotion spine, not sit in a corner as lonely numbers. So the
game doesn't pick emotions directly — it hands the brain a short *body-state*
line ("you're hungry and tired"), and the brain colors its mood + words + the
emotion it emits. Hungry => grumpy, clipped. Freshly fed / leveled => bouncy.

Feeding is two things: **attention is food** (talking to it nourishes) **and** a
literal **treat** for a dopamine hit. Leveling **unlocks** things you can see
(cosmetic accessories on the face) and do (abilities). Neglect is gentle — it
gets sleepy/wistful, never guilt-trippy.

State persists to ``data/state.json``; it even keeps (gently) getting hungry while
the app is off.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

# --- tuning (per real minute of wall-clock) --------------------------------
_HUNGER_DECAY = 0.28      # ~full -> empty over ~6h of neglect
_ENERGY_RECOVER = 0.15    # rests back up when you're not chatting
_OFFLINE_CAP_MIN = 12 * 60

# per conversation turn (attention is food)
_TURN_HUNGER = 5.0
_TURN_ENERGY = -1.5
_TURN_BOND = 2.0
_TURN_XP = 8

# a treat
_TREAT_HUNGER = 35.0
_TREAT_ENERGY = 8.0
_TREAT_XP = 5

_LEVEL_XP = [0, 30, 80, 160, 280, 450, 700, 1000]   # cumulative xp per level
_LEVEL_NAME = ["Hatchling", "Chick", "Fledgling", "Juvenile", "Bird", "Elder", "Mythic", "Legend"]

# level -> what it unlocks (a face accessory you can see + an ability it can do)
_UNLOCKS = {
    2: {"accessory": "bowtie", "ability": "telling jokes"},
    3: {"accessory": "party_hat", "ability": "trivia"},
    4: {"accessory": "monocle", "ability": "deeper facts"},
    5: {"accessory": "crown", "ability": "a fancier flair"},
}


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return lo if v < lo else hi if v > hi else v


def level_for_xp(xp: int) -> int:
    lvl = 1
    for i, need in enumerate(_LEVEL_XP):
        if xp >= need:
            lvl = i + 1
    return lvl


class Game:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.hunger = 70.0
        self.energy = 80.0
        self.bond = 10.0
        self.xp = 0
        self.level = 1
        self._last = time.time()
        self.load()

    # --- persistence -------------------------------------------------------
    def load(self) -> None:
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return  # first run / missing / corrupt -> keep defaults
        self.hunger = float(d.get("hunger", self.hunger))
        self.energy = float(d.get("energy", self.energy))
        self.bond = float(d.get("bond", self.bond))
        self.xp = int(d.get("xp", self.xp))
        self._last = float(d.get("last", time.time()))
        self.level = level_for_xp(self.xp)
        # gently catch up the hunger/energy for the time it was off
        offline_min = min(_OFFLINE_CAP_MIN, max(0.0, (time.time() - self._last) / 60.0))
        if offline_min:
            self.tick(offline_min, save=False)

    def save(self) -> None:
        self._last = time.time()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps({
                "hunger": round(self.hunger, 2), "energy": round(self.energy, 2),
                "bond": round(self.bond, 2), "xp": self.xp, "last": self._last,
            }), encoding="utf-8")
        except Exception:
            pass

    # --- simulation --------------------------------------------------------
    def tick(self, minutes: float, save: bool = True) -> None:
        self.hunger = _clamp(self.hunger - _HUNGER_DECAY * minutes)
        self.energy = _clamp(self.energy + _ENERGY_RECOVER * minutes)
        if save:
            self.save()

    def _add_xp(self, n: int) -> dict:
        before = self.level
        self.xp += n
        self.level = level_for_xp(self.xp)
        unlocked = []
        if self.level > before:
            for lv in range(before + 1, self.level + 1):
                if lv in _UNLOCKS:
                    unlocked.append(_UNLOCKS[lv])
        return {"leveled_up": self.level > before, "level": self.level, "unlocked": unlocked}

    def on_interaction(self) -> dict:
        """A conversation turn: attention nourishes (and costs a little energy)."""
        self.hunger = _clamp(self.hunger + _TURN_HUNGER)
        self.energy = _clamp(self.energy + _TURN_ENERGY)
        self.bond = _clamp(self.bond + _TURN_BOND)
        res = self._add_xp(_TURN_XP)
        self.save()
        return res

    def feed_treat(self) -> dict:
        """The literal treat button — a hunger refill + a dopamine bump."""
        self.hunger = _clamp(self.hunger + _TREAT_HUNGER)
        self.energy = _clamp(self.energy + _TREAT_ENERGY)
        res = self._add_xp(_TREAT_XP)
        self.save()
        return res

    # --- readouts ----------------------------------------------------------
    def accessories(self) -> list[str]:
        return [u["accessory"] for lv, u in _UNLOCKS.items() if lv <= self.level]

    def abilities(self) -> list[str]:
        return [u["ability"] for lv, u in _UNLOCKS.items() if lv <= self.level]

    @staticmethod
    def _word(v: float, words: list[str]) -> str:
        # words for [<20, <40, <70, else]
        return words[0] if v < 20 else words[1] if v < 40 else words[2] if v < 70 else words[3]

    def hunger_word(self) -> str:
        return self._word(self.hunger, ["starving", "peckish", "fine", "full"])

    def energy_word(self) -> str:
        return self._word(self.energy, ["exhausted", "tired", "okay", "peppy"])

    def status_line(self) -> str:
        """The body-state the brain reads so the game feeds the mood."""
        s = f"Right now you are Level {self.level} ({_LEVEL_NAME[min(self.level - 1, len(_LEVEL_NAME) - 1)]}). "
        s += f"You feel {self.hunger_word()} and {self.energy_word()}"
        if self.bond >= 70:
            s += ", and close to your human"
        s += ". Let this color your mood: hungry -> grumpy and clipped; freshly fed or just leveled up -> bouncy and generous; tired -> sleepy and soft."
        if self.abilities():
            s += " You've unlocked: " + ", ".join(self.abilities()) + "."
        return s

    def public(self) -> dict:
        nxt = next((n for n in _LEVEL_XP if n > self.xp), None)
        return {
            "level": self.level,
            "level_name": _LEVEL_NAME[min(self.level - 1, len(_LEVEL_NAME) - 1)],
            "xp": self.xp,
            "xp_to_next": (nxt - self.xp) if nxt is not None else None,
            "hunger": round(self.hunger),
            "energy": round(self.energy),
            "bond": round(self.bond),
            "hunger_word": self.hunger_word(),
            "energy_word": self.energy_word(),
            "accessories": self.accessories(),
            "abilities": self.abilities(),
        }
