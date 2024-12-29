import pandas as pd
import numpy as np
import sys
sys.path.append("<path here>")
import daycount
import calendar
import datetime
import scipy.optimize
import scipy.stats
import numpy as np
from types import NoneType

''' SIMPLE VOL '''
def simple_vol(data : pd.DataFrame):
    '''
    
    Calculates estimated historic volatility using simple log() division.
    

    Parameters
    ----------
    `data` : pd.DataFrame
        The dataframe with NON-NORMALIZED PRICES to calculate volatility for, 
        with rows ordered from oldest (top) to most recent (bottom).

        *note* n >= 2 observations required. Column header 
        names must conform to "open", "high", "low", and "close"

    Returns
    -------
    `float`
        The instrument's estimated simple historic volatility.
    
    '''

    # get past year of trading days
    DIY = 366 if calendar.isleap(data.index[-1].year - 1) else 365
    days = daycount.trading_days(start=data.index[-1] - datetime.timedelta(days=DIY), end=data.index[-1])

    temp = data[["close"]].copy()
    temp["prior_close"] = temp["close"].shift(1)
    temp.dropna(inplace=True)

    returns = np.log(temp["close"] / temp["prior_close"])

    if len(returns) == 1:
        dailyVol = np.sqrt((returns**2).values[0])
    else:
        dailyVol = returns.std()

    return dailyVol * np.sqrt(days)

''' GARMAN KLASS VOL (SINGE-PERIOD)'''
def _four_sigma(row: pd.Series) -> float:

    left = .511 * (row["u"] - row["d"])**2
    middle = .019 * (row["c"] * (row["u"] + row["d"]) - 2 * row["u"] * row["d"])
    right = .383 * row["c"]**2

    return left - middle - right

def _six_sigma(row: pd.Series) -> float:

    # trading day: 9:30-4:00: 6h + 30m (in seconds)
    tradingFor = (6 * 60 * 60) + (30 * 60)
    
    f = row["time_diff"] / (row["time_diff"] + tradingFor)
    a = .12

    left = a * ( (row["open"] - row["prior_close"])**2 / f )
    right = (1 - a) * (_four_sigma(row) / (1 - f))

    return left + right

def _garman_klass(row):
    return _six_sigma(row)

def garman_klass(data : pd.DataFrame):
    '''

    Calculates estimated historic volatility using Garman Klass (Jan 1980), JOB:
    https://www.jstor.org/stable/2352358

    *note* currenly coded for standard 0930-1600 open / close, adjust as needed.
        
    *note* Garman-Klass requires specifications for gaps between trading days - 
    currenly, the only alignments available are for midnight and Chicago
    equities market open. This is less of an issues for Mon-Fri 23/6 futures, but 
    leaves something to be desired for the Fri-Sun gap. 


    Parameters
    ----------
    `data` : pd.DataFrame
        The dataframe with NON-NORMALIZED PRICES to calculate volatility for, with 
        rows ordered from oldest (top) to most recent (bottom).

        *note* n >= 2 observations required, column header names must conform 
        to "open", "high", "low", and "close"

    Returns
    -------
    `float`
        The instrument's estimated historic volatility.
    
    '''

    # get past year of trading days
    DIY = 366 if calendar.isleap(data.index[-1].year - 1) else 365
    days = daycount.trading_days(start=data.index[-1] - datetime.timedelta(days=DIY), end=data.index[-1])

    temp = np.log(data[["open", "high", "low", "close"]].copy())

    # Garman Klass variables
    temp["u"] = temp["high"] - temp["open"]
    temp["d"] = temp["low"] - temp["open"]
    temp["c"] = temp["close"] - temp["open"]
    temp["prior_close"] = temp["close"].shift(1)

    # add 6.5h to last open to calculate close time, subtract from next open for total "non-trading" hours
    temp["time_diff"] = (temp.index.to_series() - (temp.index.to_series().shift(1) + datetime.timedelta(hours=6, minutes=30))).dt.total_seconds().values

    temp = temp.dropna().apply(_garman_klass, axis=1)
    estVol = np.sqrt(temp.mean()) * np.sqrt(days)
    
    return estVol
    
