"""Secret Santa matching engine with constraint satisfaction, feasibility checking, and gift tag code generation."""

from dataclasses import dataclass, field
import random
from typing import Optional


class MatchingError(Exception):
    """Raised when matching cannot be satisfied with the given constraints."""
    pass


@dataclass
class FeasibilityReport:
    """Diagnostic report describing Secret Santa cycle feasibility."""
    is_feasible: bool
    status: str  # "READY", "WARNING", "IMPOSSIBLE", "NOT_ENOUGH_PARTICIPANTS"
    headline: str
    details: list[str] = field(default_factory=list)


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


def validate_draw_feasibility(
    participants: list[int],
    exclusions: Optional[list[tuple[int, int]]] = None,
    names: Optional[dict[int, str]] = None,
) -> FeasibilityReport:
    """
    Proactively checks whether a single continuous Hamiltonian cycle is mathematically possible.

    Args:
        participants: List of unique participant IDs.
        exclusions: List of (user_a, user_b) tuples who cannot be paired.
        names: Optional lookup map of user_id -> display_name for human-friendly messages.

    Returns:
        FeasibilityReport with is_feasible, status, headline, and details.
    """
    n = len(participants)
    if n == 0:
        return FeasibilityReport(
            is_feasible=False,
            status="NOT_ENOUGH_PARTICIPANTS",
            headline="No participants registered yet.",
        )

    if n < 3:
        return FeasibilityReport(
            is_feasible=False,
            status="NOT_ENOUGH_PARTICIPANTS",
            headline=f"Need at least 3 participants to form a Secret Santa circle (currently {n}).",
        )

    if len(set(participants)) != n:
        return FeasibilityReport(
            is_feasible=False,
            status="IMPOSSIBLE",
            headline="Duplicate participant IDs detected.",
        )

    def name_of(u: int) -> str:
        return names.get(u, f"User {u}") if names else f"User {u}"

    # Build bidirectional exclusion set
    forbidden_pairs: set[tuple[int, int]] = set()
    if exclusions:
        for u, v in exclusions:
            forbidden_pairs.add((u, v))
            forbidden_pairs.add((v, u))

    # Directed candidate edges: u can gift v iff u != v and (u, v) not in forbidden
    adj: dict[int, list[int]] = {
        u: [v for v in participants if v != u and (u, v) not in forbidden_pairs]
        for u in participants
    }
    rev_adj: dict[int, list[int]] = {
        u: [v for v in participants if v != u and (v, u) not in forbidden_pairs]
        for u in participants
    }

    # 1. Zero out-degree check
    zero_out = [u for u in participants if len(adj[u]) == 0]
    if zero_out:
        details = [f"**{name_of(u)}** has no valid recipients left (all others excluded)." for u in zero_out]
        return FeasibilityReport(
            is_feasible=False,
            status="IMPOSSIBLE",
            headline="One or more participants have no allowed recipients.",
            details=details,
        )

    # 2. Zero in-degree check
    zero_in = [u for u in participants if len(rev_adj[u]) == 0]
    if zero_in:
        details = [f"**{name_of(u)}** has no santas who can gift them." for u in zero_in]
        return FeasibilityReport(
            is_feasible=False,
            status="IMPOSSIBLE",
            headline="One or more participants cannot receive gifts from anyone.",
            details=details,
        )

    # 3. Special case: N=3 with any exclusion
    if n == 3 and exclusions:
        u, v = exclusions[0]
        return FeasibilityReport(
            is_feasible=False,
            status="IMPOSSIBLE",
            headline=f"With 3 participants, excluding **{name_of(u)}** and **{name_of(v)}** makes a cycle impossible.",
            details=["In a 3-person Secret Santa, any mutual exclusion eliminates all possible 3-cycles."],
        )

    # 4. Maximum bipartite matching (Hall's condition / derangement feasibility)
    match: dict[int, int] = {}

    def match_dfs(u: int, visited: set[int]) -> bool:
        for v in adj[u]:
            if v not in visited:
                visited.add(v)
                if v not in match or match_dfs(match[v], visited):
                    match[v] = u
                    return True
        return False

    for u in participants:
        match_dfs(u, set())

    if len(match) < n:
        unmatched = [name_of(u) for u in participants if u not in match.values()]
        return FeasibilityReport(
            is_feasible=False,
            status="IMPOSSIBLE",
            headline="Exclusions create a recipient bottleneck preventing a complete 1-to-1 matching.",
            details=[f"Participants such as {item} cannot be assigned unique recipients." for item in unmatched[:3]],
        )

    # 5. Strong reachability check (BFS from all nodes)
    for u in participants:
        visited = set()
        queue = [u]
        visited.add(u)
        while queue:
            curr = queue.pop(0)
            for neighbor in adj[curr]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        if len(visited) < n:
            unreached = [name_of(v) for v in participants if v not in visited]
            return FeasibilityReport(
                is_feasible=False,
                status="IMPOSSIBLE",
                headline="Exclusions divide participants into disconnected groups.",
                details=[f"**{name_of(u)}** cannot reach {item} through any valid gift chain." for item in unreached[:3]],
            )

    # 6. Bounded Warnsdorff Hamiltonian cycle search
    start = participants[0]
    path = [start]
    visited = {start}
    states = 0
    max_states = 5000

    def backtrack(curr: int) -> bool:
        nonlocal states
        states += 1
        if states > max_states:
            return False
        if len(path) == n:
            return start in adj[curr]
        cands = [v for v in adj[curr] if v not in visited]
        cands.sort(key=lambda v: sum(1 for w in adj[v] if w not in visited))
        for nxt in cands:
            visited.add(nxt)
            path.append(nxt)
            if backtrack(nxt):
                return True
            path.pop()
            visited.remove(nxt)
        return False

    if not backtrack(start):
        return FeasibilityReport(
            is_feasible=False,
            status="IMPOSSIBLE",
            headline="Exclusion rules prevent a continuous Hamiltonian cycle from forming.",
            details=["No unbroken circle connecting all participants could be found."],
        )

    # 7. Check for tight constraints / warnings
    tight_1 = [u for u in participants if len(adj[u]) == 1]
    if tight_1:
        details = [f"**{name_of(u)}** has only 1 valid recipient left (**{name_of(adj[u][0])}**)." for u in tight_1]
        return FeasibilityReport(
            is_feasible=True,
            status="WARNING",
            headline="Matching is possible, but constraint bottlenecks exist.",
            details=details,
        )

    tight_2 = [u for u in participants if len(adj[u]) == 2]
    if tight_2 and n >= 6:
        details = [f"**{name_of(u)}** has only 2 valid recipients left." for u in tight_2[:3]]
        return FeasibilityReport(
            is_feasible=True,
            status="WARNING",
            headline="Matching is possible, but tight constraints exist.",
            details=details,
        )

    return FeasibilityReport(
        is_feasible=True,
        status="READY",
        headline="Valid Secret Santa cycle is ready to draw!",
        details=[f"{n} participants registered; plenty of matching combinations available."],
    )


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

    # Fast feasibility pre-check
    report = validate_draw_feasibility(participants, exclusions)
    if not report.is_feasible:
        reason = report.headline
        if report.details:
            clean_detail = report.details[0].replace("**", "")
            reason += f" ({clean_detail})"
        raise MatchingError(
            f"Could not generate a valid Secret Santa cycle. Constraints or exclusions may be too restrictive: {reason}"
        )

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

