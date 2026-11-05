"""Secret Santa matching engine with constraint satisfaction and gift tag code generation."""

import random
from typing import Optional


class MatchingError(Exception):
    """Raised when matching cannot be satisfied with the given constraints."""
    pass


GIFT_CODE_WORDS = [
    "POLAR", "RUDOLPH", "FROSTY", "SNOWFLAKE", "GINGERBREAD",
    "NUTCRACKER", "JINGLE", "TINSEL", "CANDYCANE", "BLITZEN",
    "COMET", "DASHER", "PRANCER", "VIXEN", "CUPID", "DONNER"
]


def generate_gift_tag_code(index: int, used_codes: set[str]) -> str:
    """Generate a memorable, unique gift tag code for physical wrapping."""
    while True:
        word = random.choice(GIFT_CODE_WORDS)
        num = random.randint(10, 99)
        code = f"{word}-{num}"
        if code not in used_codes:
            used_codes.add(code)
            return code


def generate_pairings(
    participants: list[int],
    exclusions: Optional[list[tuple[int, int]]] = None,
    max_attempts: int = 1000,
) -> list[tuple[int, int, str]]:
    """
    Generate Secret Santa pairings forming a single unbroken Hamiltonian cycle.

    Args:
        participants: List of unique participant IDs (integers).
        exclusions: List of (user_a, user_b) tuples who cannot be paired together.
        max_attempts: Maximum randomized restart attempts before failing.

    Returns:
        List of tuples: [(santa_id, baby_id, gift_tag_code), ...]

    Raises:
        MatchingError: If participant count < 3 or valid cycle cannot be found.
    """
    if len(participants) < 3:
        raise MatchingError("At least 3 participants are required to run Secret Santa.")

    # Check for duplicates
    if len(set(participants)) != len(participants):
        raise MatchingError("Duplicate participant IDs detected.")

    # Build bidirectional exclusion lookup set
    forbidden_pairs: set[tuple[int, int]] = set()
    if exclusions:
        for u, v in exclusions:
            forbidden_pairs.add((u, v))
            forbidden_pairs.add((v, u))

    users = list(participants)
    n = len(users)

    # Attempt to find a randomized Hamiltonian cycle using backtracking
    for _ in range(max_attempts):
        random.shuffle(users)
        start_node = users[0]
        path = [start_node]
        visited = {start_node}

        def backtrack(current: int) -> bool:
            if len(path) == n:
                # Check cycle wrap-around from last to first
                if (current, start_node) not in forbidden_pairs and current != start_node:
                    return True
                return False

            # Collect unvisited candidates that are not excluded
            candidates = [
                u for u in users
                if u not in visited and u != current and (current, u) not in forbidden_pairs
            ]
            random.shuffle(candidates)

            for cand in candidates:
                visited.add(cand)
                path.append(cand)
                if backtrack(cand):
                    return True
                path.pop()
                visited.remove(cand)

            return False

        if backtrack(start_node):
            # Successfully found Hamiltonian cycle
            # path is [p0, p1, p2, ..., pN-1]
            # p0 -> p1, p1 -> p2, ..., pN-1 -> p0
            used_codes: set[str] = set()
            pairings: list[tuple[int, int, str]] = []
            for i in range(n):
                santa = path[i]
                baby = path[(i + 1) % n]
                code = generate_gift_tag_code(i, used_codes)
                pairings.append((santa, baby, code))
            return pairings

    raise MatchingError(
        "Could not generate a valid Secret Santa cycle. Constraints or exclusions may be too restrictive."
    )
