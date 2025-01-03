import requests
import datetime
import copy
import pandas as pd
from threading import Thread, Lock
import time
import json
import sys

''' CLIENT-SERVER COMMUNICATIONS '''
def _to_strings(obj : dict) -> dict:
    ''' Designed for pre-formatting server requests, recursively replaces objects
    with their  string equivalents (datetime.datetime objects are formatted as 
    RCF3339 in UTC). *Note* Times will be converted to UTC prior to conversion -
    ensure timezones are properly assigned within datetime objects if operating 
    in a different timezone.
    
    Parameters
    ----------
    dictionary : dict
        The dictionary to recurse over.

    Returns
    -------
    dict
        A dictionary with all eligible values (recursively) formatted as 
        strings (or None).

    '''

    # recurse down list
    if isinstance(obj, list):
        for entry in range(0, len(obj)):
            obj[entry] = _to_strings(obj[entry])

    # recurse down dictionary
    elif isinstance(obj, dict):
        for key in obj:
            obj[key] = _to_strings(obj[key])

    # check if object is a datetime (and convert / format if it is)
    elif isinstance(obj, datetime.datetime):
        obj = obj.astimezone(datetime.UTC).isoformat().replace("+00:00", "Z")
        if obj[-1] != "Z":
            obj = obj + "Z"
    
    # pass over None(s)
    elif obj is None:
        pass

    # otherwise, check if object is a string (and convert if not)
    elif not isinstance(obj, str):
        obj = str(obj)

    return obj

def to_strings(dictionary : dict) -> dict:
    '''

    Recursively replaces a dictionary's non-iterables with their string 
    equivalents. *Note* This is a simple wrapper for `_to_strings()`.

    Parameters
    ----------
    `dictionary` : dict
        The dictionary to recurse over.

    Returns
    -------
    dict
        A dictionary with all non-iterables converted to strings.

    '''

    newDict = copy.deepcopy(dictionary)

    return _to_strings(newDict)

def to_objects(dictionary : dict) -> dict:
    ''' Converts eligible string values to python datatypes (does NOT throw 
    errors on any failed conversions, value will just remain a string). Used as 
    an argument for json.loads() object hook conversions: 
    json.loads(<data>, object_hook=_to_objects). Supported conversion:
            int\n
            float\n
            datetime.datetime
    
    Parameters
    ----------
    dictionary: dict
        The json to iterate over.

    Returns
    -------
    dict
    
    '''

    newDict = copy.deepcopy(dictionary)

    for key in newDict:
        if type(newDict[key]) == str:
            
            # likely a float or RCF3339 time if string contains "."
            if "." in newDict[key]:
                # more often than not, it's a float
                try: 
                    newDict[key] = float(newDict[key])
                except:
                    # otherwise typically RCF3339 time
                    try:
                        newDict[key] = datetime.datetime.fromisoformat(newDict[key])
                    # if neither, should likely remain a string
                    except:
                        pass
            
            # try converting integers, as well
            else:
                try: 
                    newDict[key] = int(newDict[key])
                except:
                    pass

    return newDict

