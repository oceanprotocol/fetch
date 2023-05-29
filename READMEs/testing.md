# Testing

## Unit testing
If you want to become a contributor on this repo, take in account that every function need to be
tested via `pytest` likewise:

```bash
pytest <test_file_that_you_want_to_test>
```

After you modified something in the connection part, please use `fingerprint` script in order to have everything up to date:

```bash
./fingerprint.sh
```

## Integration testing

Ocean Simple Seller is the middleware between Ocean connection and AEA agents.
AEA agents can be programmed to publish/consume data and use Compute to Data feature
from Ocean core.

The scenario is composed by a seller and a buyer which are two AEA agents.
The `seller` publishes data assets and algorithms with Fixed Rate/Dispenser pricing schema &
the `buyer` consumes the data and pays for the algorithm access.

If you want to see the full flow with already built agents from [Ocean Simple Seller repo](https://github.com/oceanprotocol/oceansimpleseller/tree/v4). 