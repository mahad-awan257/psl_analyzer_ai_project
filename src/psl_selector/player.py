"""Player record used by every selector."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass(frozen=True)
class Player:
    """One player: cost, value, role and statistics."""
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
        """Value for each credit spent."""
        return self.value / self.credits

    def to_dict(self) -> dict:
        """Fields as a dictionary, without the statistics."""
        d = asdict(self)
        d.pop("stats")
        return d
