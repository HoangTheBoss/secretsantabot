"""Unit tests for config-driven branding, reverse proxy hostname, and built-in asset server."""

import pytest
import discord
import aiohttp
from pathlib import Path
from src.ui.embeds import (
    resolve_color,
    build_registration_embed,
    build_santa_dm_embed,
    build_prep_dashboard_embed,
    build_public_reminder_embed,
    build_milestone_reminder_embed,
    build_dm_reminder_embed,
)
from src.config import (
    get_base_url,
    resolve_asset_url,
    EVENT_NAME,
    FOOTER_TEXT,
)
from src.services.asset_server import AssetServer


def test_resolve_color():
    assert resolve_color("RED") == discord.Color.red()
    assert resolve_color("green") == discord.Color.green()
    assert resolve_color("GOLD") == discord.Color.gold()
    assert resolve_color("blue") == discord.Color.blue()
    assert resolve_color("#FF5733") == discord.Color(0xFF5733)
    assert resolve_color("AABBCC") == discord.Color(0xAABBCC)
    assert resolve_color("invalid_color", default=discord.Color.teal()) == discord.Color.teal()
    assert resolve_color(None, default=discord.Color.purple()) == discord.Color.purple()


def test_hostname_and_asset_url_resolution(monkeypatch):
    # 1. Custom PUBLIC_URL
    monkeypatch.setattr("src.config.PUBLIC_URL", "https://santa.myparty.org/")
    monkeypatch.setattr("src.config.PUBLIC_HOSTNAME", "")
    assert get_base_url() == "https://santa.myparty.org"
    assert resolve_asset_url("logo.png") == "https://santa.myparty.org/assets/logo.png"

    # 2. Reverse proxy hostname without protocol (should default to https)
    monkeypatch.setattr("src.config.PUBLIC_URL", "")
    monkeypatch.setattr("src.config.PUBLIC_HOSTNAME", "secretsanta.internal.net")
    assert get_base_url() == "https://secretsanta.internal.net"
    assert resolve_asset_url("/banner.png") == "https://secretsanta.internal.net/assets/banner.png"

    # 3. Direct external URL should be preserved untouched
    external = "https://cdn.discordapp.com/attachments/123/456/party.png"
    assert resolve_asset_url(external) == external

    # 4. Fallback to localhost
    monkeypatch.setattr("src.config.PUBLIC_URL", "")
    monkeypatch.setattr("src.config.PUBLIC_HOSTNAME", "")
    monkeypatch.setattr("src.config.HTTP_PORT", 9090)
    assert get_base_url() == "http://localhost:9090"
    assert resolve_asset_url("tree.png") == "http://localhost:9090/assets/tree.png"


async def test_asset_server_lifecycle_and_static_serving(tmp_path):
    # Create test assets
    test_assets = tmp_path / "assets"
    test_assets.mkdir()
    (test_assets / "test_logo.png").write_bytes(b"\x89PNG\r\n\x1a\nfakeimage")

    server = AssetServer(
        host="127.0.0.1",
        port=8912,
        assets_dir=test_assets,
        event_name="Test Santa",
        public_url="http://127.0.0.1:8912",
    )

    await server.start()

    try:
        async with aiohttp.ClientSession() as session:
            # 1. Health check
            async with session.get("http://127.0.0.1:8912/health") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["status"] == "ok"
                assert data["event_name"] == "Test Santa"

            # 2. Index info
            async with session.get("http://127.0.0.1:8912/") as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["status"] == "online"

            # 3. Static asset serving
            async with session.get("http://127.0.0.1:8912/assets/test_logo.png") as resp:
                assert resp.status == 200
                content = await resp.read()
                assert content == b"\x89PNG\r\n\x1a\nfakeimage"

            # 4. 404 for nonexistent asset
            async with session.get("http://127.0.0.1:8912/assets/missing.png") as resp:
                assert resp.status == 404
    finally:
        await server.stop()


def test_embeds_with_config_branding():
    session = {
        "id": 1,
        "guild_id": 100,
        "channel_id": 200,
        "status": "REGISTRATION",
        "budget": "$30",
        "party_date": "Dec 25",
        "party_venue": "Sky Lounge",
    }
    participants = [{"display_name": "Alice", "username": "alice", "gift_status": "NOT_STARTED"}]

    # 1. Registration embed
    reg_embed = build_registration_embed(session, participants)
    assert EVENT_NAME in reg_embed.title
    assert FOOTER_TEXT in reg_embed.footer.text

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
    )
    assert EVENT_NAME in dm_embed.title
    assert dm_embed.author.name == EVENT_NAME
    assert FOOTER_TEXT in dm_embed.footer.text

    # 3. Preparation Dashboard embed
    prep_embed = build_prep_dashboard_embed(session, participants)
    assert EVENT_NAME in prep_embed.title
    assert FOOTER_TEXT in prep_embed.footer.text

    # 4. Public Reminder embed (REGISTRATION)
    pub_embed = build_public_reminder_embed(session, participants)
    assert EVENT_NAME in pub_embed.title
    assert FOOTER_TEXT in pub_embed.footer.text

    # 5. Milestone Reminder embed
    milestone_embed = build_milestone_reminder_embed(
        session, participants, "⚠️ 24 Hours Left!", discord.Color.orange()
    )
    assert EVENT_NAME in milestone_embed.title
    assert FOOTER_TEXT in milestone_embed.footer.text

    # 6. Targeted DM Reminder embed
    dm_remind_embed = build_dm_reminder_embed(
        baby_name="Bob",
        gift_tag_code="POLAR-1",
        party_date=session["party_date"],
        party_venue=session["party_venue"],
    )
    assert EVENT_NAME in dm_remind_embed.title
    assert dm_remind_embed.author.name == EVENT_NAME
    assert FOOTER_TEXT in dm_remind_embed.footer.text
