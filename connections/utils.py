# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2018-2019 Fetch.AI Limited
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

import requests
from web3.main import Web3


def get_tx_dict(ocean_config: dict, wallet, chain) -> dict:
    if "polygon" in ocean_config["NETWORK_NAME"]:
        gas_resp = requests.get("https://gasstation-mainnet.matic.network/v2")

        if not gas_resp or gas_resp.status_code != 200:
            print(
                f"Invalid response from Polygon gas station. Retry with brownie values..."
            )

            return {
                "from": wallet,
                "priority_fee": chain.priority_fee,
                "max_fee": chain.base_fee + 2 * chain.priority_fee,
                "required_confs": 3,
            }

        return {
            "from": wallet,
            "priority_fee": Web3.toWei(
                gas_resp.json()["fast"]["maxPriorityFee"], "gwei"
            ),
            "max_fee": Web3.toWei(gas_resp.json()["fast"]["maxFee"], "gwei"),
            "required_confs": 3,
        }

    return {"from": wallet}


def convert_to_bytes_format(web3, data: str) -> bytes:
    """Converts a bytes string into bytes.
    Used for smart contracts calls."""

    bytes_data = web3.toBytes(hexstr=data)
    assert isinstance(bytes_data, bytes), "Invalid data provided."

    return bytes_data
