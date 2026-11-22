"""Player record used by every selector."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass(frozen=True)
class Player:
    player_id: str
    name: str
    role: str            # WK, BAT, AR or BOWL
    overseas: bool
    credits: float       # simulated cost
    value: float         # role-normalized historical value (utility contribution)
    team: str = ""
    cluster: int = -1
    profile: str = ""
    stats: dict = field(default_factory=dict, compare=False, hash=False, repr=False)

    @property
    def value_per_credit(self) -> float:
        return self.value / self.credits

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("stats")
        return d
