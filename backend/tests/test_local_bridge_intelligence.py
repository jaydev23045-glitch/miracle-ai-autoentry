import os
import sys
import tempfile
import pytest
from PIL import Image

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from miracle_bridge_agent import (
    init_client_intelligence_db,
    optimize_and_deduplicate_image,
    match_narration_locally,
    learn_and_prune_rules,
    LOCAL_INTEL_DB
)

def test_local_db_initialization():
    """Verify SQLite database and table structures are initialized correctly."""
    init_client_intelligence_db()
    assert os.path.exists(LOCAL_INTEL_DB)

def test_image_optimization_and_deduplication():
    """Verify image compression and SHA256 deduplication skip logic."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
        img = Image.new("RGB", (2000, 2000), color="white")
        img.save(tmp_file.name)
        img_path = tmp_file.name

    try:
        # First processing pass
        res1 = optimize_and_deduplicate_image(img_path, "TEST_CLIENT_01")
        assert res1["status"] == "success"
        assert "upload_path" in res1
        assert res1["file_hash"] is not None

        # Second processing pass (same file) -> should trigger duplicate skip!
        res2 = optimize_and_deduplicate_image(img_path, "TEST_CLIENT_01")
        assert res2["status"] == "duplicate_skipped"
        assert res2["file_hash"] == res1["file_hash"]
    finally:
        if os.path.exists(img_path):
            os.remove(img_path)

def test_self_learning_and_local_regex_match():
    """Verify self-learning rule registration and local sub-millisecond regex matching."""
    client_id = "TEST_CLIENT_02"
    narration = "NEFT-JAYESH TRADERS-GS12345"
    ledger_code = "AYECD7E8"
    direction = "DR"

    # Register rule via self-learning engine
    learn_and_prune_rules(client_id, narration, ledger_code, direction)

    # Test local matching
    match_res = match_narration_locally(client_id, "NEFT-JAYESH TRADERS-REF889", direction)
    assert match_res["matched"] is True
    assert match_res["ledger_code"] == ledger_code
    assert match_res["source"] == "client_local_regex"
