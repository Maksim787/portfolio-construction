import asyncio
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.offline as offline
from colour import Color

from library.utils import *


def add_color(df):
    df = df.copy()
    lower = -2
    upper = 2
    bins = np.arange(lower, upper + 0.2, 0.2)
    colors = list(map(lambda x: x.get_web(), Color("red").range_to(Color("green"), len(bins) - 1)))
    df["color"] = pd.cut(df["return"], bins=bins, labels=colors, include_lowest=True)
    df.loc[df["return"] >= upper, "color"] = colors[-1]
    df.loc[df["return"] <= lower, "color"] = colors[0]
    assert df["color"].isna().sum() == 0
    return df


def plot_html(tickers, sectors, returns, positions, outliers_pct: float) -> str:
    max_abs_return_value = np.abs([np.quantile(returns, outliers_pct / 2 / 100),
                                   np.quantile(returns, (100 - outliers_pct) / 2 / 100)]).max()
    max_abs_return_value = round(max_abs_return_value * 2) / 2

    df = pd.DataFrame(
        {
            "ticker":   tickers,
            "sector": sectors,
            "return": returns,
            "position": positions,
        }
    )
    df = add_color(df)

    df["position"] = df["position"].round()
    df.sort_values(by=["ticker", "sector"], inplace=True)

    fig = px.treemap(
        df,
        path=["sector", "ticker"],
        # box sizes
        values="position",
        # colors
        color="return",
        color_continuous_scale=["red", "yellow", "green"],
        color_continuous_midpoint=0.0,
        range_color=[-max_abs_return_value, max_abs_return_value],
        hover_data={"return": ":.4f"},
    )
    fig.data[0].customdata = np.column_stack(
        [df["position"].tolist(), df["return"].tolist()]
    )
    fig.data[0].texttemplate = "%{label}<br>Position:\t%{customdata[0]:,} RUB<br>Return:\t%{customdata[1]:.2f}%"
    fig.update_layout(margin=dict(t=50, l=25, r=25, b=25))
    return offline.plot(fig, include_plotlyjs=True, output_type='div')


def get_return(prev_px: float, curr_px: float) -> float:
    return (curr_px - prev_px) / prev_px * 100


async def visualize_async(token: str, account_id: str) -> str:
    # Create client
    force_update = True
    N_DAYS = 10
    OUTLIERS_PCT = 10.0
    async with inv.AsyncClient(token=token) as client:
        # load shares
        shares: list[inv.Share] = (await load_from_cache('shares', get_shares(client), force_update)).instruments
        # load last prices
        last_prices: list[inv.LastPrice] = (await load_from_cache('last_prices', get_last_prices(client, shares), force_update)).last_prices
        # load positions
        positions: list[inv.PositionsSecurities] = (await load_from_cache('positions', get_positions(client, account_id), force_update)).securities

        # map figi to share and last price
        shares_by_figi: dict[str, inv.Share] = {share.figi: share for share in shares}
        last_prices_by_figi = {last_price.figi: quotation_to_float(last_price.price) for last_price in last_prices}

        # filter positions to be shares in rub
        positions = [pos for pos in positions if pos.instrument_type == 'share' and shares_by_figi[pos.figi].currency == 'rub']

        # filter shares presented in positions
        positions_figi = {pos.figi for pos in positions}
        shares = [share for share in shares if share.figi in positions_figi]

        # get candles for shares in positions
        candles: list[list[inv.GetCandlesResponse]] = (await load_from_cache('position_candles', get_candles(client, shares, n_days=N_DAYS), force_update))
        candles_by_figi = {share.figi: share_candles_response.candles for share, share_candles_response in zip(shares, candles)}

    yesterday_close_by_figi = {pos.figi: get_yesterday_close(candles_by_figi[pos.figi]) for pos in positions}

    # positions, shares_by_figi, last_prices_by_figi, candles_by_figi, yesterday_close_by_figi

    tickers = [shares_by_figi[pos.figi].ticker for pos in positions]
    sectors = [shares_by_figi[pos.figi].sector for pos in positions]
    returns = [get_return(yesterday_close_by_figi[pos.figi], last_prices_by_figi[pos.figi]) for pos in positions]
    positions_rub = np.array([pos.balance * last_prices_by_figi[pos.figi] for pos in positions])

    return plot_html(tickers, sectors, returns, positions_rub, outliers_pct=OUTLIERS_PCT)


def visualize(token: str, account_id: str) -> str:
    return asyncio.run(visualize_async(token, account_id))
