import pickle
import typing as tp
from pathlib import Path

import tinkoff.invest as inv


###################################################################################
# Utility
###################################################################################

def quotation_to_float(quotation: inv.Quotation) -> float:
    return quotation.units + quotation.nano / 1e9


###################################################################################
# Load from cache
###################################################################################

async def load_from_cache(filename: str, function: tp.Callable[..., tp.Awaitable], update_cache: bool):
    """
    Loads function return value from cache
    """
    directory = Path('cache')
    directory.mkdir(exist_ok=True)
    path = directory / (filename + '.pickle')
    if path.exists() and not update_cache:
        print(f'Load {filename} from cache')
        with open(path, 'rb') as f:
            return pickle.load(f)
    print(f'Create {filename}')
    result = await function()
    with open(path, 'wb') as f:
        pickle.dump(result, f)
    return result


###################################################################################
# Requests
###################################################################################

def get_shares(client: inv.clients.AsyncServices):
    async def function():
        return await client.instruments.shares()

    return function


def get_positions(client: inv.clients.AsyncServices, account_id: str):
    async def function():
        return await client.operations.get_positions(account_id=account_id)

    return function


def get_last_prices(client: inv.clients.AsyncServices, shares: list[inv.Share]):
    async def function():
        return await client.market_data.get_last_prices(figi=[share.figi for share in shares])

    return function
