"""
database/seed.py
Seeds realistic sales calls and transcripts into the database, including the authentic
redacted sales transcript from the CIMET challenge.
"""

import os
import re
import json
from pathlib import Path
from database.connection import get_db

_ROOT_DIR = Path(__file__).resolve().parent.parent.parent
TRANSCRIPT_TXT_PATH = _ROOT_DIR / "transcript_content.txt"


def parse_raw_transcript(txt_path: Path) -> list[dict]:
    """
    Parses dialogue from transcript_content.txt into structured speaker turns.
    """
    if not txt_path.exists():
        return []

    lines = txt_path.read_text(encoding="utf-8").splitlines()
    turns = []
    current_speaker = None
    current_text = []

    dialogue_started = False
    turn_idx = 0
    current_ms = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Skip headers / page marks
        if stripped.startswith("--- PAGE") or stripped.startswith("Total pages") or "Masking legend" in stripped:
            continue
        if stripped in ("Redacted Call Transcript", "CONFIDENTIAL", "Page 1", "Page 2", "Page 3", "Page 4", "Page 5", "Page 6"):
            continue
        if stripped == "Transcript":
            dialogue_started = True
            continue

        if not dialogue_started:
            continue

        speaker_match = re.match(r"^Speaker\s*([12]):?$", stripped, re.IGNORECASE)
        if speaker_match:
            if current_speaker and current_text:
                text = " ".join(current_text).strip()
                words = len(text.split())
                duration_ms = max(2000, words * 300)
                turns.append({
                    "turn_index": turn_idx,
                    "speaker": "Customer" if current_speaker == "1" else "Agent",
                    "text": text,
                    "start_ms": current_ms,
                    "end_ms": current_ms + duration_ms,
                })
                current_ms += duration_ms + 800
                turn_idx += 1
                current_text = []

            current_speaker = speaker_match.group(1)
        else:
            if current_speaker:
                current_text.append(stripped)

    # Flush final turn
    if current_speaker and current_text:
        text = " ".join(current_text).strip()
        words = len(text.split())
        duration_ms = max(2000, words * 300)
        turns.append({
            "turn_index": turn_idx,
            "speaker": "Customer" if current_speaker == "1" else "Agent",
            "text": text,
            "start_ms": current_ms,
            "end_ms": current_ms + duration_ms,
        })

    return turns


