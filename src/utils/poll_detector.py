"""Smart poll emoji detection: Regional Indicator ABC, contextual keywords, and Yes/No detection."""

import re
from typing import Optional

# Regional Indicator Symbols (🇦, 🇧, 🇨, 🇩, 🇪, ...)
ABC_EMOJIS: list[str] = [chr(0x1F1E6 + i) for i in range(26)]

# Fallback number keycaps (1️⃣, 2️⃣, ...)
NUMBER_EMOJIS: list[str] = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

# Budget / Money progressive emojis
BUDGET_EMOJIS: list[str] = ["🪙", "💵", "💸", "💰", "💳", "💎", "🏆", "🎁", "✨", "👑"]

# Leading emoji pattern (Discord custom emoji or standard Unicode symbols)
EMOJI_PATTERN = re.compile(
    r"^("
    r"<a?:[a-zA-Z0-9_]+:[0-9]+>"
    r"|[\U00010000-\U0010ffff]"
    r"|[\u2600-\u27bf]"
    r"|[\u2300-\u23ff]"
    r"|[\u2b50-\u2b55]"
    r")+"
)

# Optional letter/number prefix pattern (e.g. "A. ", "B) ", "1. ", "1) ")
OPTION_PREFIX_PATTERN = re.compile(r"^[A-Za-z0-9][\.\)\:\-]\s+")

# Keyword matching rules: (regex_pattern, emoji)
KEYWORD_RULES: list[tuple[str, str]] = [
    # Yes / No / Approvals
    (r"\b(yes|yeah|yep|agree|accept|có|co|ok)\b", "👍"),
    (r"\b(no|nope|nah|disagree|decline|không|khong|cancel)\b", "👎"),
    # Venues / Places
    (r"\b(home|house|apartment|nhà|nha)\b", "🏠"),
    (r"\b(restaurant|diner|buffet|quán ăn|quan an)\b", "🍽️"),
    (r"\b(bar|pub|brewery|beer garden|quán nhậu|quan nhau)\b", "🍻"),
    (r"\b(cafe|coffee|cà phê|ca phe)\b", "☕"),
    (r"\b(office|company|công ty|cong ty|workplace)\b", "🏢"),
    (r"\b(park|outdoor|ngoài trời|ngoai troi|picnic)\b", "🌳"),
    (r"\b(online|discord|zoom|virtual|google meet)\b", "💻"),
    # Food
    (r"\b(pizza)\b", "🍕"),
    (r"\b(bbq|grill|nướng|nuong|steak|meat)\b", "🥩"),
    (r"\b(hotpot|lẩu|lau|soup)\b", "🍲"),
    (r"\b(burger|fast food)\b", "🍔"),
    (r"\b(sushi|japanese|sashimi)\b", "🍣"),
    (r"\b(seafood|hải sản|hai san|fish|shrimp)\b", "🦞"),
    (r"\b(dessert|cake|bánh|banh|sweet|ice cream|chè|che)\b", "🍰"),
    # Drinks
    (r"\b(beer|bia)\b", "🍺"),
    (r"\b(wine|rượu|ruou)\b", "🍷"),
    (r"\b(cocktail)\b", "🍸"),
    (r"\b(tea|trà|tra|boba|milk tea)\b", "🧋"),
    # Activities / Entertainment
    (r"\b(game|boardgame|board game|play)\b", "🎲"),
    (r"\b(movie|film|cinema|rạp|rap)\b", "🎬"),
    (r"\b(karaoke|sing|hát|hat|music)\b", "🎤"),
    (r"\b(bowling)\b", "🎳"),
    (r"\b(gift|present|quà|qua|wrapping)\b", "🎁"),
    # Holiday / Theme
    (r"\b(santa|ông già noel|ong gia noel)\b", "🎅"),
    (r"\b(tree|cây thông|cay thong)\b", "🎄"),
    (r"\b(snow|snowflake|winter|lạnh|lanh)\b", "❄️"),
    (r"\b(party|celebrate|tiệc|tiec|festival)\b", "🎉"),
    # Days / Timing
    (r"\b(friday|thứ 6|thu 6)\b", "📅"),
    (r"\b(saturday|thứ 7|thu 7)\b", "🗓️"),
    (r"\b(sunday|chủ nhật|chu nhat)\b", "🌅"),
]