''' ENTRY ORDERS'''
class _BaseEntry():
    '''
    
    Base entry order specifications. All entry orders extend this class.
    

    Attributes
    ----------
    `payload` : dict
        Specifications of the given entry order.

    Methods
    -------
    `set_takeProfit()` : func
        Creates and sets entry order's TakeProfit dependent order.
    
    `set_stopLoss()` : func
        Creates and sets entry order's StopLoss dependent order.
    
    `set_trailingStop()` : func
        Creates and sets entry order's TrailingStopLoss dependent order.
    
    `set_guaranteedStop()` : func
        Creates and sets entry order's GuarnateedStopLoss dependent order.
    
    `get_payload()` : func
        Returns entry order's payload.

    '''

    def __init__(self) -> None:
        ''' Initializes BaseOrder object. 

        Parameters
        ----------
        None

        Returns
        -------
        `None`
        
        '''

        # shared order specifications
        self.payload = {"type" : None,
                        "instrument" : None,
                        "units" : None,
                        "timeInForce" : None,
                        "positionFill" : None}

        return None
    
    def set_takeProfit(self,
                       price : float | None = None,
                       distance : float | None = None,
                       timeInForce : str = "GTC",
                       gtdTime : datetime.datetime | str | None = None):
        ''' Creates and sets entry order's TakeProfit dependent order.

        Parameters
        ----------
        `price` : float | None = None
            The associated Trade will be closed by a market price that is equal 
            to or better than this threshold (acts as Limit Order). Only 
            `price` OR `distance` may be specified - if both are input, 
            `price` will be given preference.

        `distance` : float | None = None
            Specifies the distance (in positive price units) from the trade's current 
            price to use as the Order price. The associated Trade will be closed
            by a market price that is equal to or better than this threshold 
            (acts as Limit Order). If the Trade is short the Instruments BID 
            price is used to calculated the price (and filled once ASK hits it), and 
            for long Trades the ASK is used (and filled once BID hits it). Only 
            `price` OR `distance` may be specified - if both are input, `price` 
            will be given preference.
        
        `timeInForce` : str = "GTC"
            The time-in-force requested for the Order. TimeInForce 
            describes how long an Order should remain pending before automaticaly 
            being cancelled by the execution system. Restricted to
            “GTC”, “GFD” and “GTD” for TakeProfit Orders [Default=GTC]:
        
            "GTC"	: The Order is “Good unTil Cancelled”
            "GTD"	: The Order is “Good unTil Date” and will be cancelled at 
                the provided time
            "GFD"	: The Order is “Good For Day” and will be cancelled at 5pm 
                New York time

        `gtdTime` : datetime.datetime | str | None = None
            (Required if timeInForce=GTD) The date/time when the Order will be 
            cancelled if its timeInForce is “GTD”. If string, ensure UTC in 
            RCF3339 formatted.
        

        Returns
        -------
        `None`
        
        
        '''
        
        # create dependent field
        self.payload["takeProfitOnFill"] = {}

        # set required specifications
        if price:
            self.payload["takeProfitOnFill"]["price"] = price
        else:
            self.payload["takeProfitOnFill"]["distance"] = distance
        
        self.payload["takeProfitOnFill"]["timeInForce"] = timeInForce

        if (timeInForce == "GTD") and (gtdTime):
            self.payload["takeProfitOnFill"]["gtdTime"] = gtdTime

        return None
    
    def set_stopLoss(self,
                     price : float | None = None,
                     distance : float | None = None,
                     timeInForce : str = "GTC",
                     gtdTime : datetime.datetime | str | None = None):
        ''' Creates and sets entry order's StopLoss dependent order.

        Parameters
        ----------
        `price` : float | None = None
            The associated Trade will be closed by a market price that is equal 
            to or worse than this threshold (acts as Stop Order). Only 
            `price` OR `distance` may be specified - if both are input, 
            `price` will be given preference.

        `distance` : float | None = None
            Specifies the distance (in positive price units) from the trade's current 
            price to use as the Order price. The associated Trade will be closed
            by a market price that is equal to or worse than this threshold 
            (acts as Stop Order). If the Trade is short the Instruments BID 
            price is used to calculated the price (and filled once ASK hits it), and 
            for long Trades the ASK is used (and filled once BID hits it). Only 
            `price` OR `distance` may be specified - if both are input, `price` 
            will be given preference.
        
        `timeInForce` : str = "GTC"
            The time-in-force requested for the Order. TimeInForce 
            describes how long an Order should remain pending before automaticaly 
            being cancelled by the execution system. Restricted to
            “GTC”, “GFD” and “GTD” for StopLoss Orders [Default=GTC]:
        
            "GTC"	: The Order is “Good unTil Cancelled”
            "GTD"	: The Order is “Good unTil Date” and will be cancelled at 
                the provided time
            "GFD"	: The Order is “Good For Day” and will be cancelled at 5pm 
                New York time

        `gtdTime` : datetime.datetime | str | None = None
            (Required if timeInForce=GTD) The date/time when the Order will be 
            cancelled if its timeInForce is “GTD”. If string, ensure UTC in 
            RCF3339 formatted.
        

        Returns
        -------
        `None`
        
        
        '''
        
        # create dependent field
        self.payload["stopLossOnFill"] = {}

        # set required specifications
        if price:
            self.payload["stopLossOnFill"]["price"] = price
        else:
            self.payload["stopLossOnFill"]["distance"] = distance
        
        self.payload["stopLossOnFill"]["timeInForce"] = timeInForce

        if (timeInForce == "GTD") and (gtdTime):
            self.payload["stopLossOnFill"]["gtdTime"] = gtdTime

        return None
    
    def set_trailingStop(self,
                         distance : float,
                         timeInForce : str = "GTC",
                         gtdTime : datetime.datetime | str | None = None):
        ''' Creates and sets entry order's TrailingStopLoss dependent order.

        Parameters
        ----------
        `distance` : float | None = None
            Specifies the distance (in positive price units) from the trade's current 
            price to use as the Order price. The associated Trade will be closed
            by a market price that is equal to or worse than this threshold 
            (acts as Stop Order). If the Trade is short the Instruments BID 
            price is used to calculated the price (and filled once ASK hits it), and 
            for long Trades the ASK is used (and filled once BID hits it).
        
        `timeInForce` : str = "GTC"
            The time-in-force requested for the Order. TimeInForce 
            describes how long an Order should remain pending before automaticaly 
            being cancelled by the execution system. Restricted to
            “GTC”, “GFD” and “GTD” for TrailingStopLoss Orders [Default=GTC]:
        
            "GTC"	: The Order is “Good unTil Cancelled”
            "GTD"	: The Order is “Good unTil Date” and will be cancelled at 
                the provided time
            "GFD"	: The Order is “Good For Day” and will be cancelled at 5pm 
                New York time

        `gtdTime` : datetime.datetime | str | None = None
            (Required if timeInForce=GTD) The date/time when the Order will be 
            cancelled if its timeInForce is “GTD”. If string, ensure UTC in 
            RCF3339 formatted.
        

        Returns
        -------
        `None`
        
        
        '''

        # create dependent field
        self.payload["trailingStopLossOnFill"] = {}

        # set required specifications
        self.payload["trailingStopLossOnFill"]["distance"] = distance

        self.payload["trailingStopLossOnFill"]["timeInForce"] = timeInForce

        if (timeInForce == "GTD") and (gtdTime):
            self.payload["trailingStopLossOnFill"]["gtdTime"] = gtdTime

        return None
    
    def set_guaranteedStop(self,
                           price : float | None = None,
                           distance : float | None = None,
                           timeInForce : str = "GTC",
                           gtdTime : datetime.datetime | str | None = None):
        ''' Creates and sets entry order's GuarnateedStopLoss dependent order.

        Parameters
        ----------
        `price` : float | None = None
            The associated Trade will be closed at this price. Only 
            `price` OR `distance` may be specified - if both are input, 
            `price` will be given preference.

        `distance` : float | None = None
            Specifies the distance (in positive price units) from the trade's current 
            price to use as the Order price. The associated Trade will be closed
            at this price. If the Trade is short the Instruments BID 
            price is used to calculated the price (and filled once ASK hits it), and 
            for long Trades the ASK is used (and filled once BID hits it). Only 
            `price` OR `distance` may be specified - if both are input, `price` 
            will be given preference.
        
        `timeInForce` : str = "GTC"
            The time-in-force requested for the Order. TimeInForce 
            describes how long an Order should remain pending before automaticaly 
            being cancelled by the execution system. Restricted to
            “GTC”, “GFD” and “GTD” for GuarnateedStopLoss Orders [Default=GTC]:
        
            "GTC"	: The Order is “Good unTil Cancelled”
            "GTD"	: The Order is “Good unTil Date” and will be cancelled at 
                the provided time
            "GFD"	: The Order is “Good For Day” and will be cancelled at 5pm 
                New York time

        `gtdTime` : datetime.datetime | str | None = None
            (Required if timeInForce=GTD) The date/time when the Order will be 
            cancelled if its timeInForce is “GTD”. If string, ensure UTC in 
            RCF3339 formatted.
        

        Returns
        -------
        `None`
        
        
        '''
        
        # create dependent field
        self.payload["guaranteedStopLossOnFill"] = {}

        # set required specifications
        if price:
            self.payload["guaranteedStopLossOnFill"]["price"] = price
        else:
            self.payload["guaranteedStopLossOnFill"]["distance"] = distance
        
        self.payload["guaranteedStopLossOnFill"]["timeInForce"] = timeInForce

        if (timeInForce == "GTD") and (gtdTime):
            self.payload["guaranteedStopLossOnFill"]["gtdTime"] = gtdTime

        return None

    def get_payload(self):
        ''' Returns entry order's payload.
        
        Parameters
        ----------
        None

        Returns
        -------
        dict
            The Oanda formatted entry order's specifications.
        
        '''

        return self.payload

class MarketOrder(_BaseEntry):
    ''' 
    
    Market order specifications.
    

    Attributes
    ----------
    `payload` : dict
        Specifications of the given market order.

    Methods
    -------
    `set()` : func
        Sets required Market Order specifications. 

    '''

    def __init__(self) -> None:
        ''' 
        
        Initializes MarketOrder object. 

        
        Parameters
        ----------
        None
        
        Returns
        -------
        `None`
        
        '''

        _BaseEntry.__init__(self)

        # set Market Order type
        self.payload["type"] = "MARKET"

        return None

    def set(self,
            instrument : str,
            units : int,
            priceBounds : float | None = None,
            timeInForce : str = "FOK",
            positionFill : str = "DEFAULT",
            strategy : str | None = None) -> None:
        ''' 
        
        Sets required Market Order specifications. 
        

        Parameters
        ----------
        `instrument` : str
            The order's target instrument.

        `units` : int
            The quantity requested to be filled by the order. A positive
            number of units results in a long Order, and a negative number of units
            results in a short Order.

        `priceBound` : float | None = None
            (Optional) The worst price that the client is willing to have the Order
            filled at.

        `timeInForce` : str = "FOK"
            The time-in-force requested for the Order. TimeInForce describes
            how long an Order should remain pending before automaticaly being
            cancelled by the execution system. Must be "FOK" or "IOC" for
            Market Orders [Default=FOK]:

            "FOK"	: The Order must be immediately “Filled Or Killed”\n
            "IOC"	: The Order must be “Immediately partially filled Or Cancelled”

        `positionFill` : str = "DEFAULT"
            Specification of how Positions in the Account are modified when the Order
            is filled [Default=DEFAULT]:

            "OPEN_ONLY"	: When the Order is filled, only allow Positions to be 
                opened or extended.
            "REDUCE_FIRST"	: When the Order is filled, always fully reduce an 
                existing Position before opening a new Position.
            "REDUCE_ONLY"	: When the Order is filled, only reduce an existing 
                Position.
            "DEFAULT"	: When the Order is filled, use REDUCE_FIRST behaviour 
                for non-client hedging Accounts, and OPEN_ONLY behaviour for 
                client hedging Accounts.

        `strategy` : str | None = None
            The strategy associated with the order.

        Returns
        -------
        `None`

        '''

        
        # set required specifications
        self.payload["instrument"] = instrument
        self.payload["units"] = units
        self.payload["timeInForce"] = timeInForce
        self.payload["positionFill"] = positionFill

        # set optional specifications
        if priceBounds:
            self.payload["priceBounds"] = priceBounds

        if strategy:
            self.payload["tradeClientExtensions"] = {"tag" : strategy}

        return None
    
