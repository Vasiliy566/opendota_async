"""Pydantic models for OpenDota JSON payloads."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OpenDotaModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class PlayerProfile(OpenDotaModel):
    account_id: int | None = None
    personaname: str | None = None
    name: str | None = None
    plus: bool | None = None
    cheese: int | None = None
    steamid: str | None = None
    avatar: str | None = None
    avatarmedium: str | None = None
    avatarfull: str | None = None
    profileurl: str | None = None
    last_login: str | None = None
    loccountrycode: str | None = None
    is_contributor: bool = False
    is_subscriber: bool = False


class PlayerAlias(OpenDotaModel):
    personaname: str | None = None
    name_since: str | None = None


class PlayerData(OpenDotaModel):
    """Response from ``GET /players/{account_id}``."""

    rank_tier: float | None = None
    leaderboard_rank: float | None = None
    computed_mmr: float | None = None
    computed_mmr_turbo: int | None = None
    aliases: list[PlayerAlias] = Field(default_factory=list)
    profile: PlayerProfile | None = None


class PlayerWinLoss(OpenDotaModel):
    win: int = 0
    lose: int = 0


class PlayerRecentMatch(OpenDotaModel):
    match_id: int
    player_slot: int | None = None
    radiant_win: bool | None = None
    duration: int | None = None
    game_mode: int | None = None
    lobby_type: int | None = None
    hero_id: int | None = None
    start_time: int | None = None
    version: int | None = None
    kills: int | None = None
    deaths: int | None = None
    assists: int | None = None
    skill: int | None = None
    average_rank: int | None = None
    xp_per_min: int | None = None
    gold_per_min: int | None = None
    hero_damage: int | None = None
    hero_healing: int | None = None
    last_hits: int | None = None
    lane: int | None = None
    lane_role: int | None = None
    is_roaming: bool | None = None
    cluster: int | None = None
    leaver_status: int | None = None
    party_size: int | None = None
    hero_variant: int | None = None


class PlayerMatch(OpenDotaModel):
    match_id: int
    player_slot: int | None = None
    radiant_win: bool | None = None
    duration: int | None = None
    game_mode: int | None = None
    lobby_type: int | None = None
    hero_id: int | None = None
    start_time: int | None = None
    version: int | None = None
    kills: int | None = None
    deaths: int | None = None
    assists: int | None = None
    skill: int | None = None
    average_rank: int | None = None
    leaver_status: int | None = None
    party_size: int | None = None
    hero_variant: int | None = None


class MatchData(OpenDotaModel):
    """Parsed match payload (subset; unknown fields preserved via ``extra``)."""

    match_id: int | None = None
    duration: int | None = None
    start_time: int | None = None
    radiant_win: bool | None = None
    players: list[dict[str, Any]] = Field(default_factory=list)


class RefreshResult(OpenDotaModel):
    """POST /players/{id}/refresh may return an empty object."""
