from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Tuple

import pygame

from src.ui import sfx
from src.ui import sfx
from src.utils import storage

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = PROJECT_ROOT / "assets"
BACKGROUND_DEFAULT = ASSETS_DIR / "background_menu.png"
LOGO_DEFAULT = ASSETS_DIR / "logo.png"
TARGET_RESOLUTION = (1280, 800)
ICON_DIR = ASSETS_DIR / "sprites" / "icons" / "32x32"
BUTTON_ICONS = {
    "Jogar": "joystick.png",
    "Opcoes": "gear.png",
    "Creditos": "credits.png",
    "Sair": "exit.png",
    "Janela": "window_compact_on.png",
    "Fullscreen": "fullscreen.png",
    "Voltar": "arrow_left.png",
}


class MenuAction(Enum):
    """Ações expostas para o restante do jogo."""

    PLAY = auto()
    QUIT = auto()


class MenuState(Enum):
    MAIN = auto()
    OPTIONS = auto()
    CREDITS = auto()


@dataclass
class MenuButton:
    label: str
    callback: Callable[[], None]
    rect: pygame.Rect | None = None
    selected: bool = False
    icon: pygame.Surface | None = None


class MenuScreen:
    """Menu principal com fundo responsivo e submenus de opções/créditos."""

    def __init__(
        self,
        surface: pygame.Surface,
        background_path: Path | None = None,
        logo_path: Path | None = None,
    ) -> None:
        self.surface = surface
        self.state = MenuState.MAIN
        self.fullscreen = False
        self._pending_action: MenuAction | None = None
        self._background = self._load_background(background_path or BACKGROUND_DEFAULT)
        self._background_scaled: pygame.Surface | None = None
        self._logo = self._load_logo(logo_path or LOGO_DEFAULT)
        self.font = pygame.font.Font(None, 34)
        self.title_font = pygame.font.Font(None, 64)
        self.small_font = pygame.font.Font(None, 26)
        self.buttons: List[MenuButton] = []
        self._icon_cache: Dict[str, pygame.Surface | None] = {}
        self._pending_close = False
        self._sounds = sfx.get_ui_sounds()
        self.music_muted = storage.get_music_muted()
        self._sounds.set_music_muted(self.music_muted)
        self.music_button_rect = pygame.Rect(0, 0, 46, 46)
        self._hovered_label: str | None = None
        self._scale_background()
        self._rebuild_buttons()

    def attach_surface(self, surface: pygame.Surface) -> None:
        self.surface = surface
        self._scale_background()
        self._rebuild_buttons()

    def go_to_state(self, state: MenuState) -> None:
        if state == MenuState.MAIN:
            self._show_main_menu()
        elif state == MenuState.OPTIONS:
            self._show_options()
        elif state == MenuState.CREDITS:
            self._show_credits()

    def consume_close_request(self) -> bool:
        pending = self._pending_close
        self._pending_close = False
        return pending

    def update(self, _dt: float) -> None:
        """Reservado para animações/sons futuros."""

    def draw(self) -> None:
        if self._background_scaled:
            self.surface.blit(self._background_scaled, (0, 0))
        else:
            self.surface.fill((16, 26, 46))

        self._draw_overlay()
        self._draw_logo_or_title()
        self._draw_music_toggle()

        if self.state == MenuState.OPTIONS:
            self._draw_options_text()
        elif self.state == MenuState.CREDITS:
            self._draw_credits_text()

        self._draw_buttons()

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.VIDEORESIZE and not self.fullscreen:
            self.surface = pygame.display.set_mode(event.size, pygame.RESIZABLE)
            self._scale_background()
            self._rebuild_buttons()
            return

        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.state != MenuState.MAIN:
                self._show_main_menu()
            else:
                self._queue_action(MenuAction.QUIT)
            return

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.music_button_rect.collidepoint(event.pos):
                self._toggle_music()
                return
            for button in self.buttons:
                if button.rect and button.rect.collidepoint(event.pos):
                    self._sounds.play_click()
                    button.callback()
                    break

    def consume_action(self) -> MenuAction | None:
        action = self._pending_action
        self._pending_action = None
        return action

    # internal helpers -----------------------------------------------------
    def _load_background(self, path: Path) -> pygame.Surface:
        if path.exists():
            return pygame.image.load(str(path)).convert()
        fallback = pygame.Surface(TARGET_RESOLUTION)
        fallback.fill((20, 32, 52))
        return fallback

    def _load_logo(self, path: Path) -> pygame.Surface | None:
        if path.exists():
            return pygame.image.load(str(path)).convert_alpha()
        return None

    def _scale_background(self) -> None:
        width, height = self.surface.get_size()
        if width <= 0 or height <= 0:
            return
        self._background_scaled = pygame.transform.smoothscale(
            self._background, (width, height)
        )

    def _rebuild_buttons(self) -> None:
        specs = list(self._current_button_specs())
        width = max(int(self.surface.get_width() * 0.27), 260)
        height = 58
        gap = 16
        total_height = len(specs) * height + max(len(specs) - 1, 0) * gap
        vertical_center = int(self.surface.get_height() * 0.55)
        start_y = vertical_center - total_height // 2
        start_y = max(start_y, int(self.surface.get_height() * 0.25))
        padding_left = max(int(self.surface.get_width() * 0.08), 48)
        start_x = padding_left
        rebuilt: List[MenuButton] = []
        for index, (label, callback, selected) in enumerate(specs):
            rect = pygame.Rect(start_x, start_y + index * (height + gap), width, height)
            icon = self._get_icon(label)
            rebuilt.append(MenuButton(label=label, callback=callback, rect=rect, selected=selected, icon=icon))
        self.buttons = rebuilt

    def _current_button_specs(self) -> Iterable[Tuple[str, Callable[[], None], bool]]:
        if self.state == MenuState.MAIN:
            return [
                ("Jogar", lambda: self._queue_action(MenuAction.PLAY), False),
                ("Opcoes", self._show_options, False),
                ("Creditos", self._show_credits, False),
                ("Sair", lambda: self._queue_action(MenuAction.QUIT), False),
            ]

        if self.state == MenuState.OPTIONS:
            return [
                ("Janela", lambda: self._set_display_mode(False), not self.fullscreen),
                ("Fullscreen", lambda: self._set_display_mode(True), self.fullscreen),
                ("Voltar", self._close_submenu, False),
            ]

        # Credits state
        return [
            ("Voltar", self._close_submenu, False),
        ]

    def _draw_overlay(self) -> None:
        overlay = pygame.Surface(self.surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 95))
        self.surface.blit(overlay, (0, 0))

    def _draw_music_toggle(self) -> None:
        rect = self.music_button_rect
        rect.topright = (self.surface.get_width() - 40, 28)
        mouse_pos = pygame.mouse.get_pos()
        hovered = rect.collidepoint(mouse_pos)
        base_color = (32, 47, 74)
        if hovered:
            base_color = (45, 66, 104)
        pygame.draw.rect(self.surface, base_color, rect, border_radius=10)
        pygame.draw.rect(self.surface, (255, 255, 255), rect, width=2, border_radius=10)
        icon = self._load_music_icon()
        if icon:
            icon_rect = icon.get_rect(center=rect.center)
            self.surface.blit(icon, icon_rect)
            if self.music_muted:
                pygame.draw.line(
                    self.surface,
                    (255, 80, 80),
                    (icon_rect.left + 2, icon_rect.bottom - 2),
                    (icon_rect.right - 2, icon_rect.top + 2),
                    width=3,
                )

    def _draw_logo_or_title(self) -> None:
        center_x = self._button_column_center()
        top_padding = int(self.surface.get_height() * 0.00001)
        if self._logo:
            max_width = max(int(self.surface.get_width() * 0.45), 1000)
            scale_ratio = min(max_width / self._logo.get_width(), 2.5)
            new_size = (
                max(int(self._logo.get_width() * scale_ratio), 1),
                max(int(self._logo.get_height() * scale_ratio), 1),
            )
            logo_scaled = pygame.transform.smoothscale(self._logo, new_size)
            rect = logo_scaled.get_rect(center=(center_x, top_padding + logo_scaled.get_height() // 2))
            self.surface.blit(logo_scaled, rect)
        else:
            title = self.title_font.render("Logitcity", True, (240, 240, 240))
            rect = title.get_rect(center=(center_x, top_padding + title.get_height() // 2))
            self.surface.blit(title, rect)

    def _draw_buttons(self) -> None:
        mouse_pos = pygame.mouse.get_pos()
        hovered_label = None
        for button in self.buttons:
            if not button.rect:
                continue
            hovered = button.rect.collidepoint(mouse_pos)
            base_color = (28, 51, 78)
            highlight_color = (255, 140, 66)
            outline_color = highlight_color if hovered or button.selected else (255, 255, 255)
            pygame.draw.rect(self.surface, base_color, button.rect, border_radius=10)
            pygame.draw.rect(self.surface, outline_color, button.rect, width=2, border_radius=10)
            text_color = highlight_color if hovered or button.selected else (230, 230, 230)
            label_surface = self.font.render(button.label, True, text_color)
            if button.icon:
                icon_rect = button.icon.get_rect()
                icon_rect.centery = button.rect.centery
                icon_rect.left = button.rect.x + 16
                self.surface.blit(button.icon, icon_rect)
                text_rect = label_surface.get_rect(midleft=(icon_rect.right + 12, button.rect.centery))
            else:
                text_rect = label_surface.get_rect(center=button.rect.center)
            self.surface.blit(label_surface, text_rect)
            if hovered:
                hovered_label = button.label
        if hovered_label and hovered_label != self._hovered_label:
            self._sounds.play_hover()
        self._hovered_label = hovered_label

    def _draw_options_text(self) -> None:
        text = ""
        info = self.small_font.render(text, True, (220, 220, 220))
        rect = info.get_rect(center=(self.surface.get_width() // 2, int(self.surface.get_height() * 0.38)))
        self.surface.blit(info, rect)

    def _draw_credits_text(self) -> None:
        lines = [
            "Creditos",
            "Desenvolvimento e arte: Davi Jorge",
            "Desenvolvimento: Gabriela Mattusack",
        ]
        for idx, line in enumerate(lines):
            font = self.title_font if idx == 0 else self.small_font
            color = (245, 245, 245) if idx == 0 else (220, 220, 220)
            surf = font.render(line, True, color)
            rect = surf.get_rect(center=(self.surface.get_width() // 2, int(self.surface.get_height() * 0.32) + idx * 36))
            self.surface.blit(surf, rect)

    def _show_main_menu(self) -> None:
        self.state = MenuState.MAIN
        self._rebuild_buttons()

    def _show_options(self) -> None:
        self.state = MenuState.OPTIONS
        self._rebuild_buttons()

    def _show_credits(self) -> None:
        self.state = MenuState.CREDITS
        self._rebuild_buttons()

    def _close_submenu(self) -> None:
        self._pending_close = True
        self._show_main_menu()

    def _set_display_mode(self, fullscreen: bool) -> None:
        if self.fullscreen == fullscreen:
            current_size = self.surface.get_size()
            desired = self._desktop_resolution() if fullscreen else TARGET_RESOLUTION
            if current_size == desired:
                return

        self.fullscreen = fullscreen
        if fullscreen:
            resolution = self._desktop_resolution()
            flags = pygame.FULLSCREEN
        else:
            resolution = TARGET_RESOLUTION
            flags = pygame.RESIZABLE

        self.surface = pygame.display.set_mode(resolution, flags)
        storage.update_config("fullscreen" if fullscreen else "window")
        self._scale_background()
        self._rebuild_buttons()

    def _queue_action(self, action: MenuAction) -> None:
        self._pending_action = action

    def _toggle_music(self) -> None:
        self.music_muted = self._sounds.toggle_mute()
        storage.set_music_muted(self.music_muted)

    def _desktop_resolution(self) -> Tuple[int, int]:
        info = pygame.display.Info()
        width = max(info.current_w, TARGET_RESOLUTION[0])
        height = max(info.current_h, TARGET_RESOLUTION[1])
        return width, height

    def _button_column_center(self) -> int:
        for button in self.buttons:
            if button.rect:
                return button.rect.x + button.rect.width // 2
        return int(self.surface.get_width() * 0.3)

    def _get_icon(self, label: str) -> pygame.Surface | None:
        key = BUTTON_ICONS.get(label)
        if not key:
            return None
        if key in self._icon_cache:
            return self._icon_cache[key]
        path = ICON_DIR / key
        surface = None
        if path.exists():
            try:
                surface = pygame.transform.smoothscale(pygame.image.load(str(path)).convert_alpha(), (28, 28))
            except pygame.error:
                surface = None
        self._icon_cache[key] = surface
        return surface

    def _load_music_icon(self) -> pygame.Surface | None:
        if hasattr(self, "_music_icon_surface"):
            return self._music_icon_surface
        path = ICON_DIR / "sound.png"
        icon = None
        if path.exists():
            try:
                icon = pygame.transform.smoothscale(pygame.image.load(str(path)).convert_alpha(), (26, 26))
            except pygame.error:
                icon = None
        self._music_icon_surface = icon
        return icon
