import asyncio
import os

from aea.configurations.base import ConnectionConfig

from connections.connection import OceanConnection


def test_compute_flow(caplog):
    """Tests compute flow."""

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

    loop = asyncio.get_event_loop()
    loop.run_until_complete(ocean.connect())

    ocean.on_connect()

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

    DATA_did = caplog.records[-1].msg[12:-1]

    algorithm = {
        "type": "DEPLOY_ALGORITHM",
        "language": "python",
        "format": "docker-image",
        "version": "0.1",
        "entrypoint": "python $ALGO",
        "image": "oceanprotocol/algo_dockers",
        "checksum": "sha256:8221d20c1c16491d7d56b9657ea09082c0ee4a8ab1a6621fa720da58b09580e4",
        "tag": "python-branin",
        "files_url": "https://raw.githubusercontent.com/oceanprotocol/c2d-examples/main/branin_and_gpr/gpr.py",
        "name": "gpr",
        "description": "gpr",
        "author": "Trent",
        "license": "CCO",
        "date_created": "2019-12-28T10:55:11Z",
        "has_pricing_schema": True,
    }

    ocean.on_send(**algorithm)

    ALGO_did = caplog.records[-1].msg[12:-1]

    permission = {
        "type": "PERMISSION_DATASET",
        "data_did": DATA_did,
        "algo_did": ALGO_did,
    }

    ocean.on_send(**permission)

    DATA_ddo = ocean.ocean.assets.resolve(DATA_did)
    DATA_datatoken = DATA_ddo.datatokens[0].get("address")

    dispenser = {
        "type": "CREATE_DISPENSER",
        "datatoken_address": DATA_datatoken,
    }

    ocean.on_send(**dispenser)

    ALGO_ddo = ocean.ocean.assets.resolve(ALGO_did)
    ALGO_datatoken = ALGO_ddo.datatokens[0].get("address")

    dispenser = {
        "type": "CREATE_DISPENSER",
        "datatoken_address": ALGO_datatoken,
    }

    ocean.on_send(**dispenser)

    # Purchase datatokens as buyer
    ocean = OceanConnection(
        ConnectionConfig(
            "connection",
            "oceanprotocol",
            "0.1.0",
            ocean_network_name=os.environ["OCEAN_NETWORK_NAME"],
            key_path=os.environ["BUYER_AEA_KEY_ETHEREUM_PATH"],
        ),
        "None",
    )

    loop = asyncio.get_event_loop()
    loop.run_until_complete(ocean.connect())

    ocean.on_connect()

    receipt = {
        "type": "DOWNLOAD_JOB",
        "datatoken_address": DATA_datatoken,
        "asset_did": DATA_did,
        "datatoken_amt": 1,
    }

    ocean.on_send(**receipt)

    receipt = {
        "type": "DOWNLOAD_JOB",
        "datatoken_address": ALGO_datatoken,
        "asset_did": ALGO_did,
        "datatoken_amt": 1,
    }

    ocean.on_send(**receipt)

    c2d_job = {"type": "D2C_JOB", "data_did": DATA_did, "algo_did": ALGO_did}

    ocean.on_send(**c2d_job)

    assert "Completed D2C!" in caplog.text
