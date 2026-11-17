"""Unit tests for smart poll emoji detection (ABC indicators, keyword matching, budget & Yes/No)."""

from src.utils.poll_detector import (
    detect_poll_emojis,
    clean_option_label,
    ABC_EMOJIS,
    BUDGET_EMOJIS,
)
from src.ui.embeds import build_poll_embed


def test_clean_option_label():
    assert clean_option_label("A. First choice") == "First choice"
    assert clean_option_label("B) Second choice") == "Second choice"
    assert clean_option_label("1. Third choice") == "Third choice"
    assert clean_option_label("1) Fourth choice") == "Fourth choice"
    assert clean_option_label("Plain choice") == "Plain choice"
    assert clean_option_label("A") == "A"


def test_abc_regional_indicators_fallback():
    question = "Which movie should we watch?"
    options = ["Home Alone", "Die Hard", "Elf", "The Grinch"]

    emojis, labels = detect_poll_emojis(question, options)
    assert emojis == ["🇦", "🇧", "🇨", "🇩"]
    assert labels == options

    embed, ret_emojis = build_poll_embed(question, options)
    assert ret_emojis == ["🇦", "🇧", "🇨", "🇩"]
    assert "🇦 **Home Alone**" in embed.description
    assert "🇧 **Die Hard**" in embed.description
    assert "🇨 **Elf**" in embed.description
    assert "🇩 **The Grinch**" in embed.description


def test_yes_no_detection():
    # English Yes / No
    emojis, labels = detect_poll_emojis("Should we do a Secret Santa?", ["Yes", "No"])
    assert emojis == ["👍", "👎"]

    # Flipped No / Yes
    emojis_flip, _ = detect_poll_emojis("Any objections?", ["No", "Yes"])
    assert emojis_flip == ["👎", "👍"]

    # Vietnamese Có / Không
    emojis_vn, _ = detect_poll_emojis("Tổ chức tiệc không?", ["Có", "Không"])
    assert emojis_vn == ["👍", "👎"]


def test_budget_poll_detection():
    # Question containing budget keyword
    q = "What should the gift budget ceiling be?"
    opts = ["$20", "$35", "$50", "$75"]

    emojis, labels = detect_poll_emojis(q, opts)
    assert emojis == BUDGET_EMOJIS[:4]
    assert emojis == ["🪙", "💵", "💸", "💰"]

    # Options with k/vnd currencies
    q2 = "Chọn mức giá quà"
    opts2 = ["100k - 200k", "200k - 300k", "300k - 500k"]
    emojis2, _ = detect_poll_emojis(q2, opts2)
    assert emojis2 == ["🪙", "💵", "💸"]


def test_explicit_leading_emojis():
    question = "Holiday date preference"
    options = ["🎄 Dec 22", "🎅 Dec 23", "🎁 Dec 24"]

    emojis, labels = detect_poll_emojis(question, options)
    assert emojis == ["🎄", "🎅", "🎁"]
    assert labels == ["Dec 22", "Dec 23", "Dec 24"]

    embed, _ = build_poll_embed(question, options)
    assert "🎄 **Dec 22**" in embed.description
    assert "🎅 **Dec 23**" in embed.description
    assert "🎁 **Dec 24**" in embed.description


def test_keyword_matching_venues_and_food():
    # Venues
    q = "Where should the holiday party take place?"
    venues = ["At Alice's House", "Beer Garden / Pub", "Italian Restaurant", "Company Office"]
    emojis, labels = detect_poll_emojis(q, venues)
    assert emojis == ["🏠", "🍻", "🍽️", "🏢"]

    # Food
    q_food = "What should we order for dinner?"
    food = ["Pizza", "BBQ Meat", "Sushi Platter"]
    emojis_f, _ = detect_poll_emojis(q_food, food)
    assert emojis_f == ["🍕", "🥩", "🍣"]
