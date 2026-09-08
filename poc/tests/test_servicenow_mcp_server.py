from app.mcp.servicenow_mcp_server import ServiceNowMCPServer
from app.mcp.tool_schema import (
    ServiceNowCreateIssueInput,
    ServiceNowGetIssueInput,
    ServiceNowUpdateIssueInput,
)


def test_create_issue_returns_stub_when_not_configured(monkeypatch):
    monkeypatch.delenv("SERVICENOW_INSTANCE_URL", raising=False)
    monkeypatch.delenv("SERVICENOW_USERNAME", raising=False)
    monkeypatch.delenv("SERVICENOW_PASSWORD", raising=False)

    server = ServiceNowMCPServer()
    result = server.create_issue(
        ServiceNowCreateIssueInput(
            report_id="CAR-202",
            subscriber_id="sub-202",
            serving_market="ATL-01",
            short_description="NORA Coverage Alert CAR-202 for sub-202",
            description="diagnostic payload",
        )
    )

    assert result.mode == "stub"
    assert result.action == "create_issue"
    assert result.success is True
    assert result.number == "INC-STUB-CAR-202"


def test_create_issue_uses_live_path_when_configured(monkeypatch):
    monkeypatch.setenv("SERVICENOW_INSTANCE_URL", "https://example.service-now.com")
    monkeypatch.setenv("SERVICENOW_USERNAME", "admin")
    monkeypatch.setenv("SERVICENOW_PASSWORD", "secret")

    server = ServiceNowMCPServer()

    def fake_request(method, path, params=None, json_body=None):
        assert method == "POST"
        assert path == "/api/now/table/incident"
        assert json_body is not None
        return {
            "sys_id": "abc123",
            "number": "INC0010002",
            "state": "1",
            "short_description": json_body["short_description"],
        }

    monkeypatch.setattr(server, "_request", fake_request)

    result = server.create_issue(
        ServiceNowCreateIssueInput(
            report_id="CAR-202",
            subscriber_id="sub-202",
            serving_market="ATL-01",
            short_description="NORA Coverage Alert CAR-202 for sub-202",
            description="diagnostic payload",
        )
    )

    assert result.mode == "live"
    assert result.success is True
    assert result.number == "INC0010002"
    assert result.sys_id == "abc123"


def test_get_issue_by_number(monkeypatch):
    monkeypatch.setenv("SERVICENOW_INSTANCE_URL", "https://example.service-now.com")
    monkeypatch.setenv("SERVICENOW_USERNAME", "admin")
    monkeypatch.setenv("SERVICENOW_PASSWORD", "secret")

    server = ServiceNowMCPServer()

    def fake_request(method, path, params=None, json_body=None):
        assert method == "GET"
        assert path == "/api/now/table/incident"
        assert params is not None
        assert "number=INC0010002" in params.get("sysparm_query", "")
        return [
            {
                "sys_id": "abc123",
                "number": "INC0010002",
                "state": "1",
                "short_description": "test",
            }
        ]

    monkeypatch.setattr(server, "_request", fake_request)

    result = server.get_issue(ServiceNowGetIssueInput(number="INC0010002"))

    assert result.success is True
    assert result.number == "INC0010002"


def test_update_issue_by_sys_id(monkeypatch):
    monkeypatch.setenv("SERVICENOW_INSTANCE_URL", "https://example.service-now.com")
    monkeypatch.setenv("SERVICENOW_USERNAME", "admin")
    monkeypatch.setenv("SERVICENOW_PASSWORD", "secret")

    server = ServiceNowMCPServer()

    def fake_request(method, path, params=None, json_body=None):
        assert method == "PATCH"
        assert path == "/api/now/table/incident/abc123"
        assert json_body == {"state": "2", "work_notes": "Acknowledged"}
        return {
            "sys_id": "abc123",
            "number": "INC0010002",
            "state": "2",
            "short_description": "test",
        }

    monkeypatch.setattr(server, "_request", fake_request)

    result = server.update_issue(
        ServiceNowUpdateIssueInput(
            sys_id="abc123",
            state="2",
            work_notes="Acknowledged",
        )
    )

    assert result.success is True
    assert result.state == "2"


def test_build_verify_config_uses_ca_bundle(monkeypatch, tmp_path):
    monkeypatch.setenv("SERVICENOW_INSTANCE_URL", "https://example.service-now.com")
    monkeypatch.setenv("SERVICENOW_USERNAME", "admin")
    monkeypatch.setenv("SERVICENOW_PASSWORD", "secret")
    ca_bundle = tmp_path / "corp-ca.pem"
    ca_bundle.write_text("dummy", encoding="utf-8")
    monkeypatch.setenv("SERVICENOW_CA_BUNDLE", str(ca_bundle))

    server = ServiceNowMCPServer()

    assert server._build_verify_config() == str(ca_bundle)


def test_create_issue_reports_certificate_failure_hint(monkeypatch):
    monkeypatch.setenv("SERVICENOW_INSTANCE_URL", "https://example.service-now.com")
    monkeypatch.setenv("SERVICENOW_USERNAME", "admin")
    monkeypatch.setenv("SERVICENOW_PASSWORD", "secret")

    server = ServiceNowMCPServer()

    def fake_request(method, path, params=None, json_body=None):
        raise RuntimeError(
            "[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate"
        )

    monkeypatch.setattr(server, "_request", fake_request)

    result = server.create_issue(
        ServiceNowCreateIssueInput(
            report_id="CAR-202",
            subscriber_id="sub-202",
            serving_market="ATL-01",
            short_description="NORA Coverage Alert CAR-202 for sub-202",
            description="diagnostic payload",
        )
    )

    assert result.success is False
    assert "SERVICENOW_CA_BUNDLE" in result.message
    assert "SERVICENOW_VERIFY_SSL=false" in result.message