def clean_option_label(label: str) -> str:
    """Strip redundant prefixes like 'A. ' or '1) ' from option labels for clean display."""
    trimmed = label.strip()
    if len(trimmed) > 3 and OPTION_PREFIX_PATTERN.match(trimmed):
        return OPTION_PREFIX_PATTERN.sub("", trimmed).strip()
    return trimmed


def detect_poll_emojis(question: str, options: list[str]) -> tuple[list[str], list[str]]:
    """
    Detect the most appropriate reaction emojis and formatted labels for a poll.

    Resolution Strategy:
    1. If all options start with an emoji, extract and use each option's explicit emoji.
    2. If the poll is a 2-option Yes/No or Agree/Disagree question, use 👍 and 👎.
    3. If the poll is about Budget or all options are monetary values, use progressive money icons (🪙, 💵, 💰...).
    4. If each option matches a distinct contextual keyword (venue, food, activity), use those emojis.
    5. Fallback to clean Regional Indicator Alphabet letters (🇦, 🇧, 🇨, 🇩, 🇪...).

    Returns:
        (emojis, cleaned_labels)
    """
    raw_opts = [o.strip() for o in options if o.strip()]
    n = len(raw_opts)
    if n == 0:
        return [], []

    # 1. Check if all options explicitly start with an emoji
    lead_matches = [EMOJI_PATTERN.match(o) for o in raw_opts]
    if all(lead_matches):
        extracted_emojis = [m.group(0).strip() for m in lead_matches if m]
        # Ensure all extracted emojis are unique
        if len(set(extracted_emojis)) == n:
            cleaned_labels = [
                clean_option_label(o[len(m.group(0)) :].strip())
                for o, m in zip(raw_opts, lead_matches)
                if m
            ]
            return extracted_emojis, cleaned_labels

    cleaned_opts = [clean_option_label(o) for o in raw_opts]

    # 2. Check for Yes / No binary poll
    if n == 2:
        o1 = cleaned_opts[0].lower().strip()
        o2 = cleaned_opts[1].lower().strip()
        yes_words = {"yes", "yeah", "yep", "agree", "accept", "có", "co", "true", "ok", "join", "in"}
        no_words = {"no", "nope", "nah", "disagree", "decline", "không", "khong", "false", "cancel", "skip", "out"}

        if (o1 in yes_words and o2 in no_words) or (o1 in no_words and o2 in yes_words):
            emojis = ["👍", "👎"] if o1 in yes_words else ["👎", "👍"]
            return emojis, cleaned_opts

    # 3. Check for Budget / Price poll
    q_lower = question.lower()
    budget_kw = {"budget", "price", "ceiling", "cost", "limit", "tiền", "giá"}
    price_pattern = re.compile(r"[\$€£₫]|(\b\d+\s*(k|vnd|dong|đ)\b)", re.IGNORECASE)
    has_budget_question = any(k in q_lower for k in budget_kw)
    all_price_options = all(price_pattern.search(o) for o in cleaned_opts)

    if (has_budget_question or all_price_options) and n <= len(BUDGET_EMOJIS):
        return BUDGET_EMOJIS[:n], cleaned_opts

    # 4. Keyword matching per option (all options must match distinct keywords)
    def match_keyword_emoji(text: str) -> Optional[str]:
        for pattern, emoji in KEYWORD_RULES:
            if re.search(pattern, text, re.IGNORECASE):
                return emoji
        return None

    kw_emojis = [match_keyword_emoji(o) for o in cleaned_opts]
    if all(kw_emojis) and len(set(kw_emojis)) == n:
        return [e for e in kw_emojis if e is not None], cleaned_opts

    # 5. Default: Regional Indicator Alphabet (🇦, 🇧, 🇨, 🇩, ...)
    return ABC_EMOJIS[:n], cleaned_opts
