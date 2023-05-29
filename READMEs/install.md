# Ocean Connection

This tutorial guides you to interact with Ocean core functionalities embedded in autonomous Fetch.ai agents.

## Intro

Ocean Protocol developed an integration with Fetch.ai exposing the current flows that are available in [ocean.py](https://github.com/oceanprotocol/ocean.py)
for its agents.

The connection includes the following functionalities: 
1. Publishing a data NFT, a datatoken & a data asset
2. Can do (1) for algorithm data.
3. Getting funds for accessing data through Ocean pricing schemas (fixed rate exchanges & dispensers)
4. Downloading content from assets.
5. Running given algorithms using C2D feature.

## Install Ocean Connection

### Prerequisites

-   Linux
-   [Docker](https://docs.docker.com/engine/install/), [Docker Compose](https://docs.docker.com/compose/install/), [allowing non-root users](https://www.thegeekdiary.com/run-docker-as-a-non-root-user/)
-   Python 3.8, pipenv, build-essential

### Installation
Make sure that you have `pipenv` & `build-essential` installed on your machine.

In a new console:

```bash
cd fetch || exit
make new_env
pipenv shell
make install_env
```

**For further usage in agents implementation:**

`go` is required by the `libp2p` connection. Download & install go using the official
[installation docs](https://go.dev/doc/install).

```bash
export PATH=$PATH:/usr/local/go/bin
```

`protobuf-compiler` is required for compiling the `.proto` files.
Install it using the following command on Ubuntu:
```bash
sudo apt install protobuf-compiler
```

If it is your first interaction with AEA, we suggest to also run inside `fetch`:

```bash
aea init
```

#### Potential issues

Ocean connection has ocean.py as dependency which also uses `Brownie`, therefore if you encounter any issues, please kindly consult
[this workaround](https://github.com/oceanprotocol/ocean.py/blob/main/READMEs/install.md#potential-issues--workarounds).


### Next step

You've now installed Ocean Connection, great!

Next step is setup:
- [Remote](setup-remotely.md)
- *or* [Local](setup-locally.md)