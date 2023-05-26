import asyncio
import os

from aea.configurations.base import ConnectionConfig

from connections.connection import OceanConnection
from connections.utils import convert_to_bytes_format
from web3.main import Web3
from brownie.network import accounts

from distribute_OCEAN_tokens import distribute_ocean_tokens


def test_deploy_c2d_data_asset(caplog):
    """Tests deploying correctly a data asset for C2D."""

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

    assert "connected to Ocean with config.network_name = 'development'" in caplog.text
    assert "Received DEPLOY_D2C in connection" in caplog.text
    assert "DATA did = 'did:op:" in caplog.text
    did = caplog.records[-1].msg[12:-1]
    assert did.startswith("did:op:")


def test_deploy_algorithm(caplog):
    """Tests deploying correctly a data algorithm for C2D."""

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

    ocean.on_connect()

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

    assert "connected to Ocean with config.network_name = 'development'" in caplog.text
    assert "Received DEPLOY_ALGORITHM in connection" in caplog.text
    assert "ALGO did = 'did:op:" in caplog.text
    did = caplog.records[-1].msg[12:-1]
    assert did.startswith("did:op:")


def test_deploy_fixed_rate_exchange(caplog):
    """Tests deploying correctly a fixed rate exchange."""
    seller_wallet = accounts.add(os.environ["SELLER_AEA_KEY_ETHEREUM"])
    buyer_wallet = accounts.add(os.environ["BUYER_AEA_KEY_ETHEREUM"])
    deployer_wallet = accounts.add(os.environ["FACTORY_DEPLOYER_PRIVATE_KEY"])

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

    distribute_ocean_tokens(
        ocean=ocean.ocean,
        amount=Web3.toWei(10, "ether"),
        recipients=[seller_wallet.address, buyer_wallet.address],
        ocean_deployer_wallet=deployer_wallet,
    )

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

    did = caplog.records[-1].msg[12:-1]
    ddo = ocean.ocean.assets.resolve(did)
    datatoken_address = ddo.datatokens[0].get("address")

    fixed_rate = {
        "type": "CREATE_FIXED_RATE_EXCHANGE",
        "datatoken_address": datatoken_address,
        "ocean_amt": 1,
        "rate": 1,
    }

    ocean.on_send(**fixed_rate)

    assert "connected to Ocean with config.network_name = 'development'" in caplog.text
    assert "Received CREATE_FIXED_RATE_EXCHANGE in connection" in caplog.text
    assert "Fixed rate exchange created!" in caplog.text

    exchange_id = caplog.records[-2].msg[30:]
    exchange_id_bytes = convert_to_bytes_format(Web3, str(exchange_id))
    exchange_details = ocean.ocean.fixed_rate_exchange.getExchange(exchange_id_bytes)

    assert exchange_details[1] == datatoken_address
    assert exchange_details[5] == Web3.toWei(1, "ether")  # rate

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

    datatoken = ocean.ocean.get_datatoken(datatoken_address)

    receipt = {
        "type": "DOWNLOAD_JOB",
        "datatoken_address": datatoken_address,
        "asset_did": did,
        "datatoken_amt": 1,
        "exchange_id": exchange_id,
        "max_cost_ocean": 3,
    }

    ocean.on_send(**receipt)

    assert datatoken.balanceOf(buyer_wallet.address) == Web3.toWei(1, "ether")


def test_deploy_dispenser(caplog):
    """Tests deploying correctly a dispenser and dispense funds from it."""

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

    did = caplog.records[-1].msg[12:-1]
    ddo = ocean.ocean.assets.resolve(did)
    datatoken_address = ddo.datatokens[0].get("address")

    dispenser = {
        "type": "CREATE_DISPENSER",
        "datatoken_address": datatoken_address,
    }

    ocean.on_send(**dispenser)

    assert "connected to Ocean with config.network_name = 'development'" in caplog.text
    assert "Received CREATE_DISPENSER in connection" in caplog.text
    assert "Dispenser status: True" in caplog.text

    datatoken = ocean.ocean.get_datatoken(datatoken_address)
    assert datatoken.dispenser_status().active == True

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
        "datatoken_address": datatoken_address,
        "asset_did": did,
        "datatoken_amt": 1,
    }

    ocean.on_send(**receipt)

    buyer_wallet = accounts.add(os.environ["BUYER_AEA_KEY_ETHEREUM"])
    assert datatoken.balanceOf(buyer_wallet.address) == Web3.toWei(1, "ether")


def test_permission_dataset(caplog):
    """Tests updating datasets permissions."""

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

    assert "Permissions of dataset configured successfully." in caplog.text
