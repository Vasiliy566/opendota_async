from opendota_async.models import PlayerData


def test_player_data_extra_fields() -> None:
    raw = {
        "profile": {"account_id": 1, "personaname": "x"},
        "rank_tier": 80,
        "extra_future_field": 123,
    }
    p = PlayerData.model_validate(raw)
    assert p.rank_tier == 80
    assert getattr(p, "extra_future_field", None) == 123
