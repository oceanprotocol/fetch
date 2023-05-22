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
"""Scaffold connection and channel."""
import pickle
import time
import web3.exceptions
import brownie.exceptions
import os
import ocean_lib.exceptions
from datetime import datetime, timedelta, timezone
from typing import Any
from brownie.network import accounts, chain, priority_fee, web3


from aea.configurations.base import PublicId
from aea.connections.base import BaseSyncConnection
from aea.mail.base import Envelope
from packages.eightballer.protocols.ocean.message import OceanMessage
from packages.eightballer.connections.ocean.utils import (
    convert_to_bytes_format,
    get_tx_dict,
    get_chain_id_from_network_name,
)
from brownie.network import accounts
from ocean_lib.data_provider.data_service_provider import DataServiceProvider
from ocean_lib.example_config import get_config_dict
from ocean_lib.models.compute_input import ComputeInput
from ocean_lib.models.datatoken_base import DatatokenArguments, TokenFeeInfo
from ocean_lib.models.fixed_rate_exchange import OneExchange
from ocean_lib.ocean.ocean import Ocean
from ocean_lib.services.service import Service
from ocean_lib.structures.file_objects import UrlFile
from ocean_lib.web3_internal.constants import ZERO_ADDRESS
from ocean_lib.web3_internal.utils import connect_to_network
from web3._utils.threads import Timeout
from web3.main import Web3

"""
Choose one of the possible implementations:

Sync (inherited from BaseSyncConnection) or Async (inherited from Connection) connection and remove unused one.
"""

CONNECTION_ID = PublicId.from_str("ocean:0.1.0")


# Specify metadata and service attributes, for "GPR" algorithm script.
# In same location as Branin test dataset. GPR = Gaussian Process Regression.


