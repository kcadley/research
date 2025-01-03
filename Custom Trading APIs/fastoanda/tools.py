''' GENERAL '''
def to_baseUnits(homeUnits : float,
                 baseCurrency : str,
                 currentQuotes : dict,
                 truncate : bool = False) -> float | int:
    '''
    
    Convert units of the account's home currency to equivalent units of an 
    instrument's base currency.


    Parameters
    ----------
    
    `homeUnits` : float
        Units of the account's home currency to convert.

    `baseCurrency` : str
        The base currency to convert to, written in quoted format.
            Example: "EUR" or "JPY" or "USD"

    `currentQuotes` : dict
        A `session.pricing.pricing` value that contains an entry with current 
        base currency conversion factors. 
        *Note* `session.pricing.update_pricing()` populates `session.pricing.pricing`
        with conversion factors automatically.

    `truncate` : bool = False
        Whether to truncate the equivalent units of the base currency. Set this
        value to `True` when calculating units for an order - OANDA order units 
        are the number of the target instrument's base currency that you'd like 
        to buy or sell - these units must be INTEGERS! When `truncate=True`, if the 
        equivalent units of a base currency contain decimals, the units will be 
        "floored" to the nearest integer (decimals will be dropped) to comply 
        with OANDA order specifications. This will result in an equivalent order 
        size that is slightly smaller than that requested in `homeUnits`. 
        To verify the true value of the base currency units after truncating, use 
        `easyoanda.calc_home()`. [default=False]

    Returns
    -------
    float | int
        The equivalent units of the target instrument's base currency.
    
    '''

    # find the base conversion factor
    for currency in currentQuotes["homeConversions"]:
        if currency["currency"] == baseCurrency:
            baseConversion = currency["positionValue"]
            break

    # converting for an order
    if truncate:

        # units to buy / sell
        if homeUnits > 0:
            
            # floor if positive
            baseUnits = homeUnits // baseConversion

        else:

            # ceiling if negative
            baseUnits = -(-homeUnits // baseConversion)

        baseUnits = int(baseUnits)

    # else general conversion
    else:
        baseUnits = homeUnits / baseConversion

    return baseUnits

def to_homeUnits(baseUnits : float | int,
                 baseCurrency : str,
                 currentQuotes : dict) -> float:
    '''
    
    Convert units of an instrument's base currency to equivalent units of  
    the account's home currency.


    Parameters
    ----------
    `baseUnits` : float
        Units of the instrument's base currency to convert.

    `baseCurrency` : str
        The base currency to convert from, written in quoted format.
            Example: "EUR" or "JPY" or "USD"

    `currentQuotes` : dict
        A `session.pricing.pricing` value that contains an entry with current 
        base currency conversion factors. 
        *Note* `session.pricing.update_pricing()` populates 
        `session.pricing.pricing` with conversion factors automatically.

    Returns
    -------
    float
        The equivalent units of the account's home currency.
    
    '''

    # find the base conversion factor
    for currency in currentQuotes["homeConversions"]:
        if currency["currency"] == baseCurrency:
            baseConversion = currency["positionValue"]
            break

    # convert to home units
    homeUnits = baseUnits * baseConversion

    return homeUnits

def find_optimal_stop(baseUnits : int,
                      instrument : str,
                      currentQuotes : dict,
                      maxLoss : float,
                      entryPrice : float | None = None) -> float:
    '''
    
    Calculates the optimal stop-loss price level given an order's units
    (quoted in the target instrument's base currency) and trader's 
    maximum loss threshold (quoted in the account's home currency). *Note*
    OANDA requires stop-loss price levels be rounded to their 5th decimal place - 
    this is an industry standard. Due to this rounding, potential losses from
    the optimal stop-loss price level are slightly smaller than those 
    requested in `maxLoss`. To verify the true value of potential losses in 
    the account's home currency, use `easyoanda.get_price_impact()`.

    
    Parameters
    ----------
    `baseUnits` : int
        The order size of the trade (quoted in the target instrument's base
        currency units). Positive units indicate a long position, negative 
        units indicate a short position. *Reminder* OANDA order units must be 
        INTEGERS.

    `instrument` : str
        The trade's target instrument.
            Example: "EUR_USD" or "JPY_USD" or "USD_CHF"

    `currentQuotes` : dict
        A `session.pricing.pricing` value that contains an entry with current 
        quote currency conversion factors. 
        *Note* `session.pricing.update_pricing()` populates 
        `session.pricing.pricing` with conversion factors automatically.


    `maxLoss` : float
        The maximum allowable loss a trader is willing to take on the position
        (quoted in the account's home currency). 
    
    `entryPrice` : float | None = None
        The trade's projected entry price. If `None`, will assume trade is 
        a market order and will use most recently quoted bid / ask provided
        within `currentQuotes` (depending on sign of `baseUnits`). [default=None]

    Returns
    -------
    float
        The target instrument's optimal stop-loss price level.

    '''

    baseCurrency, quoteCurrency = instrument.split("_")

    # find quote conversion factor
    for currency in currentQuotes["homeConversions"]:
        if currency["currency"] == quoteCurrency:
            quoteConversion = currency["positionValue"]
            break

    # per unit impact
    perUnitImpact = abs(baseUnits) * quoteConversion

    # distance = maxLoss / perUnitImpact
    distance = abs(maxLoss) / perUnitImpact

    # projected price already present
    if entryPrice:
        pass

    # or using current quotes
    else:

        # find instrument
        for pair in currentQuotes["prices"]:
            if pair["instrument"] == instrument:
            
                # going long - setting price to most recent ask
                if baseUnits > 0:
                    entryPrice = pair["closeoutAsk"]

                # or going short - setting price to most recent bid
                else:
                    entryPrice = pair["closeoutBid"]


    # calculate stop for long
    if baseUnits > 0:
        stopLossAt = entryPrice - distance

        # round up to .0000X
        tempStopAt = stopLossAt * 100000
        tempStopAt = -(-tempStopAt // 1)
        stopLossAt = tempStopAt / 100000
    
    # calculate stop for short
    else:
        stopLossAt = entryPrice + distance

        # round down to .0000X
        tempStopAt = stopLossAt * 100000 // 1
        stopLossAt = tempStopAt / 100000


    return stopLossAt

def find_optimal_size(instrument : str,
                      currentQuotes : dict,
                      maxLoss : float,
                      exitPrice : float,
                      entryPrice : float | None = None) -> int:

    '''

    Calculate the optimal order size for a trade (in the target instrument's base 
    currency), given a target stop-loss price level and trader's maximum loss 
    threshold (quoted in the account's home currency). *Note* OANDA order units 
    are the number of the target instrument's base currency that you'd like 
    to buy or sell - these units must be INTEGERS! After the optimal units
    are calculated, if they contain decimals, the units will be 
    "floored" to the nearest integer (decimals will be dropped) to comply 
    with OANDA order specifications. This will result in an order size that is 
    slightly less than optimal - a "best-fit", if you will. This "best-fit" size 
    is the closest to the optimal size while still keeping potential losses below 
    the trader's maximum loss threshold. To verify the true value of the 
    optimal order size in the account's home currency, use `easyoanda.calc_home()`.


    Parameters
    ----------
    `instrument` : str
        The trade's target instrument.
            Example: "EUR_USD" or "JPY_USD" or "USD_CHF"

    `currentQuotes` : dict
        A `session.pricing.pricing` value that contains an entry with current 
        quote currency conversion factors. 
        *Note* `session.pricing.update_pricing()` populates 
        `session.pricing.pricing` with conversion factors automatically.

    `exitPrice` : float
        The trade's target stop-loss price level.

    `maxLoss` : float | None = None
        The maximum allowable loss a trader is willing to take on the position
        (quoted in the account's home currency).
    
    `entryPrice` : float | None = None
        The order's projected entry price. If `None`, will assume the order is 
        a market order and will use the most recently quoted bid / ask provided
        within `currentQuotes`. The average of the bid-ask is used as a 
        benchmark to evaluate the `exitPrice` against to determine if the
        position is long or short - if your market order stops are 
        extremely close to the bid/ask (anything less than half the spread), 
        it may be worthwhile to enter this parameter manually. [default=None]

    
    Returns
    -------
    int
        The optimal order size for the trade in the target instrument's base
        currency.

    '''

    # identify base and quote currency
    baseCurrency, quoteCurrency = instrument.split("_")

    # find quote conversion factor
    for currency in currentQuotes["homeConversions"]:
        if currency["currency"] == quoteCurrency:
            quoteConversion = currency["positionValue"]
            break

    # get entry price
    if entryPrice:
        pass
    else:
        
        # find instrument
        for pair in currentQuotes["prices"]:
            if pair["instrument"] == instrument:
    
                # benchmark to determine if long or short
                benchmark = (pair["closeoutAsk"] + pair["closeoutBid"]) / 2

                # going short - setting price to most recent bid
                if exitPrice > benchmark:
                    entryPrice = pair["closeoutBid"]

                # or going long - setting price to most recent ask
                else:
                    entryPrice = pair["closeoutAsk"]


    # calculate distance betwen entry and exit loss
    distance = entryPrice - exitPrice

    # calculate target loss perUnitImpact
    lossPerUnitImpact = abs(maxLoss) / distance

    # if long
    if lossPerUnitImpact > 0:
        
        # floor if positive
        baseUnits = lossPerUnitImpact // quoteConversion

    else:

        # short - ceiling negative
        baseUnits = -(-lossPerUnitImpact // quoteConversion)

    return baseUnits

def get_pip_impact(baseUnits : float,
                   instrument : str,
                   currentQuotes : dict) -> float:
    '''
    
    Calculate the price impact of a single pip change (as measured in the 
    account's home currency), given a number of units of the target instrument's 
    base currency. *Note* A "pip" for instrumented quoted in "JPY" or "HUF" is 
    .01, whereas for all others, a "pip" is .0001.

    
    Parameters
    ----------    
    `baseUnits` : float
        Units of the instrument's base currency.

    `instrument` : str
        The trade's target instrument.
            Example: "EUR_USD" or "JPY_USD" or "USD_CHF"

    `currentQuotes` : dict
        A `session.pricing.pricing` value that contains an entry with current 
        quote currency conversion factors. 
        *Note* `session.pricing.update_pricing()` populates 
        `session.pricing.pricing` with conversion factors automatically.

    Returns
    -------
    float
        The price impact a single pip change has (as measured in the 
        account's home currency)
    
    '''
    
    # identify base and quote currency
    baseCurrency, quoteCurrency = instrument.split("_")

    # find quote conversion factor
    for currency in currentQuotes["homeConversions"]:
        if currency["currency"] == quoteCurrency:
            quoteConversion = currency["positionValue"]
            break

    # calculating pip impact
    quotedUnits = baseUnits * quoteConversion

    # special pip adjustment if quoted in "JPY" or "HUF"
    if (quoteCurrency == "JPY") or (quoteCurrency == "HUF"):
        perPipImpact = quotedUnits / 100

    # otherwise, standard pip adjustment
    else:
        perPipImpact = quotedUnits / 10000

    return abs(perPipImpact)

def get_price_impact(baseUnits : float,
                     instrument : str,
                     currentQuotes : dict,
                     exitPrice : float,
                     entryPrice : float | None = None) -> float:

    '''
    
    Calculate the price impact of movements between two price levels within an 
    instrument (as measured in the account's home currency), given a number of 
    units of the target instrument's base currency.
    
    
    Parameters
    ----------
    `baseUnits` : float
        Units of the instrument's base currency.

    `instrument` : str
        The trade's target instrument.
            Example: "EUR_USD" or "JPY_USD" or "USD_CHF"

    `currentQuotes` : dict
        A `session.pricing.pricing` value that contains an entry with current 
        quote currency conversion factors. 
        *Note* `session.pricing.update_pricing()` populates 
        `session.pricing.pricing` with conversion factors automatically.

    `exitPrice` : float
        The instrument's ending price level.

    `entryPrice` : float | None = None
        The instrument's starting price level. If `None`, will assume entry
        price level is based on current bid/ask quotes (evaluated by sign of 
        `baseUnits`). [default=None]

    Returns
    -------
    float
        The price impact of changes between the two price levels (as measured
        in the account's home currency).

    '''

    # calculate pip impact
    pipImpact = get_pip_impact(baseUnits, instrument, currentQuotes)

    # identify base and quote currency
    baseCurrency, quoteCurrency = instrument.split("_")

    # went long - entered at the ask
    if baseUnits > 0:

        # set entry level as needed
        if entryPrice:
            pass
        else:
            # find most recent ask
            for pair in currentQuotes["prices"]:
                if pair["instrument"] == instrument:
                    entryPrice = pair["closeoutAsk"]
                    break

        # calculate long distance
        distance = exitPrice - entryPrice
        
    # went short - entered at the bid
    else:

        # set entry level as needed
        if entryPrice:
            pass

        else:
            # find most recent bid
            for pair in currentQuotes["prices"]:
                if pair["instrument"] == instrument:
                    entryPrice = pair["closeoutBid"]
                    break

        # calculate short distance
        distance = entryPrice - exitPrice

    # calculate pips in distance if "JPY" or "HUF"
    if (quoteCurrency == "JPY") or (quoteCurrency == "HUF"):
        pips = distance * 100

    # otherwise, calculate standard pips
    else:
        pips = distance * 10000

    # calculate total position impact
    positionImpact = pipImpact * pips

    return positionImpact

def get_worst_case(account : dict, trades : dict, conversionFactors : dict) -> dict:
    '''
    
    Calculates every open trade's worst case loss, provided the trade has
    a stop-loss order attached to it.
    

    Parameters
    ----------
    `account` : dict
        Polled fastoanda session account details.

    `trades` : dict
        Polled fastoanda session trade details.

    `conversionFactors` : dict
        Polled fastoanda session conversion factors.

    Returns
    -------
    `dict`
        A dictionary keyed by instrument name, with each value containing an 
        array of worst-case trade losses within that position.

        Example:
        {"EUR_USD" : [-124, -248, -284], "USD_JPY" : [-142, -482, 240]}
    
    '''

    # empty return if no trades open
    if len(account["account"]["trades"]) == 0:
        return {"NONE" : [0]}

    # stage positions
    positions = {}

    # stage losses
    losses = {}

    # sort open trades by their instrument
    for trade in trades["trades"]:

        # append to current instruments
        if trade["instrument"] in positions.keys():
            positions[trade["instrument"]].append(trade)

        # or create new key for new instrument
        else:
            positions[trade["instrument"]] = [trade]
            losses[trade["instrument"]] = []

    # calculate expected losses
    for instrument, trades in positions.items():

        # get worst case losses for each trade within the given instrument
        for trade in trades:
            
            # only perform calculation on trades with a stop loss
            if "stopLossOrder" in trade.keys():
                
                # current size
                size = trade["currentUnits"]
                
                # entry fill price
                entryPrice = trade["price"]

                # stop price as specified price
                if trade["stopLossOrder"]["price"]:
                    exitPrice = trade["stopLossOrder"]["price"]
                
                # or stop price as distance
                else:
                    # short, add price
                    if size < 0:
                        exitPrice = entryPrice + trade["stopLossOrder"]["distance"]

                    # long, subtract price
                    else:
                        exitPrice = entryPrice - trade["stopLossOrder"]["distance"]

                # calculate price impact
                projectedLoss = get_price_impact(baseUnits=size,
                                                 instrument=instrument,
                                                 currentQuotes=conversionFactors, 
                                                 entryPrice=entryPrice,
                                                 exitPrice=exitPrice)

                # record potential losses
                losses[instrument].append(projectedLoss)

    return losses


''' TESTING '''
def get_portfolio_exposure(trades : dict, 
                           conversionFactors : dict,
                           marginRate : float) -> tuple[float, float, float]:
    '''

    Calculates the portfolio's total initial position size (with leverage), 
    along with total best and worst case losses for all trades that have 
    stop-losses and take-profits attached.
    

    Parameters
    ----------
    `trades` : dict
        Polled fastoanda session trade details.

    `conversionFactors` : dict
        Polled fastoanda session conversion factors.

    `marginRate` : float
        The margin rate used to open all positions.

    Returns
    -------
    `float`
        The portfolios total initial position size (with leverage).

    `float`
        The worst case loss if all stops are hit and filled without slippage.

    `float`
        The best case profit if all take profits are hit and filled without slippage.

    '''

    initialEntrySize = []
    projectedGains = []
    projectedLosses = []

    if len(trades["trades"]) == 0:
        pass

    else:

        # index conversion factors for faster look-ups
        cfs = {}
        for cf in conversionFactors["homeConversions"]:
            cfs[cf["currency"]] = cf

        # calculate losses
        for trade in trades["trades"]:
            
            # trade information
            quoteTarget = trade["instrument"].split("_")[1]
            baseUnits = trade["currentUnits"]
            entryPrice = trade["price"]
            
            # pip impact
            quoteCF = cfs[quoteTarget]["positionValue"]
            quoteUnits = baseUnits * quoteCF
            
            # ignore trades without stops
            if "stopLossOrder" in trade.keys():

                # stop loss price
                exitPrice = trade["stopLossOrder"]["price"]
                
                # spread to stoploss 
                spread = abs(entryPrice - exitPrice)
                

                # pip calculations
                if (quoteTarget == "JPY") or (quoteTarget == "HUF"):
                    perPipImpact = abs(quoteUnits / 100)
                    pipsInSpread = spread * 100
                else:
                    perPipImpact = abs(quoteUnits / 10000)
                    pipsInSpread = spread * 10000

                # projected loss
                tradeLoss = perPipImpact * pipsInSpread

                projectedLosses.append(tradeLoss)

            # ignore trades without take profits
            if "takeProfitOrder" in trade.keys():

                # take profit price
                exitPrice = trade["takeProfitOrder"]["price"]
                
                # spread to stoploss 
                spread = abs(entryPrice - exitPrice)

                # pip calculations
                if (quoteTarget == "JPY") or (quoteTarget == "HUF"):
                    perPipImpact = abs(quoteUnits / 100)
                    pipsInSpread = spread * 100
                else:
                    perPipImpact = abs(quoteUnits / 10000)
                    pipsInSpread = spread * 10000

                # projected loss
                tradeGain = perPipImpact * pipsInSpread

                projectedGains.append(tradeGain)

            # calculate initial trade sizes
            initialEntrySize.append(trade["initialMarginRequired"] / marginRate)

    return sum(initialSizes), sum(gains), sum(losses)

def get_target_exposure(target : str,
                        trades : dict, 
                        conversionFactors : dict,
                        marginRate : float) -> tuple[float, float, float]:
    '''

    Calculates the given target's total initial position size (with leverage), 
    along with total best and worst case losses for all trades that have 
    stop-losses and take-profits attached.
    

    Parameters
    ----------
    `target` : str
        The target insrument to filter trades by.

    `trades` : dict
        Polled fastoanda session trade details.

    `conversionFactors` : dict
        Polled fastoanda session conversion factors.

    `marginRate` : float
        The margin rate used to open all positions within the target.

    Returns
    -------
    `float`
        The target's total initial position size (with leverage).

    `float`
        The worst case loss if all stops are hit and filled without slippage.

    `float`
        The best case profit if all take profits are hit and filled without slippage.

    '''

    initialSizes = []
    gains = []
    losses = []

    if len(trades["trades"]) == 0:
        pass

    else:

        # pull conversion factor & quoted currency
        quoteTarget = target.split("_")[1]
        quoteCF = [x for x in conversionFactors["homeConversions"] if x["currency"] == quoteTarget][0]["positionValue"]

        # calculate losses
        for trade in trades["trades"]:
            
            if trade["instrument"] == target:

                # trade information
                baseUnits = trade["currentUnits"]
                entryPrice = trade["price"]
                
                # pip impact
                quoteUnits = baseUnits * quoteCF
                
                # ignore trades without stops
                if "stopLossOrder" in trade.keys():

                    # stop loss price
                    exitPrice = trade["stopLossOrder"]["price"]
                    
                    # spread to stoploss 
                    spread = abs(entryPrice - exitPrice)
                    

                    # pip calculations
                    if (quoteTarget == "JPY") or (quoteTarget == "HUF"):
                        perPipImpact = abs(quoteUnits / 100)
                        pipsInSpread = spread * 100
                    else:
                        perPipImpact = abs(quoteUnits / 10000)
                        pipsInSpread = spread * 10000

                    # projected loss
                    tradeLoss = perPipImpact * pipsInSpread

                    losses.append(tradeLoss)

                # ignore trades without take profits
                if "takeProfitOrder" in trade.keys():

                    # take profit price
                    exitPrice = trade["takeProfitOrder"]["price"]
                    
                    # spread to stoploss 
                    spread = abs(entryPrice - exitPrice)

                    # pip calculations
                    if (quoteTarget == "JPY") or (quoteTarget == "HUF"):
                        perPipImpact = abs(quoteUnits / 100)
                        pipsInSpread = spread * 100
                    else:
                        perPipImpact = abs(quoteUnits / 10000)
                        pipsInSpread = spread * 10000

                    # projected loss
                    tradeGain = perPipImpact * pipsInSpread

                    gains.append(tradeGain)

                # calculate initial trade sizes
                initialSizes.append(trade["initialMarginRequired"] / marginRate)

    return sum(initialSizes), sum(gains), sum(losses)

def get_trade_projection(baseUnits : int,
                         quoteTarget : str,
                         entryPrice : float,
                         takePrice : float,
                         stopPrice : float,
                         conversionFactors : dict):
    '''

    Projects a trade's gains and losses for a given stop-loss and take profit.
    

    Parameters
    ----------
    `baseUnits` : int
        Size of the trade in the pair's base currency.

    `quoteTarget` : dict
        The pair's quoted currency string ("EUR", "USD", etc).

    `entryPrice` : float
        The expected entry price.

    `takePrice` : float
        The expected take-profit price.
        
    `stopPrice` : float
        The expected stop-out price.

    `conversionFactors` : dict
        Polled fastoanda session conversion factors.


    Returns
    -------
    `float`
        The trade's expected gain.

    `float`
        The trade's expected loss.

    '''

    # find the quote conversion factor
    for currency in conversionFactors["homeConversions"]:
        if currency["currency"] == quoteTarget:
            quoteCF = currency["positionValue"]
            break
        
    # pip impact
    quoteUnits = baseUnits * quoteCF
    
    ''' Projected Loss ''' 
    # spread to stoploss 
    spread = abs(entryPrice - stopPrice)
    
    # pip calculations
    if (quoteTarget == "JPY") or (quoteTarget == "HUF"):
        perPipImpact = abs(quoteUnits / 100)
        pipsInSpread = spread * 100
    else:
        perPipImpact = abs(quoteUnits / 10000)
        pipsInSpread = spread * 10000

    # projected loss
    tradeLoss = perPipImpact * pipsInSpread

    ''' Projected Gain '''
    # spread to stoploss 
    spread = abs(entryPrice - takePrice)

    # pip calculations
    if (quoteTarget == "JPY") or (quoteTarget == "HUF"):
        perPipImpact = abs(quoteUnits / 100)
        pipsInSpread = spread * 100
    else:
        perPipImpact = abs(quoteUnits / 10000)
        pipsInSpread = spread * 10000

    # projected loss
    tradeGain = perPipImpact * pipsInSpread

    return tradeGain, tradeLoss


''' CONVERSIONS '''
def convert(units : float,
            fromCurr : str | None = None,
            toCurr: str | None = None,
            conversions : dict | None = None,
            truncate : bool = False) -> float | int:
    '''

    Converts units of one currency to units of another currency. The home
    currency takes the place of `fromCurr` or `toCurr` if either are omitted.


    Parameters
    ----------
    `units` : float
        Units of the starting currency.

    `fromCurr` : str
        The starting currency. If a currency pair, sets itself to the base currency.

    `toCurr` : str
        The new currency. If a currency pair is provided, sets
        itself to the base currency.

    `conversions` : dict
        The most recently polled fastoanda (c)onversion factors: `a, t, c = fsession.get_polled()`.
        Must have conversion factors for any currency converted by the function.

    `truncate` : bool = False
        Whether to round down the returned units down.

    Returns
    -------
    `float` | `int`
        The units of the new currency.

    '''
    # replacements
    if not fromCurr:
        fromCurr = "USD"
    elif "_" in fromCurr:
        fromCurr = fromCurr.split("_")[0]

    if not toCurr:
        toCurr = "USD"
    elif "_" in toCurr:
        toCurr = toCurr.split("_")[0]

    # index conversion factors for faster look-ups
    cfs = {}
    for cf in conversions["homeConversions"]:
        cfs[cf["currency"]] = cf

    # in case USD not in target list
    if "USD" not in cfs.keys():
        cfs["USD"] = {"accountGain" : 1, "accountLoss" : 1}

    # calculate equivalent units of home currency
    fromCF = cfs[fromCurr]["accountGain"]         # SELL TO THE BID
    homeUnits = units * (fromCF / 1)              # X BASE Units * (X USD / 1 BASE)

    # calculate equivalent units in new currency
    toCF = cfs[toCurr]["accountLoss"]             # BUY FROM THE ASK
    newUnits = homeUnits * (1 / toCF)             # X USD Units * (1 BASE / X USD)

    # floor as needed
    if truncate:
        newUnits = int(abs(newUnits))
        
    return newUnits

''' PROJECTIONS '''
def get_exposure(trades : dict,
                 pairs : dict,
                 target : str | None = None,
                 strategy : str | None = None,
                 tradeType : str = None,
                 tradeID : int | None = None,
                 marginRate : float | None = None) -> tuple[float, float, float]:
    '''

    Calculates a position's current unadjusted value, projected losses, and projected 
    gains (if all take-profit and/or stop-losses were to be hit without slippage). 
    The "position" may be (1) the entire portfolio, (2) the portfolio filtered by a 
    specific instrument, and/or specific strategy, and/or specific position type, 
    or (3) a specific trade. If `marginRate` parameter is passed, it will be
    used for calculations across all positions specified (constant) - otherwise, 
    the account's current margin rates will be used (constant if previously set, 
    variable if not).
    

    Parameters
    ----------
    `trades` : dict
        A fastoanda session's polled (t)rades: `a, t, c = fsession.get_polled()`

    `pairs` : dict
        The fastoanda session's pairs dictionary: `fsession.pairs()`

    `target` : str | None = None
        A target instrument to filter positions by.

    `strategy` : str | None = None
        A target strategy to filter positions by.

    `tradeType` : str | None = None
        Position type to filter positions by: ["long", "short", None]

    `tradeID` : int | None = None
        Trade ID to filter by.

    `marginRate` : float | None = None
        A non-default margin rate used to enter the filtered positions.

    Returns
    -------
    `float`
        The total position's current unadjusted value in home units (units
        held * entry price * entry conversion factor).

    `float`
        The best case profit if all take profits are hit and filled without slippage.

    `float`
        The worst case loss if all stops are hit and filled without slippage.

    '''

    unadjValues = []
    projLosses = []
    projGains = []

    # no open positions
    if len(trades["trades"]) == 0:
        pass

    else:

        for trade in trades["trades"]:
            # filter
            if tradeID:
                if trade["id"] != tradeID:
                    continue
            if strategy:
                if "clientExtensions" in trade.keys():
                    if trade["clientExtensions"]["tag"] != strategy:
                        continue
            if target:
                if trade["instrument"] != target:
                    continue
            if tradeType:
                if (tradeType == "long") and (trade["units"] < 0):
                    continue
                elif (tradeType == "short") and (trade["units"] > 0):
                    continue

            ''' CURRENT UNADJUSTED VALUE '''
            # calculate current unadjusted value
            if marginRate:
                initialMarginRate = marginRate
            else:
                initialMarginRate = pairs[trade["instrument"]]["marginRate"]

            initialUnadjValue = trade["initialMarginRequired"] / initialMarginRate

            # --- position hasn't changed
            if trade["currentUnits"] == trade["initialUnits"]:
                currentUnadjValue = initialUnadjValue
            
            # --- position has changed
            else:
                initialMarginPerUnit = trade["initialMarginRequired"] / trade["initialUnits"]
                adjInitialMarginRequired = trade["currentUnits"] * initialMarginPerUnit
                currentUnadjValue = adjInitialMarginRequired / initialMarginRate

            unadjValues.append(abs(currentUnadjValue))

            ''' PROJECTED LOSSES & GAINS '''
            entryPrice = trade["price"]

            # projected losses
            if "stopLossOrder" in trade.keys():
                # entry / exit price
                entryPrice = trade["price"]
                exitPrice = trade["stopLossOrder"]["price"]

                # projected gain
                projLoss = currentUnadjValue * abs(exitPrice - entryPrice) / entryPrice
                projLosses.append(projLoss)

            # projected gains
            if "takeProfitOrder" in trade.keys():
                # entry / exit price
                entryPrice = trade["price"]
                exitPrice = trade["takeProfitOrder"]["price"]

                # projected gain
                projGain = currentUnadjValue * abs(exitPrice - entryPrice) / entryPrice
                projGains.append(projGain)

    return sum(unadjValues), sum(projLosses), sum(projGains)

def project_exposure(baseUnits : float,
                     target : str,
                     conversions : dict,
                     entryPrice : float,
                     stopPrice : float | None = None,
                     takePrice : float | None = None) -> tuple[float, float, float]:
    '''

    Projects a trades's potential loss, and potential gain if its take-profit 
    and/or stop-loss is hit without slippage. *Note* `homeUnits` intentially
    not supported, covert to baseUnits first:
            Formula for long or short, regardless of exotics:
            (1) homeUnits = X
            (2) sellUnits = convert(homeUnits, "USD", "<want to sell>", c)
            (3) buyUnits = convert(sellUnits, "<want to sell>", "<want to buy>", c)

    Parameters
    ----------
    `baseUnits` : float | None = None
        The current units of the base currency.
    
    `target` : str | None = None
        The target pair.

    `conversions` : dict | None = None
        The most recently polled fastoanda (c)onversion factors: `a, t, c = fsession.get_polled()`
    
    `entryPrice` : float
        The projected entry price of the trade.
    
    `stopPrice` : float | None = None
        The projected stop-price of the trade. Projected losses will return
        as 0 if `None`.
    
    `takePrice` : float | None = None
        The projected take-profit price of the trade. Projected gains will 
        return as 0 if `None`.

    Returns
    -------
    `float`
        The trade's entry value in home units.

    `float`
        The best case profit if the trade's take-profit is hit and filled without 
        slippage.

    `float`
        The worst case loss if the trade's stop-loss is hit and filled without 
        slippage.

    '''

    # convert to home units
    baseCurr, quoteCurr = target.split("_")
    if quoteCurr == "USD":
        homeUnits = convert(baseUnits, baseCurr, "USD", conversions=conversions)
    
    # project gain
    if takePrice:
        projGain = homeUnits * abs(takePrice - entryPrice) / entryPrice
    else:
        projGain = 0

    # project loss
    if stopPrice:
        projLoss = homeUnits * abs(stopPrice - entryPrice) / entryPrice
    else:
        projLoss = 0

    return homeUnits, projGain, projLoss

''' SIZING '''
def size_to_margin_call(riskAllotment,
                        unadjCurrentPosSize,
                        projCurrentPosLosses,
                        projCurrentPosGains,
                        posMarginRate,
                        entryPrice,
                        stopPrice,
                        takePrice) -> float:
    '''

    Maximizes limits to the size of a new trade such that if the trade is added 
    to the current position (as defined by a strategy, instrument, or other filter),
    and subsequently all trades within that position close at a loss or at
    a gain, the final margin requirement would be less than the original risk 
    allotment plus/minus the cumulative gains/losses (thus avoiding a margin call).


    Parameters
    ----------
    TBD

    Returns
    -------


    '''


    # maximize size to losses:
    # maximum size to avoid margin call as defined by: Future NAV = Future Margin Used
    #
    # (1) R - PL - NL = MR * [(PS - PL) + (NS - NL)]
    # 
    # (2) NL = NP * | [(Ex - En) / En] |
    #
    # Eq. 1 and Eq. 2 combine to Eq. 3...
    #
    # (3) NS = [MR * (PS - PL) - R + PL] / [ |([Ex - En] / En)| * (MR - 1) - MR]
    
        # NS = new trade's position size (solving for)
        # R = allotted risk (balance * martozitz)
        # PS = current unadjusted position size
        # PL = current projected losses
        # NL = new trade's projected losses
        # MR = instrument's margin rate
        # En = the trade's projected entry price
        # Ex = the trade's projected exit price
    
    # solve for NS:
    upper = posMarginRate * (unadjCurrentPosSize - projCurrentPosLosses) - riskAllotment + projCurrentPosLosses
    lower = abs((stopPrice - entryPrice) / entryPrice) * (posMarginRate - 1) - posMarginRate

    optimalLossSize = upper / lower


    # maximize size to gains:
    # maximum size to avoid margin call as defined by: Future NAV = Future Margin Used
    #
    # (1) R + PG + NG = MR * [(PS + PG) + (NS + NG)]
    # 
    # (2) NL = NP * | [(Ex - En) / En] |
    #
    # Eq. 1 and Eq. 2 combine to Eq. 3...
    #
    # (3) NS = [MR * (PS + PG) - R - PG] / [ |([Ex - En] / En)| - 2 * MR]
    
        # NS = new trade's position size (solving for)
        # R = allotted risk (balance * martozitz)
        # PS = current unadjusted position size
        # PG = current projected gains
        # NG = new trade's projected gains
        # MR = instrument's margin rate
        # En = the trade's projected entry price
        # Ex = the trade's projected exit price

    # solve for NS:
    upper = posMarginRate * (unadjCurrentPosSize + projCurrentPosGains) - riskAllotment - projCurrentPosGains
    lower = abs((takePrice - entryPrice) / entryPrice) - 2 * posMarginRate

    optimalGainsSize = upper / lower

    return optimalGainsSize, optimalLossSize





