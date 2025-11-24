from __future__ import annotations

import sys
from enum import Enum, auto
from pathlib import Path

import pygame

from src.game.mode_padrao import StandardModeGame
from src.ui.gameplay import GameplayScreen
from src.ui.menu import MenuAction, MenuScreen, MenuState, TARGET_RESOLUTION

WINDOW_TITLE = "Logitcity"
ICON_CANDIDATES: tuple[Path, ...] = (
    Path("assets/icon.png"),
)


def _configure_window() -> pygame.Surface:
    screen = pygame.display.set_mode(TARGET_RESOLUTION, pygame.RESIZABLE)
    pygame.display.set_caption(WINDOW_TITLE)
    icon = _load_window_icon()
    if icon:
        pygame.display.set_icon(icon)
    return screen


def _load_window_icon() -> pygame.Surface | None:
    for icon_path in ICON_CANDIDATES:
        if not icon_path.exists():
            continue
        try:
            icon_surface = pygame.image.load(str(icon_path)).convert_alpha()
        except pygame.error:
            continue

        max_dim = 128
        width, height = icon_surface.get_size()
        scale_ratio = min(max_dim / width, max_dim / height, 1.0)
        if scale_ratio < 1.0:
            new_size = (
                max(int(width * scale_ratio), 1),
                max(int(height * scale_ratio), 1),
            )
            icon_surface = pygame.transform.smoothscale(icon_surface, new_size)
        return icon_surface
    return None


def main() -> None:
    pygame.init()
    pygame.font.init()
    screen = _configure_window()
    clock = pygame.time.Clock()
    menu = MenuScreen(screen)
    game_logic = StandardModeGame()
    gameplay = GameplayScreen(screen, game_logic)

    class View(Enum):
        MENU = auto()
        GAMEPLAY = auto()

    current_view = View.MENU
    menu_return_view: View | None = None
    running = True

    while running:
        dt = clock.tick(60) / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break
            if current_view is View.MENU:
                menu.handle_event(event)
            else:
                gameplay.handle_event(event)

        if not running:
            break

        if current_view is View.MENU:
            menu.update(dt)
            menu.draw()
            pygame.display.flip()
            screen = menu.surface
            if menu_return_view is View.GAMEPLAY and menu.consume_close_request():
                gameplay.attach_surface(pygame.display.get_surface())
                gameplay.paused = True
                game_logic.active = True
                current_view = View.GAMEPLAY
                menu_return_view = None
                continue
            action = menu.consume_action()
            if action is MenuAction.PLAY:
                gameplay.attach_surface(pygame.display.get_surface())
                gameplay.start()
                current_view = View.GAMEPLAY
                menu_return_view = None
            elif action is MenuAction.QUIT:
                running = False
        else:
            gameplay.update(dt)
            gameplay.draw()
            pygame.display.flip()
            screen = gameplay.surface
            menu_request, menu_state = gameplay.consume_menu_request()
            if menu_request:
                menu.attach_surface(pygame.display.get_surface())
                if menu_state:
                    menu.go_to_state(menu_state)
                menu_return_view = View.GAMEPLAY if menu_state == MenuState.OPTIONS else None
                current_view = View.MENU

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
