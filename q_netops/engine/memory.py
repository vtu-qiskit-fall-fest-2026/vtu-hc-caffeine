"""Finite repeater memory slots with lazy decoherence and expiry."""
from dataclasses import dataclass
from .physics import decay_fidelity

@dataclass
class MemorySlot:
    slot_id: str
    link_id: str
    created_at_s: float
    initial_fidelity: float
    coherence_time_s: float
    occupied: bool = True

    def fidelity_at(self, now_s: float) -> float:
        if not self.occupied: return 0.25
        return decay_fidelity(self.initial_fidelity, max(0.0, now_s-self.created_at_s), self.coherence_time_s)

    def is_expired(self, now_s: float, purge_threshold: float = .50) -> bool:
        return not self.occupied or self.fidelity_at(now_s) < purge_threshold

class MemoryBank:
    def __init__(self, capacity: int):
        if capacity < 1: raise ValueError("Memory capacity must be at least one slot")
        self.capacity = capacity
        self.slots: dict[str, MemorySlot] = {}
        self.expired_count = 0

    @property
    def utilization(self) -> float:
        return len(self.slots) / self.capacity

    def allocate(self, slot: MemorySlot) -> bool:
        if len(self.slots) >= self.capacity or slot.slot_id in self.slots: return False
        self.slots[slot.slot_id] = slot
        return True

    def purge_expired(self, now_s: float, threshold: float = .50) -> int:
        expired = [key for key, slot in self.slots.items() if slot.is_expired(now_s, threshold)]
        for key in expired:
            self.slots[key].occupied = False
            del self.slots[key]
        self.expired_count += len(expired)
        return len(expired)

    def release(self, slot_id: str) -> None:
        slot = self.slots.pop(slot_id, None)
        if slot: slot.occupied = False
