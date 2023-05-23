import os

from aea.configurations.base import ConnectionConfig

from connections.connection import OceanConnection


def test_main_flow():
    ocean = OceanConnection(
        ConnectionConfig(
            "connection",
            "oceanprotocol",
            "0.1.0",
            ocean_network_name=os.environ["OCEAN_NETWORK_NAME"],
            key_path=os.environ["SELLER_AEA_KEY_ETHEREUM_PATH"],
        ),
        "None",
    )

    ocean.connect()

    dataset = {
        "type": "DEPLOY_D2C",
        "dataset_url": "https://raw.githubusercontent.com/oceanprotocol/c2d-examples/main/branin_and_gpr/branin.arff",
        "name": "example",
        "description": "example",
        "author": "Trent",
        "license": "CCO",
        "has_pricing_schema": True,
    }

    ocean.on_send(**dataset)
