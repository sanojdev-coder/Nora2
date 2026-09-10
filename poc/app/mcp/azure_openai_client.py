import os
import json
import importlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.mcp.tool_schema import CoverageAssessmentInput, RCAAnalysisToolResult
from app.services.ticket_history_repository import TicketHistoryRepository

try:
    import psycopg
except Exception:  # pragma: no cover - optional dependency
    psycopg = None


def _load_dotenv_if_present() -> None:
    """Load environment variables from the local .env file when present."""
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if not env_file.exists():
        return

    try:
        with env_file.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    except OSError:
        logger = logging.getLogger(__name__)
        logger.warning("Could not read .env file at %s", env_file)


_load_dotenv_if_present()


logger = logging.getLogger(__name__)


class AzureOpenAIClient:
    def __init__(self):
        self.endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip().rstrip("/")
        self.api_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
        self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
        self._azure_client: Any = None
        self.last_status = "stub"
        self.last_error: str | None = None
        self.ticket_history = TicketHistoryRepository()
        self.hot_cache_dsn = (
            os.getenv("HOT_CACHE_DSN")
            or os.getenv("POSTGRES_DSN")
            or os.getenv("COSMOS_POSTGRES_DSN")
            or ""
        ).strip()
        default_log_path = Path(__file__).resolve().parents[2] / "logs" / "openai_audit.jsonl"
        self.audit_path = Path(os.getenv("OPENAI_AUDIT_LOG_PATH", str(default_log_path))).expanduser()

        try:
            openai_module = importlib.import_module("openai")
            openai_cls = getattr(openai_module, "OpenAI")
        except Exception:
            openai_cls = None

        has_required_config = bool(self.endpoint and self.api_key and self.deployment)
        if has_required_config and openai_cls is not None:
            # This resource is an Azure AI Foundry endpoint (*.services.ai.azure.com),
            # which exposes an OpenAI-compatible v1 API at /openai/v1 — not the classic
            # Azure OpenAI deployments path the AzureOpenAI SDK class targets, and it
            # needs no api-version query param.
            self._azure_client = openai_cls(
                base_url=f"{self.endpoint}/openai/v1",
                api_key=self.api_key,
            )
            self.last_status = "live"
            self.last_error = None
            logger.info(
                "AzureOpenAIClient initialized mode=live endpoint=%s deployment=%s",
                self.endpoint,
                self.deployment,
            )
        else:
            self.last_status = "stub"
            self.last_error = "missing_openai_config"
            logger.info(
                "AzureOpenAIClient initialized mode=stub has_endpoint=%s has_api_key=%s deployment=%s sdk_available=%s",
                bool(self.endpoint),
                bool(self.api_key),
                self.deployment,
                openai_cls is not None,
            )

    def _persist_audit_record(self, report_id: str, request_payload: dict[str, Any], response_payload: dict[str, Any], *, status: str, error: str | None = None) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "report_id": report_id,
            "status": status,
            "error": error,
            "request": request_payload,
            "response": response_payload,
            "deployment": self.deployment,
            "endpoint": self.endpoint,
        }

        if self.hot_cache_dsn:
            self._persist_to_postgres(record)
            return

        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")

    def _persist_to_postgres(self, record: dict[str, Any]) -> None:
        if psycopg is None:
            logger.warning("psycopg is not installed; falling back to local JSONL audit log")
            self._persist_audit_record(record["report_id"], record["request"], record["response"], status=record["status"], error=record["error"])
            return

        try:
            with psycopg.connect(self.hot_cache_dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS openai_audit_log (
                            id SERIAL PRIMARY KEY,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            report_id TEXT,
                            deployment TEXT,
                            endpoint TEXT,
                            status TEXT,
                            error TEXT,
                            request_payload JSONB NOT NULL,
                            response_payload JSONB NOT NULL
                        )
                        """
                    )
                    cur.execute(
                        """
                        INSERT INTO openai_audit_log (report_id, deployment, endpoint, status, error, request_payload, response_payload)
                        VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
                        """,
                        (
                            record["report_id"],
                            record["deployment"],
                            record["endpoint"],
                            record["status"],
                            record["error"],
                            json.dumps(record["request"], default=str),
                            json.dumps(record["response"], default=str),
                        ),
                    )
        except Exception as exc:  # pragma: no cover - database not configured in local unit tests
            logger.warning("Could not persist OpenAI audit record to Postgres: %s", exc)
            self.audit_path.parent.mkdir(parents=True, exist_ok=True)
            with self.audit_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, default=str, ensure_ascii=False) + "\n")

    def analyze_coverage_report(
        self,
        report: CoverageAssessmentInput,
        previous_tickets: list[str] | None = None,
    ) -> RCAAnalysisToolResult:
        payload = report.model_dump()
        if previous_tickets is None:
            previous_tickets = self.ticket_history.get_previous_tickets(report.subscriber_id, limit=10)
        payload["previous_tickets"] = previous_tickets or []
        logger.info(
            "++++++++++ AzureOpenAI analyze_coverage_report subscriber=%s prior_tickets=%s request=%s",
            report.subscriber_id,
            payload["previous_tickets"],
            payload,
        )

        if self._azure_client is None:
            self.last_status = "stub"
            self.last_error = "missing_openai_config"
            response = self._build_stub_result(report)
            self._persist_audit_record(
                report.report_id,
                payload,
                {"mode": "stub", "reason": "missing_openai_config"},
                status="stub",
                error="missing_openai_config",
            )
            logger.info("AzureOpenAI analyze_coverage_report response_mode=stub response=%s", response.model_dump())
            return response

        try:
            completion = self._azure_client.chat.completions.create(
                model=self.deployment,
                temperature=0.2,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a telecom RCA assistant. Return only valid JSON with keys: "
                            "root_cause_summary (string), confidence (float 0.0-1.0), "
                            "hypotheses (array of objects, each with type (string), description (string), "
                            "confidence (float 0.0-1.0)), and recommended_actions (array of strings). "
                            "Do not return hypotheses as plain strings; each must be an object with "
                            "type, description, and confidence fields."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps(payload),
                    },
                ],
            )
            raw_content = completion.choices[0].message.content or "{}"
            parsed = json.loads(raw_content)

            response = RCAAnalysisToolResult(
                report_id=report.report_id,
                root_cause_summary=parsed["root_cause_summary"],
                confidence=float(parsed["confidence"]),
                mode="live",
                hypotheses=parsed.get("hypotheses", []),
                recommended_actions=parsed.get("recommended_actions", []),
            )
            self.last_status = "live"
            self.last_error = None
            self._persist_audit_record(
                report.report_id,
                payload,
                {"raw_response": raw_content, "parsed_response": response.model_dump()},
                status="success",
            )
            logger.info("AzureOpenAI analyze_coverage_report response_mode=live response=%s", response.model_dump())
            return response
        except Exception as exc:
            self.last_status = "stub"
            self.last_error = str(exc)
            logger.exception("Live Azure Open AI call failed, falling back to stub result")
            response = self._build_stub_result(report)
            self._persist_audit_record(
                report.report_id,
                payload,
                {"mode": "stub", "error": str(exc)},
                status="error",
                error=str(exc),
            )
            logger.info("AzureOpenAI analyze_coverage_report response_mode=stub_after_error response=%s", response.model_dump())
            return response

    def _build_stub_result(self, report: CoverageAssessmentInput) -> RCAAnalysisToolResult:
        # This is intentionally a lightweight stub for the POC.
        # In a real implementation, this would call Azure OpenAI with a structured tool call.
        return RCAAnalysisToolResult(
            report_id=report.report_id,
            root_cause_summary=(
                "Localized network degradation and outage conditions are the most likely cause "
                "of the coverage issue in the current serving market."
            ),
            confidence=0.89,
            mode="stub",
            hypotheses=[
                {
                    "type": "outage",
                    "description": "Regional outage or service degradation detected in the serving market.",
                    "confidence": 0.88,
                },
                {
                    "type": "coverage",
                    "description": "Subscriber is in a degraded coverage area with intermittent service quality.",
                    "confidence": 0.74,
                },
            ],
            recommended_actions=[
                "Validate network outage feed for the serving market.",
                "Confirm registration and connectivity state for the subscriber.",
                "Escalate to network operations if the issue persists beyond policy thresholds.",
            ],
        )
