import httpx
from datetime import date, timedelta
import json
import sys

BASE_URL = "http://localhost:8000"

def run_e2e():
    print("=== STARTING END-TO-END VERIFICATION ===")
    
    with httpx.Client(base_url=BASE_URL, timeout=15.0) as client:
        # 1. Login Coordinator A (Block A)
        res = client.post("/api/auth/staff/login", json={
            "email": "coordinator.block_a@git.edu",
            "password": "Coord@123"
        })
        assert res.status_code == 200, f"Coord A login failed: {res.text}"
        coord_a_token = res.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {coord_a_token}"}
        print("✓ Step 1: Coordinator A logged in successfully.")

        # 2. Login Coordinator B (Block B)
        res = client.post("/api/auth/staff/login", json={
            "email": "coordinator.block_b@git.edu",
            "password": "Coord@123"
        })
        assert res.status_code == 200, f"Coord B login failed: {res.text}"
        coord_b_token = res.json()["access_token"]
        headers_b = {"Authorization": f"Bearer {coord_b_token}"}
        print("✓ Step 2: Coordinator B logged in successfully.")

        # Dates and room details
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        room_id = 81  # A-101 in Block A (Block id 13)
        block_a_id = 13
        slot_id = 25  # Period 1 (08:30 - 09:30)

        # Clean up any existing blocks on room for tomorrow from prior test runs
        existing_blocks = client.get("/api/coordinator/room-blocks", params={"room_id": room_id, "status": "all", "date_from": tomorrow, "date_to": tomorrow}, headers=headers_a)
        if existing_blocks.status_code == 200:
            for item in existing_blocks.json().get("items", []):
                if item.get("id") and item["id"] > 0:
                    client.post(f"/api/coordinator/room-blocks/{item['id']}/release", headers=headers_a)

        # 3. Check initial availability for tomorrow
        avail_res = client.get("/api/public/availability", params={
            "date": tomorrow,
            "slot_id": slot_id,
            "capacity": 30,
            "block_id": block_a_id
        })
        assert avail_res.status_code == 200, f"Avail check failed: {avail_res.text}"
        avail_rooms = [r["id"] for r in avail_res.json().get("available_rooms", [])]
        print(f"✓ Step 3: Initial availability check for tomorrow ({tomorrow}) - Room {room_id} available: {room_id in avail_rooms}")

        # 4. Check initial timetable
        tt_res = client.get("/api/public/timetable", params={
            "date": tomorrow,
            "block_id": block_a_id
        })
        assert tt_res.status_code == 200, f"Timetable check failed: {tt_res.text}"
        tt_grid = tt_res.json().get("grid", {})
        r81_cells = tt_grid.get(str(room_id), {})
        r81_slot25_initial = r81_cells.get(str(slot_id), "FREE")
        print(f"✓ Step 4: Initial timetable status for Room {room_id} slot {slot_id}: {r81_slot25_initial}")

        # 5. Block Room A-101 for tomorrow (Maintenance)
        block_payload = {
            "room_id": room_id,
            "date_from": tomorrow,
            "date_to": tomorrow,
            "slot_ids": [slot_id],
            "reason": "MAINTENANCE",
            "note": "HVAC system filter replacement and inspection"
        }
        create_block_res = client.post("/api/coordinator/room-blocks", json=block_payload, headers=headers_a)
        assert create_block_res.status_code == 201, f"Create block failed: {create_block_res.text}"
        created_block_data = create_block_res.json()
        created_blocks = created_block_data.get("blocks", [])
        assert len(created_blocks) >= 1, f"No blocks created: {created_block_data}"
        block_record_id = created_blocks[0]["id"]
        print(f"✓ Step 5: Created RoomBlock id={block_record_id} for Room {room_id} on {tomorrow} (Slot {slot_id})")

        # 6. Verify GET /api/coordinator/room-blocks lists the created block
        list_blocks_res = client.get("/api/coordinator/room-blocks", headers=headers_a)
        assert list_blocks_res.status_code == 200, f"List blocks failed: {list_blocks_res.text}"
        list_data = list_blocks_res.json()
        item_ids = [item["id"] for item in list_data.get("items", [])]
        assert block_record_id in item_ids, f"Created block {block_record_id} not found in coordinator block list: {item_ids}"
        
        # Find matching block item in response
        target_item = next(it for it in list_data["items"] if it["id"] == block_record_id)
        assert target_item["reason"] == "MAINTENANCE"
        assert target_item["status"] in ["UPCOMING", "ACTIVE"]
        assert target_item["room"]["name"] == "A-101"
        print(f"✓ Step 6: Blocked room confirmed in GET /api/coordinator/room-blocks (Status: {target_item['status']}, Summary: {list_data.get('summary_counts')})")

        # 7. Confirm timetable immediately reflects MAINTENANCE
        tt_after_res = client.get("/api/public/timetable", params={
            "date": tomorrow,
            "block_id": block_a_id
        })
        assert tt_after_res.status_code == 200
        tt_grid_after = tt_after_res.json().get("grid", {})
        r81_slot25_blocked = tt_grid_after.get(str(room_id), {}).get(str(slot_id))
        assert r81_slot25_blocked == "MAINTENANCE", f"Expected MAINTENANCE but got: {r81_slot25_blocked}"
        print(f"✓ Step 7: Timetable correctly shows status={r81_slot25_blocked}")

        # 8. Confirm availability search no longer includes Room A-101
        avail_after_res = client.get("/api/public/availability", params={
            "date": tomorrow,
            "slot_id": slot_id,
            "capacity": 30,
            "block_id": block_a_id
        })
        assert avail_after_res.status_code == 200
        avail_after_rooms = [r["id"] for r in avail_after_res.json().get("available_rooms", [])]
        assert room_id not in avail_after_rooms, f"Room {room_id} should NOT be available, but found in: {avail_after_rooms}"
        print(f"✓ Step 8: Room {room_id} successfully excluded from public availability search.")

        # 9. Verify Coordinator B CANNOT release Coordinator A's block (403 Forbidden)
        coord_b_try_release = client.post(
            f"/api/coordinator/room-blocks/{block_record_id}/release",
            headers=headers_b
        )
        assert coord_b_try_release.status_code == 403, f"Expected 403 Forbidden for unauthorized coordinator, got: {coord_b_try_release.status_code} {coord_b_try_release.text}"
        print(f"✓ Step 9: Unauthorized release attempt by Coordinator B was rejected with 403 Forbidden.")

        # 10. Coordinator A releases the block
        release_res = client.post(
            f"/api/coordinator/room-blocks/{block_record_id}/release",
            headers=headers_a
        )
        assert release_res.status_code == 200, f"Release failed: {release_res.status_code} {release_res.text}"
        release_data = release_res.json()
        assert release_data.get("is_released") == True
        print(f"✓ Step 10: Coordinator A successfully released block id={block_record_id}.")

        # 11. Confirm timetable immediately reflects FREE
        tt_released_res = client.get("/api/public/timetable", params={
            "date": tomorrow,
            "block_id": block_a_id
        })
        assert tt_released_res.status_code == 200
        tt_grid_released = tt_released_res.json().get("grid", {})
        r81_slot25_restored = tt_grid_released.get(str(room_id), {}).get(str(slot_id), "FREE")
        assert r81_slot25_restored == "FREE", f"Expected FREE but got: {r81_slot25_restored}"
        print(f"✓ Step 11: Timetable immediately updated back to status={r81_slot25_restored}.")

        # 12. Confirm availability search includes Room A-101 again
        avail_restored_res = client.get("/api/public/availability", params={
            "date": tomorrow,
            "slot_id": slot_id,
            "capacity": 30,
            "block_id": block_a_id
        })
        assert avail_restored_res.status_code == 200
        avail_restored_rooms = [r["id"] for r in avail_restored_res.json().get("available_rooms", [])]
        assert room_id in avail_restored_rooms, f"Room {room_id} should be available again, but was not in: {avail_restored_rooms}"
        print(f"✓ Step 12: Room {room_id} immediately reappeared in availability search.")

        # 13. Test bulk release
        bulk_block_payload = {
            "room_id": room_id,
            "date_from": tomorrow,
            "date_to": tomorrow,
            "slot_ids": [26, 27],
            "reason": "EXAM",
            "note": "Mid-term examinations"
        }
        bulk_create_res = client.post("/api/coordinator/room-blocks", json=bulk_block_payload, headers=headers_a)
        assert bulk_create_res.status_code == 201
        bulk_ids = [b["id"] for b in bulk_create_res.json().get("blocks", [])]
        assert len(bulk_ids) == 2
        print(f"✓ Step 13a: Created 2 exam blocks for bulk test: {bulk_ids}")

        bulk_release_res = client.post(
            "/api/coordinator/room-blocks/release-bulk",
            json={"ids": bulk_ids},
            headers=headers_a
        )
        assert bulk_release_res.status_code == 200
        assert bulk_release_res.json().get("released_count") == 2
        print(f"✓ Step 13b: Bulk release succeeded for blocks {bulk_ids}.")

        # 14. Test Overlapping Block Prevention
        first_block = client.post("/api/coordinator/room-blocks", json={
            "room_id": room_id,
            "date_from": tomorrow,
            "date_to": tomorrow,
            "slot_ids": [28],
            "reason": "MAINTENANCE",
            "note": "Projector repair"
        }, headers=headers_a)
        assert first_block.status_code == 201
        first_id = first_block.json()["blocks"][0]["id"]

        # Attempt overlap
        overlap_attempt = client.post("/api/coordinator/room-blocks", json={
            "room_id": room_id,
            "date_from": tomorrow,
            "date_to": tomorrow,
            "slot_ids": [28],
            "reason": "EXAM",
            "note": "Surprise Quiz"
        }, headers=headers_a)
        assert overlap_attempt.status_code == 400, f"Expected 400 for overlap, got: {overlap_attempt.status_code}"
        overlap_msg = overlap_attempt.json().get("detail", "")
        assert "already blocked" in overlap_msg
        print(f"✓ Step 14: Overlap prevention rejected duplicate block with clear error: '{overlap_msg}'")

        # Clean up step 14 block
        client.post(f"/api/coordinator/room-blocks/{first_id}/release", headers=headers_a)

        # 15. Test Indefinite Maintenance & Release
        # Login Admin to put room in maintenance
        admin_login = client.post("/api/auth/staff/login", json={
            "email": "admin@git.edu",
            "password": "Admin@123"
        })
        assert admin_login.status_code == 200
        admin_token = admin_login.json()["access_token"]
        headers_admin = {"Authorization": f"Bearer {admin_token}"}

        patch_res = client.patch(f"/api/admin/rooms/{room_id}/status", json={
            "status": "MAINTENANCE",
            "maintenance_note": "Electrical board short-circuit repair"
        }, headers=headers_admin)
        assert patch_res.status_code == 200

        # Coordinator sees room in room-blocks
        coord_blocks_maint = client.get("/api/coordinator/room-blocks", headers=headers_a)
        assert coord_blocks_maint.status_code == 200
        indef_items = [it for it in coord_blocks_maint.json().get("items", []) if it.get("is_indefinite")]
        assert len(indef_items) >= 1
        print(f"✓ Step 15a: Room under maintenance appears in Blocked Rooms list as indefinite item.")

        # Coordinator releases maintenance via POST /api/coordinator/rooms/{room_id}/release-maintenance
        release_maint_res = client.post(f"/api/coordinator/rooms/{room_id}/release-maintenance", headers=headers_a)
        assert release_maint_res.status_code == 200, f"Release maint failed: {release_maint_res.text}"
        release_maint_data = release_maint_res.json()
        assert release_maint_data["status"] == "ACTIVE"
        print(f"✓ Step 15b: Room maintenance released by coordinator back to ACTIVE.")

        print("\n=======================================================")
        print(">>> ALL END-TO-END VERIFICATION STEPS PASSED 100%! <<<")
        print("=======================================================")

if __name__ == "__main__":
    run_e2e()
