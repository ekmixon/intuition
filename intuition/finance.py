# -*- coding: utf-8 -*-
# vim:fenc=utf-8

'''
  Intuition finance core
  ----------------------

  Financial library

  :copyright (c) 2014 Xavier Bruhiere
  :license: Apache 2.0, see LICENSE for more details.
'''


from pandas.core.datetools import BDay
import numpy as np
import math
import datetime as dt
import dna.logging

log = dna.logging.logger(__name__)


# NOTE This is temporary copied from QSTK library
#     which will be more used in the future
def qstk_get_sharpe_ratio(rets, risk_free=0.00):
    """
    @summary Returns the daily Sharpe ratio of the returns.
    @param rets: 1d numpy array or fund list of daily returns (centered on 0)
    @param risk_free: risk free returns, default is 0%
    @return Annualized rate of return, not converted to percent
    """
    f_dev = np.std(rets, axis=0)
    f_mean = np.mean(rets, axis=0)

    return (f_mean * 252 - risk_free) / (f_dev * np.sqrt(252))


def moving_average(data, periods, type='simple'):
    """
    compute a <periods> period moving average.
    type is 'simple' | 'exponential'
    """
    data = np.asarray(data)
    if type == 'simple':
        weights = np.ones(periods)
    else:
        weights = np.exp(np.linspace(-1., 0., periods))

    weights /= weights.sum()

    mavg = np.convolve(data, weights, mode='full')[:len(data)]
    mavg[:periods] = mavg[periods]
    return mavg


def relative_strength(prices, periods=14):
    """
    compute the <periods> period relative strength indicator
    http://stockcharts.com/school/doku.php?\
        id=chart_school:glossary_r#relativestrengthindex
    http://www.investopedia.com/terms/r/rsi.asp
    """
    deltas = np.diff(prices)
    seed = deltas[:periods + 1]
    up = seed[seed >= 0].sum() / periods
    down = -seed[seed < 0].sum() / periods
    ratio = up / down
    rsi = np.zeros_like(prices)
    rsi[:periods] = 100. - 100. / (1. + ratio)

    for i in range(periods, len(prices)):
        delta = deltas[i - 1]  # Cause the diff is 1 shorter

        if delta > 0:
            upval = delta
            downval = 0.
        else:
            upval = 0.
            downval = -delta

        up = (up * (periods - 1) + upval) / periods
        down = (down * (periods - 1) + downval) / periods

        ratio = up / down
        rsi[i] = 100. - 100. / (1. + ratio)

    return rsi


def moving_average_convergence(data, nslow=26, nfast=12):
    """
    compute the MACD (Moving Average Convergence/Divergence)
    using a fast and slow exponential moving avg
    return value is emaslow, emafast, macd which are len(data) arrays
    """
    emaslow = moving_average(data, nslow, type='exponential')
    emafast = moving_average(data, nfast, type='exponential')
    return emaslow, emafast, emafast - emaslow


def cc_annualize_returns(ret_per_period, periods_per_year):
    return math.log(1 + annualized_returns(ret_per_period, periods_per_year))


def annualized_returns(ret_per_period, periods_per_year):
    ''' Could use:
    res1 = averageReturns(Series([ret_per_period]*periods_per_year), \
            period=1, type='net')
    '''
    return pow(1 + ret_per_period, periods_per_year) - 1


def average_returns(ts, **kwargs):
    ''' Compute geometric average returns from a returns time serie'''
    average_type = kwargs.get('type', 'net')
    relative = 0 if average_type == 'net' else -1
    #start = kwargs.get('start', ts.index[0])
    #end = kwargs.get('end', ts.index[len(ts.index) - 1])
    #delta = kwargs.get('delta', ts.index[1] - ts.index[0])
    period = kwargs.get('period')
    avg_ret = 1
    for idx in range(len(ts.index)):
        if idx % period == 0:
            avg_ret *= (1 + ts[idx] + relative)
    return avg_ret - 1


def cc_returns(ts, **kwargs):
    start = kwargs.get('start')
    end = kwargs.get('end', dt.datetime.now())
    delta = kwargs.get('deltaya', BDay())
    period = kwargs.get('period')
    rets = returns(ts, type='net', start=start, end=end,
                   delta=delta, period=period)
    return math.log(1 + rets)


#TODO care of dividends
#TODO care of inflation
def returns(ts, **kwargs):
    '''
    Compute returns on the given period

    @param ts : time serie to process
    @param kwargs.type: gross or simple returns
    @param delta : period betweend two computed returns
    @param start : with end, will return the return betweend this elapsed time
    @param period : delta is the number of lines/periods provided
    @param end : so said
    @param cumulative: compute cumulative returns
    '''
    returns_type = kwargs.get('type', 'net')
    cumulative = kwargs.get('cumulative', False)
    relative = 0 if returns_type == 'net' else 1
    start = kwargs.get('start')
    end = kwargs.get('end', dt.datetime.now())
    #delta = kwargs.get('delta', None)
    period = kwargs.get('period', 1)
    if isinstance(start, dt.datetime):
        log.debug(f'{ts[end]} / {ts[start]} -1')
        return ts[end] / ts[start] - 1 + relative
    rets_df = ts / ts.shift(period) - 1 + relative
    return rets_df.cumprod() if cumulative else rets_df[1:]


def daily_returns(ts, **kwargs):
    ''' re-compute ts on a daily basis '''
    relative = kwargs.get('relative', 0)
    return returns(ts, delta=BDay(), relative=relative)


def panel_to_retsDF(data, kept_field='close', output='dataframe'):
    '''
    @summary transform data in DataAccess format to a dataframe
             suitable for qstk.tsutils.optimizePortfolio()
    @param data: data like quotes['close']['google']
    @output : a dataframe, cols = companies, rows = dates
    '''
    #TODO Here a need of data normalisation
    df = data[kept_field]
    df.fillna(method='ffill')
    df.fillna(method='backfill')
    if output == 'array':
        return returns(df, relative=0).values
    return returns(df, relative=0)  # 1 in doc, 0 in example


def sharpe_ratio(ts):
    #TODO: Dataframe handler
    rets = daily_returns(ts)
    return (np.mean(rets) / rets.stdev()) * np.sqrt(len(rets))


def high_low_spread(df, offset):
    ''' Compute continue spread on given datafrme every offset period '''
    #TODO: handling the offset period with reindexing or resampling, sthg like:
    # subIndex = df.index[conditions]
    # df = df.reindex(subIndex)
    return df['high'] - df['low']
