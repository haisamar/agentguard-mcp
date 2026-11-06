"""Opt-in live RPC test; synthetic ledger effects only, no Auth0/MCP claim.

Run from the backend root: python tests/verify_request_concurrency.py --live
Uses only AgentGuard's configured Supabase project and cleans its own fixtures.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import httpx
from dotenv import load_dotenv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", required=True)
    parser.parse_args()
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    url = os.environ["SUPABASE_URL"].rstrip("/")
    if url != "https://mvzsoxdxpszvslcelmpg.supabase.co":
        raise RuntimeError("This live check is restricted to the AgentGuard project")
    headers = {"apikey": os.environ["SUPABASE_SECRET_KEY"], "Content-Type": "application/json"}
    identity = "test-concurrency-not-human:" + uuid4().hex
    outcomes = []
    try:
        with httpx.Client(base_url=url + "/rest/v1/", headers=headers, timeout=30) as client:
            budget = client.get("rpc/autonomous_budget_status")
            budget.raise_for_status()
            if budget.json()["remaining_minor"] < 1:
                raise RuntimeError("Autonomous test requires one cent of available sandbox budget")
            for request_id, amount in [("same_small_request", 1), ("same_large_request", 75100)]:
                barrier = Barrier(8)
                def submit(_):
                    barrier.wait(timeout=30)
                    response = client.post("rpc/submit_refund_request", json={
                        "p_identity": identity, "p_request_id": request_id,
                        "p_account_id": "acct_001", "p_amount_minor": amount,
                        "p_currency": "USD", "p_reason": "Synthetic concurrent verification; no human approval",
                    })
                    response.raise_for_status()
                    return response.json()
                with ThreadPoolExecutor(max_workers=8) as pool:
                    results = list(pool.map(submit, range(8)))
                assert all(result == results[0] for result in results), "Concurrent responses diverged"
                assert results[0]["decision"] == ("ALLOW" if amount == 1 else "APPROVAL_REQUIRED")
                outcomes.append({"case": request_id, "calls": 8, "identical_results": True, "decision": results[0]["decision"]})
            for table, field, expected in [
                ("refund_requests", "identity", 2),
                ("autonomous_refund_receipts", "identity", 1),
                ("approvals", "requesting_identity", 1),
                ("audit_events", "identity", 2),
            ]:
                response = client.get(table, params={field: "eq." + identity, "select": "*"})
                response.raise_for_status()
                assert len(response.json()) == expected, f"Unexpected {table} count"
    finally:
        # Only this run's random identity is eligible for fixture cleanup.
        with httpx.Client(base_url=url + "/rest/v1/", headers=headers, timeout=30) as client:
            for table, field in [
                ("audit_events", "identity"), ("refund_requests", "identity"),
                ("autonomous_refund_receipts", "identity"), ("approvals", "requesting_identity"),
            ]:
                response = client.delete(table, params={field: "eq." + identity})
                response.raise_for_status()
                check = client.get(table, params={field: "eq." + identity, "select": "*"})
                check.raise_for_status()
                assert check.json() == [], f"Fixture cleanup incomplete: {table}"
    print(json.dumps({"test": "live-database-rpc-concurrency", "cases": outcomes,
                      "fixtures_cleaned": True, "real_payments": False}, indent=2))


if __name__ == "__main__":
    main()
