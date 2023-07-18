# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2018-2023 Fetch.AI Limited
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
"""Scaffold connection and channel."""
from typing import Any, Optional

from aea.configurations.base import PublicId
from aea.connections.base import BaseSyncConnection, Connection
from aea.mail.base import Envelope

import os
from datetime import datetime, timedelta, timezone
from typing import Any
from brownie.network import accounts, chain, priority_fee, web3


from aea.configurations.base import PublicId
from aea.connections.base import BaseSyncConnection
from ocean_connection.connections.ocean_connection.utils import (
    convert_to_bytes_format,
    get_tx_dict,
    validate_args,
)
from ocean_lib.example_config import get_config_dict
from ocean_lib.models.compute_input import ComputeInput
from ocean_lib.models.fixed_rate_exchange import OneExchange
from ocean_lib.ocean.ocean import Ocean
from ocean_lib.ocean.util import to_wei
from ocean_lib.web3_internal.constants import ZERO_ADDRESS
from ocean_lib.web3_internal.utils import connect_to_network
from web3.main import Web3


"""
Choose one of the possible implementations:

Sync (inherited from BaseSyncConnection) or Async (inherited from Connection) connection and remove unused one.
"""

CONNECTION_ID = PublicId.from_str("ocean_protocol/ocean_connection:0.1.3")


