"""Unit tests for Secret Santa matching service."""

import pytest
from src.services.matcher import generate_pairings, MatchingError


def test_matching_requires_minimum_three():
    with pytest.raises(MatchingError, match="At least 3 participants"):
        generate_pairings([101, 102])


def test_matching_detects_duplicates():
    with pytest.raises(MatchingError, match="Duplicate participant"):
        generate_pairings([101, 102, 101])


def test_basic_derangement_cycle():
    participants = [1, 2, 3, 4, 5]
    pairings = generate_pairings(participants)

    assert len(pairings) == 5

    santas = [p[0] for p in pairings]
    babies = [p[1] for p in pairings]
    codes = [p[2] for p in pairings]

    # Everyone is a Santa once and a Baby once
    assert sorted(santas) == sorted(participants)
    assert sorted(babies) == sorted(participants)

    # No one gives to themselves
    for s, b, _ in pairings:
        assert s != b

    # Codes are unique and properly formatted
    assert len(set(codes)) == 5
    for c in codes:
        assert "-" in c


def test_exclusions_respected():
    participants = [1, 2, 3, 4, 5, 6]
    # 1 and 2 are a couple (excluded both ways)
    # 3 and 4 are roommates (excluded both ways)
    exclusions = [(1, 2), (3, 4)]

    for _ in range(20):  # Run 20 times to ensure probabilistic consistency
        pairings = generate_pairings(participants, exclusions=exclusions)
        pairing_map = {s: b for s, b, _ in pairings}

        # 1 never gives to 2, 2 never gives to 1
        assert pairing_map[1] != 2
        assert pairing_map[2] != 1

        # 3 never gives to 4, 4 never gives to 3
        assert pairing_map[3] != 4
        assert pairing_map[4] != 3

        # No self assignments
        for s, b in pairing_map.items():
            assert s != b


def test_overconstrained_exclusions_raises_error():
    # 3 participants where 1 excludes 2 and 1 excludes 3
    # 1 has no valid recipients
    participants = [1, 2, 3]
    exclusions = [(1, 2), (1, 3)]

    with pytest.raises(MatchingError, match="Could not generate a valid Secret Santa cycle"):
        generate_pairings(participants, exclusions=exclusions, max_attempts=50)


def test_single_hamiltonian_cycle():
    participants = list(range(1, 11))
    pairings = generate_pairings(participants)
    pairing_dict = {s: b for s, b, _ in pairings}

    # Traverse cycle from participant 1
    current = 1
    visited = [current]
    for _ in range(len(participants) - 1):
        current = pairing_dict[current]
        visited.append(current)

    # Next node should loop back to 1
    assert pairing_dict[current] == 1
    # All 10 participants must be in this single cycle
    assert len(set(visited)) == 10