class LimitOrder(_BaseEntry):
    ''' 
    
    Limit order specifications. *Note* A general note on LimitOrders:

    
    If POSITIVE units provided (Going Long / Closing Short)...
        AND Current Price < Order Price: 
            order will be filled immediately at CURRENT market prices (if not
            enough market liquidity and markets move UPWARD, will continue to be 
            filled only at prices LESS THAN or EQUAL TO the ORDER price)
        
        AND Current Price = Order Price: 
            order will be filled immediately at ORDER / CURRENT price or LESS 
            (if enough market liquidity)

        AND Current Price > Order Price: 
            order will sit at ORDER price until CURRENT price FALLS to ORDER price,
            at which point the order will be filled at ORDER price or LESS (if 
            enough market liquidity)
        
    If Negative Units Provided (Going Short / Closing Long) and...
        AND Current Price < Order Price: 
            order will sit at ORDER price until CURRENT price RISES to ORDER price,
            at which point the order will be filled at ORDER price or GREATER 
            (if enough market liquidity)

        AND Current Price = Order Price: 
            order will be filled immediately at ORDER / CURRENT price or GREATER
            (if enough market liquidity)
        
        AND Current Price > Order Price: 
            order will be filled immediately at CURRENT market prices (if not
            enough market liquidity and markets move DOWNWARD, will continue to
            be filled  only at prices GREATER THAN or EQUAL TO the ORDER price)
        
    
    Attributes
    ----------
    `payload` : dict
        Specifications of the given limit order.

    Methods
    -------
    `set()` : func
        Sets required Limit Order specifications. 

    '''

    def __init__(self) -> None:
        ''' 
        
        Initializes LimitOrder object. 

        
        Parameters
        ----------
        None
        
        Returns
        -------
        `None`
        
        '''

        _BaseEntry.__init__(self)

        # set Market Order type
        self.payload["type"] = "LIMIT"

        return None

    def set(self,
                  instrument : str,
                  units : int,
                  price : float,
                  timeInForce : str = "GTC",
                  gtdTime : datetime.datetime | str | None = None,
                  positionFill : str = "DEFAULT",
                  triggerCondition : str = "DEFAULT",
                  strategy : str | None = None) -> None:
        ''' 
        
        Sets required Market Order specifications. 

        
        Parameters
        ----------
        `instrument` : str
            The order's target instrument.

        `units` : int
            The quantity requested to be filled by the order. A positive
            number of units results in a long Order, and a negative number of units
            results in a short Order.

        `price` : float | None = None
            The price threshold specified for the Order. The Limit Order will 
            only be filled by a market price that is equal to or better than 
            this price.

        `timeInForce` : str = "GTC"
            The time-in-force requested for the Order. TimeInForce describes
            how long an Order should remain pending before automaticaly being
            cancelled by the execution system [Default=GTC]:

            "GTC"	: The Order is “Good unTil Cancelled”
            "GTD"	: The Order is “Good unTil Date” and will be cancelled at 
                the provided time
            "GFD"	: The Order is “Good For Day” and will be cancelled at 5pm 
                New York time
            "FOK"	: The Order must be immediately “Filled Or Killed”
            "IOC"	: The Order must be “Immediately partially filled Or Cancelled”

        `gtdTime` : datetime.datetime | str | None = None
            (Required if timeInForce="GTD") The date/time when the Order will be 
            cancelled if its timeInForce is “GTD”. If string, ensure UTC in 
            RCF3339 formatted.

        `positionFill` : str = "DEFAULT"
            Specification of how Positions in the Account are modified when the Order
            is filled [Default=DEFAULT]:

            "OPEN_ONLY"	: When the Order is filled, only allow Positions to be 
                opened or extended.
            "REDUCE_FIRST"	: When the Order is filled, always fully reduce an 
                existing Position before opening a new Position.
            "REDUCE_ONLY"	: When the Order is filled, only reduce an existing 
                Position.
            "DEFAULT"	: When the Order is filled, use REDUCE_FIRST behaviour 
                for non-client hedging Accounts, and OPEN_ONLY behaviour for 
                client hedging Accounts.

        `triggerCondition` : str = "DEFAULT"
            Specification of which price component should be evaluated when
            determining if an Order should be triggered and filled [Default=DEFAULT]. 

            "DEFAULT"	: Trigger an Order the “natural” way: compare its price 
                to the ask for long Orders and bid for short Orders.
            "INVERSE"	: Trigger an Order the opposite of the “natural” way: 
                compare its price the bid for long Orders and ask for short Orders.
            "BID"	: Trigger an Order by comparing its price to the bid 
                regardless of whether it is long or short.
            "ASK"	: Trigger an Order by comparing its price to the ask 
                regardless of whether it is long or short.
            "MID"	: Trigger an Order by comparing its price to the midpoint 
                regardless of whether it is long or short.

        `strategy` : str | None = None
            The strategy associated with the order.

        Returns
        -------
        `None`

        '''

        
        # set required specifications
        self.payload["instrument"] = instrument
        self.payload["units"] = units
        self.payload["price"] = price
        self.payload["timeInForce"] = timeInForce
        
        if (timeInForce == "GTD") and (gtdTime):
            self.payload["gtdTime"] = gtdTime

        self.payload["positionFill"] = positionFill
        self.payload["triggerCondition"] = triggerCondition

        if strategy:
            self.payload["clientExtensions"] = {"tag" : strategy}

        return None

