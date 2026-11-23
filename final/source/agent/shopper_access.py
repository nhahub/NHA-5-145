"""Browser authority and bounded linking challenges; independent of shopping interpretation."""

import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass, field
from time import monotonic


@dataclass(frozen=True)
class ShopperBinding:
    shopper_id: str
    generation: str

    @property
    def context(self) -> str:
        return hashlib.sha256(f"{self.shopper_id}:{self.generation}".encode()).hexdigest()


@dataclass
class BrowserAuthority:
    csrf: str
    last_activity: float
    shopper: ShopperBinding | None = None
    challenges: dict[str, float] = field(default_factory=dict)
    sessions: set[str] = field(default_factory=set)


class ShopperAccess:
    def __init__(self, clock: Callable[[], float] = monotonic, capacity: int = 100):
        self.clock = clock
        self.capacity = capacity
        self.records: dict[str, BrowserAuthority] = {}

    def resolve(self, credential: str, *, touch: bool = False) -> BrowserAuthority | None:
        now = self.clock()
        for key, record in list(self.records.items()):
            if now - record.last_activity >= 86400:
                del self.records[key]
        record = self.records.get(hashlib.sha256(credential.encode()).hexdigest())
        if record and touch:
            record.last_activity = now
        return record

    def create(self) -> tuple[str, BrowserAuthority]:
        self.resolve("")
        if len(self.records) >= self.capacity:
            raise OverflowError("Browser capacity reached")
        credential = secrets.token_hex(32)
        record = BrowserAuthority(csrf=secrets.token_hex(32), last_activity=self.clock())
        self.records[hashlib.sha256(credential.encode()).hexdigest()] = record
        return credential, record

    def owns_session(self, session_id: str, binding: ShopperBinding, admitted=None) -> bool:
        self.resolve("")
        return any(
            record.shopper == binding
            and session_id in record.sessions
            and (admitted is None or admitted(record))
            for record in self.records.values()
        )

    async def owns_session_async(self, session_id, binding, admitted=None):
        from inspect import isawaitable

        self.resolve("")
        for key, record in tuple(self.records.items()):
            if record.shopper != binding or session_id not in record.sessions:
                continue
            allowed = True if admitted is None else admitted(record)
            if isawaitable(allowed):
                allowed = await allowed
            self.resolve("")
            if (
                allowed is True
                and self.records.get(key) is record
                and record.shopper == binding
                and session_id in record.sessions
            ):
                return True
        return False

    def challenge(self, record: BrowserAuthority) -> str:
        now = self.clock()
        record.challenges = {
            key: expiry for key, expiry in record.challenges.items() if expiry > now
        }
        if len(record.challenges) >= 4:
            raise OverflowError("Too many pending links")
        challenge = secrets.token_hex(32)
        record.challenges[challenge] = now + 60
        return challenge

    def consume_challenge(self, record: BrowserAuthority, challenge: str) -> bool:
        return record.challenges.pop(challenge, 0) > self.clock()
