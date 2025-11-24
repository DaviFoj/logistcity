from __future__ import annotations

import math
import random
from dataclasses import dataclass
from pathlib import Path
import time
from typing import Dict, List, Optional, Sequence, Tuple

import pygame

from src.algorithms import sorting
from src.game.mode_padrao import Batch, DeliveryOutcome, StandardModeGame
from src.ui import sfx
from src.ui.menu import MenuState
from src.utils import storage

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = PROJECT_ROOT / "assets"
BACKGROUND_DEFAULT = ASSETS_DIR / "background_menu.png"
BOX_SPRITES_DIR = ASSETS_DIR / "sprites" / "cardboard"
SMALL_TRUCK_FULL = ASSETS_DIR / "sprites" / "small_truck_full.png"
SMALL_TRUCK_EMPTY = ASSETS_DIR / "sprites" / "small_truck_empty.png"
BIG_TRUCK_FULL = ASSETS_DIR / "sprites" / "big_truck_full.png"
BIG_TRUCK_EMPTY = ASSETS_DIR / "sprites" / "big_truck_empty.png"
ICON_DIR = ASSETS_DIR / "sprites" / "icons" / "32x32"

DISPLAY_LABELS = {
    "bubble": "Bubble Sort",
    "selection": "Selection Sort",
    "insertion": "Insertion Sort",
    "quick": "Quick Sort",
}
ALGORITHM_INFO = {
    "bubble": "Compara pares adjacentes e troca ate que nenhuma troca seja necessária.",
    "selection": "Busca a menor caixa restante e troca com a posicao atual.",
    "insertion": "Percorre a fila inserindo cada caixa no ponto correto.",
    "quick": "Escolhe um pivo, particiona menores/maiores e repete o processo.",
}
PAUSE_BUTTON_ICONS = {
    "resume": "arrow_play.png",
    "options": "gear.png",
    "quit": "exit.png",
}


@dataclass
class AlgorithmCard:
    algorithm: str
    display_name: str
    rect: pygame.Rect


@dataclass
class BoxVisual:
    index: int
    value: int
    surface: pygame.Surface
    rect: pygame.Rect


@dataclass
class SortingAnimation:
    steps: List[sorting.SortStep]
    algorithm: str
    result: sorting.SortingResult
    batch_id: int
    current_step: int = 0
    timer: float = 0.0
    interval: float = 0.35
    cooldown: float = 0.8
    phase: str = "running"


