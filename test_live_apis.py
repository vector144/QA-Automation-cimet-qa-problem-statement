import json
from fastapi.testclient import TestClient
from main import app
from services.openrouter import MockOpenRouterClient
from unittest.mock import patch

client = TestClient(app)

print("=== 1. TEST GET /health ===")
r = client.get("/health")
print("Status:", r.status_code, r.json())

print("\n=== 2. TEST GET /api/leads ===")
r = client.get("/api/leads")
print("Status:", r.status_code)
for lead in r.json():
    print(f" - Lead: {lead['id']} | Retailer: {lead['retailer_name']} | Gate: {lead['gate_status']} | Has Transcript: {lead['has_transcript']}")

print("\n=== 3. TEST GET /api/leads/lead-cimet-real-01 ===")
r = client.get("/api/leads/lead-cimet-real-01")
print("Status:", r.status_code)
lead_data = r.json()
print(" - CRM Fields:", lead_data["crm_fields"])

print("\n=== 4. TEST POST /api/scoring/run/lead-cimet-real-01 ===")
def mock_responder(messages):
    content = messages[1]["content"]
    if "Recording Disclaimer" in content:
        return {
            "status": "PASS",
            "confidence": 0.98,
            "agent_said": "this call will be recorded for quality assuranceand, training purposes",
            "transcript_turn": 3,
            "reason": "Mandatory recording disclosure delivered.",
        }
    elif "Agent Identity Disclosed" in content:
        return {
            "status": "PASS",
            "confidence": 0.95,
            "agent_said": "This is [AGENT_NAME] from Internet's comparison",
            "transcript_turn": 1,
            "reason": "Agent disclosed name and company.",
        }
    elif "plan_price_intro" in content:
        return {
            "status": "PASS",
            "confidence": 0.99,
            "spoken_value": "42.90",
            "agent_said": "forty two dollars and ninety",
            "transcript_turn": 3,
            "reason": "Introductory price matches CRM.",
        }
    elif "plan_price_standard" in content:
        return {
            "status": "PASS",
            "confidence": 0.99,
            "spoken_value": "72.90",
            "agent_said": "Seventy two dollars and ninety",
            "transcript_turn": 3,
            "reason": "Standard price matches CRM.",
        }
    elif "customer_full_name" in content:
        return {"status": "PASS", "confidence": 0.95, "spoken_value": "[CUSTOMER_FULL_NAME]", "reason": "Name verified."}
    elif "email" in content:
        return {"status": "PASS", "confidence": 0.95, "spoken_value": "[EMAIL]", "reason": "Email verified."}
    elif "service_address" in content:
        return {"status": "PASS", "confidence": 0.95, "spoken_value": "[SERVICE_ADDRESS]", "reason": "Address verified."}
    elif "modem_upfront_cost" in content:
        return {"status": "PASS", "confidence": 0.99, "spoken_value": "0", "reason": "Free modem verified."}
    elif "delivery_days" in content:
        return {"status": "PASS", "confidence": 0.95, "spoken_value": "3 to 5 business days", "reason": "Delivery stated."}
    return {
        "status": "PASS",
        "confidence": 0.9,
        "agent_said": "Verified compliant",
        "transcript_turn": 3,
        "reason": "Passed check.",
    }

mock_llm = MockOpenRouterClient(responder_fn=mock_responder)

with patch("services.scoring.orchestrator.get_openrouter_client", return_value=mock_llm):
    r = client.post("/api/scoring/run/lead-cimet-real-01")
    print("Status:", r.status_code)
    run_res = r.json()
    print(f"Score: {run_res['score']}% | Gate: {run_res['gate_decision']} | Critical Fails: {run_res['critical_failed_count']}")
    print("Total checks evaluated:", len(run_res["check_results"]))
    for chk in run_res["check_results"][:5]:
        ts_sec = (chk["timestamp_ms"] or 0) / 1000
        mins = int(ts_sec // 60)
        secs = int(ts_sec % 60)
        print(f"  [{chk['status']}] {chk['check_name']} at {mins:02d}:{secs:02d} ({ts_sec:.1f}s) — Quote: {chk['agent_said']}")

print("\n=== 5. TEST GET /api/export/compliance-pack/lead-cimet-real-01 ===")
r = client.get("/api/export/compliance-pack/lead-cimet-real-01")
print("Status:", r.status_code)
pack = r.json()
print("Certified:", pack["compliance_certification"]["certified"])
print("Total checks in pack:", len(pack["checks"]))

print("\n=== 6. TEST GET /api/export/csv ===")
r = client.get("/api/export/csv")
print("Status:", r.status_code, "Content-Type:", r.headers["content-type"])
print("First 3 lines of CSV:")
for line in r.text.splitlines()[:3]:
    print(" ", line)

print("\n=== 7. TEST POST /api/reviews/lead-cimet-real-01/override ===")
override_payload = {
    "check_id": "BB-001",
    "reviewer_id": "qa-lead-sarah",
    "reviewer_name": "Sarah Miller (Senior QA)",
    "new_status": "PASS",
    "gate_status_override": "PASSED",
    "justification": "Checked recording audio at 00:13 — disclaimer stated clearly with quality disclosure.",
}
r = client.post("/api/reviews/lead-cimet-real-01/override", json=override_payload)
print("Status:", r.status_code, r.json())
