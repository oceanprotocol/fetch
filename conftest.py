import os
import pytest

from brownie.network import accounts


@pytest.fixture(autouse=True)
def setup_all():
    """Set up the environment for the tests"""

    # Creates file with ethereum_private_key.txt file in the root folder to be used by some functions
    with open(os.environ.get("SELLER_AEA_KEY_ETHEREUM_PATH"), "w") as f:
        f.write(os.environ.get("SELLER_AEA_KEY_ETHEREUM"))

    with open(os.environ.get("BUYER_AEA_KEY_ETHEREUM_PATH"), "w") as f:
        f.write(os.environ.get("BUYER_AEA_KEY_ETHEREUM"))


@pytest.fixture
def publisher_wallet():
    return accounts.add(os.getenv("SELLER_AEA_KEY_ETHEREUM"))
