from __future__ import annotations

from pathlib import Path

import pygame

ASSETS_DIR = Path(__file__).resolve().parents[2] / "assets"
HOVER_SOUND = ASSETS_DIR / "sounds" / "UI Soundpack" / "MP3" / "Abstract1.mp3"
CLICK_SOUND = ASSETS_DIR / "sounds" / "UI Soundpack" / "MP3" / "Abstract2.mp3"
BOX_MOVE_SOUND = ASSETS_DIR / "sounds" / "Retro FootStep 03.wav"
DELIVERY_SOUND = ASSETS_DIR / "sounds" / "UI Soundpack" / "MP3" / "Modern7.mp3"
POINT_SOUND = ASSETS_DIR / "sounds" / "Retro PickUp Coin 07.wav"
MUSIC_FILES = [
    ASSETS_DIR / "sounds" / "music-loop-bundle-troubadeck" / "Troubadeck 01 A Simple Snail.ogg",
    ASSETS_DIR / "sounds" / "music-loop-bundle-troubadeck" / "Troubadeck 02 Leapfrogs.ogg",
    ASSETS_DIR / "sounds" / "music-loop-bundle-troubadeck" / "Troubadeck 03 Frolicking.ogg",
]

_INSTANCE: "UISounds | None" = None


class UISounds:
    def __init__(self) -> None:
        self._ensure_mixer()
        self.hover = self._load(HOVER_SOUND)
        self.click = self._load(CLICK_SOUND)
        self.move = self._load(BOX_MOVE_SOUND)
        self.delivery = self._load(DELIVERY_SOUND)
        self.point = self._load(POINT_SOUND)
        self.music_tracks = [str(path) for path in MUSIC_FILES if path.exists()]
        self.music_index = 0
        self.music_muted = False
        if self.music_tracks:
            try:
                pygame.mixer.music.load(self.music_tracks[0])
                pygame.mixer.music.play(-1)
            except pygame.error:
                self.music_tracks = []

    def _ensure_mixer(self) -> None:
        if not pygame.mixer.get_init():
            try:
                pygame.mixer.init()
            except pygame.error:
                pass

    def _load(self, path: Path) -> pygame.mixer.Sound | None:
        if not path.exists():
            return None
        try:
            return pygame.mixer.Sound(str(path))
        except pygame.error:
            return None

    def play_hover(self) -> None:
        if self.hover:
            self.hover.play()

    def play_click(self) -> None:
        if self.click:
            self.click.play()

    def play_move(self) -> None:
        if self.move:
            self.move.play()

    def play_delivery(self) -> None:
        if self.delivery:
            self.delivery.play()

    def play_point(self) -> None:
        if self.point:
            self.point.play()

    def toggle_mute(self) -> bool:
        self.set_music_muted(not self.music_muted)
        return self.music_muted

    def set_music_muted(self, muted: bool) -> None:
        self.music_muted = muted
        if pygame.mixer.get_init():
            pygame.mixer.music.set_volume(0.0 if muted else 1.0)

    def next_track(self) -> None:
        if not self.music_tracks:
            return
        self.music_index = (self.music_index + 1) % len(self.music_tracks)
        try:
            pygame.mixer.music.load(self.music_tracks[self.music_index])
            pygame.mixer.music.play(-1)
            if self.music_muted:
                pygame.mixer.music.set_volume(0.0)
        except pygame.error:
            pass

    def current_track_name(self) -> str | None:
        if not self.music_tracks:
            return None
        return Path(self.music_tracks[self.music_index]).stem


def get_ui_sounds() -> UISounds:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = UISounds()
    return _INSTANCE