''' YANG ZHANG VOL (MULTI-PERIOD)'''
def _rogers_satchell(data : pd.DataFrame) -> float:

    u = np.log(data["high"] / data["open"]) 
    d = np.log(data["low"] / data["open"])
    c = np.log(data["close"] / data["open"])

    return (u * (u - c) + d * (d - c)).mean()
    
def _overnight(data : pd.DataFrame) -> float:

    temp = np.log(data["open"] / data["prior_close"])

    if len(temp) == 1:
        return (temp**2).values[0]
    else:
        return temp.var()

def _open_to_close(data : pd.DataFrame) -> float:

    temp = np.log(data["close"] / data["open"])

    if len(temp) == 1:
        return (temp**2).values[0]
    else:
        return temp.var()

def yang_zhang(data : pd.DataFrame) -> float:
    '''
    
    Calculates estimated historic volatility using Yang Zhang (July 2000), JOB:
    https://www.jstor.org/stable/10.1086/209650?seq=1
    

    Parameters
    ----------
    `data` : pd.DataFrame
        The dataframe with NON-NORMALIZED prices to calculate volatility for, 
        with rows ordered from oldest (top) to most recent (bottom).

        *note* n >= 2 observations required, column header names must conform 
        to "open", "high", "low", and "close"

    Returns
    -------
    `float`
        The instrument's estimated historic volatility.
    
    '''

    # get past year of trading days
    DIY = 366 if calendar.isleap(data.index[-1].year - 1) else 365
    days = daycount.trading_days(start=data.index[-1] - datetime.timedelta(days=DIY), end=data.index[-1])

    # create temp dataset with prior close column
    temp = data.copy()
    length = len(temp)

    temp["prior_close"] = temp["close"].shift(1)
    temp.dropna(inplace=True)

    k = 0.34 / (1.34 + (length + 1) / (length - 1))

    return np.sqrt(_overnight(temp) + k * _open_to_close(temp) + (1 - k) * _rogers_satchell(temp)) * np.sqrt(days)

''' NEW OPTION VOL '''
def _newton_implied(vol : float, realPrice : float, otype : str, 
                    ccr : float, r_tenor : float, t_tenor : float, 
                    f_mark : float, strike : float) -> float:

    # Black-76 Variables
    discount = np.exp((-ccr) * r_tenor)
    d_plus = (np.log(f_mark / strike) + (vol**2 / 2) * t_tenor) / (vol * np.sqrt(t_tenor))
    d_minus = d_plus - vol * np.sqrt(t_tenor)

    # Black-76 Option Pricing Model (OPM)
    if otype == "call":
        estPrice = discount * (f_mark * scipy.stats.norm.cdf(d_plus) - strike * scipy.stats.norm.cdf(d_minus))

    elif otype == "put":
        estPrice = discount * (strike * scipy.stats.norm.cdf(-d_minus) - f_mark * scipy.stats.norm.cdf(-d_plus))

    return estPrice - realPrice

def _corrado_miller_implied(realPrice : float, otype : str, 
                            t_tenor : float, f_mark : float, 
                            strike : float, discount : float) -> float:

    # Put-Call Parity as needed, Corrado & Miller written for calls
    if otype == "put":

        # C - P = D * (F - K)
        C = realPrice + discount * (f_mark - strike)

    else:
        C = realPrice

    # Corrado & Miller Estimation:
    left = np.sqrt(2 * np.pi) * ( ( C - ( (f_mark*discount - strike*discount) / 2) ) / (f_mark*discount + strike*discount) )
    rightLeft = 2*np.pi * ( ( C - ( (f_mark*discount - strike*discount) / 2) ) / (f_mark*discount + strike*discount) )**2
    rightRight = 1.85 * ( (f_mark*discount - strike*discount)**2 / (4*np.pi * (f_mark*discount + strike*discount) * np.sqrt(strike*discount*f_mark*discount)) )
    
    # Corrado & Miller's estimate
    estVol = left + np.sqrt(rightLeft - rightRight) / np.sqrt(t_tenor)

    return estVol

