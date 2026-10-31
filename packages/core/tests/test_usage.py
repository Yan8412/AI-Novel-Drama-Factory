from drama_core import UsageMeter, UsageUnits, drain_engine_usage


def test_meter_drains_and_resets() -> None:
    meter = UsageMeter()
    meter.add_tokens(prompt=10, completion=5)
    meter.add_images(2)
    meter.add_video(8.5)
    meter.add_tts(12)
    units = meter.drain()
    assert units.tokens == 15
    assert units.images == 2
    assert units.video_seconds == 8.5
    assert units.tts_chars == 12
    assert units.source == "recorded"
    assert meter.tokens == 0
    empty = meter.drain()
    assert empty.has_values() is False


def test_drain_engine_usage_reads_client_shape() -> None:
    class _Client:
        def drain_usage(self) -> dict[str, int]:
            return {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}

    units = drain_engine_usage(_Client())
    assert units is not None
    assert units.tokens == 7
    assert drain_engine_usage(object()) is None


def test_units_normalized_tokens() -> None:
    assert UsageUnits(prompt_tokens=2, completion_tokens=3).normalized_tokens() == 5
    assert UsageUnits(tokens=9, prompt_tokens=2).normalized_tokens() == 9
