import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx

from app.mcp.tool_schema import (
    ServiceNowCreateIssueInput,
    ServiceNowGetIssueInput,
    ServiceNowIssueResult,
    ServiceNowUpdateIssueInput,
)


logger = logging.getLogger(__name__)


class ServiceNowMCPServer:
    """MCP-style ServiceNow tool adapter for incident create/get/update."""

    def __init__(self):
        self.instance_url = os.getenv("SERVICENOW_INSTANCE_URL", "").strip().rstrip("/")
        self.username = os.getenv("SERVICENOW_USERNAME", "").strip()
        self.password = os.getenv("SERVICENOW_PASSWORD", "").strip()
        verify_ssl_raw = os.getenv("SERVICENOW_VERIFY_SSL", "true").strip().lower()
        self.verify_ssl = verify_ssl_raw not in {"0", "false", "no"}
        self.ca_bundle = os.getenv("SERVICENOW_CA_BUNDLE", "").strip()
        self.timeout_s = float(os.getenv("SERVICENOW_TIMEOUT_SECONDS", "20"))

    def create_issue(self, request: ServiceNowCreateIssueInput) -> ServiceNowIssueResult:
        logger.info("ServiceNow MCP create_issue request=%s", request.model_dump())
        if not self._is_configured():
            response = ServiceNowIssueResult(
                mode="stub",
                action="create_issue",
                success=True,
                message="ServiceNow credentials are not configured; returning stub ticket",
                sys_id=f"stub-{request.report_id.lower()}",
                number=f"INC-STUB-{request.report_id}",
                state="1",
                short_description=request.short_description,
            )
            logger.info("ServiceNow MCP create_issue response=%s", response.model_dump())
            return response

        payload = {
            "short_description": request.short_description,
            "description": request.description,
            "category": request.category,
            "subcategory": request.subcategory,
            "impact": str(request.impact),
            "urgency": str(request.urgency),
            "contact_type": "api",
        }

        try:
            result = self._request("POST", "/api/now/table/incident", json_body=payload)
            response = ServiceNowIssueResult(
                mode="live",
                action="create_issue",
                success=True,
                message="Incident created",
                sys_id=result.get("sys_id"),
                number=result.get("number"),
                state=result.get("state"),
                short_description=result.get("short_description"),
            )
        except Exception as exc:
            logger.exception("ServiceNow MCP create_issue failed")
            response = ServiceNowIssueResult(
                mode="live",
                action="create_issue",
                success=False,
                message=self._format_error_message("create", exc),
            )

        logger.info("ServiceNow MCP create_issue response=%s", response.model_dump())
        return response

    def get_issue(self, request: ServiceNowGetIssueInput) -> ServiceNowIssueResult:
        logger.info("ServiceNow MCP get_issue request=%s", request.model_dump())
        if not self._is_configured():
            response = ServiceNowIssueResult(
                mode="stub",
                action="get_issue",
                success=False,
                message="ServiceNow credentials are not configured",
            )
            logger.info("ServiceNow MCP get_issue response=%s", response.model_dump())
            return response

        try:
            if request.sys_id:
                result = self._request(
                    "GET",
                    f"/api/now/table/incident/{request.sys_id}",
                    params={"sysparm_fields": "sys_id,number,state,short_description"},
                )
            elif request.number:
                query = f"number={request.number}"
                result = self._request(
                    "GET",
                    "/api/now/table/incident",
                    params={
                        "sysparm_query": query,
                        "sysparm_limit": "1",
                        "sysparm_fields": "sys_id,number,state,short_description",
                    },
                )
                rows = result if isinstance(result, list) else []
                if not rows:
                    return ServiceNowIssueResult(
                        mode="live",
                        action="get_issue",
                        success=False,
                        message="Incident not found",
                    )
                result = rows[0]
            else:
                return ServiceNowIssueResult(
                    mode="live",
                    action="get_issue",
                    success=False,
                    message="sys_id or number is required",
                )

            response = ServiceNowIssueResult(
                mode="live",
                action="get_issue",
                success=True,
                message="Incident fetched",
                sys_id=result.get("sys_id"),
                number=result.get("number"),
                state=result.get("state"),
                short_description=result.get("short_description"),
            )
        except Exception as exc:
            logger.exception("ServiceNow MCP get_issue failed")
            response = ServiceNowIssueResult(
                mode="live",
                action="get_issue",
                success=False,
                message=self._format_error_message("get", exc),
            )

        logger.info("ServiceNow MCP get_issue response=%s", response.model_dump())
        return response

    def update_issue(self, request: ServiceNowUpdateIssueInput) -> ServiceNowIssueResult:
        logger.info("ServiceNow MCP update_issue request=%s", request.model_dump())
        if not self._is_configured():
            response = ServiceNowIssueResult(
                mode="stub",
                action="update_issue",
                success=False,
                message="ServiceNow credentials are not configured",
            )
            logger.info("ServiceNow MCP update_issue response=%s", response.model_dump())
            return response

        sys_id = request.sys_id
        if not sys_id and request.number:
            fetched = self.get_issue(ServiceNowGetIssueInput(number=request.number))
            if fetched.success:
                sys_id = fetched.sys_id

        if not sys_id:
            response = ServiceNowIssueResult(
                mode="live",
                action="update_issue",
                success=False,
                message="sys_id or resolvable number is required",
            )
            logger.info("ServiceNow MCP update_issue response=%s", response.model_dump())
            return response

        payload: dict[str, Any] = {}
        if request.state is not None:
            payload["state"] = request.state
        if request.work_notes is not None:
            payload["work_notes"] = request.work_notes
        if request.comments is not None:
            payload["comments"] = request.comments

        if not payload:
            response = ServiceNowIssueResult(
                mode="live",
                action="update_issue",
                success=False,
                message="No update fields provided",
                sys_id=sys_id,
            )
            logger.info("ServiceNow MCP update_issue response=%s", response.model_dump())
            return response

        try:
            result = self._request("PATCH", f"/api/now/table/incident/{sys_id}", json_body=payload)
            response = ServiceNowIssueResult(
                mode="live",
                action="update_issue",
                success=True,
                message="Incident updated",
                sys_id=result.get("sys_id", sys_id),
                number=result.get("number"),
                state=result.get("state"),
                short_description=result.get("short_description"),
            )
        except Exception as exc:
            logger.exception("ServiceNow MCP update_issue failed")
            response = ServiceNowIssueResult(
                mode="live",
                action="update_issue",
                success=False,
                message=self._format_error_message("update", exc),
                sys_id=sys_id,
            )

        logger.info("ServiceNow MCP update_issue response=%s", response.model_dump())
        return response

    def _is_configured(self) -> bool:
        return bool(self.instance_url and self.username and self.password)

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, str] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        url = f"{self.instance_url}{path}"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        with httpx.Client(
            auth=(self.username, self.password),
            verify=self._build_verify_config(),
            timeout=self.timeout_s,
        ) as client:
            response = client.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                content=json.dumps(json_body) if json_body is not None else None,
            )
            response.raise_for_status()

        body = response.json()
        result = body.get("result")
        if result is None:
            raise ValueError("ServiceNow response missing result field")

        return result

    def _build_verify_config(self) -> bool | str:
        if not self.verify_ssl:
            return False

        if self.ca_bundle:
            ca_bundle_path = Path(self.ca_bundle)
            if not ca_bundle_path.exists():
                raise FileNotFoundError(f"SERVICENOW_CA_BUNDLE not found: {self.ca_bundle}")
            return str(ca_bundle_path)

        return True

    def _format_error_message(self, operation: str, exc: Exception) -> str:
        message = str(exc)
        if "CERTIFICATE_VERIFY_FAILED" in message or "unable to get local issuer certificate" in message:
            return (
                f"ServiceNow {operation} failed: TLS certificate verification failed. "
                "Set SERVICENOW_CA_BUNDLE to your corporate root CA bundle path, or set "
                "SERVICENOW_VERIFY_SSL=false only for local testing."
            )
        return f"ServiceNow {operation} failed: {exc}"
