import pickle
import typing as tp
import yaml
import datetime
import asyncio
from pathlib import Path

import tinkoff.invest as inv


###################################################################################
# Utility
###################################################################################


def quotation_to_float(quotation: inv.Quotation) -> float:
    return round(quotation.units + quotation.nano / 1e9, 9)


def get_token_account_id(filename: str = "keys.yaml") -> tuple[str, str]:
    with open(filename) as f:
        keys = yaml.safe_load(f)
    token = keys["token"]
    account_id = str(keys["account_id"])
    return token, account_id


def get_yesterday_close(candles: list[inv.HistoricCandle]) -> float | None:
    today = datetime.datetime.utcnow()
    for candle in reversed(candles):
        if candle.time.date() >= today.date():
            continue
        return quotation_to_float(candle.close)
    return None


###################################################################################
# Load from cache
###################################################################################


async def load_from_cache(
    filename: str, function: tp.Callable[..., tp.Awaitable], force_update: bool
):
    """
    Loads function return value from cache
    """
    directory = Path("cache")
    directory.mkdir(exist_ok=True)
    path = directory / (filename + ".pickle")
    if path.exists() and not force_update:
        print(f"Load {filename} from cache")
        with open(path, "rb") as f:
            return pickle.load(f)
    print(f"Create {filename}")
    result = await function()
    with open(path, "wb") as f:
        pickle.dump(result, f)
    return result


###################################################################################
# Requests
###################################################################################


def get_shares(client: inv.clients.AsyncServices):
    async def function() -> inv.SharesResponse:
        return await client.instruments.shares()

    return function


def get_positions(client: inv.clients.AsyncServices, account_id: str):
    async def function() -> inv.PositionsResponse:
        return await client.operations.get_positions(account_id=account_id)

    return function


def get_last_prices(client: inv.clients.AsyncServices, shares: list[inv.Share]):
    async def function() -> inv.GetLastPricesResponse:
        return await client.market_data.get_last_prices(
            figi=[share.figi for share in shares]
        )

    return function


def get_candles(
    client: inv.clients.AsyncServices, shares: list[inv.Share], n_days: int
):
    to = datetime.datetime.utcnow()
    start_day = to - datetime.timedelta(days=n_days)

    async def get_candles_for_share(share: inv.Share) -> inv.GetCandlesResponse:
        return await client.market_data.get_candles(
            figi=share.figi,
            from_=start_day,
            to=to,
            interval=inv.CandleInterval.CANDLE_INTERVAL_DAY,
        )

    async def function():
        return await asyncio.gather(*[get_candles_for_share(share) for share in shares])

    return function


async def main():
    token, account_id = get_token_account_id("keys.yaml")

    # Create client
    force_update = True
    async with inv.AsyncClient(token=token) as client:
        shares: list[inv.Share] = (
            await load_from_cache("shares", get_shares(client), force_update)
        ).instruments
        candles = await load_from_cache(
            "candles", get_candles(client, shares[1:5], days=365), force_update
        )
        print(candles)


if __name__ == "__main__":
    asyncio.run(main())
