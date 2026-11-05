"""Unit tests for event branding and appearance customization."""

import pytest
import discord
from src.database.db import init_db
from src.database.repo import SantaRepository
from src.ui.embeds import (
    resolve_color,
    build_registration_embed,
    build_santa_dm_embed,
    build_prep_dashboard_embed,
    build_public_reminder_embed,
    build_milestone_reminder_embed,
    build_dm_reminder_embed,
)
from src.ui.modals import BrandingModal


@pytest.fixture
async def temp_repo(tmp_path):
    db_file = str(tmp_path / "test_branding.db")
    await init_db(db_file)
    return SantaRepository(db_file)


def test_resolve_color():
    assert resolve_color("RED") == discord.Color.red()
    assert resolve_color("green") == discord.Color.green()
    assert resolve_color("GOLD") == discord.Color.gold()
    assert resolve_color("blue") == discord.Color.blue()
    assert resolve_color("#FF5733") == discord.Color(0xFF5733)
    assert resolve_color("AABBCC") == discord.Color(0xAABBCC)
    assert resolve_color("invalid_color", default=discord.Color.teal()) == discord.Color.teal()
    assert resolve_color(None, default=discord.Color.purple()) == discord.Color.purple()


async def test_repo_branding_lifecycle(temp_repo):
    session_id = await temp_repo.create_session(guild_id=1001, channel_id=2001)
    session = await temp_repo.get_session_by_id(session_id)
    assert session is not None
    assert session.get("event_name") == "Buda Secret Santa"

    # Update branding details
    await temp_repo.update_session_details(
        session_id=session_id,
        event_name="Buda Winter Wonderland 2026",
        logo_url="https://example.com/logo.png",
        banner_url="https://example.com/banner.png",
        footer_text="Buda Winter Gala • Ho Ho Ho!",
        theme_color="#1ABC9C",
    )

    updated = await temp_repo.get_session_by_id(session_id)
    assert updated["event_name"] == "Buda Winter Wonderland 2026"
    assert updated["logo_url"] == "https://example.com/logo.png"
    assert updated["banner_url"] == "https://example.com/banner.png"
    assert updated["footer_text"] == "Buda Winter Gala • Ho Ho Ho!"
    assert updated["theme_color"] == "#1ABC9C"

    # Clear branding fields back to NULL
    await temp_repo.update_session_details(
        session_id=session_id,
        event_name=None,
        logo_url=None,
        banner_url=None,
        footer_text=None,
        theme_color=None,
    )
    cleared = await temp_repo.get_session_by_id(session_id)
    assert cleared["event_name"] is None
    assert cleared["logo_url"] is None
    assert cleared["banner_url"] is None
    assert cleared["footer_text"] is None
    assert cleared["theme_color"] is None


async def test_branding_modal_init(temp_repo):
    session_id = await temp_repo.create_session(guild_id=1001, channel_id=2001)
    await temp_repo.update_session_details(
        session_id=session_id,
        event_name="Corporate Holiday Bash",
        logo_url="https://img.com/logo.png",
        banner_url="https://img.com/banner.png",
        footer_text="Custom Footer 2026",
        theme_color="GOLD",
    )
    session = await temp_repo.get_session_by_id(session_id)
    modal = BrandingModal(repo=temp_repo, session=session)

    assert len(modal.children) == 5
    assert modal.event_name_input.default == "Corporate Holiday Bash"
    assert modal.logo_url_input.default == "https://img.com/logo.png"
    assert modal.banner_url_input.default == "https://img.com/banner.png"
    assert modal.footer_text_input.default == "Custom Footer 2026"
    assert modal.theme_color_input.default == "GOLD"


def test_embeds_with_branding():
    session = {
        "id": 1,
        "guild_id": 100,
        "channel_id": 200,
        "status": "REGISTRATION",
        "budget": "$30",
        "party_date": "Dec 25",
        "party_venue": "Sky Lounge",
        "event_name": "Custom Gala 2026",
        "logo_url": "https://example.com/icon.png",
        "banner_url": "https://example.com/banner.png",
        "footer_text": "Custom Gala Rules",
        "theme_color": "#E67E22",
    }
    participants = [{"display_name": "Alice", "username": "alice", "gift_status": "NOT_STARTED"}]

    # 1. Registration embed
    reg_embed = build_registration_embed(session, participants)
    assert "Custom Gala 2026" in reg_embed.title
    assert reg_embed.thumbnail.url == "https://example.com/icon.png"
    assert reg_embed.image.url == "https://example.com/banner.png"
    assert "Custom Gala Rules" in reg_embed.footer.text
    assert reg_embed.color == discord.Color(0xE67E22)

    # 2. Santa DM embed
    dm_embed = build_santa_dm_embed(
        baby_name="Bob",
        baby_username="bob",
        avatar_url=None,
        wishlist="Books",
        dislikes="Candy",
        offline_notes="Beer",
        gift_tag_code="POLAR-1",
        budget=session["budget"],
        party_date=session["party_date"],
        party_venue=session["party_venue"],
        event_name=session["event_name"],
        logo_url=session["logo_url"],
        footer_text=session["footer_text"],
        theme_color=session["theme_color"],
    )
    assert "Custom Gala 2026" in dm_embed.title
    assert dm_embed.author.name == "Custom Gala 2026"
    assert dm_embed.author.icon_url == "https://example.com/icon.png"
    assert "Custom Gala Rules" in dm_embed.footer.text
    assert dm_embed.color == discord.Color(0xE67E22)

    # 3. Preparation Dashboard embed
    prep_embed = build_prep_dashboard_embed(session, participants)
    assert "Custom Gala 2026" in prep_embed.title
    assert prep_embed.thumbnail.url == "https://example.com/icon.png"
    assert prep_embed.image.url == "https://example.com/banner.png"
    assert "Custom Gala Rules" in prep_embed.footer.text
    assert prep_embed.color == discord.Color(0xE67E22)

    # 4. Public Reminder embed (REGISTRATION)
    pub_embed = build_public_reminder_embed(session, participants)
    assert "Custom Gala 2026" in pub_embed.title
    assert pub_embed.thumbnail.url == "https://example.com/icon.png"
    assert pub_embed.image.url == "https://example.com/banner.png"
    assert "Custom Gala Rules" in pub_embed.footer.text
    assert pub_embed.color == discord.Color(0xE67E22)

    # 5. Milestone Reminder embed
    milestone_embed = build_milestone_reminder_embed(
        session, participants, "⚠️ 24 Hours Left!", discord.Color.orange()
    )
    assert "Custom Gala 2026" in milestone_embed.title
    assert milestone_embed.thumbnail.url == "https://example.com/icon.png"
    assert "Custom Gala Rules" in milestone_embed.footer.text

    # 6. Targeted DM Reminder embed
    dm_remind_embed = build_dm_reminder_embed(
        baby_name="Bob",
        gift_tag_code="POLAR-1",
        party_date=session["party_date"],
        party_venue=session["party_venue"],
        event_name=session["event_name"],
        logo_url=session["logo_url"],
        footer_text=session["footer_text"],
        theme_color=session["theme_color"],
    )
    assert "Custom Gala 2026" in dm_remind_embed.title
    assert dm_remind_embed.author.name == "Custom Gala 2026"
    assert dm_remind_embed.author.icon_url == "https://example.com/icon.png"
    assert "Custom Gala Rules" in dm_remind_embed.footer.text
    assert dm_remind_embed.color == discord.Color(0xE67E22)