class GameplayScreen:
    """Tela do modo padrao com HUD, visualizacao das caixas e cards dos algoritmos."""

    def __init__(self, surface: pygame.Surface, game: StandardModeGame) -> None:
        self.surface = surface
        self.game = game
        self.font = pygame.font.Font(None, 32)
        self.big_font = pygame.font.Font(None, 46)
        self.small_font = pygame.font.Font(None, 24)
        self.box_font = pygame.font.Font(None, 24)
        self.background = self._load_background()
        self.background_scaled: pygame.Surface | None = None
        self.cards: List[AlgorithmCard] = []
        self.last_message = "Selecione um algoritmo para ordenar o lote."
        self._request_menu = False
        self._finished_notified = False
        self._scale_background()
        self._layout_cards()

        self.random = random.Random()
        self.box_textures = self._load_box_sprites()
        self.truck_images = {
            "small": {
                "empty": self._load_image(SMALL_TRUCK_EMPTY, (220, 140)),
                "full": self._load_image(SMALL_TRUCK_FULL, (220, 140)),
            },
            "big": {
                "empty": self._load_image(BIG_TRUCK_EMPTY, (260, 150)),
                "full": self._load_image(BIG_TRUCK_FULL, (260, 150)),
            },
        }
        self.current_truck_key = "small"
        self.truck_loaded = False
        self.current_truck: Optional[pygame.Surface] = None
        self.truck_rect = pygame.Rect(0, 0, 0, 0)
        self._refresh_truck_surface()

        self.boxes: List[BoxVisual] = []
        self.box_lookup: Dict[int, BoxVisual] = {}
        self.highlight_positions: Tuple[int, ...] | None = None
        self.animation: Optional[SortingAnimation] = None
        self.paused: bool = False
        self.pause_button_rect = pygame.Rect(0, 0, 48, 48)
        self.pause_icon = self._load_pause_icon()
        self.pause_menu_buttons: Dict[str, pygame.Rect] = {}
        self._requested_menu_state: MenuState | None = None
        self.pause_icons: Dict[str, pygame.Surface | None] = {
            key: self._load_ui_icon(filename, (24, 24))
            for key, filename in PAUSE_BUTTON_ICONS.items()
        }
        self.show_results: bool = False
        self.result_summary: Dict[str, any] | None = None
        self.results_buttons: Dict[str, pygame.Rect] = {}
        self.sounds = sfx.get_ui_sounds()
        self._hovered_card: str | None = None
        self._pause_button_hover = False
        self._hovered_pause_menu_button: str | None = None
        self._hovered_results_button: str | None = None
        self._last_move_sound = 0
        self._move_sound_cooldown = 70  # milliseconds

    # Lifecycle ----------------------------------------------------------------
    def attach_surface(self, surface: pygame.Surface) -> None:
        self.surface = surface
        self._scale_background()
        self._layout_cards()
        self._position_boxes()

    def start(self) -> None:
        self.game.start()
        self.last_message = "Selecione um algoritmo para ordenar o lote."
        self._request_menu = False
        self._finished_notified = False
        self.animation = None
        self.highlight_positions = None
        self.paused = False
        self.pause_menu_buttons.clear()
        self.show_results = False
        self.result_summary = None
        storage.set_current_run(
            {
                "start_time": time.time(),
                "duration_seconds": self.game.duration_seconds,
                "deliveries": 0,
                "items": 0,
                "best_algorithm": None,
            }
        )
        if self.game.current_batch:
            self._apply_new_batch(self.game.current_batch)
        else:
            self.boxes = []
            self.box_lookup.clear()

    def update(self, delta_seconds: float) -> None:
        if self.game.active and not (self.paused or self.show_results):
            self.game.update(delta_seconds)
            if not self.game.active and not self._finished_notified:
                self.last_message = "Tempo esgotado! Pressione ESC para voltar ao menu."
                self._finished_notified = True
        self._update_animation(delta_seconds)
        if not self.game.active and not self.show_results and not self.paused and not self.animation:
            self.show_results = True
            self.result_summary = self.game.build_summary()
            storage.complete_run(self.result_summary)

    def handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.VIDEORESIZE:
            self.attach_surface(pygame.display.set_mode(event.size, pygame.RESIZABLE))
            return
        if self.show_results:
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self._handle_results_modal_click(event.pos)
            return
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.paused:
                self.paused = False
            elif self.game.active:
                self.sounds.play_click()
                self.paused = True
            else:
                self._requested_menu_state = MenuState.MAIN
                self._request_menu = True
            return
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._pause_button_hit(event.pos):
                self.sounds.play_click()
                self.paused = not self.paused
                return
            if self.paused:
                self._handle_pause_modal_click(event.pos)
                return
            self._handle_click(event.pos)

    def draw(self) -> None:
        if self.show_results:
            self._draw_results_screen()
            return
        self._draw_background()
        self._draw_overlay()
        self._draw_header()
        self._draw_hud()
        self._draw_pause_button()
        self._draw_playfield()
        self._draw_cards()
        self._draw_message()
        if self.paused:
            self._draw_pause_modal()
        else:
            self.pause_menu_buttons.clear()

    def consume_menu_request(self) -> Tuple[bool, Optional[MenuState]]:
        requested = self._request_menu
        target = self._requested_menu_state
        self._request_menu = False
        self._requested_menu_state = None
        return requested, target

    # Drawing helpers ----------------------------------------------------------
    def _draw_background(self) -> None:
        if self.background_scaled:
            self.surface.blit(self.background_scaled, (0, 0))
        else:
            self.surface.fill((12, 20, 32))

    def _draw_overlay(self) -> None:
        overlay = pygame.Surface(self.surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.surface.blit(overlay, (0, 0))

    def _draw_header(self) -> None:
        timer_text = self._format_timer(self.game.remaining_time)
        header = self.big_font.render(f"Modo Padrao - Tempo: {timer_text}", True, (255, 255, 255))
        rect = header.get_rect(midtop=(self.surface.get_width() // 2, 20))
        self.surface.blit(header, rect)

    def _draw_hud(self) -> None:
        hud = self.game.hud_data()
        lines = [
            f"Entregas: {hud['entregas']}",
            f"Itens organizados: {hud['itens_organizados']}",
        ]
        last_exec = hud["ultima_execucao_ms"]
        if last_exec is not None:
            lines.append(f"Ultima ordenacao: {last_exec:.2f} ms")
        else:
            lines.append("Ultima ordenacao: -")
        x = 40
        y = 90
        for line in lines:
            text = self.font.render(line, True, (240, 240, 240))
            self.surface.blit(text, (x, y))
            y += text.get_height() + 8

    def _draw_pause_button(self) -> None:
        size = 46
        rect = pygame.Rect(0, 0, size, size)
        rect.topleft = (40, 32)
        self.pause_button_rect = rect
        mouse_pos = pygame.mouse.get_pos()
        hovered = rect.collidepoint(mouse_pos)
        base_color = (32, 47, 74)
        if self.paused:
            base_color = (70, 55, 80)
        elif hovered:
            base_color = (45, 66, 104)
        pygame.draw.rect(self.surface, base_color, rect, border_radius=10)
        pygame.draw.rect(self.surface, (255, 255, 255), rect, width=2, border_radius=10)
        if self.pause_icon:
            icon_rect = self.pause_icon.get_rect(center=rect.center)
            self.surface.blit(self.pause_icon, icon_rect)
        else:
            bar_width = 6
            gap = 8
            bar_height = rect.height - 16
            x = rect.x + (rect.width - (2 * bar_width + gap)) // 2
            y = rect.y + (rect.height - bar_height) // 2
            pygame.draw.rect(self.surface, (255, 255, 255), (x, y, bar_width, bar_height))
            pygame.draw.rect(self.surface, (255, 255, 255), (x + bar_width + gap, y, bar_width, bar_height))
        if hovered and not self._pause_button_hover:
            self.sounds.play_hover()
        self._pause_button_hover = hovered

    def _draw_playfield(self) -> None:
        area = self._box_area()
        pygame.draw.rect(self.surface, (18, 30, 52), area, border_radius=14)
        pygame.draw.rect(self.surface, (255, 255, 255), area, width=2, border_radius=14)
        title_text = "Lote atual" if self.game.current_batch else "Sem lotes"
        title = self.font.render(title_text, True, (255, 200, 120))
        self.surface.blit(title, (area.x + 16, area.y + 10))
        self._draw_boxes()
        self._draw_truck()

    def _draw_boxes(self) -> None:
        for idx, box in enumerate(self.boxes):
            self.surface.blit(box.surface, box.rect)
            label = self.box_font.render(str(box.value), True, (255, 255, 255))
            label_rect = label.get_rect(center=(box.rect.centerx, box.rect.y - 10))
            self.surface.blit(label, label_rect)
        if self.highlight_positions:
            for pos in self.highlight_positions:
                if 0 <= pos < len(self.boxes):
                    rect = self.boxes[pos].rect.inflate(8, 8)
                    pygame.draw.rect(self.surface, (255, 215, 0), rect, width=3, border_radius=6)

    def _draw_truck(self) -> None:
        if not self.current_truck:
            return
        truck = self.current_truck
        rect = truck.get_rect()
        area = self._box_area()
        rect.midbottom = (area.centerx, area.top - 20)
        min_top = 100
        screen_rect = self.surface.get_rect()
        if rect.top < min_top:
            rect.top = min_top
        if rect.bottom > area.top - 8:
            rect.bottom = area.top - 8
        if rect.left < screen_rect.left + 20:
            rect.left = screen_rect.left + 20
        if rect.right > screen_rect.right - 20:
            rect.right = screen_rect.right - 20
        self.truck_rect = rect
        self.surface.blit(truck, rect)

    def _draw_cards(self) -> None:
        if not self.cards:
            return
        mouse_pos = pygame.mouse.get_pos()
        disabled = (
            not self.game.active
            or self.animation is not None
            or self.game.awaiting_next_cycle()
            or self.paused
        )
        tooltip: Tuple[str, Tuple[int, int]] | None = None
        hovered_label = None
        for card in self.cards:
            hovered = card.rect.collidepoint(mouse_pos) and not disabled
            base_color = (32, 47, 74)
            if hovered:
                base_color = (45, 66, 104)
            if disabled:
                base_color = (26, 34, 50)
            outline_color = (255, 255, 255)
            pygame.draw.rect(self.surface, base_color, card.rect, border_radius=12)
            pygame.draw.rect(self.surface, outline_color, card.rect, width=2, border_radius=12)
            label = self.font.render(card.display_name, True, (255, 233, 210))
            self.surface.blit(label, (card.rect.x + 16, card.rect.y + 12))

            info_rect = self._info_icon_rect(card)
            pygame.draw.circle(self.surface, (255, 233, 210), info_rect.center, info_rect.width // 2)
            pygame.draw.circle(self.surface, (70, 55, 80), info_rect.center, info_rect.width // 2, width=2)
            letter = self.small_font.render("i", True, (20, 20, 40))
            letter_rect = letter.get_rect(center=info_rect.center)
            self.surface.blit(letter, letter_rect)
            if info_rect.collidepoint(mouse_pos):
                info_text = ALGORITHM_INFO.get(card.algorithm, card.display_name)
                tooltip = (info_text, (info_rect.centerx, info_rect.top - 8))

            stats = self.game.algorithm_stats[card.algorithm]
            uses_text = f"Usos: {stats.uses}"
            avg_text = f"Media: {stats.average_time_ms:.1f} ms" if stats.average_time_ms is not None else "Media: -"
            uses_surface = self.small_font.render(uses_text, True, (220, 220, 220))
            avg_surface = self.small_font.render(avg_text, True, (220, 220, 220))
            self.surface.blit(uses_surface, (card.rect.x + 16, card.rect.y + 50))
            self.surface.blit(avg_surface, (card.rect.x + 16, card.rect.y + 78))
            if hovered:
                hovered_label = card.display_name

        if tooltip:
            self._draw_tooltip(tooltip[0], tooltip[1])
        if hovered_label and hovered_label != self._hovered_card:
            self.sounds.play_hover()
        self._hovered_card = hovered_label

    def _draw_message(self) -> None:
        message_rect = pygame.Rect(40, self.surface.get_height() - 80, self.surface.get_width() - 80, 50)
        pygame.draw.rect(self.surface, (20, 32, 52), message_rect, border_radius=12)
        pygame.draw.rect(self.surface, (255, 255, 255), message_rect, width=1, border_radius=12)
        message = self.small_font.render(self.last_message, True, (255, 255, 255))
        text_rect = message.get_rect(center=message_rect.center)
        self.surface.blit(message, text_rect)

    def _draw_pause_modal(self) -> None:
        overlay = pygame.Surface(self.surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 128))
        self.surface.blit(overlay, (0, 0))

        width = min(460, self.surface.get_width() - 120)
        height = 320
        modal = pygame.Rect(0, 0, width, height)
        modal.center = self.surface.get_rect().center
        pygame.draw.rect(self.surface, (24, 36, 58), modal, border_radius=16)
        pygame.draw.rect(self.surface, (255, 255, 255), modal, width=2, border_radius=16)

        title = self.big_font.render("Jogo pausado", True, (255, 233, 210))
        title_rect = title.get_rect(center=(modal.centerx, modal.y + 50))
        self.surface.blit(title, title_rect)

        buttons = [
            ("resume", "Continuar"),
            ("options", "Opcoes"),
            ("quit", "Abandonar partida"),
        ]
        self.pause_menu_buttons = {}
        button_width = modal.width - 80
        button_height = 48
        start_y = modal.y + 100
        hovered_key = None
        for idx, (key, label) in enumerate(buttons):
            rect = pygame.Rect(
                modal.x + 40,
                start_y + idx * (button_height + 18),
                button_width,
                button_height,
            )
            self.pause_menu_buttons[key] = rect
            hovered = rect.collidepoint(pygame.mouse.get_pos())
            base_color = (32, 47, 74) if not hovered else (45, 66, 104)
            pygame.draw.rect(self.surface, base_color, rect, border_radius=10)
            pygame.draw.rect(self.surface, (255, 255, 255), rect, width=2, border_radius=10)
            label_surface = self.font.render(label, True, (255, 233, 210))
            icon = self.pause_icons.get(key)
            if icon:
                icon_rect = icon.get_rect()
                icon_rect.centery = rect.centery
                icon_rect.left = rect.x + 20
                self.surface.blit(icon, icon_rect)
                text_rect = label_surface.get_rect(midleft=(icon_rect.right + 12, rect.centery))
            else:
                text_rect = label_surface.get_rect(center=rect.center)
            self.surface.blit(label_surface, text_rect)
            if hovered:
                hovered_key = key
        if hovered_key and hovered_key != self._hovered_pause_menu_button:
            self.sounds.play_hover()
        self._hovered_pause_menu_button = hovered_key

    def _draw_results_screen(self) -> None:
        self._draw_background()
        overlay = pygame.Surface(self.surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 120))
        self.surface.blit(overlay, (0, 0))

        stats = storage.get_stats()
        recent = self.result_summary or stats.get("last") or {}
        best = stats.get("best") or recent

        title = self.big_font.render("Placar de lideres", True, (255, 233, 210))
        self.surface.blit(title, title.get_rect(center=(self.surface.get_width() // 2, 90)))

        cards_area = pygame.Rect(0, 0, self.surface.get_width() - 160, 260)
        cards_area.center = (self.surface.get_width() // 2, self.surface.get_height() // 2 - 60)
        card_width = (cards_area.width - 20) // 2
        card_height = cards_area.height
        card_titles = [
            ("Partida recente", recent),
            ("Melhor partida", best),
        ]
        for idx, (label, data) in enumerate(card_titles):
            rect = pygame.Rect(cards_area.x + idx * (card_width + 20), cards_area.y, card_width, card_height)
            pygame.draw.rect(self.surface, (24, 36, 58), rect, border_radius=16)
            pygame.draw.rect(self.surface, (255, 255, 255), rect, width=2, border_radius=16)
            heading = self.font.render(label, True, (255, 233, 210))
            heading_rect = heading.get_rect(center=(rect.centerx, rect.y + 32))
            self.surface.blit(heading, heading_rect)
            lines = [
                f"Entregas: {data.get('deliveries', 0)}",
                f"Itens: {data.get('items', 0)}",
                f"Algoritmo: {data.get('best_algorithm') or '-'}",
            ]
            if data.get("timestamp"):
                lines.append(f"Data: {data['timestamp'][:19]}")
            for line_idx, line in enumerate(lines):
                text = self.small_font.render(line, True, (230, 230, 230))
                text_rect = text.get_rect(center=(rect.centerx, rect.y + 80 + line_idx * 28))
                self.surface.blit(text, text_rect)

        buttons = [
            ("restart", "Jogar novamente"),
            ("menu", "Menu principal"),
        ]
        self.results_buttons = {}
        button_width = 260
        button_height = 56
        start_x = (self.surface.get_width() - (len(buttons) * (button_width + 20) - 20)) // 2
        y = cards_area.bottom + 60
        hovered_button = None
        for idx, (key, label) in enumerate(buttons):
            rect = pygame.Rect(start_x + idx * (button_width + 20), y, button_width, button_height)
            self.results_buttons[key] = rect
            hovered = rect.collidepoint(pygame.mouse.get_pos())
            base_color = (32, 47, 74) if not hovered else (45, 66, 104)
            pygame.draw.rect(self.surface, base_color, rect, border_radius=12)
            pygame.draw.rect(self.surface, (255, 255, 255), rect, width=2, border_radius=12)
            label_surface = self.font.render(label, True, (255, 233, 210))
            label_rect = label_surface.get_rect(center=rect.center)
            self.surface.blit(label_surface, label_rect)
            if hovered:
                hovered_button = key
        if hovered_button and hovered_button != self._hovered_results_button:
            self.sounds.play_hover()
        self._hovered_results_button = hovered_button

    def _info_icon_rect(self, card: AlgorithmCard) -> pygame.Rect:
        size = 22
        return pygame.Rect(card.rect.right - size - 12, card.rect.y + 8, size, size)

    def _draw_tooltip(self, text: str, anchor: Tuple[int, int]) -> None:
        padding = 8
        surf = self.small_font.render(text, True, (20, 20, 20))
        rect = surf.get_rect()
        rect.topleft = (anchor[0] + 12, anchor[1] - rect.height // 2)
        rect.inflate_ip(padding * 2, padding * 2)

        screen_rect = self.surface.get_rect()
        if rect.right > screen_rect.right - 10:
            rect.right = anchor[0] - 12
        if rect.left < screen_rect.left + 10:
            rect.left = screen_rect.left + 10
        if rect.top < screen_rect.top + 10:
            rect.top = screen_rect.top + 10
        if rect.bottom > screen_rect.bottom - 10:
            rect.bottom = screen_rect.bottom - 10

        pygame.draw.rect(self.surface, (255, 230, 210), rect, border_radius=8)
        pygame.draw.rect(self.surface, (70, 55, 80), rect, width=2, border_radius=8)
        text_rect = surf.get_rect(center=rect.center)
        self.surface.blit(surf, text_rect)

    def _pause_button_hit(self, position: Tuple[int, int]) -> bool:
        return self.pause_button_rect.collidepoint(position)

    def _handle_pause_modal_click(self, position: Tuple[int, int]) -> None:
        for key, rect in self.pause_menu_buttons.items():
            if rect.collidepoint(position):
                self.sounds.play_click()
                if key == "resume":
                    self.paused = False
                elif key == "options":
                    self._requested_menu_state = MenuState.OPTIONS
                    self._request_menu = True
                    self.game.active = False
                elif key == "quit":
                    self.paused = False
                    self._requested_menu_state = MenuState.MAIN
                    self._request_menu = True
                    self.game.active = False
                break

    def _handle_results_modal_click(self, position: Tuple[int, int]) -> None:
        for key, rect in self.results_buttons.items():
            if rect.collidepoint(position):
                self.sounds.play_click()
                if key == "restart":
                    self.show_results = False
                    self.result_summary = None
                    self.start()
                elif key == "menu":
                    self.show_results = False
                    self.result_summary = None
                    self._requested_menu_state = MenuState.MAIN
                    self._request_menu = True
                    self.game.active = False
                break

    # Layout, pause e interação -----------------------------------------------
    def _handle_click(self, position: tuple[int, int]) -> None:
        if (
            not self.game.active
            or self.animation is not None
            or self.game.awaiting_next_cycle()
            or self.paused
            or self.show_results
        ):
            return
        for card in self.cards:
            if card.rect.collidepoint(position):
                if self._info_icon_rect(card).collidepoint(position):
                    return
                self._activate_card(card.algorithm)
                break

    def _activate_card(self, algorithm: str) -> None:
        try:
            outcome = self.game.choose_algorithm(algorithm)
        except RuntimeError as exc:
            self.last_message = str(exc)
            return
        self.sounds.play_click()
        self._start_animation(outcome)

    def _start_animation(self, outcome: DeliveryOutcome) -> None:
        steps = outcome.run.steps
        self.animation = SortingAnimation(
            steps=steps,
            algorithm=outcome.run.result.algorithm,
            result=outcome.run.result,
            batch_id=outcome.batch.identifier,
        )
        self._set_truck_loaded(False)
        self.sounds.play_point()
        if not steps:
            self.animation.phase = "cooldown"
            self.animation.timer = 0.0
            self._set_truck_loaded(True)
        self.highlight_positions = None
        total_steps = max(len(steps), 1)
        self.last_message = f"{DISPLAY_LABELS[outcome.run.result.algorithm]} rodando ({total_steps} passos)."
        self._sync_current_run_stats()

    def _update_animation(self, delta_seconds: float) -> None:
        if not self.animation:
            return
        animation = self.animation
        if animation.phase == "running" and not self.paused:
            if not animation.steps:
                animation.phase = "cooldown"
                animation.timer = 0.0
                self._set_truck_loaded(True)
                return
            animation.timer += delta_seconds
            while animation.timer >= animation.interval and animation.current_step < len(animation.steps):
                animation.timer -= animation.interval
                step = animation.steps[animation.current_step]
                self._apply_step(step)
                animation.current_step += 1
                self.last_message = (
                    f"{DISPLAY_LABELS[animation.algorithm]} passo "
                    f"{animation.current_step}/{len(animation.steps)}"
                )
            if animation.current_step >= len(animation.steps):
                animation.phase = "cooldown"
                animation.timer = 0.0
                self._set_truck_loaded(True)
                self.last_message = "Lote organizado. Preparando proximo caminhao..."
        elif not self.paused:
            animation.timer += delta_seconds
            if animation.timer >= animation.cooldown:
                self._finish_animation()

    def _apply_step(self, step: sorting.SortStep) -> None:
        if not self.box_lookup:
            return
        ordered: List[BoxVisual] = []
        for idx in step.order:
            box = self.box_lookup.get(idx)
            if box:
                ordered.append(box)
        if ordered:
            self.boxes = ordered
            self._position_boxes()
        self.highlight_positions = step.highlight
        now = pygame.time.get_ticks()
        if now - self._last_move_sound >= self._move_sound_cooldown:
            self.sounds.play_move()
            self._last_move_sound = now

    def _finish_animation(self) -> None:
        if not self.animation:
            return
        metrics = self.animation.result.metrics
        algorithm = self.animation.algorithm
        self.animation = None
        self.highlight_positions = None
        self.last_message = (
            f"{DISPLAY_LABELS[algorithm]} finalizado em {metrics.duration_ms:.2f} ms."
        )
        self._set_truck_loaded(True)
        self.sounds.play_delivery()
        self.game.advance_to_next_batch()
        if self.game.active and self.game.current_batch:
            self._apply_new_batch(self.game.current_batch)
            self._sync_current_run_stats()

    def _apply_new_batch(self, batch: Batch | None) -> None:
        self.boxes = []
        self.box_lookup.clear()
        if not batch:
            return
        textures = self.box_textures or [self._fallback_box_surface()]
        box_width = 70
        box_height = 70
        visuals: List[BoxVisual] = []
        for idx, value in enumerate(batch.items):
            texture = self.random.choice(textures)
            surface = pygame.transform.smoothscale(texture, (box_width, box_height))
            rect = surface.get_rect()
            visual = BoxVisual(index=idx, value=value, surface=surface, rect=rect)
            visuals.append(visual)
            self.box_lookup[idx] = visual
        self.boxes = visuals
        self._position_boxes()
        self._select_truck(len(batch.items))
        self._set_truck_loaded(False)

    def _position_boxes(self) -> None:
        if not self.boxes:
            return
        area = self._box_area()
        box_width = self.boxes[0].rect.width
        box_height = self.boxes[0].rect.height
        left_padding = 50
        right_padding = 50
        bottom_offset = 32
        row_gap = 26
        available_width = area.width - left_padding - right_padding
        gap_min = 10
        per_row = max(1, int(available_width / (box_width + gap_min)))
        rows = max(1, math.ceil(len(self.boxes) / per_row))
        total_height = rows * box_height + (rows - 1) * row_gap
        vertical_margin = 64
        top_base = area.y + vertical_margin + box_height
        for row in range(rows):
            start = row * per_row
            row_boxes = self.boxes[start : start + per_row]
            if not row_boxes:
                break
            count = len(row_boxes)
            if count == 1:
                positions = [area.centerx]
            else:
                left_edge = area.x + left_padding + box_width / 2
                right_edge = area.right - right_padding - box_width / 2
                step = (right_edge - left_edge) / (count - 1)
                positions = [left_edge + i * step for i in range(count)]
            y = top_base + row * (box_height + row_gap)
            for box, pos in zip(row_boxes, positions):
                box.rect.centerx = int(pos)
                box.rect.bottom = y

    def _box_area(self) -> pygame.Rect:
        width = self.surface.get_width()
        height = self.surface.get_height()
        return pygame.Rect(40, 180, width - 80, max(240, height // 3))

    def _select_truck(self, batch_size: int) -> None:
        threshold = 12
        self.current_truck_key = "big" if batch_size >= threshold else "small"
        self._refresh_truck_surface()

    def _set_truck_loaded(self, loaded: bool) -> None:
        self.truck_loaded = loaded
        self._refresh_truck_surface()

    def _refresh_truck_surface(self) -> None:
        images = self.truck_images.get(self.current_truck_key)
        if not images:
            self.current_truck = None
            return
        key = "full" if self.truck_loaded else "empty"
        self.current_truck = images.get(key)

    def _sync_current_run_stats(self) -> None:
        storage.update_current_run(
            {
                "deliveries": self.game.deliveries_completed,
                "items": self.game.total_items_sorted,
                "time_remaining": max(self.game.remaining_time, 0),
                "best_algorithm": self.game.best_algorithm(),
            }
        )

    # Asset helpers ------------------------------------------------------------
    def _load_background(self) -> pygame.Surface:
        if BACKGROUND_DEFAULT.exists():
            return pygame.image.load(str(BACKGROUND_DEFAULT)).convert()
        fallback = pygame.Surface((1280, 720))
        fallback.fill((12, 20, 32))
        return fallback

    def _load_box_sprites(self) -> List[pygame.Surface]:
        if not BOX_SPRITES_DIR.exists():
            return []
        textures: List[pygame.Surface] = []
        for path in BOX_SPRITES_DIR.glob("*.png"):
            try:
                textures.append(pygame.image.load(str(path)).convert_alpha())
            except pygame.error:
                continue
        return textures

    def _fallback_box_surface(self) -> pygame.Surface:
        surface = pygame.Surface((60, 60))
        surface.fill((255, 180, 92))
        pygame.draw.rect(surface, (110, 70, 40), surface.get_rect(), width=2)
        return surface

    def _load_image(self, path: Path, size: Tuple[int, int]) -> Optional[pygame.Surface]:
        if not path.exists():
            return None
        try:
            image = pygame.image.load(str(path)).convert_alpha()
            return pygame.transform.smoothscale(image, size)
        except pygame.error:
            return None

    def _load_ui_icon(self, filename: str, size: Tuple[int, int]) -> Optional[pygame.Surface]:
        path = ICON_DIR / filename
        if not path.exists():
            return None
        try:
            return pygame.transform.smoothscale(
                pygame.image.load(str(path)).convert_alpha(),
                size,
            )
        except pygame.error:
            return None

    def _load_pause_icon(self) -> Optional[pygame.Surface]:
        default_path = ICON_DIR / "clock_stop.png"
        candidate = default_path if default_path.exists() else None
        if candidate is None:
            for path in ICON_DIR.glob("*pause*.png"):
                candidate = path
                break
        if candidate and candidate.exists():
            try:
                return pygame.transform.smoothscale(
                    pygame.image.load(str(candidate)).convert_alpha(),
                    (32, 32),
                )
            except pygame.error:
                return None
        return None

    def _layout_cards(self) -> None:
        algorithms = sorting.available_algorithms()
        count = len(algorithms)
        if count == 0:
            self.cards = []
            return
        width = 220
        height = 110
        gap = 24
        total_width = count * width + (count - 1) * gap
        start_x = max((self.surface.get_width() - total_width) // 2, 40)
        y = self.surface.get_height() - height - 120
        laid_out: List[AlgorithmCard] = []
        for index, algorithm in enumerate(algorithms):
            rect = pygame.Rect(start_x + index * (width + gap), y, width, height)
            display = DISPLAY_LABELS.get(algorithm, algorithm.title())
            laid_out.append(AlgorithmCard(algorithm=algorithm, display_name=display, rect=rect))
        self.cards = laid_out

    def _scale_background(self) -> None:
        width, height = self.surface.get_size()
        if width <= 0 or height <= 0:
            self.background_scaled = None
            return
        self.background_scaled = pygame.transform.smoothscale(self.background, (width, height))

    @staticmethod
    def _format_timer(seconds: float) -> str:
        seconds = max(int(seconds), 0)
        minutes = seconds // 60
        remainder = seconds % 60
        return f"{minutes:02}:{remainder:02}"
