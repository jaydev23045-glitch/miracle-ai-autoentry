import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))

def test_dictionary_batch_slicing():
    print("==================================================")
    print("  TESTING AI MAPPING DICTIONARY BATCH SLICING    ")
    print("==================================================\n")

    # Mock 100 unmapped narration entries in a dictionary
    unique_susp_narrs = {f"UPI {i:012d} DEBIT PARTY {i}": {"tx_type": "Payment", "group_hint": ""} for i in range(1, 101)}

    narr_keys = list(unique_susp_narrs.keys())
    batch_size = 30
    narr_batches = [
        narr_keys[i : i + batch_size]
        for i in range(0, len(narr_keys), batch_size)
    ]

    print(f"Total Dictionary Keys  : {len(unique_susp_narrs)}")
    print(f"Total Batches Created   : {len(narr_batches)}")

    assert len(narr_batches) == 4, f"Expected 4 batches, got {len(narr_batches)}"
    assert len(narr_batches[0]) == 30, f"Batch 1 should have 30 items, got {len(narr_batches[0])}"
    assert len(narr_batches[3]) == 10, f"Batch 4 should have 10 items, got {len(narr_batches[3])}"

    print("\n✅ AI Mapping Dictionary Batch Slicing Test Passed 100%!")

if __name__ == "__main__":
    test_dictionary_batch_slicing()
