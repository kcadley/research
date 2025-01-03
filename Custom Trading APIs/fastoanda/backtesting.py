from __future__ import annotations
from threading import Thread
import datetime
import pandas as pd
from matplotlib.backends.backend_pdf import PdfPages
from threading import Thread
import matplotlib as mpl
import matplotlib.style as mplstyle
import matplotlib.pyplot as plt
import numpy as np
from scipy import stats

class Trade():
    '''
    
    A simple trade recording class.

    Attributes
    ----------
    `isOpen` : bool = True
        State of trade

    `tradeType` : str = "long"
        The position type of the trade ("long" or "short") - this is used
        to evaluated `self.pl` when the trade is closed.

    `entryPrice` : float
        The entry "fill price" of the trade.

    `exitPrice` : float
        The exit "fill price" of the trade.

    `stopLoss` : float | None = None
        The stop-loss price level attached to the trade.
    
    `takeProfit` : float | None = None
        The take-profit price level attached to the trade.

    `entryIndex` : datetime.datetime()
        The trade's starting index within the historic data used for testing.

    `exitIndex` : datetime.datetime()
        The trade's final index within the historic data used for testing.

    `age` : datetime.timedelta()
        How long the trade was open for.

    `margin` : float
        Units of capital to control a given size.
    
    `leverage` : float
        How many units of a position a single unit of margin can control,
        as defined by a float: 20:1 = .05, 50:1 = .02, etc.

    `size` : float
        Total units controlled in the trade.

    `pl` : float
        P/L of the trade.

    `ret` : float
        Percentage return on the trade.

    `priceChange` : float
        The change in asset price relative to position from entry to exit:
        short: (entry - exit) / exit
        long:  (exit - entry) / exit

    `subreturns` : pandas.DataFrame
        A dataframe indexed by the portion of historic data that the trade
        was executed over, with each entry taking the trade's return 
        on a per-period basis.

    `history` : pandas.DataFrame
        The portion of historic data that the trade was executed over.


    Methods
    -------
    `open()` : func
        Opens the trade. *note* Initializes the Trade object.

    `close()` : func
        Closes the trade, recording trade metrics. 

    `get_stats()` : func
        Prints the trade's statistics.

    '''

    # backtest data
    _data = None

    # slippage attributes
    _slipEstimates = {
            #''' Major Pairs '''
            "USD_JPY" : {"lowVol" : np.arange(0.001, 0.0051, .0001),       "highVol" : np.arange(.01, .031, .0001)},
            "USD_CAD" : {"lowVol" : np.arange(0.00002, 0.000071, .000001), "highVol" : np.arange(.0001, .00041, .000001)},
            "USD_CHF" : {"lowVol" : np.arange(0.00002, 0.000071, .000001), "highVol" : np.arange(.0001, .00041, .000001)},
            "NZD_USD" : {"lowVol" : np.arange(0.00003, 0.000081, .000001), "highVol" : np.arange(.0001, .00051, .000001)},
            "GBP_USD" : {"lowVol" : np.arange(0.00002, 0.000061, .000001), "highVol" : np.arange(.0001, .00031, .000001)},
            "EUR_USD" : {"lowVol" : np.arange(0.00001, 0.000051, .000001), "highVol" : np.arange(.0001, .00031, .000001)},

            #''' Minor Pairs '''
            "USD_DKK" : {"lowVol" : np.arange(0.0001, .0003, .000001),    "highVol" : np.arange(.0005, .0015, .000001)},
            "GBP_AUD" : {"lowVol" : np.arange(0.00009, .000141, .000001), "highVol" : np.arange(.0004, .00071, .000001)},
            "GBP_CAD" : {"lowVol" : np.arange(0.00009, .000141, .000001), "highVol" : np.arange(.0004, .00071, .000001)},
            "GBP_CHF" : {"lowVol" : np.arange(0.00009, .000141, .000001), "highVol" : np.arange(.0004, .00071, .000001)},
            "GBP_NZD" : {"lowVol" : np.arange(0.00009, .000141, .000001), "highVol" : np.arange(.0004, .00071, .000001)},
            "GBP_SGD" : {"lowVol" : np.arange(0.00009, .000141, .000001), "highVol" : np.arange(.0004, .00071, .000001)},
            "EUR_NOK" : {"lowVol" : np.arange(0.00008, .000131, .000001), "highVol" : np.arange(.0003, .00071, .000001)},
            "EUR_NZD" : {"lowVol" : np.arange(0.00008, .000131, .000001), "highVol" : np.arange(.0003, .00071, .000001)},
            "EUR_PLN" : {"lowVol" : np.arange(0.00008, .000131, .000001), "highVol" : np.arange(.0003, .00071, .000001)},
            "EUR_SEK" : {"lowVol" : np.arange(0.00008, .000131, .000001), "highVol" : np.arange(.0003, .00071, .000001)},
            "EUR_SGD" : {"lowVol" : np.arange(0.00008, .000131, .000001), "highVol" : np.arange(.0003, .00071, .000001)},
            "AUD_NZD" : {"lowVol" : np.arange(0.00008, .000131, .000001), "highVol" : np.arange(.0003, .00071, .000001)},
            "AUD_SGD" : {"lowVol" : np.arange(0.00008, .000131, .000001), "highVol" : np.arange(.0003, .00071, .000001)},
            "AUD_USD" : {"lowVol" : np.arange(0.00002, .000061, .000001), "highVol" : np.arange(.0001, .00041, .000001)},
            "CAD_SGD" : {"lowVol" : np.arange(0.00008, .000131, .000001), "highVol" : np.arange(.0003, .00071, .000001)},
            "SGD_CHF" : {"lowVol" : np.arange(0.00008, .000131, .000001), "highVol" : np.arange(.0003, .00071, .000001)},
            "NZD_CAD" : {"lowVol" : np.arange(0.00008, .000131, .000001), "highVol" : np.arange(.0003, .00071, .000001)},
            "NZD_SGD" : {"lowVol" : np.arange(0.00008, .000131, .000001), "highVol" : np.arange(.0003, .00071, .000001)},
            "NZD_CHF" : {"lowVol" : np.arange(0.00008, .000131, .000001), "highVol" : np.arange(.0003, .00071, .000001)},
            "GBP_ZAR" : {"lowVol" : np.arange(.0001, .00031, .000001),    "highVol" : np.arange(.0005, .00151, .000001)},
            "EUR_GBP" : {"lowVol" : np.arange(0.00005, .00011, .000001),  "highVol" : np.arange(.0002, .00051, .000001)},
            "NZD_JPY" : {"lowVol" : np.arange(0.007, .0121, .0001),       "highVol" : np.arange(.03, .061, .0001)},
            "GBP_JPY" : {"lowVol" : np.arange(0.007, .0121, .0001),       "highVol" : np.arange(.03, .061, .0001)},
            "EUR_JPY" : {"lowVol" : np.arange(0.005, .011, .0001),        "highVol" : np.arange(.02, .051, .0001)},
            "CHF_JPY" : {"lowVol" : np.arange(0.007, .0131, .0001),       "highVol" : np.arange(.03, .071, .0001)},
            "CAD_JPY" : {"lowVol" : np.arange(0.008, .0131, .0001),       "highVol" : np.arange(.03, .071, .0001)},
            "AUD_JPY" : {"lowVol" : np.arange(0.007, .0121, .0001),       "highVol" : np.arange(.03, .061, .0001)},
            "SGD_JPY" : {"lowVol" : np.arange(0.008, .0131, .0001),       "highVol" : np.arange(.03, .071, .0001)},

            # ''' Exotic Pairs '''
            "GBP_PLN" : {"lowVol" : np.arange(.0005, .001, .000001),          "highVol" : np.arange(.002, .005, .000001)},
            "USD_HUF" : {"lowVol" : np.arange(.01, .031, .0001),          "highVol" : np.arange(.05, .151, .0001)},
            "USD_SGD" : {"lowVol" : np.arange(0.00008, .00021, .000001),  "highVol" : np.arange(.0004, .0011, .000001)},
            "EUR_HUF" : {"lowVol" : np.arange(.01, .031, .0001),          "highVol" : np.arange(.05, .151, .0001)},
            "ZAR_JPY" : {"lowVol" : np.arange(.01, .031, .0001),          "highVol" : np.arange(.05, .151, .0001)},
            "USD_MXN" : {"lowVol" : np.arange(.0001, .00031, .000001),    "highVol" : np.arange(.0005, .00151, .000001)},
            "USD_NOK" : {"lowVol" : np.arange(.0001, .00031, .000001),    "highVol" : np.arange(.0005, .00151, .000001)},
            "USD_PLN" : {"lowVol" : np.arange(.0001, .00031, .000001),    "highVol" : np.arange(.0005, .00151, .000001)},
            "USD_SEK" : {"lowVol" : np.arange(.0001, .00031, .000001),    "highVol" : np.arange(.0005, .00151, .000001)},
            "USD_THB" : {"lowVol" : np.arange(.0001, .00031, .000001),    "highVol" : np.arange(.0005, .00151, .000001)},
            "USD_ZAR" : {"lowVol" : np.arange(.0001, .00031, .000001),    "highVol" : np.arange(.0005, .00151, .000001)},
            "USD_CNH" : {"lowVol" : np.arange(.0001, .00031, .000001),    "highVol" : np.arange(.0005, .00151, .000001)},
            "USD_CZK" : {"lowVol" : np.arange(.0001, .00031, .000001),    "highVol" : np.arange(.0005, .00151, .000001)},
            "EUR_ZAR" : {"lowVol" : np.arange(.0001, .00031, .000001),    "highVol" : np.arange(.0005, .00151, .000001)},
            "CHF_ZAR" : {"lowVol" : np.arange(.0001, .00031, .000001),    "highVol" : np.arange(.0005, .00151, .000001)},
            "EUR_CZK" : {"lowVol" : np.arange(.0001, .00031, .000001),    "highVol" : np.arange(.0005, .00151, .000001)},
            "EUR_AUD" : {"lowVol" : np.arange(0.00005, .00011, .000001),  "highVol" : np.arange(.0002, .00061, .000001)},
            "EUR_CAD" : {"lowVol" : np.arange(0.00005, .00011, .000001),  "highVol" : np.arange(.0002, .00061, .000001)},
            "EUR_CHF" : {"lowVol" : np.arange(0.00006, .00011, .000001),  "highVol" : np.arange(.0002, .00051, .000001)},
            "CAD_CHF" : {"lowVol" : np.arange(0.00008, .000131, .000001), "highVol" : np.arange(.0003, .00071, .000001)},
            "AUD_CHF" : {"lowVol" : np.arange(0.00008, .000131, .000001), "highVol" : np.arange(.0003, .00071, .000001)},
            "AUD_CAD" : {"lowVol" : np.arange(0.00008, .000131, .000001), "highVol" : np.arange(.0003, .00071, .000001)}
           }

    _volPivot = None
    _lowVol = None
    _highVol = None
    _hlVol = None
    _slippage = None

    @classmethod
    def load(cls, target : str, data : pd.DataFrame) -> None:
        '''
        
        Loads data and slippage estimates to into the class prior to creating
        trade objects.

        
        Parameters
        ----------
        `target` : str
            The target instrument backtesting over: "EUR_USD", etc.

        `data` : pd.DataFrame
            The historic data used in the backtest - must contain bid-ask
            details with columns named "o_ask", "o_bid", "c_ask", and "c_bid".
        
        Returns
        -------
        `None`
        
        '''

        ''' LOAD DATA '''
        # set the data
        cls._data = data

        ''' SLIPPAGE ESTIMATES '''
        # calculate distance between spread
        open_spreads = data["o_ask"] - data["o_bid"]
        close_spreads = data["c_ask"] - data["c_bid"]

        # aggregate spreads
        all_spreads = pd.concat([open_spreads, close_spreads], axis=0)

        # set volatility point (below will be considered "low volatility" and 
        # above will be "high volatility"
        cls._volPivot = all_spreads.median() + all_spreads.std()

        # segregate data by volatility point - *note* only including `=` in 
        # _lowVol to avoid percentile filtering errors, anything that is equal 
        # to _volPivot will be actually classified as "high" later on
        cls._lowVol = all_spreads[all_spreads <= cls._volPivot]
        cls._highVol = all_spreads[all_spreads >= cls._volPivot]

        # pull high-low spread (will used for "mid" spread multiplier)
        cls._hlVol = data["h_ask"] - data["l_bid"]

        # pull slippage estimates
        cls._slippage = cls._slipEstimates[target]

        return None

    def __init__(self, 
                 tradeType : str,
                 entryPrice : float,
                 entryIndex : datetime.datetime,
                 margin : float | int = 1,
                 leverage : float | int = 1,
                 stopLoss : float | None = None, 
                 takeProfit : float | None = None,
                 slipOn : str | None = None) -> None:
        '''
        
        Initializes `trade` object.

        
        Parameters
        ----------
        `tradeType` : str = "long"
            The position type of the trade ("long" or "short") - this is used
            to evaluated `self.pl` when the trade is closed.

        `entryPrice` : float
            The entry "fill price" of the trade.

        `entryIndex` : datetime.datetime
            The trade's starting index within the historic data used for testing.

        `margin` : float | int = 1
            Capital used to enter the position.

        `leverage` : float | int = 1
            Size controlled to margin used: .05 = 20:1, .02 = 50:1, etc.
            *note* position size = `margin` * 1 / `leverage`.

        `stopLoss` : float | None = None
            The stop-loss price level attached to the trade.
        
        `takeProfit` : float | None = None
            The take-profit price level attached to the trade.

        `slipOn` : str | None = None
            Whether to apply slippage to the order. Slippaged applied is based 
            on the volatility of the `entryIndex`'s open or close spread: 
            ["open", "close"]


        Returns
        -------
        Trade : obj
            (Custom) A simple trade recording object.

        '''

        # open attributes
        self.isOpen = True
        self.tradeType = tradeType

        if tradeType == "long":
            self.entryPrice = entryPrice + self._est_slippage(entryIndex, slipOn)
        elif tradeType == "short":
            self.entryPrice = entryPrice - self._est_slippage(entryIndex, slipOn)
        
        self.margin = margin
        self.leverage = leverage
        self.size = self.margin * (1 / self.leverage)
        self.stopLoss = stopLoss
        self.takeProfit = takeProfit
        self.entryIndex = entryIndex
        
        # close attributes
        self.exitPrice = None
        self.exitIndex = None
        self.pl = None
        self.ret = None
        self.priceChange = None
        self.avgRets = None
        self.history = None
        self.age = None

        return None
    
    def _est_slippage(self, index : datetime.datetime, slipOn : str | None) -> float:
        '''
        
        Estimates slippage on a given trade's entry / exit order.
        

        Parameters
        -----------
        `index` : datetime.datetime
            Index of the Series in the backtest's DataFrame that the order is
            entering / exiting on.

        `slipOn` : str
            Whether the slippage should be calculated off of "open" or "close"
            estimates: ["open", "close"]
        
        '''
        
        if isinstance(slipOn, str):

            # calculate spread between bid and ask
            if slipOn == "open":
                spread = self._data.loc[index]["o_ask"] - self._data.loc[index]["o_bid"]

            elif slipOn == "close":
                spread = self._data.loc[index]["c_ask"] - self._data.loc[index]["c_bid"]

            elif slipOn == "mid":
                # average of opening spread and closing spread
                openSpread = self._data.loc[index]["o_ask"] - self._data.loc[index]["o_bid"]
                closeSpread = self._data.loc[index]["c_ask"] - self._data.loc[index]["c_bid"]
                midSpread = (openSpread + closeSpread) / 2
                
                # multiplied by volatility of high / low between the open and close
                # multiplier = percentile / 50 -> median H/L spread will only multiply by 1
                hlSpread = self._data.loc[index]["h_ask"] - self._data.loc[index]["l_bid"]
                multiplier = stats.percentileofscore(self._hlVol, hlSpread) / 50
                spread = midSpread * multiplier

            # if considered "low volatility", pull percentile within low volatility
            if spread < self._volPivot:
                percentile = stats.percentileofscore(self._lowVol, spread)
                percentile = (percentile * 100 // 1) / 100
                slippage = np.percentile(self._slippage["lowVol"], percentile)

            # if considered "high volatility", pull percentile within high volatility
            else:
                percentile = stats.percentileofscore(self._highVol, spread)
                percentile = (percentile * 100 // 1) / 100
                slippage = np.percentile(self._slippage["highVol"], percentile)

        else:
            slippage = 0

        return slippage

    def _get_subreturns(self):
        '''
        
        Calculates a trade's per-period returns over the lifetime of the trade.

        
        Parameters
        ----------
        None

        Returns
        -------
        `None`
        
        '''

        subreturns = []
        startVal = self.entryPrice
        size = self.size

        if self.tradeType == "long":

            for index, row in self.history.iterrows():
                
                # current period's returns are projected as selling at the end of this period
                if index != self.exitIndex:
                    endVal = row["c_bid"]

                # otherwise use final price of trade
                else:
                    endVal = self.exitPrice
                
                # returns as measured by capital (margin) put up
                priceChange = (endVal - startVal) / startVal
                newSize = size * (1 + priceChange)
                pl = newSize - size
                subreturns.append(pl / self.margin)
                
                # next period's returns are measured as if never actually sold this period
                startVal = row["c_bid"]
                size = newSize

        # repeat the above process, but for short trades:
        elif self.tradeType == "short":

            for index, row in self.history.iterrows():
            
                if index != self.exitIndex:
                    endVal = row["c_ask"]
            
                else:
                    endVal = self.exitPrice
                
                priceChange = (endVal - startVal) / startVal
                newSize = size * (1 + (-1) * priceChange)
                pl = newSize - size
                subreturns.append(pl / self.margin)

                # next period's returns are measured as if never actually sold this period
                startVal = row["c_ask"]
                size = newSize

        # index by history
        indexed_subreturns = pd.DataFrame({"subreturns" : subreturns}, 
                                           index=self.history.index)

        return indexed_subreturns

    @classmethod
    def open(cls,
             tradeType : str,
             entryPrice : float,
             entryIndex : datetime.datetime,
             margin : float | int = 1,
             leverage : float | int = 1,
             stopLoss : float | None = None, 
             takeProfit : float | None = None,
             slipOn : str | None = None) -> Trade:
        '''
        
        Intuitive wrapper for __init__(): Initializes `trade` object.
        Opens the trade with directional and entry "fill price" parameters 
        (and optional take profit / stop loss / historic index parameters).

        
        Parameters
        ----------
        `tradeType` : str = "long"
            The position type of the trade ("long" or "short") - this is used
            to evaluated `self.pl` when the trade is closed.

        `entryPrice` : float
            The entry "fill price" of the trade.

        `entryIndex` : datetime.datetime
            The trade's starting index within the historic data used for testing.

        `margin` : float | int = 1
            Capital used to enter the position.

        `leverage` : float | int = 1
            Capital controlled to margin used: position size = margin * (1 / leverage).
            1 = 1:1, .05 = 20:1, .02 = 50:1, etc.

        `stopLoss` : float | None = None
            The stop-loss price level attached to the trade.
        
        `takeProfit` : float | None = None
            The take-profit price level attached to the trade.

        `slippage` : str | None = None
            Whether to apply slippage to the order. Slippaged applied is based 
            on the volatility of the `entryIndex`'s open or close spread: 
            ["open", "close"]

        Returns
        -------
        Trade : obj
            (Custom) A simple trade recording object.

        '''

        newTrade = cls(tradeType=tradeType,
                       entryPrice=entryPrice,
                       margin=margin,
                       leverage=leverage,
                       stopLoss=stopLoss,
                       takeProfit=takeProfit,
                       entryIndex=entryIndex,
                       slipOn=slipOn)

        return newTrade

    def close(self,
              exitPrice : float,
              exitIndex : datetime.datetime,
              slipOn : str | None = None) ->  None:
        '''
        
        Closes the trade by setting `self.isOpen` to False and calculating the 
        trade's PL (`self.pl`) based on trade type (`self.tradeType`).

        
        Parameters
        ----------
        `exitPrice` : float
            The exit price of the trade.

        `exitIndex` : datetime.datetime
            The trade's final index within the historic data used for testing.

        `slipOn` : str | None = None
            Whether to apply slippage to the order. Slippaged applied is based 
            on the volatility of the `exitIndex`'s open or close spread: 
            ["open", "close"]
            *note* for "take profit" orders leave `slipOn=None`, "take profit"
            orders do not incur negative slippage.

        Returns
        -------
        `None`
        
        '''

        # close the trade
        self.isOpen = False
        self.exitIndex = exitIndex
        self.age = self.exitIndex - self.entryIndex

        # calculate the P/L
        if self.tradeType == "long":
            self.exitPrice = exitPrice - self._est_slippage(exitIndex, slipOn)
            self.priceChange = (self.exitPrice - self.entryPrice) / self.entryPrice
            self.pl = self.size * self.priceChange

        elif self.tradeType == "short":
            self.exitPrice = exitPrice + self._est_slippage(exitIndex, slipOn)
            self.priceChange = (self.exitPrice - self.entryPrice) / self.entryPrice
            self.pl = self.size * (-1) * self.priceChange

        self.ret = self.pl / self.margin

        # slice historic: `.loc[]` IS inclusive of end index, iloc IS NOT!
        self.history = self._data.loc[self.entryIndex:self.exitIndex]
        
        self.subreturns = self._get_subreturns()

        return None
    
    def get_stats(self) -> None:
        '''
        
        Prints the trade's statistics.

        
        Parameters
        ----------
        None

        Returns
        -------
        `None`
        
        '''

        # print stats
        print("Entry Price:  ", self.entryPrice)
        print("Stop Loss:    ", self.stopLoss)
        print("Take Profit:  ", self.takeProfit)
        print("Exit Price:   ", self.exitPrice)
        print("P/L:          ", self.pl)
        print("ER:           ", self.ret)
        print("Price Change: ", self.priceChange)
        print("Entered on:   ", self.entryIndex)
        print("Exited on:    ", self.exitIndex)
        print("Trade Age:    ", self.age)

        return None
    
def _saveTrades(trades : list[Trade],
                outfile : str,
                columns : list[str] | None = None) -> None:
    '''
    
    Given a list of Trade() objects, create a single PDF with each trade's
    history saved to its own page.


    Parameters
    ----------
    `trades` : list
        List of `Trade()` objects to save.
    
    `outfile` : str
        Full path to pdf file (name and `.pdf` extention included).

    `columns` : list[str] | None = None
        Columns within the trade's history to chart - the index will always
        be used for the x-axis, but the y-axis may be selected on a 
        column-by-column basis:
            exp: columns=["c", "sma"]
    
    Returns
    -------
    `None`
    
    '''

    # record start time
    startTime = datetime.datetime.now()

    # set speed optimization
    mpl.rcParams['path.simplify'] = True            # whether to simplify
    mpl.rcParams['path.simplify_threshold'] = 1.0   # how much to simplify
    mpl.rcParams['agg.path.chunksize'] = 10000      # breaking up lines into chunks

    # create the figure
    fig, axes = plt.subplots()
    plt.tight_layout()

    with PdfPages(outfile) as pdf:

        # for each trade
        for trade in trades:

            # plot the chart
            if columns:
                axes.plot(trade.history.index.to_numpy(),
                          trade.history[columns])

            else:
                axes.plot(trade.history.index.to_numpy(),
                          trade.history)

            mplstyle.use('fast')                        # optimizes additional configs for plotting

            # write the page
            pdf.savefig(fig)

            # clear the current axes
            axes.clear()

    plt.close()

    # record end time
    endTime = datetime.datetime.now()

    # alert user plots are done
    with open(outfile + "DONE", "w") as alert:
        
        alert.write("PDF complete...\n")
        alert.write("Trades Plotted: {}\n".format(len(trades)))
        alert.write("Time Elapsed: {}\n".format(endTime - startTime))

    return None

def saveTrades(trades : list[Trade],
               outfile : str,
               columns : list[str] | None = None) -> None:
    '''
    
    Given a list of Trade() objects, starts a thread to create a single PDF 
    with each trade's history saved to its own page. A "DONE" file will
    be created once the PDF is complete:

    Example:
            output.pdf
            
            output.pdfDONE


    Parameters
    ----------
    `trades` : list
        List of `Trade()` objects to save.
    
    `outfile` : str
        Full path to pdf file (name and `.pdf` extention included).

    `columns` : list[str] | None = None
        Columns within the trade's history to chart - the index will always
        be used for the x-axis, but the y-axis may be selected on a 
        column-by-column basis:\n
            
        Example: columns=["c", "sma"]
    
    Returns
    -------
    `None`
    
    '''

    # build the thread
    t = Thread(target=_saveTrades, kwargs={"trades" : trades, 
                                           "outfile" : outfile, 
                                           "columns" : columns})
    
    # start the thread
    t.start()

    return t