def option_vol(oPrice : tuple[float], 
               otype: str,
               strike : float,
               now : datetime.datetime,
               expir : datetime.datetime,
               fMark : float,
               rf : float,
               lastVol : float | None = None) -> None:

    # static variables
    otype = otype
    strike = strike
    t_tenor = daycount.trading_T(now, expir)
    r_tenor = daycount.actual360_T(now, expir)
    f_mark = fMark
    
    # prices
    bid = oPrice[0]
    ask = oPrice[1]

    # compounded rates / discount
    ccr = 360 * np.log(1 + rf / 360)
    discount = np.exp((-ccr) * r_tenor)

    # set initial vol estimate
    rerun = False
    if isinstance(lastVol, NoneType):
        
        # will need to rerun entire function once final implied vol calculated,
        # this vol is an initial estimate for bid-ask weights when picking mark
        rerun = True

        # choose nearest mark, consider null contracts 0
        if isinstance(bid, NoneType):
            tempMark = ask
        elif isinstance(ask, NoneType):
            tempMark = bid
        else:
            tempMark = (bid * .5) + (ask * .5)

        # there must must be intrinsic value no matter how far in the money
        if (otype == "call") and (f_mark >= strike + tempMark):
            
            # will either drop between bid / ask, or only be worth intrinsic value
            tempPrice = (f_mark - strike)
        
        # there must be intrinsic value no matter how far in the money
        elif (otype == "put") and (f_mark <= strike - tempMark):
            
            # will either drop between bid / ask, or only be worth intrinsic value
            tempPrice = (strike - f_mark)
        
        # otherwise priced in already
        else:
            tempPrice = tempMark

        # initial vol estimate
        vol = _corrado_miller_implied(tempPrice, otype, t_tenor, 
                                      f_mark, strike, discount)
    
    else:
        vol = lastVol

    # estimate standardized moneyness (vol adjusted, time independent):
    if otype == "call":
        moneyness = np.log(f_mark / strike) / ( np.sqrt(t_tenor) * vol )

    elif otype == "put":
        moneyness = np.log(strike / f_mark) / ( np.sqrt(t_tenor) * vol )

    # probability of closing ITM
    probability = scipy.stats.norm(0, 1).cdf(moneyness)

    # weigh towards bid, more sellers than buyers for ITM
    if moneyness >= 0:
        bidAdj = probability
        askAdj = 1 - bidAdj

    # weigh towards ask, more buyers than sellers for OTM
    else:
        askAdj = probability
        bidAdj = 1 - askAdj

    # consider null contracts 0, adjust for weights
    if isinstance(bid, NoneType):
        newTempMark = ask
    elif isinstance(ask, NoneType):
        newTempMark = bid
    else:
        realMark = (bid + ask) / 2
        newTempMark = (bid * bidAdj) + (ask * askAdj)

    # there must must be intrinsic value no matter how far in the money
    if (otype == "call") and (f_mark - strike > newTempMark):
        
        # will either drop between bid / ask, or only be worth intrinsic value
        realPrice = (f_mark - strike)
    
    # there must be intrinsic value no matter how far in the money
    elif (otype == "put") and (strike - f_mark > newTempMark):
        
        # will either drop between bid / ask, or only be worth intrinsic value
        realPrice = (strike - f_mark)
        
    else:
        realPrice = newTempMark

    # estimate implied vol via Newton-Raphson convergence (first guess is either prior vol or Corrado-Miller estimate)
    vol = scipy.optimize.newton(_newton_implied, vol,
                                 args=(realPrice, otype, ccr, r_tenor, 
                                       t_tenor, f_mark, strike))
    
    # if initializing, rerun with new implied vol to narrow estimates
    if rerun:
        vol = option_vol(oPrice, otype, strike, now,
                         expir, f_mark, rf, vol)
    
    return vol






