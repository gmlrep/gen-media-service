from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ProviderSubmitResult:
    external_id: str


class ProviderError(Exception):
    """Synchronous failure talking to a provider (5xx / timeout)."""


class ProviderClient(Protocol):
    async def submit_task(
        self,
        *,
        provider: str,
        prompt: str,
        ref_images: list[str],
        model_slug: str,
    ) -> ProviderSubmitResult: ...