class OceanConnection(BaseSyncConnection):
    """Proxy to the functionality of the SDK or API."""

    connection_id = CONNECTION_ID

    MAX_WORKER_THREADS = 5

    def __init__(self, *args: Any, **kwargs: Any) -> None:  # pragma: no cover
        """
        Initialize the connection.

        The configuration must be specified if and only if the following
        parameters are None: connection_id, excluded_protocols or restricted_to_protocols.

        Possible arguments:
        - configuration: the connection configuration.
        - data_dir: directory where to put local files.
        - identity: the identity object held by the agent.
        - crypto_store: the crypto store for encrypted communication.
        - restricted_to_protocols: the set of protocols ids of the only supported protocols for this connection.
        - excluded_protocols: the set of protocols ids that we want to exclude for this connection.

        :param args: arguments passed to component base
        :param kwargs: keyword arguments passed to component base
        """
        super().__init__(*args, **kwargs)
        self.logger.setLevel(10)

    def main(self) -> None:
        """
        Run synchronous code in background.

        SyncConnection `main()` usage:
        The idea of the `main` method in the sync connection
        is to provide for a way to actively generate messages by the connection via the `put_envelope` method.

        A simple example is the generation of a message every second:
        ```
        while self.is_connected:
            envelope = make_envelope_for_current_time()
            self.put_envelope(envelope)
            time.sleep(1)
        ```
        In this case, the connection will generate a message every second
        regardless of envelopes sent to the connection by the agent.
        For instance, this way one can implement periodically polling some internet resources
        and generate envelopes for the agent if some updates are available.
        Another example is the case where there is some framework that runs blocking
        code and provides a callback on some internal event.
        This blocking code can be executed in the main function and new envelops
        can be created in the event callback.
        """

    def on_send(self, **kwargs) -> None:
        """
        Send a message.

        param kwargs: the kwargs to use.
        """
        if "type" not in kwargs or kwargs["type"] not in [
            "DEPLOY_C2D",
            "DEPLOY_ALGORITHM",
            "PERMISSION_DATASET",
            "C2D_JOB",
            "DEPLOY_DATA_DOWNLOAD",
            "CREATE_DISPENSER",
            "CREATE_FIXED_RATE_EXCHANGE",
            "DOWNLOAD_JOB",
        ]:
            raise Exception(
                "Message type is not correctly provided. Please add the message type according to your action."
            )
        message_type = kwargs["type"]
        self.logger.debug(f"Received {message_type} in connection")

        if message_type == "DEPLOY_C2D":
            self._deploy_data_for_C2D(**kwargs)
        if message_type == "DEPLOY_ALGORITHM":
            self._deploy_algorithm(**kwargs)
        if message_type == "PERMISSION_DATASET":
            self._permission_dataset(**kwargs)
        if message_type == "C2D_JOB":
            self._create_C2D_job(**kwargs)
        if message_type == "DEPLOY_DATA_DOWNLOAD":
            self._deploy_data_to_download(**kwargs)
        if message_type == "CREATE_DISPENSER":
            self._create_dispenser(**kwargs)
        if message_type == "CREATE_FIXED_RATE_EXCHANGE":
            self._create_fixed_rate(**kwargs)
        if message_type == "DOWNLOAD_JOB":
            self._purchase_datatoken(**kwargs)

    def _purchase_datatoken(self, **kwargs):
        """
        Buys datatokens available on the fixed rate exchange in order to consume services.

        param kwargs: necessary parameters to use.
        They are:
        - `datatoken_address`;
        - `asset_did`;
        - `datatoken_amt`;
        - optional: `exchange_id` if there exists a fixed rate exchange attached to the datatoken
        - optional: `max_cost_ocean` if there exists a fixed rate exchange attached to the datatoken
        """
        valid, validation_message = validate_args(**kwargs)
        if not valid:
            raise Exception(f"{validation_message}")
        else:
            try:
                datatoken_address = kwargs["datatoken_address"]
                asset_did = kwargs["asset_did"]
                datatoken_amt = kwargs["datatoken_amt"]

                if "exchange_id" in kwargs:
                    self.logger.info("Starting to buy DTs from fixed rate exchange...")
                    exchange_id = kwargs["exchange_id"]
                    max_cost_ocean = kwargs["max_cost_ocean"]
                    self._buy_dt_from_fre(
                        exchange_id=exchange_id,
                        datatoken_amt=datatoken_amt,
                        max_cost_ocean=max_cost_ocean,
                    )
                    msg = {
                        "type": "DOWNLOAD_JOB",
                        "datatoken_address": datatoken_address,
                        "datatoken_amt": datatoken_amt,
                        "max_cost_ocean": max_cost_ocean,
                        "asset_did": asset_did,
                        "exchange_id": str(exchange_id),
                        "has_pricing_schema": True,
                    }
                else:
                    self.logger.info("Request DTs from the dispenser")
                    tx = self._dispense(
                        datatoken_address=datatoken_address,
                        datatoken_amt=datatoken_amt,
                    )
                    msg = {
                        "type": "DOWNLOAD_JOB",
                        "datatoken_address": datatoken_address,
                        "datatoken_amt": datatoken_amt,
                        "asset_did": asset_did,
                        "order_tx_id": tx.txid,
                        "has_pricing_schema": False,
                    }

                self.logger.info(f"Purchased datatokens successfully!")
                return msg

            except Exception as e:
                self.logger.error("Couldn't purchase datatokens")
                self.logger.error(e)

    def _download_asset(self, retries: int = 2, **kwargs):
        """
        Downloads files from the asset.

        param retries: number of retries for downloading the asset.
        param kwargs: necessary parameters to use.
        They are:
        - `datatoken_address`;
        - `asset_did`;
        - `datatoken_amt`;
        - optional: `exchange_id` if there exists a fixed rate exchange attached to the datatoken
        - optional: `max_cost_ocean` if there exists a fixed rate exchange attached to the datatoken
        - optional: `order_tx_id` if there exists a dispenser attached to the datatoken
        """
        valid, validation_message = validate_args(**kwargs)
        if not valid:
            raise Exception(f"{validation_message}")
        else:
            did = kwargs["asset_did"]
            datatoken = self.ocean.get_datatoken(kwargs["datatoken_address"])
            datatoken_amt = kwargs["datatoken_amt"]

            if datatoken.balanceOf(self.wallet.address) < datatoken_amt:
                self.logger.info(f"Insufficient datatokens. Purchasing right now ...")
                if "exchange_id" in kwargs:
                    exchange_id = kwargs["exchange_id"]
                    max_cost_ocean = kwargs["max_cost_ocean"]
                    self._buy_dt_from_fre(
                        exchange_id=exchange_id,
                        datatoken_amt=datatoken_amt,
                        max_cost_ocean=max_cost_ocean,
                    )
                else:
                    self._dispense(
                        datatoken_address=kwargs["datatoken_address"],
                        datatoken_amt=datatoken_amt,
                    )
            else:
                self.logger.info(f"Already has sufficient datatokens.")

            asset = self.ocean.assets.resolve(did)
            if retries == 0:
                raise ValueError("Failed to pay for compute service after retrying.")

            try:
                if "exchange_id" in kwargs:
                    tx_dict = get_tx_dict(self.ocean_config, self.wallet, chain)
                    order_tx_id = self.ocean.assets.pay_for_access_service(
                        asset=asset,
                        tx_dict=tx_dict,
                    )
                else:
                    order_tx_id = kwargs["order_tx_id"]
                self.logger.info(f"Order tx: '{order_tx_id}'")
            except Exception as e:
                self.logger.error(
                    f"Failed to pay for access service with error: {e}\n Retrying..."
                )
                self._download_asset(retries - 1, **kwargs)

            # Download has begun for the agent. If the connection breaks, agent can request again by showing order_tx_id.
            file_path = self.ocean.assets.download(
                asset=asset,
                consumer_wallet=self.wallet,
                destination="./downloads/",
                order_tx_id=order_tx_id,
            )
            self.logger.info(f"file_path = {file_path}")
            data = open(file_path, "rb").read()

            self.logger.info(f"Download completed!")
            msg = {"type": "RESULTS", "data": data}

            return msg

    def _create_dispenser(self, retries: int = 2, **kwargs):
        """
        Deploys a dispenser.

        param retries: number of retries for creating the dispenser.
        param kwargs: necessary parameters to use.
        They are:
        - `datatoken_address`
        """
        valid, validation_message = validate_args(**kwargs)
        if not valid:
            raise Exception(f"{validation_message}")
        else:
            if retries == 0:
                raise ValueError("Failed to deploy dispenser after retrying.")
            try:
                datatoken_address = kwargs["datatoken_address"]
                self._create_dispenser_helper(datatoken_address)
                datatoken = self.ocean.get_datatoken(datatoken_address)
                dispenser_status = datatoken.dispenser_status().active
                self.logger.info(f"Dispenser status: {dispenser_status}")
                msg = {
                    "type": "DISPENSER_DEPLOYMENT_RECEIPT",
                    "datatoken_address": datatoken.address,
                    "dispenser_status": dispenser_status,
                    "has_pricing_schema": False,
                }
                self.logger.info(f"Dispenser created!")

                return msg
            except Exception as e:
                self.logger.error(
                    f"Failed to deploy dispenser with the following error: {e}. Retrying..."
                )
                self._create_dispenser(retries - 1, **kwargs)

    def _create_fixed_rate(self, retries: int = 2, **kwargs):
        """
        Creates a fixed rate exchange with OCEAN as base tokens.

        param retries: number of retries for creating the FRE.
        param kwargs: necessary parameters to use.
        They are:
        - `datatoken_address`;
        - `rate`;
        - `ocean_amt`
        """
        valid, validation_message = validate_args(**kwargs)
        if not valid:
            raise Exception(f"{validation_message}")
        else:
            if retries == 0:
                raise ValueError("Failed to deploy fixed rate exchange after retrying.")
            try:
                datatoken_address = kwargs["datatoken_address"]
                ocean_amt = kwargs["ocean_amt"]
                rate = kwargs["rate"]
                exchange_id = self._create_fixed_rate_helper(
                    datatoken_address=datatoken_address, ocean_amt=ocean_amt, rate=rate
                )
                self.logger.info(f"Deployed fixed rate exchange: {exchange_id}")
                msg = {
                    "type": "EXCHANGE_DEPLOYMENT_RECEIPT",
                    "exchange_id": str(exchange_id),
                    "has_pricing_schema": True,
                }
                self.logger.info(f"Fixed rate exchange created!")

                return msg
            except Exception as e:
                self.logger.error(
                    f"Failed to deploy fixed rate exchange with the following error {e}. Retrying..."
                )
                self._create_fixed_rate(retries - 1, **kwargs)

    def _create_C2D_job(self, retries: int = 4, **kwargs):
        """
        Pays for compute service & starts the compute job.

        param retries: number of retries for starting a compute job.
        param kwargs: necessary parameters to use.
        They are:
        - `data_did`;
        - `algo_did`
        """
        valid, validation_message = validate_args(**kwargs)
        if not valid:
            raise Exception(f"{validation_message}")
        else:
            DATA_did = kwargs["data_did"]
            ALG_did = kwargs["algo_did"]
            DATA_DDO = self.ocean.assets.resolve(DATA_did)
            ALG_DDO = self.ocean.assets.resolve(ALG_did)

            compute_service = DATA_DDO.services[1]
            algo_service = ALG_DDO.services[0]

            self.logger.info(f"Paying for dataset {DATA_did}...")
            if retries == 0:
                raise ValueError("Failed to pay for compute service after retrying.")
            try:
                c2d_env = self.ocean.compute.get_c2d_environments(
                    service_endpoint=compute_service.service_endpoint,
                    chain_id=DATA_DDO.chain_id,
                )[0]
                self.logger.info(f"c2d env: {c2d_env}")

                if "feeToken" in c2d_env.keys():
                    fee_datatoken = self.ocean.get_datatoken(c2d_env["feeToken"])
                    fee_datatoken.approve(
                        compute_service.datatoken, to_wei(100), {"from": self.wallet}
                    )
                    fee_datatoken.approve(
                        c2d_env["consumerAddress"], to_wei(100), {"from": self.wallet}
                    )

                DATA_compute_input = ComputeInput(DATA_DDO, compute_service)
                ALGO_compute_input = ComputeInput(ALG_DDO, algo_service)

                tx_dict = get_tx_dict(self.ocean_config, self.wallet, chain)
                datasets, algorithm = self.ocean.assets.pay_for_compute_service(
                    datasets=[DATA_compute_input],
                    algorithm_data=ALGO_compute_input,
                    compute_environment=c2d_env["id"],
                    valid_until=int(
                        (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp()
                    ),
                    consume_market_order_fee_address=compute_service.datatoken,
                    tx_dict=tx_dict,
                    consumer_address=c2d_env["consumerAddress"],
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to pay for compute service with error: {e}\n Retrying..."
                )
                self._create_C2D_job(retries - 1, **kwargs)

            self.logger.info(
                f"Paid for dataset {DATA_did} receipt: {[dataset.as_dictionary() for dataset in datasets]} with algorithm {algorithm.as_dictionary()}"
            )

            self.logger.info(f"Starting compute job....")
            job_id = self.ocean.compute.start(
                consumer_wallet=self.wallet,
                dataset=datasets[0],
                compute_environment=c2d_env["id"],
                algorithm=algorithm,
            )

            self.logger.info(f"Started compute job with job id: {job_id}")

            msg = {"type": "RESULTS", "job_id": job_id}

            return msg

    def _permission_dataset(self, retries: int = 2, **kwargs):
        """
        Updates the trusted algorithm publishers list in order to start a compute job.

        param retries: number of retries for updating trusted algorithm publishers list.
        param kwargs: necessary parameters to use.
        They are:
        - `data_did`;
        - `algo_did`
        """
        valid, validation_message = validate_args(**kwargs)
        if not valid:
            raise Exception(f"{validation_message}")
        else:
            data_ddo = self.ocean.assets.resolve(kwargs["data_did"])
            algo_ddo = self.ocean.assets.resolve(kwargs["algo_did"])

            if data_ddo is None or algo_ddo is None:
                raise ValueError(
                    f"Unable to loaded the assets from their DIDs. Please confirm correct deployment on Ocean!"
                )

            compute_service = data_ddo.services[1]
            compute_service.add_publisher_trusted_algorithm(algo_ddo)

            if retries == 0:
                raise ValueError("Failed to create data asset after retrying.")
            try:
                tx_dict = get_tx_dict(self.ocean_config, self.wallet, chain)
                data_ddo = self.ocean.assets.update(
                    data_ddo,
                    tx_dict,
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to update asset permissions with error: {e}\n Retrying..."
                )
                self._permission_dataset(retries - 1, **kwargs)

            msg = {
                "type": "DEPLOYMENT_RECEIPT",
                "did": data_ddo.did,
                "datatoken_contract_address": data_ddo.datatokens[0].get("address"),
            }

            self.logger.info(f"Permissions of dataset configured successfully.")

            return msg

    def _deploy_data_to_download(self, retries: int = 2, **kwargs):
        """
        Creates an Ocean asset with access service.

        param kwargs: necessary parameters to use.
        They are:
        - `description`;
        - `name`;
        - `author`;
        - `license`;
        - `dataset_url`;
        - `has_pricing_schema`
        """
        valid, validation_message = validate_args(**kwargs)
        if not valid:
            raise Exception(f"{validation_message}")
        else:
            if retries == 0:
                raise ValueError("Failed to create data asset after retrying.")

            DATA_metadata = {
                "created": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "description": kwargs["description"],
                "name": kwargs["name"],
                "type": "dataset",
                "author": kwargs["author"],
                "license": kwargs["license"],
            }
            try:
                tx_dict = get_tx_dict(self.ocean_config, self.wallet, chain)
                (
                    DATA_data_nft,
                    DATA_datatoken,
                    DATA_ddo,
                ) = self.ocean.assets.create_url_asset(
                    kwargs["name"],
                    kwargs["dataset_url"],
                    tx_dict,
                    metadata=DATA_metadata,
                    wait_for_aqua=True,
                )

                self.logger.info(f"DATA did = '{DATA_ddo.did}'")
            except Exception as error:
                self.logger.error(f"Error with creating asset. {error}. Retrying...")
                self._deploy_data_to_download(retries - 1, **kwargs)

            msg = {
                "type": "DEPLOYMENT_RECEIPT",
                "did": DATA_ddo.did,
                "datatoken_contract_address": DATA_datatoken.address,
                "has_pricing_schema": kwargs["has_pricing_schema"],
            }

            return msg

    def _deploy_data_for_C2D(self, retries: int = 2, **kwargs):
        """
        Creates data NFT, datatoken & data asset for compute.

        param retries: number of retries for creating data for compute.
        param kwargs: necessary parameters to use.
        They are:
        - `description`;
        - `name`;
        - `author`;
        - `license`;
        - `dataset_url`;
        - `has_pricing_schema`
        """
        valid, validation_message = validate_args(**kwargs)
        if not valid:
            raise Exception(f"{validation_message}")
        else:
            if retries == 0:
                raise ValueError("Failed to create data asset after retrying.")

            DATA_metadata = {
                "created": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "description": kwargs["description"],
                "name": kwargs["name"],
                "type": "dataset",
                "author": kwargs["author"],
                "license": kwargs["license"],
            }

            try:
                tx_dict = get_tx_dict(self.ocean_config, self.wallet, chain)
                (
                    DATA_data_nft,
                    DATA_datatoken,
                    DATA_ddo,
                ) = self.ocean.assets.create_url_asset(
                    kwargs["name"],
                    kwargs["dataset_url"],
                    tx_dict,
                    metadata=DATA_metadata,
                    with_compute=True,
                    wait_for_aqua=True,
                )

                self.logger.info(f"DATA did = '{DATA_ddo.did}'")
            except Exception as e:
                self.logger.error(
                    f"Failed to deploy a data NFT and a datatoken with error: {e}\n Retrying..."
                )
                self._deploy_data_for_C2D(retries - 1, **kwargs)

            msg = {
                "type": "DEPLOYMENT_RECEIPT",
                "did": DATA_ddo.did,
                "datatoken_contract_address": DATA_datatoken.address,
                "has_pricing_schema": kwargs["has_pricing_schema"],
            }

            return msg

    def _deploy_algorithm(self, retries: int = 2, **kwargs):
        """
        Creates data NFT, datatoken & asset for the algorithm for compute.

        param retries: number of retries for creating data for compute.
        param kwargs: necessary parameters to use.
        They are:
        - `description`;
        - `name`;
        - `author`;
        - `license`;
        - `language`;
        - `format`;
        - `version`;
        - `entrypoint`;
        - `image`;
        - `tag`;
        - `checksum`;
        - `files_url`;
        - `has_pricing_schema`
        """
        valid, validation_message = validate_args(**kwargs)
        if not valid:
            raise Exception(f"{validation_message}")
        else:
            if retries == 0:
                raise ValueError("Failed to deploy an algorithm after retrying.")
            ALGO_metadata = {
                "created": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "description": kwargs["description"],
                "name": kwargs["name"],
                "type": "algorithm",
                "author": kwargs["author"],
                "license": kwargs["license"],
                "algorithm": {
                    "language": kwargs["language"],
                    "format": kwargs["format"],
                    "version": kwargs["version"],
                    "container": {
                        "entrypoint": kwargs["entrypoint"],
                        "image": kwargs["image"],
                        "tag": kwargs["tag"],
                        "checksum": kwargs["checksum"],
                    },
                },
            }

            try:
                tx_dict = get_tx_dict(self.ocean_config, self.wallet, chain)
                (
                    ALGO_data_nft,
                    ALGO_datatoken,
                    ALGO_ddo,
                ) = self.ocean.assets.create_algo_asset(
                    kwargs["name"],
                    kwargs["files_url"],
                    tx_dict,
                    metadata=ALGO_metadata,
                    wait_for_aqua=True,
                )

                self.logger.info(f"ALGO did = '{ALGO_ddo.did}'")
            except Exception as e:
                self.logger.error(
                    f"Failed to create an ALGO asset with error: {e}\n Retrying..."
                )
                self._deploy_algorithm(retries - 1, **kwargs)

            msg = {
                "type": "DEPLOYMENT_RECEIPT",
                "did": ALGO_ddo.did,
                "datatoken_contract_address": ALGO_datatoken.address,
                "has_pricing_schema": kwargs["has_pricing_schema"],
            }

            return msg

    def _create_dispenser_helper(self, datatoken_address):
        """
        Helper for creating a dispenser with minting option activated.

        param datatoken_address: the contract address of the datatoken.
        """
        datatoken = self.ocean.get_datatoken(datatoken_address)
        self.logger.info(f"Datatoken: {datatoken.address}")
        tx_dict = get_tx_dict(self.ocean_config, self.wallet, chain)

        try:
            datatoken.create_dispenser(tx_dict=tx_dict)
        except Exception as e:
            self.logger.error(f"Failed to deploy dispenser in helper! {e}")

    def _dispense(self, datatoken_address, datatoken_amt, retries: int = 2):
        """
        Helper function for requesting datatokens from the dispenser depending on the datatoken template.

        param datatoken_address: the contract address of the datatoken.
        param datatoken_amt: the amount of the datatoken.
        param retries: number of retries for dispensing.
        """
        datatoken = self.ocean.get_datatoken(datatoken_address)

        tx_dict = get_tx_dict(self.ocean_config, self.wallet, chain)
        if retries == 0:
            raise ValueError("Failed to request datatokens after retrying.")
        try:
            return datatoken.dispense(
                amount=Web3.toWei(datatoken_amt, "ether"),
                tx_dict=tx_dict,
            )
        except (
            ValueError,
            brownie.exceptions.VirtualMachineError,
            brownie.exceptions.ContractNotFound,
        ) as e:
            self.logger.error(
                f"Failed to buy datatokens from FRE with error: {e}\n Retrying..."
            )
            self._dispense(datatoken_address, datatoken_amt, retries - 1)

    def _create_fixed_rate_helper(self, datatoken_address, ocean_amt, rate) -> bytes:
        """
        Helper for creating a fixed rate exchange with minting option activated.

        param datatoken_address: the contract address of the datatoken.
        param ocean_amt: the amount of the OCEAN tokens.
        param rate: rate for BT:DT in fixed rate exchange.
        """
        datatoken = self.ocean.get_datatoken(datatoken_address)
        self.logger.info(f"Approving ocean tokens to the FRE...")
        tx_dict = get_tx_dict(self.ocean_config, self.wallet, chain)
        self.ocean.OCEAN_token.approve(
            self.ocean.fixed_rate_exchange.address,
            Web3.toWei(ocean_amt, "ether"),
            tx_dict,
        )
        self.logger.info(f"Approved ocean tokens to the FRE")
        try:
            exchange, tx = datatoken.create_exchange(
                rate=Web3.toWei(rate, "ether"),
                base_token_addr=self.ocean.OCEAN_address,
                owner_addr=self.wallet.address,
                publish_market_fee_collector=ZERO_ADDRESS,
                publish_market_fee=Web3.toWei("0.01", "ether"),
                with_mint=True,
                allowed_swapper=ZERO_ADDRESS,
                full_info=True,
                tx_dict=tx_dict,
            )

            return exchange.exchange_id
        except Exception as e:
            self.logger.error(f"Failed to deploy fixed rate exchange in helper! {e}")

    def _buy_dt_from_fre(
        self, exchange_id, datatoken_amt, max_cost_ocean, retries: int = 2
    ):
        """
        Helper function for approving tokens from the fixed rate exchange & buying datatokens.

        param exchange_id: the identifier of exchange.
        param datatoken_amt: the amount of the datatoken.
        param max_cost_ocean: the maximum amount of the OCEAN tokens in the exchange.
        param retries: number of retries for buying DTs.
        """
        exchange_id = convert_to_bytes_format(web3, str(exchange_id))
        exchange_details = self.ocean.fixed_rate_exchange.getExchange(exchange_id)
        datatoken = self.ocean.get_datatoken(exchange_details[1])
        exchange = OneExchange(self.ocean.fixed_rate_exchange, exchange_id)
        OCEAN_token = self.ocean.OCEAN_token
        tx_dict = get_tx_dict(self.ocean_config, self.wallet, chain)

        if retries == 0:
            raise ValueError("Failed to buy datatokens after retrying.")
        try:
            datatoken.approve(
                exchange.address,
                Web3.toWei(datatoken_amt, "ether"),
                tx_dict,
            )
            OCEAN_token.approve(exchange.address, Web3.toWei(100, "ether"), tx_dict)

            exchange.buy_DT(
                datatoken_amt=Web3.toWei(datatoken_amt, "ether"),
                tx_dict=tx_dict,
                max_basetoken_amt=Web3.toWei(max_cost_ocean, "ether"),
                consume_market_fee=Web3.toWei("0.01", "ether"),
            )
            self.logger.info(f"balance: {self.wallet.balance()}")
        except Exception as e:
            self.logger.error(
                f"Failed to buy datatokens from FRE with error: {e}\n Retrying..."
            )
            self._buy_dt_from_fre(
                exchange_id, datatoken_amt, max_cost_ocean, retries - 1
            )

    def on_connect(self) -> None:
        """
        Tear down the connection.

        Connection status set automatically.
        """
        network_name = os.environ["OCEAN_NETWORK_NAME"]
        connect_to_network(network_name)
        if network_name != "development":
            priority_fee(chain.priority_fee)

        self.ocean_config = get_config_dict(network_name)
        self.ocean = Ocean(self.ocean_config)

        accounts.clear()
        with open(self.configuration.config.get("key_path"), "r") as f:
            key = f.read()
        self.wallet = accounts.add(key)

        self.logger.info(
            f"connected to Ocean with config.network_name = '{self.ocean_config['NETWORK_NAME']}'"
        )

        self.logger.info(
            f"connected to Ocean with config.metadata_cache_uri = '{self.ocean_config['METADATA_CACHE_URI']}'"
        )
        self.logger.info(
            f"connected to Ocean with config.provider_url = '{self.ocean_config['PROVIDER_URL']}'"
        )
        self.logger.info(f"Address used: {self.wallet.address}")

    def on_disconnect(self) -> None:
        """
        Tear down the connection.

        Connection status set automatically.
        """