class StopOrder(_BaseEntry):
    ''' 
    
    Stop order specifications. *Note* A general note on StopOrders:

    
    If POSITIVE units provided (Going Long / Closing Short)...
        AND Current Price < Order Price: 
            order will sit at ORDER price until CURRENT price RISES to ORDER price,
            at which point the order will be filled at the ORDER price or
            GREATER (if enough market liquidity)

        AND Current Price = Order Price: 
            order will be filled immediately at ORDER / CURRENT price or GREATER
            (if enough market liquidity)
        
        AND Current Price > Order Price: 
            order will be filled immediately at CURRENT market prices (if not
            enough market liquidity and markets move DOWNWARD, will continue to
            be filled only at prices GREATER THAN or EQUAL TO the ORDER price).
        
    If Negative Units Provided (Going Short / Closing Long)...
        AND Current Price > Order Price:
            order will sit at ORDER price until CURRENT prices FALL to ORDER price,
            at which point the order will be filled at the ORDER price or LESS
            (if enough market liquidity)

        AND Current Price = Order Price: 
            order will be filled immediately at ORDER / CURRENT price or LESS
            (if enough market liquidity)
        
        AND Current Price < Order Price: 
            order will be filled immediately at CURRENT market prices (if not
            enough market liquidity and markets move UPWARD, will continue to
            be filled only at prices LESS THAN or EQUAL TO the ORDER price)
    
    Attributes
    ----------
    `payload` : dict
        Specifications of the given stop order.

    Methods
    -------
    `set()` : func
        Sets required Stop Order specifications. 

    '''

    def __init__(self) -> None:
        ''' 
        
        Initializes StopOrder object. 

        
        Parameters
        ----------
        None
        
        Returns
        -------
        `None`
        
        '''

        _BaseEntry.__init__(self)

        # set Market Order type
        self.payload["type"] = "STOP"

        return None

    def set(self,
                  instrument : str,
                  units : int,
                  price : float,
                  priceBound : float | None = None,
                  timeInForce : str = "GTC",
                  gtdTime : datetime.datetime | str | None = None,
                  positionFill : str = "DEFAULT",
                  triggerCondition : str = "DEFAULT",
                  strategy : str | None = None) -> None:
        ''' 
        
        Sets required Stop Order specifications. 
        

        Parameters
        ----------
        `instrument` : str
            The order's target instrument.

        `units` : int
            The quantity requested to be filled by the order. A positive
            number of units results in a long Order, and a negative number of units
            results in a short Order.

        `price` : float
            The price threshold specified for the Order. The Stop Order will 
            only be filled by a market price that is equal to or worse than this 
            price.

        `priceBound` : float | None = None
            (Optional) The worst price that the client is willing to have the Order
            filled at.

        `timeInForce` : str = "GTC"
            The time-in-force requested for the Order. TimeInForce describes
            how long an Order should remain pending before automaticaly being
            cancelled by the execution system [Default=GTC]:

            "GTC"	: The Order is “Good unTil Cancelled”
            "GTD"	: The Order is “Good unTil Date” and will be cancelled at 
                the provided time
            "GFD"	: The Order is “Good For Day” and will be cancelled at 5pm 
                New York time
            "FOK"	: The Order must be immediately “Filled Or Killed”
            "IOC"	: The Order must be “Immediately partially filled Or Cancelled”

        `gtdTime` : datetime.datetime | str | None = None
            (Required if timeInForce="GTD") The date/time when the Order will be 
            cancelled if its timeInForce is “GTD”. If string, ensure UTC in 
            RCF3339 formatted.

        `positionFill` : str = "DEFAULT"
            Specification of how Positions in the Account are modified when the Order
            is filled [Default=DEFAULT]:

            "OPEN_ONLY"	: When the Order is filled, only allow Positions to be 
                opened or extended.
            "REDUCE_FIRST"	: When the Order is filled, always fully reduce an 
                existing Position before opening a new Position.
            "REDUCE_ONLY"	: When the Order is filled, only reduce an existing 
                Position.
            "DEFAULT"	: When the Order is filled, use REDUCE_FIRST behaviour 
                for non-client hedging Accounts, and OPEN_ONLY behaviour for 
                client hedging Accounts.

        `triggerCondition` : str = "DEFAULT"
            Specification of which price component should be evaluated when
            determining if an Order should be triggered and filled [Default=DEFAULT]. 

            "DEFAULT"	: Trigger an Order the “natural” way: compare its price 
                to the ask for long Orders and bid for short Orders.
            "INVERSE"	: Trigger an Order the opposite of the “natural” way: 
                compare its price the bid for long Orders and ask for short Orders.
            "BID"	: Trigger an Order by comparing its price to the bid 
                regardless of whether it is long or short.
            "ASK"	: Trigger an Order by comparing its price to the ask 
                regardless of whether it is long or short.
            "MID"	: Trigger an Order by comparing its price to the midpoint 
                regardless of whether it is long or short.

        `strategy` : str | None = None
            The strategy associated with the order.

        Returns
        -------
        `None`

        '''

        
        # set required specifications
        self.payload["instrument"] = instrument
        self.payload["units"] = units
        self.payload["price"] = price
        self.payload["timeInForce"] = timeInForce
        
        if (timeInForce == "GTD") and (gtdTime):
            self.payload["gtdTime"] = gtdTime

        self.payload["positionFill"] = positionFill
        self.payload["triggerCondition"] = triggerCondition

        # set optional specifications
        if priceBound:
            self.payload["priceBound"] = priceBound

        if strategy:
            self.payload["clientExtensions"] = {"tag" : strategy}

        return None

