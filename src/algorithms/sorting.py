from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Callable, Dict, List, Sequence, Tuple


@dataclass
class SortingMetrics:
    comparisons: int
    swaps: int
    duration_ms: float


@dataclass
class SortingResult:
    algorithm: str
    original: List[int]
    sorted_values: List[int]
    metrics: SortingMetrics


@dataclass
class SortStep:
    order: List[int]
    highlight: Tuple[int, ...] | None = None


@dataclass
class SortingRun:
    result: SortingResult
    steps: List[SortStep]


@dataclass
class _SortingComputation:
    values: List[int]
    comparisons: int
    swaps: int
    steps: List[SortStep]
    duration_ms: float = 0.0


@dataclass
class _SortItem:
    value: int
    index: int


AlgorithmRunner = Callable[[List[int], bool], _SortingComputation]


def execute(algorithm: str, values: List[int]) -> SortingResult:
    return run(algorithm, values, capture_steps=False).result


def run(algorithm: str, values: List[int], *, capture_steps: bool = False) -> SortingRun:
    normalized = algorithm.lower()
    if normalized not in _ALGORITHMS:
        available = ", ".join(sorted(_ALGORITHMS))
        raise ValueError(f"Algoritmo '{algorithm}' nao suportado. Disponiveis: {available}")
    computation = _timed_execution(normalized, values, capture_steps)
    duration = computation.duration_ms
    result = SortingResult(
        algorithm=normalized,
        original=values.copy(),
        sorted_values=computation.values,
        metrics=SortingMetrics(
            comparisons=computation.comparisons,
            swaps=computation.swaps,
            duration_ms=duration,
        ),
    )
    return SortingRun(result=result, steps=computation.steps)


def available_algorithms() -> List[str]:
    return list(_ALGORITHMS.keys())


# Internal helpers -----------------------------------------------------------
def _timed_execution(name: str, values: List[int], capture_steps: bool) -> _SortingComputation:
    runner = _ALGORITHMS[name]
    start = perf_counter()
    computation = runner(values, capture_steps)
    duration_ms = (perf_counter() - start) * 1000
    computation.values = computation.values.copy()
    computation.duration_ms = duration_ms
    return computation


def _snapshot(items: Sequence[_SortItem]) -> List[int]:
    return [item.index for item in items]


def _record_step(items: Sequence[_SortItem], steps: List[SortStep], highlight: Tuple[int, ...] | None) -> None:
    steps.append(SortStep(order=_snapshot(items), highlight=highlight))


def _ensure_final_step(items: Sequence[_SortItem], steps: List[SortStep]) -> None:
    final_snapshot = _snapshot(items)
    if not steps or steps[-1].order != final_snapshot:
        steps.append(SortStep(order=final_snapshot, highlight=None))


def _prepare_items(values: List[int]) -> List[_SortItem]:
    return [_SortItem(value=value, index=index) for index, value in enumerate(values)]


def _insertion(values: List[int], capture_steps: bool) -> _SortingComputation:
    items = _prepare_items(values)
    steps: List[SortStep] = []
    comparisons = swaps = 0
    for i in range(1, len(items)):
        key_item = items[i]
        j = i - 1
        while j >= 0 and items[j].value > key_item.value:
            comparisons += 1
            items[j + 1] = items[j]
            swaps += 1
            if capture_steps:
                _record_step(items, steps, (j, j + 1))
            j -= 1
        if j >= 0:
            comparisons += 1
        items[j + 1] = key_item
        if capture_steps:
            _record_step(items, steps, (j + 1,))
    if capture_steps:
        _ensure_final_step(items, steps)
    return _SortingComputation(
        values=[item.value for item in items],
        comparisons=comparisons,
        swaps=swaps,
        steps=steps if capture_steps else [],
    )


def _selection(values: List[int], capture_steps: bool) -> _SortingComputation:
    items = _prepare_items(values)
    steps: List[SortStep] = []
    comparisons = swaps = 0
    length = len(items)
    for i in range(length):
        min_index = i
        for j in range(i + 1, length):
            comparisons += 1
            if items[j].value < items[min_index].value:
                min_index = j
        if min_index != i:
            items[i], items[min_index] = items[min_index], items[i]
            swaps += 1
            if capture_steps:
                _record_step(items, steps, (i, min_index))
    if capture_steps:
        _ensure_final_step(items, steps)
    return _SortingComputation(
        values=[item.value for item in items],
        comparisons=comparisons,
        swaps=swaps,
        steps=steps if capture_steps else [],
    )


def _bubble(values: List[int], capture_steps: bool) -> _SortingComputation:
    items = _prepare_items(values)
    steps: List[SortStep] = []
    comparisons = swaps = 0
    n = len(items)
    for i in range(n):
        swapped = False
        for j in range(0, n - i - 1):
            comparisons += 1
            if items[j].value > items[j + 1].value:
                items[j], items[j + 1] = items[j + 1], items[j]
                swaps += 1
                swapped = True
                if capture_steps:
                    _record_step(items, steps, (j, j + 1))
        if not swapped:
            break
    if capture_steps:
        _ensure_final_step(items, steps)
    return _SortingComputation(
        values=[item.value for item in items],
        comparisons=comparisons,
        swaps=swaps,
        steps=steps if capture_steps else [],
    )


def _quick(values: List[int], capture_steps: bool) -> _SortingComputation:
    items = _prepare_items(values)
    steps: List[SortStep] = []
    comparisons = swaps = 0

    def partition(low: int, high: int) -> int:
        nonlocal comparisons, swaps, items
        pivot = items[high]
        i = low
        for j in range(low, high):
            comparisons += 1
            if items[j].value <= pivot.value:
                items[i], items[j] = items[j], items[i]
                swaps += 1
                if capture_steps:
                    _record_step(items, steps, (i, j))
                i += 1
        items[i], items[high] = items[high], items[i]
        swaps += 1
        if capture_steps:
            _record_step(items, steps, (i, high))
        return i

    def quick_sort(low: int, high: int) -> None:
        if low >= high:
            return
        pivot_index = partition(low, high)
        quick_sort(low, pivot_index - 1)
        quick_sort(pivot_index + 1, high)

    if items:
        quick_sort(0, len(items) - 1)
    if capture_steps:
        _ensure_final_step(items, steps)
    return _SortingComputation(
        values=[item.value for item in items],
        comparisons=comparisons,
        swaps=swaps,
        steps=steps if capture_steps else [],
    )


_ALGORITHMS: Dict[str, AlgorithmRunner] = {
    "bubble": _bubble,
    "selection": _selection,
    "insertion": _insertion,
    "quick": _quick,
}
