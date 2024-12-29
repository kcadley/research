import sys
sys.path.append("<path here>")
import tsty
sys.path.append("<path here>")
import dxlink
sys.path.append("<path here>")
import contracts

import datetime
import time
import numpy as np
import pandas as pd 
from scipy.interpolate import LSQUnivariateSpline

''' VOL SMILE '''
def vol_smile(rf : float, 
              qf : float, 
              settle : datetime.datetime,
              ftsym : str, 
              fqsym : str, 
              ocode : str, 
              expir : datetime.datetime,
              afterHours : bool = False) -> list[pd.DataFrame]:
    '''
    
    Calculates the current volatility smile of a given issue. Takes a minimum
    of 15 seconds to allow for all quotes to populate prior to modeling.
    
    *note* An active dxlink market token is required.
    
    
    Parameters
    ----------
    `rf` : float
        The quoted currency's risk-free rate ("domestic").

    `qf` : float
        The base currency's risk-free rate ("foreign").

    `settle` : datetime.datetime
        The settlement date of the contract.
        
    `ftsym` : str
        Symbol used to place trades on the instrument.

        *note* Must be in Tasty symbology.

    `fqsym` : str
        Symbol used to request quotes on the future.

        *note* Must be in DXLink symbology.
    
    `ocode` : str
        The option issue's DXLink code (month and TWO DIGIT year included): "EUUZ24"

    `expir` : datetime.datetime,
        The option issue's expiration.

    `afterHours` : bool = False
        Whether to pull afterhours data or not.

    Returns
    -------
    `LSQUnivariateSpline`
        A scipy.interpolate model (spline), with knots set at the underlying's 
        expected value at time of the options expirations (1-3 standard deviations
        from current price, using current strike's implied vol)

    `pd.DataFrame`
        A dataframe with the fitted implied volatilities (spline w/ knots at
        1, 2, and 3 std deviations of volatility), and equivalent median-smoothed
        "real" implied volatilities:
        ["fitted", "median"]

    '''

    # APIs
    tasty = tsty.Tasty(live=True)
    link = dxlink.DXLink(afterHours=afterHours)

    # model underlying
    spot = contracts.FXSpot(qsym="", tsym="")
    future = contracts.CurrencyFuture(rf=rf, 
                                      qf=qf,
                                      settle=settle,
                                      tsym=ftsym,
                                      qsym=fqsym,
                                      underlying=spot)

    # start underlying stream
    futureStream = link.stream([future.qsym])
    time.sleep(.5)
    while not futureStream.quote():
        futureStream = link.stream([future.qsym])
        time.sleep(.5)

    # attach stream
    future.attach_stream(futureStream)

    # pull all strikes
    allContracts = tasty.contracts(future.tsym[1:3])
    allStrikes = allContracts.options.strikes[ocode.replace("2", "")]
    allStrikes = [float(x) for x in list(allStrikes.keys())]

    # model strikes
    query = []; calls = []; puts = []
    for strike in allStrikes:
        # ITM vol on calls
        if strike >= future.mark:
            newQuery = "./{}C{}:XCME".format(ocode, str(strike))
            call = contracts.CurrencyFutureOption(otype="call", 
                                                 strike=strike, 
                                                 expir=expir, 
                                                 tsym = newQuery,
                                                 qsym = newQuery,
                                                 underlying=future)
            calls.append(call)
        
        # ITM vol on puts
        else:
            newQuery = "./{}P{}:XCME".format(ocode, str(strike))
            put = contracts.CurrencyFutureOption(otype="put", 
                                                 strike=strike, 
                                                 expir=expir, 
                                                 tsym = newQuery,
                                                 qsym = newQuery,
                                                 underlying=future)
            puts.append(put)

        query.append(newQuery)

    # start option chain stream
    chainStream = link.stream(query)
    time.sleep(.5)
    while not chainStream.quote():
        chainStream = link.stream(query)
        time.sleep(.5)
    
    # 5 seconds to populate all quotes
    time.sleep(5)

    # attach streams
    for call in calls:
        call.attach_stream(chainStream)
    for put in puts:
        put.attach_stream(chainStream)

    # 5 seconds for calculations
    time.sleep(10)
    
    # close APIs
    try:
        chainStream.close()
        link.close()
        tasty.close()
    except:
        pass

    # pull vols
    vols = []
    for call in calls:
        vols.append((call.strike, call.vol))
    for put in puts:
        vols.append((put.strike, put.vol))

    # load smile
    strikeVols = pd.DataFrame(vols).dropna()
    strikeVols = strikeVols.set_index(0).sort_index()
    strikeVols.columns = ["real"]

    # smooth significant outliers via median filter
    medFilt = strikeVols.rolling(3, center=True).median().dropna()
    medFilt.columns = ["median"]

    # create null range of prices within .000025 intervals
    start = int(medFilt.index[0] * 1000000)
    end = int(medFilt.index[-1] * 1000000)
    newIndex = [x / 1000000 for x in range(start, end + 25, 25)]
    nullRange = [np.nan for x in newIndex]

    # update null with real values
    extendedMedFilt = pd.DataFrame(nullRange, index=newIndex).sort_index()
    extendedMedFilt.columns = ["median"]     # rename for update() below
    extendedMedFilt.update(medFilt)

    # linearly interpolate median vols
    extendedMedFilt.interpolate(inplace=True)

    # identify nearest ATM median vol
    ATM = round(.000005 * round(float(future.mark)/.000005), 6)
    ATMVol = extendedMedFilt.loc[ATM].values[0]

    # use arbitrary call for time-till-expir
    up = np.exp(ATMVol * np.sqrt(calls[0].t_tenor))
    down = np.exp(-ATMVol * np.sqrt(calls[0].t_tenor))

    # calculate std deviation knots
    right3 = future.mark * up**3
    right2 = future.mark * up**2
    right1 = future.mark * up
    left1 = future.mark * down
    left2 = future.mark * down**2
    left3 = future.mark * down**3

    # set spline knots at mean and 3 std deviations up / down
    knots = [left3, left2, left1, ATM, right1, right2, right3]
    knots.sort()

    # weight heavily towards mean:
    #         N/A  3std   2std   1std   ATM    1std   2std   3std  N/A
    # weights: 1 --- 5 --- 10 --- 15 --- 15 --- 15 --- 10 --- 5 --- 1
    mask = ((extendedMedFilt.index >= left3) & (extendedMedFilt.index <= right3)).astype(int) * 4 + 1
    mask += ((extendedMedFilt.index >= left2) & (extendedMedFilt.index <= right2)).astype(int) * 5
    mask += ((extendedMedFilt.index >= left1) & (extendedMedFilt.index <= right1)).astype(int) * 5
    
    # model
    model = LSQUnivariateSpline(extendedMedFilt.index, extendedMedFilt["median"], t=knots, w=mask)
    modelYs = model(extendedMedFilt.index)
    fitted = pd.DataFrame({"strikes" : extendedMedFilt.index, "fitted" : modelYs, "median" : extendedMedFilt["median"]}).set_index("strikes")
    fitted = fitted.join(strikeVols["real"], how="outer")

    # return
    return model, fitted

