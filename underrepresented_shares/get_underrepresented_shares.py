import datetime
import asyncio
import yaml
import pandas as pd

from library.utils import *


###################################################################################
# Sort and filter
###################################################################################

def get_share_key(last_prices_by_figi: dict[str, inv.LastPrice]):
    def compare_key(share: inv.Share):
        return quotation_to_float(last_prices_by_figi[share.figi].price) * share.lot

    return compare_key


def filter_share(share: inv.Share, positions_figi: set[str], last_prices_by_figi: dict[str, inv.LastPrice], max_price: float):
    if share.currency != 'rub':
        return False
    if share.otc_flag:
        return False
    if not share.buy_available_flag or not share.sell_available_flag:
        return False
    if share.for_qual_investor_flag:
        return False
    if share.class_code != 'TQBR':
        return False
    if share.figi in positions_figi:
        return False
    if share.country_of_risk != 'RU':
        return False
    last_price = last_prices_by_figi[share.figi]
    if datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc) - last_price.time > datetime.timedelta(days=7):
        return False
    price = quotation_to_float(last_price.price)
    if share.lot * price > max_price:
        return False
    return True


###################################################################################
# Print
###################################################################################

def get_share_row(share: inv.Share, last_prices_by_figi: dict[str, inv.LastPrice]) -> list:
    return [share.ticker, share.name, quotation_to_float(last_prices_by_figi[share.figi].price) * share.lot, share.sector, share.share_type.name, share.exchange]


###################################################################################
# Main
###################################################################################

async def main(force_update: bool):
    # Read config
    token, account_id = get_token_account_id()

    with open('underrepresented_shares/config.yaml') as f:
        config = yaml.safe_load(f)
    max_price = config['max_price']

    # Create client
    async with inv.AsyncClient(token=token) as client:
        shares: list[inv.Share] = (await load_from_cache('shares', get_shares(client), force_update)).instruments
        last_prices: list[inv.LastPrice] = (await load_from_cache('last_prices', get_last_prices(client, shares), force_update)).last_prices
        positions: list[inv.PositionsSecurities] = (await load_from_cache('positions', get_positions(client, account_id), force_update)).securities

    positions_figi = {position.figi for position in positions}
    last_prices_by_figi = {last_price.figi: last_price for last_price in last_prices}

    shares = [share for share in shares if filter_share(share, positions_figi, last_prices_by_figi, max_price)]
    shares.sort(key=get_share_key(last_prices_by_figi))

    print(f'Number of shares: {len(shares)}\n')
    rows = [get_share_row(share, last_prices_by_figi) for share in shares]
    columns = ['ticker', 'name', 'price', 'sector', 'share_type', 'exchange']
    df = pd.DataFrame(rows, columns=columns)
    print(df.to_string())

    result_directory = Path('result/')
    result_directory.mkdir(exist_ok=True)
    df.to_csv(result_directory / 'shares.csv', index=False)


if __name__ == '__main__':
    asyncio.run(main(force_update=True))
