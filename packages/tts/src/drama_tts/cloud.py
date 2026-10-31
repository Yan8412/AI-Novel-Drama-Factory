"""Optional OpenAI-compatible TTS. Never required for demo / CI."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import httpx
from drama_core import Project, Settings, Shot, missing_credential_text

from drama_tts.cues import cue_text
from drama_tts.mock import MockTtsEngine


class TtsError(RuntimeError):
    pass


class CloudTtsEngine:
    """POST {base}/audio/speech. Falls back to mock sidecars if the call fails.

    Paid path is opt-in via ``TTS_ENGINE=openai``. No secrets live in the repo.
    """

    name = "openai-tts"

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self._client = client

    def synthesize(
        self,
        project: Project,
        shots: Sequence[Shot],
        *,
        out_dir: Path,
    ) -> list[Path]:
        key = self.settings.tts_api_key or self.settings.openai_api_key
        if not key:
            raise TtsError(
                missing_credential_text("TTS_ENGINE=openai", "TTS_API_KEY", "OPENAI_API_KEY")
            )
        base = (self.settings.tts_base_url or self.settings.openai_base_url).rstrip("/")
        folder = out_dir / "episode" / "tts"
        folder.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        client = self._client or httpx.Client(timeout=60.0)
        owns = self._client is None
        try:
            for shot in shots:
                text = cue_text(project, shot)
                if not text:
                    continue
                voice = self._voice_for(project, shot)
                try:
                    response = client.post(
                        f"{base}/audio/speech",
                        headers={"Authorization": f"Bearer {key}"},
                        json={
                            "model": self.settings.tts_model,
                            "voice": voice,
                            "input": text,
                        },
                    )
                    response.raise_for_status()
                    chapter = next(
                        (c.index for c in project.chapters if c.id == shot.chapter_id), 0
                    )
                    path = folder / f"shot_{chapter:03d}_{shot.index:03d}.mp3"
                    path.write_bytes(response.content)
                    written.append(path)
                except (httpx.HTTPError, OSError):
                    # Paid TTS must never block the export path.
                    continue
        finally:
            if owns:
                client.close()
        if written:
            return written
        return MockTtsEngine().synthesize(project, shots, out_dir=out_dir)

    def _voice_for(self, project: Project, shot: Shot) -> str:
        for char in project.characters:
            if char.id in shot.character_ids and char.voice.tts_voice_id:
                return char.voice.tts_voice_id
        return self.settings.tts_voice
