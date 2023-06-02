import os
import pytest

from aea.configurations.base import ConnectionConfig

from connections.connection import OceanConnection
from connections.utils import get_tx_dict, convert_to_bytes_format

from brownie.network import chain
from web3.main import Web3


def test_get_tx_dict_on_ganache(publisher_wallet):
    """Tests get_tx_dict function on Ganache."""

    os.environ["RPC_URL"] = "http://127.0.0.1:8545"
    os.environ["OCEAN_NETWORK_NAME"] = "development"
    ocean = OceanConnection(
        ConnectionConfig(
            "connection",
            "oceanprotocol",
            "0.1.0",
            ocean_network_name="development",
            key_path=os.environ["SELLER_AEA_KEY_ETHEREUM_PATH"],
        ),
        "None",
    )

    ocean.on_connect()

    tx_dict = get_tx_dict(ocean.ocean.config, publisher_wallet, chain)
    assert tx_dict == {"from": publisher_wallet}


def test_convert_to_bytes_format():
    """Tests convert_to_bytes_format function."""

    data = "0x026c072ecb088ee833e8e98776fe31e2779888852c7619ed9aa8ca4942e9608a"
    assert isinstance(data, str)
    new_data = convert_to_bytes_format(Web3, data=data)
    assert isinstance(new_data, bytes)
    assert len(new_data) == 32


def test_validation_errors():
    """Tests validation possible errors."""

    os.environ["RPC_URL"] = "http://127.0.0.1:8545"
    os.environ["OCEAN_NETWORK_NAME"] = "development"
    ocean = OceanConnection(
        ConnectionConfig(
            "connection",
            "oceanprotocol",
            "0.1.0",
            ocean_network_name="development",
            key_path=os.environ["SELLER_AEA_KEY_ETHEREUM_PATH"],
        ),
        "None",
    )

    ocean.on_connect()
    with pytest.raises(Exception) as e:
        kwargs = {"some_key": "some_value"}
        ocean.on_send(**kwargs)

    assert (
        e.value.args[0]
        == "Message type is not correctly provided. Please add the message type according to your action."
    )
