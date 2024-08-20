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


def get_accounts_from_token(token: str) -> list[inv.Account] | None:
    """
    Get one account with the highest RUB balance from token
    """
    try:
        with inv.Client(token=token) as client:
            accounts: list[inv.Account] = client.users.get_accounts().accounts
        accounts = [account for account in accounts if account.status == inv.AccountStatus.ACCOUNT_STATUS_OPEN and account.type != inv.AccountType.ACCOUNT_TYPE_INVEST_BOX]
        return accounts
    except inv.exceptions.UnauthenticatedError:
        return None


def get_previous_close(candles: list[inv.HistoricCandle], n_days: int) -> float | None:
    today = datetime.datetime.utcnow()
    last_candle = None
    for candle in reversed(candles):
        last_candle = candle
        if candle.time.date() > today.date() - datetime.timedelta(days=n_days):
            continue
        return quotation_to_float(candle.close)
    return quotation_to_float(last_candle.close) if last_candle is not None else None


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
        from_day = start_day
        while True:
            try:
                return await client.market_data.get_candles(
                    figi=share.figi,
                    from_=from_day,
                    to=to,
                    interval=inv.CandleInterval.CANDLE_INTERVAL_DAY,
                )
                break
            except inv.exceptions.AioRequestError as ex:
                # Extract the message from the exception tuple
                status_code, error_code, metadata = ex.args
                error_message = metadata.message

                if error_message == 'The maximum request period for the given candle interval has been exceeded':
                    if from_day == to - datetime.timedelta(days=1):
                        raise
                    if from_day >= to - datetime.timedelta(days=365):
                        from_day = min(from_day + datetime.timedelta(days=30), to - datetime.timedelta(days=1))
                    else:
                        from_day = min(from_day + datetime.timedelta(days=30), to - datetime.timedelta(days=365))
                    continue
                raise

    async def function():
        return await asyncio.gather(*[get_candles_for_share(share) for share in shares])

    return function


async def main():
    token, account_id = get_token_account_id("keys.yaml")
    from pprint import pprint
    pprint(get_accounts_from_token(token))


if __name__ == "__main__":
    asyncio.run(main())
