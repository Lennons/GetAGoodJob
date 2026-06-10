"""Test REST API endpoints."""


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


def test_version(client):
    resp = client.get("/api/version")
    assert resp.status_code == 200


def test_settings_read(client):
    resp = client.get("/api/settings")
    assert resp.status_code == 200


def test_settings_patch(client):
    resp = client.patch("/api/settings", json={"daily_chat_limit": 30})
    assert resp.status_code == 200


def test_resume_list(client):
    resp = client.get("/api/resumes")
    assert resp.status_code == 200


def test_jobs_list(client):
    resp = client.get("/api/jobs")
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


def test_automation_status(client):
    resp = client.get("/api/automation/playwright/status")
    assert resp.status_code == 200
    assert resp.json()["running"] is False


def test_reply_monitor_status(client):
    resp = client.get("/api/reply-monitor/status")
    assert resp.status_code == 200


def test_reply_logs(client):
    resp = client.get("/api/reply-logs")
    assert resp.status_code == 200


def test_events(client):
    resp = client.get("/api/events")
    assert resp.status_code == 200


def test_browser_status(client):
    resp = client.get("/api/setup/browser-status")
    assert resp.status_code == 200
