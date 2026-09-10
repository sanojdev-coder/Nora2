import csv
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SnowflakeMCPServer:
    """Operational data source for subscriber troubleshooting.

    The implementation prefers a staged data file under the nora-package folder when
    Snowflake credentials are not configured, while still allowing a direct Snowflake
    connection when environment variables are present.
    """

    DEFAULT_SUBSCRIBER_DATA = {
        "sub-201": {"subscriber_id": "sub-201", "provision_status": "ON", "package": "VALID"},
        "sub-202": {"subscriber_id": "sub-202", "provision_status": "ON", "package": "VALID"},
        "sub-203": {"subscriber_id": "sub-203", "provision_status": "ON", "package": "VALID"},
        "sub-204": {"subscriber_id": "sub-204", "provision_status": "ON", "package": "VALID"},
        "sub-205": {"subscriber_id": "sub-205", "provision_status": "ON", "package": "VALID"},
        "sub-206": {"subscriber_id": "sub-206", "provision_status": "ON", "package": "VALID"},
        "sub-207": {"subscriber_id": "sub-207", "provision_status": "ON", "package": "INVALID"},
        "sub-208": {"subscriber_id": "sub-208", "provision_status": "ON", "package": "VALID"},
        "sub-209": {"subscriber_id": "sub-209", "provision_status": "ON", "package": "VALID"},
        "sub-210": {"subscriber_id": "sub-210", "provision_status": "ON", "package": "VALID"},
    }

    def __init__(self) -> None:
        self.data_path = Path(
            os.getenv(
                "SNOWFLAKE_OPERATIONAL_DATA_PATH",
                str(Path(__file__).resolve().parents[2] / "nora-package" / "subscriber_operational_data.csv"),
            )
        ).expanduser()
        self.subscriber_operational_data = self._load_operational_data()

    def _load_operational_data(self) -> dict[str, dict[str, Any]]:
        if self._can_use_direct_snowflake_connection():
            try:
                return self._fetch_from_snowflake()
            except Exception as exc:  # pragma: no cover - connection dependent path
                logger.warning("Snowflake connection failed; falling back to staged CSV data: %s", exc)

        if self.data_path.exists():
            try:
                return self._load_csv_data(self.data_path)
            except Exception as exc:  # pragma: no cover - file-loading fallback
                logger.warning("Could not load CSV operational dataset at %s: %s", self.data_path, exc)

        return dict(self.DEFAULT_SUBSCRIBER_DATA)

    def _can_use_direct_snowflake_connection(self) -> bool:
        return all(
            os.getenv(name)
            for name in (
                "SNOWFLAKE_ACCOUNT",
                "SNOWFLAKE_USER",
                "SNOWFLAKE_PASSWORD",
            )
        )

    def _fetch_from_snowflake(self) -> dict[str, dict[str, Any]]:
        try:
            import snowflake.connector  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("snowflake-connector-python is not installed") from exc

        account = os.getenv("SNOWFLAKE_ACCOUNT", "").strip()
        user = os.getenv("SNOWFLAKE_USER", "").strip()
        password = os.getenv("SNOWFLAKE_PASSWORD", "").strip()
        warehouse = os.getenv("SNOWFLAKE_WAREHOUSE", "").strip()
        database = os.getenv("SNOWFLAKE_DATABASE", "").strip()
        schema = os.getenv("SNOWFLAKE_SCHEMA", "").strip()

        with snowflake.connector.connect(
            account=account,
            user=user,
            password=password,
            warehouse=warehouse or None,
            database=database or None,
            schema=schema or None,
        ) as conn:
            table_name = os.getenv("SNOWFLAKE_OPERATIONAL_TABLE", "NORA_PACKAGE.SUBSCRIBER_OPERATIONAL_DATA")
            query = (
                f"SELECT subscriber_id, provision_status, package FROM {table_name} "
                "WHERE subscriber_id IS NOT NULL"
            )
            rows = conn.cursor().execute(query).fetchall()
            return {
                subscriber_id: {
                    "subscriber_id": subscriber_id,
                    "provision_status": provision_status,
                    "package": package,
                }
                for subscriber_id, provision_status, package in rows
            }

    def _load_csv_data(self, path: Path) -> dict[str, dict[str, Any]]:
        data: dict[str, dict[str, Any]] = {}
        with path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                if not row:
                    continue
                subscriber_id = str(row.get("subscriber_id", "")).strip()
                if not subscriber_id:
                    continue
                data[subscriber_id] = {
                    "subscriber_id": subscriber_id,
                    "provision_status": str(row.get("provision_status", "UNKNOWN")).strip().upper(),
                    "package": str(row.get("package", "UNKNOWN")).strip().upper(),
                }
        logger.info("Loaded operational data from %s: %s", path, data)
        return data or dict(self.DEFAULT_SUBSCRIBER_DATA)

    def get_subscriber_operational_data(self, subscriber_id: str) -> dict[str, Any]:
        normalized = str(subscriber_id or "").strip()
        record = self.subscriber_operational_data.get(normalized)
        if record is not None:
            logger.info(
                "Snowflake subscriber operational data for %s: %s",
                subscriber_id,
                record,
            )
            return dict(record)

        fallback = {
            "subscriber_id": normalized,
            "provision_status": "UNKNOWN",
            "package": "UNKNOWN",
        }
        logger.info(
            "Snowflake subscriber operational data missing for %s; using fallback %s",
            subscriber_id,
            fallback,
        )
        return fallback

    def get_all_operational_data(self) -> dict[str, dict[str, Any]]:
        return {
            subscriber_id: dict(record)
            for subscriber_id, record in self.subscriber_operational_data.items()
        }
