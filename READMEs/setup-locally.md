# Local Setup

Here, we do setup for local testing.

We assume you've already [installed Ocean Connection](install.md).

## 1. Download barge and run services

Ocean `barge` runs ganache (local blockchain), Provider (data service), Aquarius (metadata cache), and Compute-to-Data (feature for running algorithms in Ocean ecosystem).

Barge helps you quickly become familiar with Ocean, because the local blockchain has low latency and no transaction fees.

In a new console:

```console
# Grab repo
git clone https://github.com/oceanprotocol/barge
cd barge

# Clean up old containers (to be sure)
docker system prune -a --volumes

# Run barge: start Ganache, Provider, Aquarius, Compute-to-Data; deploy contracts; update ~/.ocean
./start_ocean.sh --with-c2d
```

Now that we have barge running, we can mostly ignore its console while it runs.

## 2. Brownie local network configuration

(You don't need to do anything in this step, it's just useful to understand.)

Brownie's network configuration file is at `~/.brownie/network-config.yaml`.

When running locally, Brownie will use the chain listed under `development`, having id `development`. This refers to Ganache, which is running in Barge.

## 3. Set envvars

From here on, go to a console different from Barge.

First, ensure that you're in the working directory, with venv activated:

```bash
cd fetch
pipenv shell
```

Then, set keys in the same console:

```bash
# connect to Fetch network
export FETCH_URL=https://rest-dorado.fetch.ai:443
export FETCH_DENOM=atestfet
export FETCH_CHAIN_ID=dorado-1

export SELLER_AEA_KEY_ETHEREUM=<your_private_key_from_ganache>
export SELLER_AEA_KEY_FETCHAI=<your_private_key_from_fetch>

export BUYER_AEA_KEY_ETHEREUM=<your_private_key_from_ganache>
export BUYER_AEA_KEY_FETCHAI=<your_private_key_from_fetch>

# key for minting fake OCEAN
export FACTORY_DEPLOYER_PRIVATE_KEY=0xc594c6e5def4bab63ac29eed19a134c130388f74f019bc74b8f4389df2837a58

# Ocean configuration
export RPC_URL="http://127.0.0.1:8545" 
export OCEAN_NETWORK_NAME="development" 
```

### Next step
Next step is testing:
- [Testing](testing.md)