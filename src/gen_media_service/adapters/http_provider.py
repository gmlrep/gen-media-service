import httpx

from gen_media_service.adapters.provider import ProviderError, ProviderSubmitResult
from gen_media_service.core.config import ProviderSettings


class HttpProviderClient:
    def __init__(self, settings: ProviderSettings) -> None:
        self._settings = settings
        self._base_urls = {
            "alpha": settings.ALPHA_BASE_URL.rstrip("/"),
            "beta": settings.BETA_BASE_URL.rstrip("/"),
        }

    async def submit_task(
        self,
        *,
        provider: str,
        prompt: str,
        ref_images: list[str],
        model_slug: str,
    ) -> ProviderSubmitResult:
        base = self._base_urls.get(provider)
        if base is None:
            raise ProviderError(f"Unknown provider: {provider}")

        try:
            async with httpx.AsyncClient(timeout=self._settings.PROVIDER_HTTP_TIMEOUT) as client:
                response = await client.post(
                    f"{base}/tasks",
                    json={
                        "prompt": prompt,
                        "ref_images": ref_images,
                        "model_slug": model_slug,
                    },
                )
        except httpx.TimeoutException as exc:
            raise ProviderError("Provider request timed out") from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Provider HTTP error: {exc}") from exc

        if response.status_code >= 500:
            raise ProviderError(f"Provider returned {response.status_code}")
        if response.status_code != 202:
            raise ProviderError(f"Unexpected provider status {response.status_code}")

        data = response.json()
        external_id = data.get("external_id")
        if not external_id:
            raise ProviderError("Provider response missing external_id")
        return ProviderSubmitResult(external_id=str(external_id))
