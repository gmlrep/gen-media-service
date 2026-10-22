from dependency_injector import containers, providers

from gen_media_service.adapters.http_provider import HttpProviderClient
from gen_media_service.core.config import get_settings
from gen_media_service.core.database import Database
from gen_media_service.repository.catalog import CatalogRepository
from gen_media_service.repository.ledger import LedgerRepository
from gen_media_service.repository.task import TaskRepository
from gen_media_service.repository.user import UserRepository
from gen_media_service.services.generation import GenerationService
from gen_media_service.services.payment import PaymentService


def _db_url() -> str:
    return get_settings().database.db_url


def _provider_settings():
    return get_settings().providers


class Container(containers.DeclarativeContainer):
    wiring_config = containers.WiringConfiguration(
        modules=[
            "gen_media_service.api.endpoints.generate",
            "gen_media_service.api.endpoints.tasks",
            "gen_media_service.api.endpoints.users",
            "gen_media_service.api.endpoints.webhooks",
        ]
    )

    settings = providers.Singleton(get_settings)

    db = providers.Singleton(Database, db_url=providers.Callable(_db_url))

    user_repository = providers.Factory(
        UserRepository, session_factory=db.provided.session
    )
    ledger_repository = providers.Factory(
        LedgerRepository, session_factory=db.provided.session
    )
    catalog_repository = providers.Factory(
        CatalogRepository, session_factory=db.provided.session
    )
    task_repository = providers.Factory(
        TaskRepository, session_factory=db.provided.session
    )

    provider_client = providers.Factory(
        HttpProviderClient, settings=providers.Callable(_provider_settings)
    )

    payment_service = providers.Factory(
        PaymentService,
        ledger_repository=ledger_repository,
        user_repository=user_repository,
    )
    generation_service = providers.Factory(
        GenerationService,
        task_repository=task_repository,
        catalog_repository=catalog_repository,
        ledger_repository=ledger_repository,
        user_repository=user_repository,
        provider_client=provider_client,
        settings=settings,
    )
