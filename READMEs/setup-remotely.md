# Local Setup

Here, we do setup for remote testing.

We assume you've already [installed Ocean Connection](install.md).

For this tutorial you won't need `barge`.

## 1. Brownie network configuration

(You don't need to do anything in this step, it's just useful to understand.)

Brownie's network configuration file is at `~/.brownie/network-config.yaml`.

When running remotely, you'll need to modify `network-config.yaml` accordingly with your wanted chain.
Make sure that you choose a chain that is supported by [Ocean contracts](https://github.com/oceanprotocol/contracts/blob/main/addresses/address.json).

## 2. Set envvars
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

export SELLER_AEA_KEY_ETHEREUM=<your_private_key>
export SELLER_AEA_KEY_FETCHAI=<your_private_key_from_fetch>

export BUYER_AEA_KEY_ETHEREUM=<your_private_key>
export BUYER_AEA_KEY_FETCHAI=<your_private_key_from_fetch>

# Ocean configuration
export RPC_URL="https://rpc-mumbai.maticvigil.com" 
export OCEAN_NETWORK_NAME="polygon-test" 
#export WEB3_INFURA_PROJECT_ID=<your_infura_key> if you have an Infura node
```

If you do not have an Infura node, modify in `network-config.yaml` with a public RPc for your wanted network.

### Next step
Next step is testing:
- [Testing](testing.md)