"""Team selection methods."""
from .base import TeamSelector, SelectionResult
from .greedy import GreedySelector
from .backtracking import BacktrackingSelector
from .genetic import GeneticSelector

SELECTORS = {"Backtracking": BacktrackingSelector, "Genetic": GeneticSelector, "Greedy": GreedySelector}

__all__ = ["TeamSelector", "SelectionResult", "GreedySelector", "BacktrackingSelector",
           "GeneticSelector", "SELECTORS"]
