#!/usr/bin/env python3

import os
from typing import List
from brownie.network import accounts
from web3.main import Web3
from ocean_lib.example_config import get_config_dict
from ocean_lib.models.datatoken_base import DatatokenBase
from ocean_lib.ocean.ocean import Ocean
from ocean_lib.ocean.util import get_ocean_token_address
from ocean_lib.web3_internal.utils import connect_to_network


def distribute_ocean_tokens(
    ocean: Ocean,
    amount: int,
    recipients: List[str],
    ocean_deployer_wallet,
) -> None:
    """
    Mint OCEAN tokens to seller and buyer
    """
    OCEAN_token = DatatokenBase.get_typed(
        ocean.config_dict, address=get_ocean_token_address(ocean.config_dict)
    )

    for recipient in recipients:
        if OCEAN_token.balanceOf(recipient) < amount:
            OCEAN_token.mint(recipient, amount, {"from": ocean_deployer_wallet})


if __name__ == "__main__":
    connect_to_network("development")

    config = get_config_dict("development")
    ocean = Ocean(config)
    amount = Web3.toWei(10000, "ether")
    ocean_deployer_wallet = accounts.add(os.getenv("FACTORY_DEPLOYER_PRIVATE_KEY"))

    recipients = []
    for private_key_envvar in ["SELLER_AEA_KEY_ETHEREUM", "BUYER_AEA_KEY_ETHEREUM"]:
        private_key = os.environ.get(private_key_envvar)
        if not private_key:
            continue

        w = accounts.add(private_key)
        recipients.append(w.address)

    distribute_ocean_tokens(ocean, amount, recipients, ocean_deployer_wallet)