class OceanConnection(BaseSyncConnection):
    """Proxy to the functionality of the SDK or API."""

    MAX_WORKER_THREADS = 5

    connection_id = CONNECTION_ID

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

    def on_send(self, envelope: Envelope) -> None:
        """
        Send an envelope.

        param envelope: the envelope to send.
        """
        self.logger.debug(f"Received {envelope} in connection")

        if envelope.message.performative == OceanMessage.Performative.DEPLOY_D2C:
            self._deploy_data_for_d2c(envelope)
        if envelope.message.performative == OceanMessage.Performative.DEPLOY_ALGORITHM:
            self._deploy_algorithm(envelope)
        if (
            envelope.message.performative
            == OceanMessage.Performative.PERMISSION_DATASET
        ):
            self._permission_dataset(envelope)
        if envelope.message.performative == OceanMessage.Performative.D2C_JOB:
            self._create_d2c_job(envelope)
        if (
            envelope.message.performative
            == OceanMessage.Performative.DEPLOY_DATA_DOWNLOAD
        ):
            self._deploy_data_to_download(envelope)
        if envelope.message.performative == OceanMessage.Performative.CREATE_DISPENSER:
            self._create_dispenser(envelope)
        if (
            envelope.message.performative
            == OceanMessage.Performative.CREATE_FIXED_RATE_EXCHANGE
        ):
            self._create_fixed_rate(envelope)
        if envelope.message.performative == OceanMessage.Performative.DOWNLOAD_JOB:
            self._purchase_datatoken(envelope)

    def _purchase_datatoken(self, envelope: Envelope):
        """
        Buys datatokens available on the fixed rate exchange in order to consume services.

        param envelope: the envelope to send.
        """
        try:
            if envelope.message.has_pricing_schema:
                self.logger.info("Starting to buy DTs from fixed rate exchange...")
                self._buy_dt_from_fre(envelope=envelope)
                msg = OceanMessage(
                    performative=OceanMessage.Performative.DOWNLOAD_JOB,
                    **{
                        "datatoken_address": envelope.message.datatoken_address,
                        "datatoken_amt": envelope.message.datatoken_amt,
                        "max_cost_ocean": envelope.message.max_cost_ocean,
                        "asset_did": envelope.message.asset_did,
                        "exchange_id": str(envelope.message.exchange_id),
                        "has_pricing_schema": True,
                    },
                )
            else:
                self.logger.info("Request DTs from the dispenser")
                tx = self._dispense(envelope=envelope)
                msg = OceanMessage(
                    performative=OceanMessage.Performative.DOWNLOAD_JOB,
                    **{
                        "datatoken_address": envelope.message.datatoken_address,
                        "datatoken_amt": envelope.message.datatoken_amt,
                        "asset_did": envelope.message.asset_did,
                        "order_tx_id": tx.txid,
                        "has_pricing_schema": False,
                    },
                )

            msg.sender = envelope.to
            msg.to = envelope.sender
            envelope = Envelope(to=msg.to, sender=msg.sender, message=msg)
            self.put_envelope(envelope)
            self.logger.info(f"Purchased datatokens successfully!")

        except Exception as e:
            self.logger.error("Couldn't purchase datatokens")
            self.logger.error(f"balance of matic: {self.wallet.balance()}")
            self.logger.error(e)

    def _download_asset(self, envelope: Envelope, retries: int = 2):
        """
        Downloads files from the asset.

        param envelope: the envelope to send.
        """
        did = envelope.message.asset_did
        datatoken = self.ocean.get_datatoken(envelope.message.datatoken_address)

        if datatoken.balanceOf(self.wallet.address) < envelope.message.datatoken_amt:
            self.logger.info(
                f"insufficient data tokens.. Purchasing from the open market."
            )
            if envelope.message.exchange_id:
                self._buy_dt_from_fre(envelope=envelope)
            else:
                self._dispense(envelope=envelope)
        else:
            self.logger.info(f"Already has sufficient Datatokens.")

        asset = self.ocean.assets.resolve(did)
        service = asset.get_service_by_id("0")
        if retries == 0:
            raise ValueError("Failed to pay for compute service after retrying.")
        # Agent needs to pay in order to have rights for consume service.
        try:
            if envelope.message.exchange_id:
                tx_dict = get_tx_dict(self.ocean_config, self.wallet, chain)
                order_tx_id = self.ocean.assets.pay_for_access_service(
                    asset=asset,
                    service=service,
                    consume_market_order_fee_address=self.wallet.address,
                    consume_market_order_fee_token=service.datatoken.address,
                    consume_market_order_fee_amount=0,
                    tx_dict=tx_dict,
                )
            else:
                order_tx_id = envelope.message.order_tx_id
            self.logger.info(f"order_tx_id = '{order_tx_id}'")
        except (
            ValueError,
            brownie.exceptions.VirtualMachineError,
            brownie.exceptions.ContractNotFound,
        ) as e:
            self.logger.error(
                f"Failed to pay for access service with error: {e}\n Retrying..."
            )
            self._download_asset(envelope, retries - 1)

        # Download has begun for the agent. If the connection breaks, agent can request again by showing order_tx_id.
        file_path = self.ocean.assets.download(
            asset=asset,
            consumer_wallet=self.wallet,
            destination="./downloads/",
            order_tx_id=order_tx_id,
            service=service,
        )
        self.logger.info(f"file_path = '{file_path}'")
        data = open(file_path, "rb").read()

        msg = OceanMessage(performative=OceanMessage.Performative.RESULTS, content=data)
        msg.sender = envelope.to
        msg.to = envelope.sender
        envelope = Envelope(to=msg.to, sender=msg.sender, message=msg)
        self.put_envelope(envelope)
        self.logger.info(f"completed download! Sending result to handler!")

    def _create_dispenser(self, envelope: Envelope, retries: int = 2):
        """
        Deploys a dispenser.

        param envelope: the envelope to send.
        param retries: number of retries for creating the dispenser.
        """
        if retries == 0:
            raise ValueError("Failed to deploy dispenser...")
        try:
            self._create_dispenser_helper(envelope=envelope)
            datatoken = self.ocean.get_datatoken(envelope.message.datatoken_address)
            dispenser_status = datatoken.dispenser_status().active
            self.logger.info(f"Dispenser status = '{dispenser_status}'")
            msg = OceanMessage(
                performative=OceanMessage.Performative.DISPENSER_DEPLOYMENT_RECIEPT,
                datatoken_address=datatoken.address,
                dispenser_status=dispenser_status,
                has_pricing_schema=False,
            )
            msg.sender = envelope.to
            msg.to = envelope.sender
            envelope = Envelope(to=msg.to, sender=msg.sender, message=msg)
            self.put_envelope(envelope)
            self.logger.info(f"Dispenser created! Sending result to handler!")
        except (web3.exceptions.TransactionNotFound, ValueError) as e:
            self.logger.error(f"Failed to deploy dispenser!")
            self._create_fixed_rate(envelope, retries - 1)

    def _create_fixed_rate(self, envelope: Envelope, retries: int = 2):
        """
        Creates a fixed rate exchange with OCEAN as base tokens.

        param envelope: the envelope to send.
        param retries: number of retries for creating the FRE.
        """
        if retries == 0:
            raise ValueError("Failed to deploy fixed rate exchange...")
        try:
            exchange_id = self._create_fixed_rate_helper(envelope=envelope)
            self.logger.info(f"Deployed fixed rate exchange = '{exchange_id}'")
            msg = OceanMessage(
                performative=OceanMessage.Performative.EXCHANGE_DEPLOYMENT_RECIEPT,
                exchange_id=str(exchange_id),
                has_pricing_schema=True,
            )
            msg.sender = envelope.to
            msg.to = envelope.sender
            envelope = Envelope(to=msg.to, sender=msg.sender, message=msg)
            self.put_envelope(envelope)
            self.logger.info(f"Fixed rate exchange created! Sending result to handler!")
        except (web3.exceptions.TransactionNotFound, ValueError) as e:
            self.logger.error(f"Failed to deploy fixed rate exchange!")
            self._create_fixed_rate(envelope, retries - 1)

    def _create_d2c_job(self, envelope: Envelope, retries: int = 2):
        """
        Pays for compute service & starts the compute job.

        param envelope: the envelope to send.
        """
        DATA_did = envelope.message.data_did
        ALG_did = envelope.message.algo_did
        DATA_DDO = self.ocean.assets.resolve(DATA_did)
        ALG_DDO = self.ocean.assets.resolve(ALG_did)

        compute_service = DATA_DDO.services[1]
        algo_service = ALG_DDO.services[0]
        self.logger.info(
            f'chain id: {DATA_DDO.chain_id}'
        )
        free_c2d_env = self.ocean.compute.get_free_c2d_environment(
            service_endpoint=compute_service.service_endpoint,
            chain_id=DATA_DDO.chain_id,
        )
        self.logger.info(f"free c2d env: {free_c2d_env}")

        DATA_compute_input = ComputeInput(DATA_DDO, compute_service)
        ALGO_compute_input = ComputeInput(ALG_DDO, algo_service)

        # Pay for dataset and algo for 1 day
        self.logger.info(f"paying for dataset {DATA_did}")
        if retries == 0:
            raise ValueError("Failed to pay for compute service after retrying.")
        try:
            tx_dict = get_tx_dict(self.ocean_config, self.wallet, chain)
            self.logger.info(f"paying for compute service {datetime.now()}")
            datasets, algorithm = self.ocean.assets.pay_for_compute_service(
                datasets=[DATA_compute_input],
                algorithm_data=ALGO_compute_input,
                compute_environment=free_c2d_env["id"],
                valid_until=int((datetime.now(timezone.utc) + timedelta(days=1)).timestamp()),
                consume_market_order_fee_address=compute_service.datatoken,
                tx_dict=tx_dict,
                consumer_address=free_c2d_env["consumerAddress"],
            )
            self.logger.info(f"finishing paying for compute service {datetime.now()}")
        except (
            ValueError,
            brownie.exceptions.VirtualMachineError,
            brownie.exceptions.ContractNotFound,
        ) as e:
            self.logger.error(
                f"Failed to pay for compute service with error: {e}\n Retrying..."
            )
            self._create_d2c_job(envelope, retries - 1)

        self.logger.info(
            f"paid for dataset {DATA_did} receipt: {[dataset.as_dictionary() for dataset in datasets]} with algorithm {algorithm.as_dictionary()}"
        )

        self.logger.info(f"starting compute job....")
        self.logger.info(f"dataset[0]: {datasets[0].as_dictionary()}")
        job_id = self.ocean.compute.start(
            consumer_wallet=self.wallet,
            dataset=datasets[0],
            compute_environment=free_c2d_env["id"],
            algorithm=algorithm,
        )

        status = self.ocean.compute.status(
            DATA_DDO, compute_service, job_id, self.wallet
        )
        self.logger.info(f"got job status: {status}")

        assert (
            status and status["ok"]
        ), f"something not right about the compute job, got status: {status}"

        self.logger.info(f"Started compute job with id: {job_id}")

        for _ in range(0, 200):
            status = self.ocean.compute.status(
                DATA_DDO, compute_service, job_id, self.wallet
            )
            if status.get("statusText") == "Job finished":
                break

            time.sleep(5)

        status = self.ocean.compute.status(
            DATA_DDO, compute_service, job_id, self.wallet
        )
        assert status[
            "results"
        ], f"something not right about the compute job, results were not fetched: {status} "
        self.logger.info(f"status results: {status['results']}\n status: {status}")

        function_result = []
        for i in range(len(status["results"])):
            result = None
            result_type = status["results"][i]["type"]
            if result_type == "output":
                result = self.ocean.compute.result(
                    DATA_DDO, compute_service, job_id, i, self.wallet
                )
                self.logger.info(f"result: {result}")
                function_result.append(result)

        assert len(function_result) > 0, "empty results"
        model = [pickle.loads(res) for res in function_result]
        assert len(model) > 0, "unpickle result unsuccessful"

        msg = OceanMessage(
            performative=OceanMessage.Performative.RESULTS, content=model
        )
        msg.sender = envelope.to
        msg.to = envelope.sender
        envelope = Envelope(to=msg.to, sender=msg.sender, message=msg)
        self.put_envelope(envelope)
        self.logger.info(f"completed D2C! Sending result to handler!")

    def _permission_dataset(self, envelope: Envelope, retries: int = 2):
        """
        Updates the trusted algorithm publishers list in order to start a compute job.

        param envelope: the envelope to send.
        """
        data_ddo = self.ocean.assets.resolve(envelope.message.data_did)
        algo_ddo = self.ocean.assets.resolve(envelope.message.algo_did)

        if data_ddo is None or algo_ddo is None:
            raise ValueError(
                f"Unable to loaded the assets from their dids. Please confirm correct deployment on Ocean!"
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
        except (
            ValueError,
            brownie.exceptions.VirtualMachineError,
            brownie.exceptions.ContractNotFound,
        ) as e:
            self.logger.error(
                f"Failed to update asset permissions with error: {e}\n Retrying..."
            )
            self._permission_dataset(envelope, retries - 1)

        msg = OceanMessage(
            performative=OceanMessage.Performative.DEPLOYMENT_RECIEPT,
            type="permissions",
            did=data_ddo.did,
            datatoken_contract_address=data_ddo.datatokens[0].get("address"),
        )
        msg.sender = envelope.to
        msg.to = envelope.sender
        envelope = Envelope(to=msg.to, sender=msg.sender, message=msg)
        self.put_envelope(envelope)
        self.logger.info(f"Permission datasets. ")

    def _deploy_data_to_download(self, envelope: Envelope):
        """
        Creates an Ocean asset with access service.

        param envelope: the envelope to send.
        """

        DATA_metadata = {
            "created": envelope.message.date_created,
            "updated": envelope.message.date_created,
            "description": envelope.message.description,
            "name": envelope.message.name,
            "type": "dataset",
            "author": envelope.message.author,
            "license": envelope.message.license,
        }
        try:
            tx_dict = get_tx_dict(self.ocean_config, self.wallet, chain)
            (
                DATA_data_nft,
                DATA_datatoken,
                DATA_ddo,
            ) = self.ocean.assets.create_url_asset(
                envelope.message.name,
                envelope.message.dataset_url,
                tx_dict,
                metadata=DATA_metadata,
                wait_for_aqua=True,
            )

            self.logger.info(f"DATA did = '{DATA_ddo.did}'")
        except ocean_lib.exceptions.AquariusError as error:
            self.logger.error(f"Error with creating asset. {error}")
            msg = error.args[0]
            if "is already registered to another asset." in msg:
                self.logger.error(f"Trying to resolve pre-existing did..")
                DATA_ddo = self.ocean.assets.resolve(msg.split(" ")[2])

        self.logger.info(f"Ensure asset is cached in aquarius")

        msg = OceanMessage(
            performative=OceanMessage.Performative.DEPLOYMENT_RECIEPT,
            type="data_download",
            did=DATA_ddo.did,
            datatoken_contract_address=DATA_datatoken.address,
            has_pricing_schema=envelope.message.has_pricing_schema,
        )
        msg.sender = envelope.to
        msg.to = envelope.sender
        deployment_envelope = Envelope(to=msg.to, sender=msg.sender, message=msg)
        self.put_envelope(deployment_envelope)

    def _deploy_data_for_d2c(self, envelope: Envelope, retries: int = 2):
        """
        Creates data NFT, datatoken & data asset for compute.

        param envelope: the envelope to send.
        """

        DATA_metadata = {
            "created": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "description": envelope.message.description,
            "name": envelope.message.name,
            "type": "dataset",
            "author": envelope.message.author,
            "license": envelope.message.license,
        }

        if retries == 0:
            raise ValueError("Failed to create data asset after retrying.")
        try:
            tx_dict = get_tx_dict(self.ocean_config, self.wallet, chain)
            (
                DATA_data_nft,
                DATA_datatoken,
                DATA_ddo,
            ) = self.ocean.assets.create_url_asset(
                envelope.message.name,
                envelope.message.dataset_url,
                tx_dict,
                metadata=DATA_metadata,
                with_compute=True,
                wait_for_aqua=True,
            )

            self.logger.info(f"DATA did = '{DATA_ddo.did}'")
        except (
            ValueError,
            brownie.exceptions.VirtualMachineError,
            brownie.exceptions.ContractNotFound,
        ) as e:
            self.logger.error(
                f"Failed to deploy a data NFT and a datatoken with error: {e}\n Retrying..."
            )
            self._deploy_data_for_d2c(envelope, retries - 1)

        msg = OceanMessage(
            performative=OceanMessage.Performative.DEPLOYMENT_RECIEPT,
            type="d2c",
            did=DATA_ddo.did,
            datatoken_contract_address=DATA_datatoken.address,
            has_pricing_schema=envelope.message.has_pricing_schema,
        )
        msg.sender = envelope.to
        msg.to = envelope.sender
        deployment_envelope = Envelope(to=msg.to, sender=msg.sender, message=msg)
        self.put_envelope(deployment_envelope)

    def _deploy_algorithm(self, envelope: Envelope, retries: int = 2):
        """
        Creates data NFT, datatoken & asset for the algorithm for compute.

        param envelope: the envelope to send.
        """
        ALGO_date_created = envelope.message.date_created
        ALGO_metadata = {
            "created": ALGO_date_created,
            "updated": ALGO_date_created,
            "description": envelope.message.description,
            "name": envelope.message.author,
            "type": "algorithm",
            "author": envelope.message.author,
            "license": envelope.message.license,
            "algorithm": {
                "language": envelope.message.language,
                "format": envelope.message.format,
                "version": envelope.message.version,
                "container": {
                    "entrypoint": envelope.message.entrypoint,
                    "image": envelope.message.image,
                    "tag": envelope.message.tag,
                    "checksum": envelope.message.checksum,
                },
            },
        }

        if retries == 0:
            raise ValueError("Failed to deploy an algorithm after retrying.")
        try:
            tx_dict = get_tx_dict(self.ocean_config, self.wallet, chain)
            (
                ALGO_data_nft,
                ALGO_datatoken,
                ALGO_ddo,
            ) = self.ocean.assets.create_algo_asset(
                envelope.message.name,
                envelope.message.files_url,
                tx_dict,
                metadata=ALGO_metadata,
                wait_for_aqua=True,
            )

            self.logger.info(f"ALGO did = '{ALGO_ddo.did}'")
        except (
            ValueError,
            brownie.exceptions.VirtualMachineError,
            brownie.exceptions.ContractNotFound,
        ) as e:
            self.logger.error(
                f"Failed to create an ALGO asset with error: {e}\n Retrying..."
            )
            self._deploy_algorithm(envelope, retries - 1)

        msg = OceanMessage(
            performative=OceanMessage.Performative.DEPLOYMENT_RECIEPT,
            type="algorithm",
            did=ALGO_ddo.did,
            datatoken_contract_address=ALGO_datatoken.address,
            has_pricing_schema=envelope.message.has_pricing_schema,
        )
        msg.sender = envelope.to
        msg.to = envelope.sender
        deployment_envelope = Envelope(to=msg.to, sender=msg.sender, message=msg)
        self.put_envelope(deployment_envelope)

    def _ensure_asset_cached_in_aquarius(
        self, did: str, timeout: float = 600, poll_latency: float = 1
    ):
        """
        Ensure asset is cached in Aquarius
        Default timeout = 10 mins
        Default poll_latency = 1 second
        """
        with Timeout(timeout) as _timeout:
            while True:
                asset = self.ocean.assets.resolve(did)
                if asset is not None:
                    break
                _timeout.sleep(poll_latency)

    def _deploy_datatoken(self, envelope: Envelope, retries: int = 2):
        """
        Creates a data NFT & a datatoken.

        param envelope: the envelope to send.
        """
        if retries == 0:
            raise ValueError("Failed to deploy data nft and datatoken after retrying.")

        try:
            self.logger.info(
                f"interacting with Ocean to deploy data NFT and datatoken..."
            )
            self.logger.info("Create data NFT: begin.")
            tx_dict = get_tx_dict(self.ocean_config, self.wallet, chain)
            data_nft = self.ocean.data_nft_factory.create(
                tx_dict=tx_dict,
                name=envelope.message.data_nft_name,
                symbol=envelope.message.datatoken_name,
            )
            publish_market_order_fees = TokenFeeInfo(
                address=self.wallet.address, token=ZERO_ADDRESS, amount=0
            )
            datatoken = data_nft.create_datatoken(
                tx_dict=tx_dict,
                name=envelope.message.datatoken_name,
                symbol=envelope.message.datatoken_name,
                template_index=1,
                minter=self.wallet.address,
                fee_manager=self.wallet.address,
                publish_market_order_fees=publish_market_order_fees,
                bytess=[b""],
            )
            self.logger.info(f"created the data token.")

            self.logger.info(
                f"DATA_datatoken.address = '{datatoken.address}'\n publishing"
            )
            return data_nft, datatoken
        except (
            ValueError,
            brownie.exceptions.VirtualMachineError,
            brownie.exceptions.ContractNotFound,
        ) as e:
            self.logger.error(
                f"Failed to deploy a data NFT and a datatoken with error: {e}\n Retrying..."
            )
            self._deploy_datatoken(envelope, retries - 1)

    def _create_dispenser_helper(self, envelope: Envelope):
        """
        Helper for creating a dispenser with minting option activated.

        param envelope: the envelope to send.
        """
        datatoken = self.ocean.get_datatoken(envelope.message.datatoken_address)
        self.logger.info(f"Datatoken: {datatoken.address}")
        tx_dict = get_tx_dict(self.ocean_config, self.wallet, chain)

        try:
            datatoken.create_dispenser(tx_dict=tx_dict)
        except Exception as e:
            self.logger.error(f"Failed to deploy dispenser in helper! {e}")

    def _dispense(self, envelope: Envelope, retries: int = 2):
        """
        Helper function for requesting datatokens from the dispenser depending on the datatoken template.

        param envelope: the envelope to send.
        """
        datatoken = self.ocean.get_datatoken(envelope.message.datatoken_address)

        tx_dict = get_tx_dict(self.ocean_config, self.wallet, chain)
        if retries == 0:
            raise ValueError("Failed to request datatokens after retrying.")
        try:
            return datatoken.dispense(
                amount=Web3.toWei(envelope.message.datatoken_amt, "ether"),
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
            self._dispense(envelope, retries - 1)

    def _create_fixed_rate_helper(self, envelope: Envelope) -> bytes:
        """
        Helper for creating a fixed rate exchange with minting option activated.

        param envelope: the envelope to send.
        """
        datatoken = self.ocean.get_datatoken(envelope.message.datatoken_address)
        self.logger.info(f"Datatoken: {datatoken.address}")
        self.logger.info(f"Approving ocean tokens to the FRE...")
        tx_dict = get_tx_dict(self.ocean_config, self.wallet, chain)
        self.ocean.OCEAN_token.approve(
            self.ocean.fixed_rate_exchange.address,
            Web3.toWei(envelope.message.ocean_amt, "ether"),
            tx_dict,
        )
        self.logger.info(f"Approved ocean tokens to the FRE")
        try:
            exchange, tx = datatoken.create_exchange(
                rate=Web3.toWei(envelope.message.rate, "ether"),
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

    def _buy_dt_from_fre(self, envelope: Envelope, retries: int = 2):
        """
        Helper function for approving tokens from the fixed rate exchange & buying datatokens.

        param envelope: the envelope to send.
        """
        exchange_id = convert_to_bytes_format(web3, str(envelope.message.exchange_id))
        exchange_details = self.ocean.fixed_rate_exchange.getExchange(exchange_id)
        datatoken = self.ocean.get_datatoken(exchange_details[1])
        exchange = OneExchange(self.ocean.fixed_rate_exchange, exchange_id)
        self.logger.info(f"one exchange: {exchange}")
        OCEAN_token = self.ocean.OCEAN_token
        self.logger.info(
            f"OCEAN token: {OCEAN_token}\n OCEAN config: {self.ocean_config}\n wallet: {self.wallet}"
        )
        tx_dict = get_tx_dict(self.ocean_config, self.wallet, chain)
        self.logger.info(f"tx dict: {tx_dict}")
        if retries == 0:
            raise ValueError("Failed to buy datatokens after retrying.")
        try:
            # TODO: do the logic for enterprise as well
            datatoken.approve(
                exchange.address,
                Web3.toWei(envelope.message.datatoken_amt, "ether"),
                tx_dict,
            )
            OCEAN_token.approve(exchange.address, Web3.toWei(100, "ether"), tx_dict)

            exchange.buy_DT(
                datatoken_amt=Web3.toWei(envelope.message.datatoken_amt, "ether"),
                tx_dict=tx_dict,
                max_basetoken_amt=Web3.toWei(envelope.message.max_cost_ocean, "ether"),
                consume_market_fee=Web3.toWei("0.01", "ether"),
            )
            self.logger.info(f"balance: {self.wallet.balance()}")
        except (
            ValueError,
            brownie.exceptions.VirtualMachineError,
            brownie.exceptions.ContractNotFound,
        ) as e:
            self.logger.error(
                f"Failed to buy datatokens from FRE with error: {e}\n Retrying..."
            )
            self._buy_dt_from_fre(envelope, retries - 1)

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