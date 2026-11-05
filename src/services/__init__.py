"""Services package for Buda Secret Santa."""
from .matcher import generate_pairings, MatchingError

__all__ = ["generate_pairings", "MatchingError"]
