""
from __future__ import annotations
import math
from typing import Dict, Optional

                                                                           
A = 3.0 / math.log(4.0 / 3.0)                                     
                                                                               
MAX_WINDOW_64 = A * math.log(2.0 ** 64)                                                
_SD = 16.42198                                


def window_for_seed(seed: int) -> float:
    ""
    return 0.0 if seed < 2 else A * math.log(seed)


def seed_for_window(W: float) -> int:
    ""
    if W > MAX_WINDOW_64:
        return 0
    return int(math.exp(W / A))


def window_sd(seed: int) -> float:
    ""
    return 0.0 if seed < 2 else _SD * math.sqrt(math.log(seed))


def lifetime(n: int) -> int:
    ""
    c = 0
    while n != 1:
        n = 3 * n + 1 if n & 1 else n >> 1
        c += 1
    return c


class Organism:
    ""

    __slots__ = ("count", "payload", "life", "next_seed", "confirm", "cap",
                 "ticks", "cycles", "prunes", "dropped", "seen", "oid")

    def __init__(self, first_seed: int = 4, confirm: int = 2,
                 cap: int = 4096, oid: int = 0):
        if first_seed < 2:
            first_seed = 4
        self.count: Dict[int, int] = {}
        self.payload: Dict[int, object] = {}
        self.confirm = max(1, confirm)
        self.cap = cap
        self.oid = oid
                                                                             
                                                                          
        self.next_seed = first_seed + oid * 1009
        self.life = self.next_seed                                            
        self.next_seed += 1
        self.ticks = self.cycles = self.prunes = self.dropped = self.seen = 0

                                                                              
    def beat(self) -> int:
        ""
        self.life = 3 * self.life + 1 if self.life & 1 else self.life >> 1
        if self.life == 1:                              
            self._prune()
            self.life = self.next_seed                                     
            self.next_seed += 1
            self.cycles += 1
        self.ticks += 1
        return self.life

    def _prune(self) -> None:
        keep = {k: c for k, c in self.count.items() if c >= self.confirm}
        self.dropped += len(self.count) - len(keep)
        self.count = keep
        self.payload = {k: v for k, v in self.payload.items() if k in keep}
        self.prunes += 1

                                                                              
    def observe(self, key: int, payload: object = None) -> None:
        self.count[key] = self.count.get(key, 0) + 1
        self.payload[key] = payload
        self.seen += 1
        self.beat()
        if len(self.count) > (self.cap * 3) // 4:                             
            self._prune()

    def adopted(self, key: int) -> bool:
        ""
        return self.count.get(key, 0) >= self.confirm

    def get(self, key: int):
        return self.payload.get(key) if self.adopted(key) else None

    def alive(self) -> bool:
        return self.ticks > 0 and self.life != 0

    def fingerprint(self) -> int:
        ""
        acc = 0
        for k, c in self.count.items():
            if c >= self.confirm:
                h = (k * 0x9E3779B97F4A7C15) ^ (c * 0xC4CEB9FE1A85EC53)
                acc = (acc + (h & 0xFFFFFFFFFFFFFFFF)) & 0xFFFFFFFFFFFFFFFF
        return acc

    @property
    def window(self) -> float:
        ""
        return window_for_seed(self.next_seed)

    def __repr__(self) -> str:
        return (f"Organism(seed_now={self.next_seed}, lives={self.cycles}, "
                f"held={len(self.count)}, W~{self.window:.0f})")