class MarketIfTouchedOrder(_BaseEntry):
    ''' 
    
    MarketIfTouched order specifications. *Note* A general note on 
    MarketIfTouchedOrders:

    
    Think of a MarketIfTouchedOrder as taking ONE direction at a specific
    price point no matter where the market price comes from before hand.

    If POSITIVE units provided (Going Long / Closing Short)...
        AND Current Price < Order Price: 
            [Acts as Long Stop] order will sit at ORDER price until CURRENT price 
            RISES to ORDER price, at which point the order will be filled at the 
            ORDER price or GREATER (if enough market liquidity)

        AND Current Price = Order Price: 
            N/A
        
        AND Current Price > Order Price: 
            [Acts as Long Limit]  order will sit at ORDER price until CURRENT price 
            FALLS to ORDER price, at which point the order will be filled at 
            ORDER price or LESS (if enough market liquidity)
        
    If Negative Units Provided (Going Short / Closing Long)...
        AND Current Price > Order Price: 
            [Acts as Short Stop] order will sit at ORDER price until CURRENT price
            FALLS to ORDER price, at which point the order will be filled at the
            ORDER price or LESS (if enough market liquidity)

        AND Current Price = Order Price: 
            N/A

        AND Current Price < Order Price:
            [Acts as Short Limit] order will sit at ORDER price until CURRENT price 
            RISES to ORDER price, at which point the order will be filled at 
            ORDER price or GREATER (if enough market liquidity)
    
    Attributes
    ----------
    `payload` : dict
        Specifications of the given market-if-touched order.

    Methods
    -------
    `set()` : func
        Sets required MarketIfTouched Order specifications. 

    '''

    def __init__(self) -> None:
        ''' 
        
        Initializes MarketIfTouchedOrder object. 

        
        Parameters
        ----------
        None
        
        Returns
        -------
        `None`
        
        '''

        _BaseEntry.__init__(self)

        # set Market Order type
        self.payload["type"] = "MARKET_IF_TOUCHED"

        return None

    def set(self,
            instrument : str,
            units : int,
            price : float,
            priceBound : float | None = None,
            timeInForce : str = "GTC",
            gtdTime : datetime.datetime | str | None = None,
            positionFill : str = "DEFAULT",
            triggerCondition : str = "DEFAULT",
            strategy : str | None = None) -> None:
        ''' 
        
        Sets required MarketIfTouched Order specifications. 
        

        Parameters
        ----------
        `instrument` : str
            The order's target instrument.

        `units` : int
            The quantity requested to be filled by the order. A positive
            number of units results in a long Order, and a negative number of units
            results in a short Order.

        `price` : float
            The price threshold specified for the Order. The MarketIfTouched 
            Order will only be filled by a market price that crosses this price 
            from the direction of the market price at the time when the Order 
            was created (the initialMarketPrice). Depending on the value of the 
            Orders price and initialMarketPrice, the MarketIfTouchedOrder will 
            behave like a Limit or a Stop Order.

        `priceBound` : float | None = None
            (Optional) The worst price that the client is willing to have the Order
            filled at.

        `timeInForce` : str = "GTC"
            The time-in-force requested for the Order. TimeInForce describes
            how long an Order should remain pending before automaticaly being
            cancelled by the execution system. Restricted to “GTC”, “GFD” and 
            “GTD” for MarketIfTouched Orders [Default=GTC]:

            "GTC"	: The Order is “Good unTil Cancelled”
            "GTD"	: The Order is “Good unTil Date” and will be cancelled at 
                the provided time
            "GFD"	: The Order is “Good For Day” and will be cancelled at 5pm 
                New York time

        `gtdTime` : datetime.datetime | str | None = None
            (Required if timeInForce="GTD") The date/time when the Order will be 
            cancelled if its timeInForce is “GTD”. If string, ensure UTC in 
            RCF3339 formatted.

        `positionFill` : str = "DEFAULT"
            Specification of how Positions in the Account are modified when the Order
            is filled [Default=DEFAULT]:

            "OPEN_ONLY"	: When the Order is filled, only allow Positions to be 
                opened or extended.
            "REDUCE_FIRST"	: When the Order is filled, always fully reduce an 
                existing Position before opening a new Position.
            "REDUCE_ONLY"	: When the Order is filled, only reduce an existing 
                Position.
            "DEFAULT"	: When the Order is filled, use REDUCE_FIRST behaviour 
                for non-client hedging Accounts, and OPEN_ONLY behaviour for 
                client hedging Accounts.

        `triggerCondition` : str = "DEFAULT"
            Specification of which price component should be evaluated when
            determining if an Order should be triggered and filled [Default=DEFAULT]. 

            "DEFAULT"	: Trigger an Order the “natural” way: compare its price 
                to the ask for long Orders and bid for short Orders.
            "INVERSE"	: Trigger an Order the opposite of the “natural” way: 
                compare its price the bid for long Orders and ask for short Orders.
            "BID"	: Trigger an Order by comparing its price to the bid 
                regardless of whether it is long or short.
            "ASK"	: Trigger an Order by comparing its price to the ask 
                regardless of whether it is long or short.
            "MID"	: Trigger an Order by comparing its price to the midpoint 
                regardless of whether it is long or short.

        `strategy` : str | None = None
            The strategy associated with the order.
                
        Returns
        -------
        `None`

        '''

        
        # set required specifications
        self.payload["instrument"] = instrument
        self.payload["units"] = units
        self.payload["price"] = price
        self.payload["timeInForce"] = timeInForce
        
        if (timeInForce == "GTD") and (gtdTime):
            self.payload["gtdTime"] = gtdTime

        self.payload["positionFill"] = positionFill
        self.payload["triggerCondition"] = triggerCondition

        # set optional specifications
        if priceBound:
            self.payload["priceBound"] = priceBound

        if strategy:
            self.payload["clientExtensions"] = {"tag" : strategy}

        return None

