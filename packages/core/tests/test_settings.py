from drama_core import Settings


def test_from_env_reads_llm_fields() -> None:
    s = Settings.from_env(
        {
            "NOVEL_ENGINE": "cloud",
            "REVIEW_ENGINE": "llm_judge",
            "OPENAI_API_KEY": "sk-test",
            "OPENAI_BASE_URL": "https://example.test/v1",
            "NOVEL_MODEL": "novel-x",
            "REVIEW_MODEL": "judge-x",
            "STORYBOARD_ENGINE": "structured",
            "VISION_ENGINE": "cloud",
            "STORYBOARD_MODEL": "sb-x",
            "VISION_MODEL": "img-x",
            "VIDEO_ENGINE": "cloud",
            "VIDEO_MODEL": "sora-2",
            "VIDEO_API_KEY": "sk-video",
            "VIDEO_BASE_URL": "https://i2v.test/v1",
            "ASSEMBLE_ENGINE": "ffmpeg",
            "TTS_ENGINE": "openai",
            "SUBTITLE_FORMAT": "srt",
            "REVIEW_MAX_RETRIES": "4",
            "REVIEW_OVERRIDE": "pass",
            "REDIS_URL": "redis://127.0.0.1:6379/1",
            "JOB_QUEUE": "auto",
            "PRICE_TOKEN_PER_1K_USD": "0.002",
            "PRICE_IMAGE_USD": "0.08",
            "QUOTA_CURRENCY": "CNY",
            "QUOTA_SOFT_USD": "1.5",
            "QUOTA_MAX_USD": "9",
        }
    )
    assert s.novel_engine == "cloud"
    assert s.review_engine == "llm_judge"
    assert s.openai_api_key == "sk-test"
    assert s.openai_base_url == "https://example.test/v1"
    assert s.novel_model == "novel-x"
    assert s.review_model == "judge-x"
    assert s.storyboard_engine == "structured"
    assert s.vision_engine == "cloud"
    assert s.storyboard_model == "sb-x"
    assert s.vision_model == "img-x"
    assert s.video_engine == "cloud"
    assert s.video_model == "sora-2"
    assert s.video_api_key == "sk-video"
    assert s.video_base_url == "https://i2v.test/v1"
    assert s.assemble_engine == "ffmpeg"
    assert s.tts_engine == "openai"
    assert s.subtitle_format == "srt"
    assert s.review_max_attempts == 4
    assert s.review_override == "pass"
    assert s.tts_api_key == "sk-test"
    assert s.redis_url == "redis://127.0.0.1:6379/1"
    assert s.job_queue == "auto"
    assert s.price_token_per_1k_usd == 0.002
    assert s.price_image_usd == 0.08
    assert s.quota_currency == "CNY"
    assert s.quota_soft_usd == 1.5
    assert s.quota_max_usd == 9.0


def test_defaults_stay_mock_and_offline() -> None:
    s = Settings()
    assert s.novel_engine == "mock"
    assert s.review_engine == "mock"
    assert s.storyboard_engine == "mock"
    assert s.vision_engine == "mock"
    assert s.video_engine == "mock"
    assert s.assemble_engine == "mock"
    assert s.tts_engine == "mock"
    assert s.openai_api_key == ""
    assert s.video_api_key == ""
    assert s.job_queue == "auto"
    assert s.redis_url == "redis://127.0.0.1:6379/0"
    assert s.quota_max_usd is None
    assert s.price_token_per_1k_usd == 0.00015


def test_kling_api_key_fills_video_key() -> None:
    s = Settings.from_env({"VIDEO_ENGINE": "cloud:kling", "KLING_API_KEY": "kling-secret"})
    assert s.video_engine == "cloud:kling"
    assert s.video_api_key == "kling-secret"
