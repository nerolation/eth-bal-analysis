import os
import sys
import copy
from typing import List
from pathlib import Path
from eth_utils import to_canonical_address


project_root = str(Path(__file__).parent.parent)
src_dir = os.path.join(project_root, "src")
sys.path.insert(0, src_dir)

from bal_builder import (
    get_storage_diff_from_block,
    get_balance_diff_from_block,
    get_code_diff_from_block,
    build_contract_nonce_diffs_from_state,
)

## Auxiliary functions


def single_transaction_trace(contract_address) -> List[dict]:
    pre_dict = {
        contract_address: {
            "balance": "0x01",
            "code": "0x61",
            "nonce": 1,
            "storage": {"0x01": "0x02"},
        }
    }
    result = {
        "pre": pre_dict,
        "post": copy.deepcopy(pre_dict),
    }
    trace_output = [
        {
            "txHash": "0xfdc",
            "result": result,
        }
    ]
    return trace_output


## Tests


def test_storage_diff_single_slot_update():
    contract_address = "0x1385cfe2ac49c92c28e63e51f9fcdcc06f93ed09"
    trace_output = single_transaction_trace(contract_address)
    trace_output[0]["result"]["post"][contract_address]["storage"]["0x01"] = "0x03"
    _, account_access_list = get_storage_diff_from_block(trace_output)
    # Single contract
    assert len(account_access_list) == 1
    # Correct contract address
    assert account_access_list[0].address == to_canonical_address(contract_address)
    # Single slot accessed
    assert len(account_access_list[0].accesses) == 1
    # Correct slot
    assert int.from_bytes(account_access_list[0].accesses[0].slot) == 1
    # Single transaction accessed the slot
    assert len(account_access_list[0].accesses[0].accesses) == 1
    # Correct transaction index accessed the slot
    assert account_access_list[0].accesses[0].accesses[0].tx_index == 0
    # Correct slot update by transaction
    assert (
        int.from_bytes(account_access_list[0].accesses[0].accesses[0].value_after) == 3
    )


def test_balance_diff_single_balance_update():
    contract_address = "0x1385cfe2ac49c92c28e63e51f9fcdcc06f93ed09"
    trace_output = single_transaction_trace(contract_address)
    trace_output[0]["result"]["post"][contract_address]["balance"] = "0x02"
    _, balance_diff_list = get_balance_diff_from_block(trace_output)
    # Single contract
    assert len(balance_diff_list) == 1
    # Correct contract address
    assert balance_diff_list[0].address == to_canonical_address(contract_address)
    # Single balance change
    assert len(balance_diff_list[0].changes) == 1
    # Correct tx index
    assert balance_diff_list[0].changes[0].tx_index == 0
    # Correct tx delta
    assert int.from_bytes(balance_diff_list[0].changes[0].delta) == 1


def test_code_diff_single_code_update():
    contract_address = "0x1385cfe2ac49c92c28e63e51f9fcdcc06f93ed09"
    trace_output = single_transaction_trace(contract_address)
    trace_output[0]["result"]["post"][contract_address]["code"] = "0x62"
    _, code_diff_list = get_code_diff_from_block(trace_output)
    # Single contract
    assert len(code_diff_list) == 1
    # Correct contract address
    assert code_diff_list[0].address == to_canonical_address(contract_address)
    # Single code change
    assert len(code_diff_list[0].changes) == 1
    # Correct tx index
    assert code_diff_list[0].changes[0].tx_index == 0
    # Correct new code
    assert code_diff_list[0].changes[0].new_code.hex() == "62"


def test_contract_nonce_diffs_eoa_nonce_update():
    contract_address = "0x1385cfe2ac49c92c28e63e51f9fcdcc06f93ed09"
    trace_output = single_transaction_trace(contract_address)
    del trace_output[0]["result"]["pre"][contract_address]["code"]
    del trace_output[0]["result"]["post"][contract_address]["code"]
    trace_output[0]["result"]["post"][contract_address]["nonce"] = 2
    # no nonce diffs
    _, nonce_diffs_list = build_contract_nonce_diffs_from_state(trace_output)
    assert len(nonce_diffs_list) == 0


def test_contract_nonce_diffs_contract_nonce_update():
    contract_address = "0x1385cfe2ac49c92c28e63e51f9fcdcc06f93ed09"
    trace_output = single_transaction_trace(contract_address)
    trace_output[0]["result"]["post"][contract_address]["nonce"] = 2
    # no nonce diffs
    _, nonce_diffs_list = build_contract_nonce_diffs_from_state(trace_output)
    assert len(nonce_diffs_list) == 1


def test_no_update():
    contract_address = "0x1385cfe2ac49c92c28e63e51f9fcdcc06f93ed09"
    trace_output = single_transaction_trace(contract_address)
    # no access updates
    _, account_access_list = get_storage_diff_from_block(trace_output)
    assert len(account_access_list) == 0
    # no balance diffs
    _, balance_diff_list = get_balance_diff_from_block(trace_output)
    assert len(balance_diff_list) == 0
    # no code diffs
    _, code_diff_list = get_code_diff_from_block(trace_output)
    assert len(code_diff_list) == 0
    # no nonce diffs
    _, nonce_diffs_list = build_contract_nonce_diffs_from_state(trace_output)
    assert len(nonce_diffs_list) == 0
