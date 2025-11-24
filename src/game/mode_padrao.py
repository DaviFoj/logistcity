from __future__ import annotations

from dataclasses import dataclass, field
import random
from datetime import datetime
from typing import Dict, List, Optional

from src.algorithms import sorting


@dataclass
class Batch:
    """Representa um lote de caixas aguardando ordenação."""

    identifier: int
    items: List[int]


@dataclass
class AlgorithmStats:
    uses: int = 0
    total_time_ms: float = 0.0
    best_time_ms: Optional[float] = None

    def register(self, time_ms: float) -> None:
        self.uses += 1
        self.total_time_ms += time_ms
        if self.best_time_ms is None or time_ms < self.best_time_ms:
            self.best_time_ms = time_ms

    @property
    def average_time_ms(self) -> Optional[float]:
        if self.uses == 0:
            return None
        return self.total_time_ms / self.uses


@dataclass
class DeliverySummary:
    batch_id: int
    batch_size: int
    result: sorting.SortingResult


@dataclass
class DeliveryOutcome:
    batch: Batch
    run: sorting.SortingRun


class StandardModeGame:
    """Controla o fluxo do modo padrão (2 minutos, entregas repetidas)."""

    def __init__(
        self,
        *,
        duration_seconds: int = 120,
        batch_size_range: tuple[int, int] = (6, 20),
        value_range: tuple[int, int] = (1, 99),
        rng_seed: int | None = None,
    ) -> None:
        self.duration_seconds = duration_seconds
        self.batch_size_range = batch_size_range
        self.value_range = value_range
        self.rng = random.Random(rng_seed)

        self.remaining_time: float = float(duration_seconds)
        self.active: bool = False
        self.current_batch: Batch | None = None
        self.deliveries_completed = 0
        self.total_items_sorted = 0
        self.last_result: sorting.SortingResult | None = None
        self.algorithm_stats: Dict[str, AlgorithmStats] = {
            name: AlgorithmStats() for name in sorting.available_algorithms()
        }
        self.history: List[DeliverySummary] = []
        self._batch_counter = 0
        self._next_batch: Batch | None = None
        self._awaiting_cycle: bool = False

    # Public API --------------------------------------------------------------
    def start(self) -> None:
        self.remaining_time = float(self.duration_seconds)
        self.active = True
        self.deliveries_completed = 0
        self.total_items_sorted = 0
        self.last_result = None
        self.history.clear()
        for stats in self.algorithm_stats.values():
            stats.uses = 0
            stats.total_time_ms = 0.0
            stats.best_time_ms = None
        self._batch_counter = 0
        self.current_batch = self._generate_batch()
        self._next_batch = None
        self._awaiting_cycle = False

    def update(self, delta_seconds: float) -> None:
        if not self.active:
            return
        self.remaining_time = max(self.remaining_time - delta_seconds, 0)
        if self.remaining_time <= 0:
            self.active = False

    def choose_algorithm(self, algorithm_name: str) -> DeliveryOutcome:
        if not self.active or self.remaining_time <= 0:
            raise RuntimeError("Partida nao esta ativa.")
        if not self.current_batch:
            raise RuntimeError("Nenhum lote disponivel.")
        if self._awaiting_cycle:
            raise RuntimeError("Aguarde o carregamento do proximo lote.")

        batch = self.current_batch
        run = sorting.run(algorithm_name, batch.items, capture_steps=True)
        result = run.result
        self.last_result = result
        self.deliveries_completed += 1
        self.total_items_sorted += len(batch.items)
        self.algorithm_stats[result.algorithm].register(result.metrics.duration_ms)
        self.history.append(DeliverySummary(batch.identifier, len(batch.items), result))
        self._next_batch = self._generate_batch()
        self._awaiting_cycle = True
        return DeliveryOutcome(batch=batch, run=run)

    def advance_to_next_batch(self) -> None:
        if self._next_batch:
            self.current_batch = self._next_batch
            self._next_batch = None
        self._awaiting_cycle = False

    def awaiting_next_cycle(self) -> bool:
        return self._awaiting_cycle

    def is_finished(self) -> bool:
        return not self.active

    def hud_data(self) -> Dict[str, float | int | None]:
        return {
            "tempo_restante": self.remaining_time,
            "entregas": self.deliveries_completed,
            "itens_organizados": self.total_items_sorted,
            "ultima_execucao_ms": self.last_result.metrics.duration_ms if self.last_result else None,
        }

    def best_algorithm(self) -> Optional[str]:
        best_name = None
        best_average = None
        for name, stats in self.algorithm_stats.items():
            avg = stats.average_time_ms
            if avg is None:
                continue
            if best_average is None or avg < best_average:
                best_average = avg
                best_name = name
        return best_name

    def build_summary(self) -> Dict[str, float | int | str | None]:
        return {
            "deliveries": self.deliveries_completed,
            "items": self.total_items_sorted,
            "duration_seconds": self.duration_seconds,
            "best_algorithm": self.best_algorithm(),
            "timestamp": datetime.utcnow().isoformat(),
        }

    # Internal helpers -------------------------------------------------------
    def _generate_batch(self) -> Batch:
        self._batch_counter += 1
        size = self.rng.randint(*self.batch_size_range)
        low, high = self.value_range
        items = [self.rng.randint(low, high) for _ in range(size)]
        return Batch(identifier=self._batch_counter, items=items)