''' SESSION '''
class FastOanda():
    '''
    
    A pythonic wrapper for OANDA's APIs - only supports necessary operations
    for basic strategy execution. Utilizing a single HTTPS session to support
    rapid network requests (max 100/s).
    
    
    Attributes
    ----------
    _accountID : str
        The target OANDA account.

    _token : str
        The account's authorization header.

    _server  : str
        The server that all HTTPS requests will be sent to. *Note* this is
        determined base off of `sessionType` initialization parameter.
    
    _headers : dict
        Standard header's for OANDA endpoints.
    
    _session : requests.Session()
        A persistent HTTPS session that all requests are sent through. *Note* 
        This session maintains a Keep-Alive connection, supporting a maximum of 
        100 requests per second.
    
    _accountResponse : requests.Response()
        The HTTP response object received after account details are requested.
    
    _account : dict
        Most recent account data pulled.
    
    _tradesResponse : requests.Response()
        The HTTP response object received after trade details are requested.
    
    _trades : dict
        Most recent trade data pulled.

    _conversionsResponse  : requests.Response()
        The HTTP response object received after conversion factors are requested.
    
    _conversions : dict
        Most recent conversion factor data pulled.
    
    _httpLag : datetime.timedelta
        The estimated time it takes for an HTTP request to reach and be
        processed by OANDA servers.
        
    _candlesReponse : dict[requests.Response()]
        The HTTP response object received after conversion factors are requested.
        *Note* Dictionary is keyed by instrument names.

    _candles : dict[dict]
        Most recent candles pulled for the given instrument. *Note* Dictionary
        is keyed by instrument names.

    _orderResponse : dict[requests.Response()]
        The HTTP response object received after an order is placed. *Note* 
        Dictionary is keyed by instrument names.
    
    _orders : dict
        Most recent order response data. *Note* Dictionary is keyed by 
        instrument names.

    _autopolling : bool
        Whether the account is automatically polling for data.
    
    _targetCache : str | list
        The default targest list to use within the following methods:
            1) `poll()`
            2) `errors()`
            3) `verify()`
            4) `auto_poll()`

    _pollingLock : threading.Lock()
        A locked to avoid race conditions between automatted polling and 
        on-demand polling.

    _updateLock : threading.Lock()
        A lock to avoid race conditions when printing session updates to
        stderr.

    _orderLock : threading.Lock()
        A lock to avoid race conditions when printing session order 
        confirmations to stdout.

    _isTrading : bool
        Flag that indicates whether or not to continue using the session for 
        trading. [default=True]

    _pairs : dict
        Dicionary keyed with with all available currency pairs available to the
        session for trading. Values are keyed by price precision and margin rate.
        exp: {"EUR_USD" : {"precision" : 5, "marginRate" : .02}, ...}

    Methods
    -------
    `poll()` : func
        Retrieves a given account's key details for strategy execution:
                - account details
                - trade details
                - conversion factors

    `get_polled()` : func
        Returns the most recently polled key account details.

    `candles()` : func
        Retrieves candles.
    
    `get_candles()` : func
        Returns the most recently retrieved instrument candles for a given
        instrument.

    `place()` : func
        Places an BASE order.

    `get_orders()` : func
        Returns order confirmations for a given instrument for any order
        placed within the session.

    `close()` : func
        Closes open positions for the given target(s).

    `get_errors()` : func
        Returns session errors.

    `verify()` : func
        Verifies whether all session requests made have been successful.

    `start_polling()` : func
        Automates retrieval of key account details, continuously updating
        variables with background thread - implements `self.poll()` for
        retrieval.

    `stop_polling()` : func
        Stops automatic polling.

    `server_time()` : func
        Returns the equivalent OANDA server time when factoring in the time
        it would take for an HTTP request to hit their servers.

    `is_trading()` : func
        Whether or not to use the session for trading.

    `stop()` : func
        Gracefully ends the fastoanda session:
            (1) Sets `self._isTrading` to False
            (2) Stops automated polling if active
            (3) Releases the session's resources

    `pairs()` : func
        Returns all available instruments available for trading, to include
        their price precisions and margin rates.

    '''

    def __init__(self, 
                 sessionType : str, 
                 accountID : str, 
                 token : str, 
                 defaultTargets : str | list[str]) -> None:
        '''

        Initializes a dedicated `FastOanda` session.


        Parameters
        ----------
        `sessionType` : str
            Determines which OANDA server to send all subsequent communications
            to: ["paper", "live"]

        `accountID` : str
            Unique OANDA account ID.
        
        `token` : str
            Unique API token for Oanda account.

        `defaultTargets : str | list[str]
            A default list of instruments for requests in the session.


        Returns
        -------
        `FastOanda` : obj
            A dedicated `FastOanda` session.

        '''

        ''' CONFIGURATIONS '''
        # auth configurations
        self._accountID = accountID
        self._token = "Bearer {}".format(token)

        # point at correct server
        if sessionType == "paper":
            self._server = "https://api-fxpractice.oanda.com"

        elif sessionType == "live":
            self._server = "https://api-fxtrade.oanda.com"

        # set mandatory headers
        self._headers = {"Authorization" : self._token, 
                         "Content-Type" : "application/json",
                         "AcceptDatetimeFormat" : "RFC3339"}

        # build session (mandatory headers included in all request from here on out)
        self._session = requests.Session()
        self._session.headers.update(self._headers)

        # http timing details
        self._httpLag = datetime.timedelta(seconds=.1)

        # key `requests` responses
        self._accountResponse = None
        self._account = None

        self._tradesResponse = None
        self._trades = None

        self._conversionsResponse = None
        self._conversions = None

        # automation tools
        self._autopolling = False
        self._targetCache = defaultTargets
        
        # collision avoidance locks
        self._pollingLock = Lock()
        self._updateLock = Lock()
        self._orderLock = Lock()

        # session manager
        self._isTrading = True

        ''' SESSION BEGIN '''
        # pull available instruments
        url = self._server + "/v3/accounts/{}/instruments".format(self._accountID)
        pairsResponse = self._session.get(url=url)

        # don't begin session without instrument details
        pairsResponse.raise_for_status()
        self._pairs = {}
        
        for pair in pairsResponse.json(object_hook=to_objects)["instruments"]:
            # get APR swap rates
            self._pairs[pair["name"]] = {"precision" : pair["displayPrecision"], 
                                         "marginRate" : pair["marginRate"],
                                         "longSwap" : pair["financing"]["longRate"],
                                         "shortSwap" : pair["financing"]["shortRate"]}

            # get daily ANNUALIZED "admin" rates:
            baseCurr, quoteCurr = pair["name"].split("_")
            adminFees = {"TRY" : .04, "CZK" : .02, "HUF" : .02,
                         "SAR" : .02, "THB" : .02, "ZAR" : .02}

            if baseCurr == "TRY" or quoteCurr == "TRY":
                self._pairs[pair["name"]]["adminFee"] = .02

            elif (baseCurr in adminFees.keys()) or (quoteCurr in adminFees.keys()):
                self._pairs[pair["name"]]["adminFee"] = .04
            
            else:
                self._pairs[pair["name"]]["adminFee"] = .01


        return None

    def poll(self, targets : str | list | None = None) -> tuple[dict, dict]:
        '''

        Retrieves a given account's key details for strategy execution:
                - account details
                - trade details
                - conversion factors


        Parameters
        ----------
        `targets` : str | list | None = None
            The given strategy's target instrument(s). If `None`, uses
            default target list set on initialization. [default=None]

        Returns
        -------
        `dict`
            An account's full details:
                - account details
                - trade details
                - position details

        `dict`
            The target instrument(s) conversion factors.

        '''

        # aquire lock
        with self._pollingLock:

            # (1) pull account details
            url = self._server + "/v3/accounts/{}".format(self._accountID)
            self._accountResponse = self._session.get(url=url)
            
            try:
                self._accountResponse.raise_for_status()
                self._account = self._accountResponse.json(object_hook=to_objects)

            except:
                self._account = False

            # (2) pull trade details
            url = self._server + "/v3/accounts/{}/openTrades".format(self._accountID)
            self._tradesResponse = self._session.get(url=url)

            try:
                self._tradesResponse.raise_for_status()
                self._trades = self._tradesResponse.json(object_hook=to_objects)

            except:
                self._trades = False

            # (3) pull conversion details
            if not targets:
                targets = self._targetCache

            if isinstance(targets, list):
                targets = ",".join(targets)

            url = self._server + "/v3/accounts/{}/pricing".format(self._accountID)
            self._conversionsResponse = self._session.get(url=url,
                                                          params={"instruments" : targets,
                                                                  "includeHomeConversions" : True})

            try:
                self._conversionsResponse.raise_for_status()
                self._conversions = self._conversionsResponse.json(object_hook=to_objects)
            
            except:
                self._conversions = False

        return self._account, self._trades, self._conversions

    def get_polled(self) -> tuple[dict, dict, dict]:
        '''

        Returns the most recently polled key account details.

        
        Parameters
        ----------
        None


        Returns
        -------
        `dict`
            An account's full details:
                - account details
                - trade details
                - position details

        `dict`
            An account's full trade details.

        `dict`
            The default target instrument(s) conversion factors.

        '''

        return self._account, self._trades, self._conversions

    def candles(self,
                target : str,
                price : str = "M",
                granularity : str = "D",
                count : int | str | None = None,
                fromTime : datetime.datetime | str | None = None,
                toTime : datetime.datetime | str | None = None,
                smooth : bool = False,
                includeFirst : bool | None = None,
                dailyAlignment : int | str = 17,
                alignmentTimezone : str = "America/New_York",
                weeklyAlignment : str = "Friday"
                ) -> pd.DataFrame:
        ''' 
        
        Retrieves candles.
        

        Parameters
        ----------
        `target` : str
            Name of the Instrument to request candles for.

        `price` : str = "M"
            The Price component(s) to get candlestick data for. [default=M]
                "M" : Midpoint candles
                "B" : Bid candles
                "A" : Ask candles
                "BA" : Bid and Ask candles
                "MBA" : Mid, Bid, and Ask candles

        `granularity` : str = "D"
            The granularity of the candlesticks to fetch [default=S5]
                "S5"	: 5 second candlesticks, minute alignment\n
                "S10"	: 10 second candlesticks, minute alignment\n
                "S15"	: 15 second candlesticks, minute alignment\n
                "S30"	: 30 second candlesticks, minute alignment\n
                "M1"	: 1 minute candlesticks, minute alignment\n
                "M2"	: 2 minute candlesticks, hour alignment\n
                "M4"	: 4 minute candlesticks, hour alignment\n
                "M5"	: 5 minute candlesticks, hour alignment\n
                "M10"	: 10 minute candlesticks, hour alignment\n
                "M15"	: 15 minute candlesticks, hour alignment\n
                "M30"	: 30 minute candlesticks, hour alignment\n
                "H1"	: 1 hour candlesticks, hour alignment\n
                "H2"	: 2 hour candlesticks, day alignment\n
                "H3"	: 3 hour candlesticks, day alignment\n
                "H4"	: 4 hour candlesticks, day alignment\n
                "H6"	: 6 hour candlesticks, day alignment\n
                "H8"	: 8 hour candlesticks, day alignment\n
                "H12"	: 12 hour candlesticks, day alignment\n
                "D" 	: 1 day candlesticks, day alignment\n
                "W"	    : 1 week candlesticks, aligned to start of week\n
                "M" 	: 1 month candlesticks, aligned to first day of the month\n

        `count` : int | str | None = None
            The number of candlesticks to return in the response. `count` 
            should not be specified if both the `fromTime` and `toTime` 
            parameters are provided, as the time range combined with the 
            granularity will determine the number of candlesticks to return.
            `count` may be specified if only one `(from or to)Time` is provided. 
            [Default=500 if `None`, or only one of `fromTime` or `toTime`
            is set]. (Max 5000)
        
        `fromTime` : datetime.datetime | str | None = None
            The start of the time range to fetch candlesticks for. 
            *Note* Strings must be RFC3339 format.
        
        `toTime` : datetime.datetime | str | None = None
            The end of the time range to fetch candlesticks for.
            *Note* Strings must be RFC3339 format.
        
        `smooth` : bool = False
            A flag that controls whether the candlestick is “smoothed” or 
            not. A smoothed candlestick uses the previous candles close 
            price as its open price, while an un-smoothed candlestick uses 
            the first price from its time range as its open price. 
            [default=False]
        
        `includeFirst` : bool | None = None
            A flag that controls whether the candlestick that is covered by 
            the from time should be included in the results. This flag 
            enables clients to use the timestamp of the last completed 
            candlestick received to poll for future candlesticks but avoid 
            receiving the previous candlestick repeatedly. [default=True, 
            if using 'fromTime' argument and left as `None`]
        
        `dailyAlignment` : int | str = 17
            The hour of the day (in the specified timezone) to use for 
            granularities that have daily alignments. [default=17, 
            minimum=0, maximum=23]
        
        `alignmentTimezone` : str = "America/New_York"
            The timezone to use for the dailyAlignment parameter. 
            Candlesticks with daily alignment will be aligned to the 
            dailyAlignment hour within the alignmentTimezone. Note that the 
            returned times will still be represented in UTC. 
            [default=America/New_York].
            List of "TZ Identifiers": https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
        
        `weeklyAlignment` : str = "Friday"
            The day of the week used for granularities that have weekly 
            alignment. [default=Friday]
                "Monday"	: Monday\n
                "Tuesday"	: Tuesday\n
                "Wednesday"	: Wednesday\n
                "Thursday"	: Thursday\n
                "Friday"	: Friday\n
                "Saturday"	: Saturday\n
                "Sunday"	: Sunday\n
                
        Returns
        -------
        `pandas.DataFrame`
            The requested candles.
        
        '''

        # get candles
        url = self._server + "/v3/instruments/{}/candles".format(target)
        params = {"price" : price,
                  "granularity" : granularity,
                  "count" : count,
                  "from" :  fromTime,
                  "to" :  toTime,
                  "smooth" : smooth,
                  "includeFirst" : includeFirst,
                  "dailyAlignment" : dailyAlignment,
                  "alignmentTimezone" : alignmentTimezone,
                  "weeklyAlignment" : weeklyAlignment}
        
        candlesResponse = self._session.get(url=url, 
                                            params=to_strings(params))

        try:
            candlesResponse.raise_for_status()
            candles = candlesResponse.json(object_hook=to_objects)

            # will contain mid / bid / ask / spread(s)
            mids = []
            bids = []
            asks = []
            datetimes = []

            # iterate over all retrieved candles
            for item in candles["candles"]:

                # attach datetime key to mid
                if "M" in price:
                    mids.append(item["mid"])

                # attach datetime key to bid
                if "B" in price:
                    bids.append(item["bid"])

                # attach datetime key to ask
                if "A" in price:
                    asks.append(item["ask"])

                datetimes.append(item["time"])

            # will contain individual quotes
            quotes = []

            # format
            if mids:
                quotes.append([{k + "_mid" : v for k, v in ohlc.items()} for ohlc in mids])
            if bids:
                quotes.append([{k + "_bid" : v for k, v in ohlc.items()} for ohlc in bids])
            if asks:
                quotes.append([{k + "_ask" : v for k, v in ohlc.items()} for ohlc in asks])

            # join all if more than one price type requested
            if len(quotes) > 1:
                
                # for each additional bid / ask / mid requests
                for quote in quotes[1:]:

                    # iterate over each OHLC pair
                    for i in range(0, len(quote)):

                        # append them to the very first quote type
                        for key, value in quote[i].items():
                            quotes[0][i][key] = value

            # turn into Dataframe
            dfQuotes = pd.DataFrame(quotes[0], index=datetimes)
            dfQuotes.index.name="datetime"

        except:
            dfQuotes = False

        return dfQuotes

    def place(self, order : object) -> dict:
        '''

        Places a BASE order.


        Parameters
        ----------
        `order` : object
            Any base order with configured settings:
                - MarketOrder()
                - LimitOrder()
                - StopOrder()
                - MarketIfTouchedOrder()

        Returns
        -------
        `dict`
            The order's confirmation details.

        '''
        orderSpecs = order.get_payload()

        # place the order
        url = self._server + "/v3/accounts/{}/orders".format(self._accountID)
        orderResponse = self._session.post(url=url,
                                           json=to_strings({"order" : orderSpecs}))

        # record responses
        orderConfirmation = orderResponse.json(object_hook=to_objects)
            
        return orderConfirmation

    def close(self, 
              targets : list | str | None = None,
              cutBy : float | None = None,
              update : bool = False) -> dict | list[dict]:
        '''

        Closes open positions for the given target(s).

        
        Parameters
        ----------
        `target` : list | str | None = None
            The list of instruments to close out. If `None`, closes
            all open positions within the account. [default=None]
            *Note* DOES NOT USE DEFAULT TARGET LIST - WILL CLOSE OUT
            EVERYTHING.

        `cutBy` : float | None = None
            Cuts each specified target position by the given `cutBy` fraction, rounding
            UP to nearest integer (will marginally more if necessary). If
            `target=None` (default), cuts will be applied across all open positions.

        `update` : bool = False
            Whether to poll the account for details prior to closing positions.
            *Note* Executes `self.poll()` operation with last used polling
            parameters - may be useful if suspected new trades have recently 
            executedm, or if running in an emergency, otherwise likely wasteful.

        Returns
        -------
        `dict` | `list`
            The order(s) confirmation details - `dict` if single, `list` if
            multiple.

        '''

        # get most recent details
        if update:
            _, _, _ = self.poll(self._targetCache)

        # all positions
        if not targets:
            tempTargets = [x["instrument"] for x in self._account["account"]["positions"] if ((x["long"]["units"] != 0) | (x["short"]["units"] != 0))]

        # single position
        elif isinstance(targets, str):
            tempTargets = [targets]

        # multiple positions
        else:
            tempTargets = targets

        # hold all confirmation
        confirmations = []

        for target in tempTargets:
            
                # set blanks
                longUnits = None
                shortUnits = None

                # pull position type
                for position in self._account["account"]["positions"]:
                    
                    if position["instrument"] == target:
                        
                        if position["long"]["units"] != 0:

                            shortUnits = "NONE"

                            if cutBy:
                                longUnits = int(-(-(position["long"]["units"] * cutBy) // 1))
                            else:
                                longUnits = "ALL"

                            break

                        elif position["short"]["units"] != 0:

                            longUnits = "NONE"
                            
                            if cutBy:
                                shortUnits =  int(-((position["short"]["units"] * cutBy) // 1))

                            else:
                                shortUnits = "ALL"

                            break
                
                # if no position open
                if not longUnits:
                    pass

                else:

                    # set target
                    url = self._server + "/v3/accounts/{}/positions/{}/close".format(self._accountID, target)
                    
                    # load payload
                    data = {"longUnits" : longUnits,
                            "shortUnits" : shortUnits}        

                    # close position
                    orderResponse = self._session.put(url=url, json=to_strings(data))
                    
                    # record responses
                    orderConfirmation = orderResponse.json(object_hook=to_objects)                
                    confirmations.append(orderConfirmation)

        if len(confirmations) == 1:
            confirmations = confirmations[0]

        return confirmations

    def _auto_poll(self, targets : str | list | None, seconds : int) -> None:
        '''

        Automatically polls account data via a backgrounded thread.


        Parameters
        ----------
        `targets` : str | list
            The list of target instruments to collect details on.

        `seconds` : int = 2
            How often to poll the account.

        Returns
        -------
        `None`

        '''

        while self._autopolling:
            _, _, _ = self.poll(targets)
            time.sleep(seconds)

        return None

    def start_polling(self, targets : str | list | None = None, seconds : int = 2) -> None:
        '''

        Automatically polls account data via a backgrounded thread.
        *Note* A simple wrapper for `self._auto_poll()`.


        Parameters
        ----------
        `targets` : str | list
            The list of target instruments to collect details on. If `None`, 
            uses default target list set on initialization. [default=None]

        `seconds` : int = 2
            How often to poll for data.

        Returns
        -------
        `None`

        '''

        self._autopolling = True

        if not targets:
            targets = self._targetCache

        t = Thread(target=self._auto_poll, kwargs={"targets" : targets, "seconds" : seconds})
        t.start()

        return None

    def stop_polling(self) -> None:
        '''

        Stops automatic polling.


        Parameters
        ----------
        None

        Returns
        -------
        `None`

        '''

        self._autopolling = False

        return None

    def server_time(self) -> datetime.datetime:
        '''

        Returns the equivalent OANDA server time when factoring in the time
        it would take for an HTTP request to hit their servers.

        
        Parameters
        ----------
        None


        Returns
        -------
        `datetime.datetime`
            The estimated remote server time by the time an HTTP request
            reaches it.

        '''

        return datetime.datetime.now() + self._httpLag

    def is_trading(self) -> bool:
        '''

        Whether or not to use the session for trading.

        
        Paramaters
        ----------
        None

        Returns
        -------
        `bool`
            The continuation flag.

        '''

        return self._isTrading

    def stop(self) -> None:
        '''

        Gracefully ends the fastoanda session:
            (1) Sets `self._isTrading` to False
            (2) Stops automated polling if active
            (3) Closes the session's https keep-alive channel.

        
        Paramaters
        ----------
        None

        Returns
        -------
        `None`

        '''

        self._isTrading = False
        self.stop_polling()
        self._session.close()

        return None

    def pairs(self) -> dict:
        '''

        Returns all available instruments available for trading, to include
        their price precisions and margin rates.


        Parameters
        ----------
        None

        Returns
        -------
        `dict`
            Dicionary keyed with with all available currency pairs available to the
        session for trading. Values are keyed by price precision and margin rate.
        exp: {"EUR_USD" : {"precision" : 5, "marginRate" : .02}, ...}


        '''

        return self._pairs

class Logger():
    '''

    A logging class used in tandum with a `FastOanda` session - instantiated 
    logging objects enable isolated record keeping across multiple process 
    threads while simultaneously supporting aggregated output destinations.

    
    Attributes
    ----------
    `_target` : str
        The target instrument the logger is being used on.

    `_updates` : list
        A list of custom log updates.

    `_orders` : list
        A list of the intrument's order confirmation.
    
    `_session` : FastOanda
        The `FastOanda` session in use for the logger's instrument.

    Methods
    -------
    `update()` : func
        Appends a custom message to `self._update`, prepended with OANDA's 
        estimated server time.

    `orders()` : func
        Appends an order confirmation to `self._orders`, prepended with 
        OANDA's estimated server time.

    `post()` : func
        Prints updates (stderr) and order confirmations (stdout), wiping
        contents from memory.
    
    '''


    def __init__(self,
                 target : str,
                 session : FastOanda) -> None:
        '''

        Initializes a `Logger` object.


        Parameters
        ----------
        `target` : str
            The target instrument to log details on.

        `session` : FastOanda
            The `FastOanda` session being used to interact with the instrument.

        Returns
        -------
        `None`

        '''
        
        self._target = target
        self._updates = []
        self._orders = []
        self._session = session

        return None

    def update(self, message : str) -> None:
        '''
        
        Appends a custom message to `self._update`, prepended with OANDA's 
        estimated server time.

        
        Parameters
        ----------
        `message` : str
            The message to record.

        Returns
        -------
        `None`
        
        '''

        # format timestamp
        timestamp = self._session.server_time().strftime("%Y-%m-%d %H:%M:%S %f")
        
        # record message
        self._updates.append("{}: {}".format(timestamp, message))

        return None

    def orders(self, conf : dict) -> None:
        '''

        Appends an order confirmation to `self._orders`, prepended with 
        OANDA's estimated server time.

        Parameters
        ----------
        `conf` : dict
            The order's confirmation message.
        Returns
        -------
        `None`
        
        '''

        # format timestamp
        timestamp = self._session.server_time().strftime("%Y-%m-%d %H:%M:%S %f")
        
        # record message
        self._orders.append("~~~ {} ~~~\n{}".format(timestamp, json.dumps(conf, default=str, indent=4)))

        return None

    def post(self) -> None:
        '''

        Prints updates (stderr) and order confirmations (stdout), wiping
        contents from memory.

        
        Parameters
        ----------
        None

        Returns
        -------
        `None`
        
        '''

        # containers for messages (printing in one single write)
        marker = "+==================================================+"


        # collect updates
        updates = "\n{}\n{}\n{}\n".format(marker, " " * 18 + self._target + " UPDATES", marker)

        for update in self._updates:
            append = update + "\n"
            updates += append

        # print updates to stderr
        with self._session._updateLock:
            print(updates, file=sys.stderr)

        # reset memory
        self._updates = []


        # only post orders if something to post
        if self._orders:
            orders = "\n{}\n{}\n{}\n".format(marker, " " * 12 + self._target + " ORDER CONFIRMATIONS", marker)

            # collect confirmations
            for order in self._orders:
                    append = order + "\n"
                    orders += append
        
            # print orders to stdout
            with self._session._orderLock:
                print(orders, file=sys.stdout)
                
            # reset memory
            self._orders = []


        return None



