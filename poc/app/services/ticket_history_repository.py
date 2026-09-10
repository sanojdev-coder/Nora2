import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

try:
    from azure.cosmos import CosmosClient
except Exception:  # pragma: no cover - optional dependency
    CosmosClient = None


class TicketHistoryRepository:
    """Persist and query per-subscriber ticket history in Cosmos DB."""

    def __init__(self) -> None:
        self.endpoint = os.getenv("COSMOS_ENDPOINT", "").strip()
        self.key = os.getenv("COSMOS_KEY", "").strip()
        self.database_name = os.getenv("COSMOS_DATABASE", "nora").strip() or "nora"
        self.container_name = os.getenv("COSMOS_CONTAINER", "tickets").strip() or "tickets"
        self.client: Any = None
        self.container: Any = None

        if not self.endpoint or not self.key or CosmosClient is None:
            if not self.endpoint or not self.key:
                logger.info(
                    "Cosmos ticket history repository is disabled: COSMOS_ENDPOINT/COSMOS_KEY not configured"
                )
            if CosmosClient is None:
                logger.warning(
                    "azure-cosmos package is not installed; Cosmos ticket history will be disabled"
                )
            return

        try:
            self.client = CosmosClient(url=self.endpoint, credential=self.key)
            database = self.client.get_database_client(self.database_name)
            self.container = database.get_container_client(self.container_name)
            logger.info(
                "Cosmos ticket history repository initialized database=%s container=%s",
                self.database_name,
                self.container_name,
            )
        except Exception as exc:  # pragma: no cover - runtime configuration issue
            logger.warning("Cosmos ticket history repository failed to initialize: %s", exc)
            self.client = None
            self.container = None

    def is_enabled(self) -> bool:
        return self.container is not None

    def save_ticket_record(
        self,
        *,
        report_id: str,
        subscriber_id: str,
        ticket_id: str,
        ticket_timestamp: str | None = None,
        status: str = "open",
        serving_market: str | None = None,
    ) -> bool:
        if not self.is_enabled():
            return False

        record = {
            "id": f"{report_id}|{ticket_id}",
            "report_id": report_id,
            "subscriber_id": subscriber_id,
            "ticket_id": ticket_id,
            "ticket_timestamp": ticket_timestamp or datetime.now(timezone.utc).isoformat(),
            "status": status,
            "serving_market": serving_market,
        }

        try:
            self.container.upsert_item(record)
            logger.info(
                "Saved Cosmos ticket history record for subscriber=%s ticket=%s report=%s",
                subscriber_id,
                ticket_id,
                report_id,
            )
            return True
        except Exception as exc:  # pragma: no cover - runtime DB issue
            logger.warning("Failed to save Cosmos ticket history record: %s", exc)
            return False

    def get_previous_tickets(self, subscriber_id: str, limit: int = 10) -> list[str]:
        if not self.is_enabled():
            return []

        query = (
            "SELECT TOP @limit c.ticket_id FROM c "
            "WHERE c.subscriber_id = @subscriber_id "
            "ORDER BY c.ticket_timestamp DESC"
        )
        params = [
            {"name": "@limit", "value": limit},
            {"name": "@subscriber_id", "value": subscriber_id},
        ]

        try:
            items = list(
                self.container.query_items(
                    query=query,
                    parameters=params,
                    enable_cross_partition_query=True,
                )
            )
            ticket_ids = [item.get("ticket_id") for item in items if item.get("ticket_id")]
            logger.info(
                "Loaded %s prior tickets for subscriber=%s from Cosmos",
                len(ticket_ids),
                subscriber_id,
            )
            return ticket_ids
        except Exception as exc:  # pragma: no cover - runtime DB issue
            logger.warning("Failed to fetch Cosmos ticket history for subscriber=%s: %s", subscriber_id, exc)
            return []