async def seed_initial_data(test_mode: bool = False) -> None:
    """
    Populates database with the authentic call recording leads.
    """
    if test_mode:
        return

    async with get_db(test_mode=test_mode) as db:
        # ── 1. Real Audio Call Leads (Always Seeded) ──────────────────────────
        audio_leads = [
            {
                "id": "lead-audio-3613793",
                "retailer_id": "retailer-broadband",
                "retailer_name": "Dodo NBN",
                "agent_id": "agent-marco-01",
                "agent_name": "Marco Santos",
                "call_date": "2024-06-15",
                "crm_fields": json.dumps({
                    "customer_full_name": "Helen (Call 3613793)",
                    "audio_file": "3613793.mp3.mpeg",
                    "phone": "0412 345 678",
                    "email": "helen.customer@example.com",
                    "service_address": "14 Harbour Street, Parramatta NSW 2150",
                    "plan_price_intro": 42.90,
                    "plan_price_standard": 72.90,
                    "modem_upfront_cost": 0.00,
                    "delivery_days": "3 to 5 business days",
                }),
                "gate_status": "PENDING",
                "recording_url": "/audio/3613793.mp3.mpeg",
            },
            {
                "id": "lead-audio-3613794",
                "retailer_id": "retailer-broadband",
                "retailer_name": "Dodo NBN",
                "agent_id": "agent-marco-02",
                "agent_name": "Marco Santos",
                "call_date": "2024-06-16",
                "crm_fields": json.dumps({
                    "customer_full_name": "Helen (Call 3613794)",
                    "audio_file": "3613794.mp3.mpeg",
                    "phone": "0412 345 678",
                    "email": "helen.customer@example.com",
                    "service_address": "14 Harbour Street, Parramatta NSW 2150",
                    "plan_price_intro": 42.90,
                    "plan_price_standard": 72.90,
                    "modem_upfront_cost": 0.00,
                    "delivery_days": "3 to 5 business days",
                }),
                "gate_status": "PENDING",
                "recording_url": "/audio/3613794.mp3.mpeg",
            },
        ]

        data_dir = Path(__file__).resolve().parent.parent / "data"

        for lead in audio_leads:
            async with db.execute("SELECT id FROM leads WHERE id = ?", (lead["id"],)) as cur:
                existing = await cur.fetchone()
            if existing is None:
                await db.execute(
                    """INSERT INTO leads (id, retailer_id, retailer_name, agent_id, agent_name,
                                         call_date, crm_fields, gate_status, recording_url)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        lead["id"], lead["retailer_id"], lead["retailer_name"],
                        lead["agent_id"], lead["agent_name"], lead["call_date"],
                        lead["crm_fields"], lead["gate_status"], lead["recording_url"],
                    ),
                )
            else:
                await db.execute(
                    """UPDATE leads SET retailer_name = ?, agent_name = ?, crm_fields = ?, recording_url = ?
                       WHERE id = ?""",
                    (lead["retailer_name"], lead["agent_name"], lead["crm_fields"], lead["recording_url"], lead["id"]),
                )

            stem = lead["id"].split("-")[-1]
            json_file = data_dir / f"transcript_{stem}.json"
            if json_file.exists():
                async with db.execute("SELECT lead_id FROM transcripts WHERE lead_id = ?", (lead["id"],)) as tr_cur:
                    has_tr = await tr_cur.fetchone()
                if has_tr is None:
                    with open(json_file, "r", encoding="utf-8") as jf:
                        tr_data = json.load(jf)
                    await db.execute(
                        """INSERT OR REPLACE INTO transcripts (lead_id, turns, full_text, redacted, source)
                           VALUES (?, ?, ?, ?, ?)""",
                        (lead["id"], json.dumps(tr_data["turns"]), tr_data["full_text"], 0, f"pregenerated:{stem}"),
                    )

        await db.commit()

        # ── 2. Synthetic Test Leads (Only Seeded During Test Mode) ────────────
        if not test_mode:
            return

        # Check if authentic challenge lead already exists
        async with db.execute("SELECT COUNT(*) as cnt FROM leads WHERE id = 'lead-cimet-real-01'") as cursor:
            row = await cursor.fetchone()
            cimet_seeded = bool(row and row["cnt"] > 0)

        if not cimet_seeded:
            turns = parse_raw_transcript(TRANSCRIPT_TXT_PATH)
            from generate_timestamped_pdf import unredact_text
            for t in turns:
                t["text"] = unredact_text(t["text"])

            full_text = " ".join(t["text"] for t in turns) if turns else "Call dialogue"

            crm_fields_bb = {
                "customer_full_name": "Margaret Jenkins",
                "customer_name": "Margaret",
                "service_address": "14/28 Riverview Road, Parramatta NSW 2150",
                "delivery_address": "Unit 14, 28 Riverview Road, Parramatta NSW 2150",
                "email": "margaret.jenkins48@gmail.com",
                "phone": "0412 345 678",
                "plan_price_intro": 42.90,
                "plan_price_standard": 72.90,
                "modem_upfront_cost": 0.0,
                "delivery_days": "3 to 5 business days",
                "speed_tier": "25 Mbps",
                "contract_term": "Month to month",
                "current_provider": "iPrimus",
                "current_price": 65.0,
            }

            await db.execute(
                """
                INSERT OR REPLACE INTO leads (id, retailer_id, retailer_name, agent_id, agent_name, call_date, crm_fields, gate_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "lead-cimet-real-01",
                    "retailer-broadband",
                    "Dodo NBN",
                    "agent-cimet-12",
                    "Marcus Vance",
                    "2024-06-15",
                    json.dumps(crm_fields_bb),
                    "PENDING",
                ),
            )

            if turns:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO transcripts (lead_id, turns, full_text, redacted, source)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    ("lead-cimet-real-01", json.dumps(turns), full_text, 0, "authentic-pdf-transcript"),
                )

        # 2. Energy Challenge Lead (Sample)
        crm_fields_energy = {
            "customer_full_name": "David Miller",
            "email": "david.miller@example.com",
            "service_address": "88 Collins Street, Melbourne VIC 3000",
            "nmi": "6001234567",
            "peak_rate_cents": 28.5,
            "offpeak_rate_cents": 16.2,
            "supply_charge_cents": 110.0,
            "move_in_date": "2024-07-01",
        }

        await db.execute(
            """
            INSERT OR REPLACE INTO leads (id, retailer_id, retailer_name, agent_id, agent_name, call_date, crm_fields, gate_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "lead-energy-sample-01",
                "retailer-energy",
                "PowerGrid Energy",
                "agent-cimet-08",
                "Samantha Clark",
                "2024-06-20",
                json.dumps(crm_fields_energy),
                "PENDING",
            ),
        )

        energy_turns = [
            {"turn_index": 0, "speaker": "Agent", "text": "This call may be recorded for quality and training purposes. Can I confirm I am speaking with the account holder?", "start_ms": 0, "end_ms": 5000},
            {"turn_index": 1, "speaker": "Customer", "text": "Yes, David Miller speaking.", "start_ms": 5500, "end_ms": 7000},
            {"turn_index": 2, "speaker": "Agent", "text": "I am required to advise you that you have the right to compare energy offers on the Victorian Default Offer.", "start_ms": 7500, "end_ms": 12500},
            {"turn_index": 3, "speaker": "Customer", "text": "Got it, thank you.", "start_ms": 13000, "end_ms": 14500},
            {"turn_index": 4, "speaker": "Agent", "text": "Your peak usage rate is 28.5 cents per kilowatt hour and off-peak is 16.2 cents.", "start_ms": 15000, "end_ms": 20000},
        ]
        await db.execute(
            """
            INSERT OR REPLACE INTO transcripts (lead_id, turns, full_text, redacted, source)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("lead-energy-sample-01", json.dumps(energy_turns), "Energy conversation sample", 0, "sample-energy-call"),
        )

        # 3. Lead 3613790 — Illustrative Worked Example from Problem Statement
        # 30-minute call, Retailer 1, Agent A. Sale held due to email mismatch at 14:20.
        crm_fields_3613790 = {
            "customer_full_name": "Sarah Jenkins",
            "email": "sarah.jenkins@gmail.com",
            "service_address": "74 Riverview Road, Parramatta NSW 2150",
            "nmi": "6401928374",
            "peak_rate_cents": 28.5,
            "offpeak_rate_cents": 16.2,
            "supply_charge_cents": 115.0,
            "move_in_date": "2024-07-10",
        }

        await db.execute(
            """
            INSERT OR REPLACE INTO leads (id, retailer_id, retailer_name, agent_id, agent_name, call_date, crm_fields, gate_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "lead-3613790",
                "retailer-energy",
                "Retailer 1",
                "agent-A",
                "Agent A",
                "2024-06-18",
                json.dumps(crm_fields_3613790),
                "FAILED",
            ),
        )

        turns_3613790 = [
            {"turn_index": 0, "speaker": "Agent", "text": "Good morning, this call may be recorded for quality and training purposes. Speaking with Sarah Jenkins?", "start_ms": 0, "end_ms": 6000},
            {"turn_index": 1, "speaker": "Customer", "text": "Yes, Sarah speaking.", "start_ms": 6500, "end_ms": 8000},
            {"turn_index": 2, "speaker": "Agent", "text": "I am required to advise you that you have the right to compare energy offers on the Victorian Default Offer.", "start_ms": 135000, "end_ms": 142000},
            {"turn_index": 3, "speaker": "Customer", "text": "Understood, please proceed.", "start_ms": 143000, "end_ms": 145000},
            {"turn_index": 14, "speaker": "Agent", "text": "Your peak usage rate is twenty eight point five cents per kilowatt hour and off-peak is sixteen point two cents.", "start_ms": 520000, "end_ms": 528000},
            {"turn_index": 15, "speaker": "Customer", "text": "That sounds competitive compared to my current bill.", "start_ms": 529000, "end_ms": 533000},
            {"turn_index": 26, "speaker": "Agent", "text": "And for your confirmation email, I have recorded sarah.jenkins88@hotmail.com, is that correct?", "start_ms": 860000, "end_ms": 868000},
            {"turn_index": 27, "speaker": "Customer", "text": "Wait, no, my email is sarah.jenkins@gmail.com, not hotmail.", "start_ms": 869000, "end_ms": 876000},
            {"turn_index": 48, "speaker": "Agent", "text": "Thank you for choosing Retailer 1 today. Your welcome pack is being generated now. Have a great day.", "start_ms": 1780000, "end_ms": 1795000},
            {"turn_index": 49, "speaker": "Customer", "text": "Thank you, bye.", "start_ms": 1796000, "end_ms": 1800000},
        ]

        await db.execute(
            """
            INSERT OR REPLACE INTO transcripts (lead_id, turns, full_text, redacted, source)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "lead-3613790",
                json.dumps(turns_3613790),
                "Illustrative 30-minute sales call with email readback discrepancy.",
                0,
                "worked-example-lead-3613790",
            ),
        )

        # Seed the score run showing SALE HELD for lead-3613790
        await db.execute(
            """
            INSERT OR REPLACE INTO score_runs (id, lead_id, check_library_id, check_library_version, overall_status, gate_decision, score, run_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "run-3613790-auto",
                "lead-3613790",
                "energy-v1",
                "energy-v1",
                "FAIL",
                "FAILED",
                81.8,
                "2024-06-18T10:30:00Z",
            ),
        )

        # Seed check results for lead-3613790
        chk_items_3613790 = [
            ("chk-3613-01", "EN-001", "Recording Disclaimer", "VERBATIM", 1, 1, "PASS", 0.98, "this call may be recorded for quality and training purposes", None, 0, 0, "Recording disclaimer delivered at start of call."),
            ("chk-3613-02", "EN-002", "Account Holder Confirmed", "VERBATIM", 1, 1, "PASS", 0.96, "Speaking with Sarah Jenkins?", None, 0, 0, "Account holder verified."),
            ("chk-3613-03", "EN-003", "DMO/VDO Read Verbatim", "VERBATIM", 1, 1, "PASS", 0.95, "you have the right to compare energy offers on the Victorian Default Offer", None, 2, 135000, "VDO statement read accurately at 02:15."),
            ("chk-3613-04", "EN-005", "Peak Rate Quoted Correctly", "FACTUAL", 1, 1, "PASS", 0.99, "twenty eight point five cents per kilowatt hour", "28.5", 14, 520000, "Peak rate of 28.5c matches CRM truth."),
            ("chk-3613-05", "EN-006", "Off-Peak Rate Quoted Correctly", "FACTUAL", 1, 1, "PASS", 0.99, "sixteen point two cents", "16.2", 14, 520000, "Off-peak rate of 16.2c matches CRM truth."),
            ("chk-3613-06", "EN-008", "Email Address Confirmed", "FACTUAL", 1, 1, "FAIL", 0.92, "sarah.jenkins88@hotmail.com", "sarah.jenkins@gmail.com", 26, 860000, "Factual mismatch at 14:20: Agent read back hotmail.com; customer corrected to gmail.com. Sale held for TL verification."),
        ]

        for cid, chkid, name, ctype, is_crit, blocks, status, conf, said, exp, turn, ts, rsn in chk_items_3613790:
            await db.execute(
                """
                INSERT OR REPLACE INTO check_results (
                    id, run_id, check_id, check_name, check_type, is_critical, blocks_sale,
                    status, confidence, agent_said, expected_value, transcript_turn, timestamp_ms, reason, check_library_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (cid, "run-3613790-auto", chkid, name, ctype, is_crit, blocks, status, conf, said, exp, turn, ts, rsn, "energy-v1"),
            )

        await db.commit()
