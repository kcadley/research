from __future__ import annotations
import abc
import copy
import datetime
from typing import Any
import numpy as np
from types import NoneType, SimpleNamespace
import scipy.stats
import scipy.optimize
import asyncio
import sys
sys.path.append("<path here>")
import daycount


''' BASE '''
class BaseInstrument(abc.ABC):
    '''
    
    Abstract base class for all financial instruments.

    
    Attributes
    ----------
    `tsym` : str 
        Symbol used to place trades on the instrument.

    `qsym` : str
        Symbol used to request quotes on the instrument.

    `underlying` : object | None = None
        The underlying instrument, if any, that the instance depends on.

    `derivatives` : list | None
        The derivatives, if any, that are based off of the instance.
        
    `now` : datetime.datetime
        The current time from the contract's perspective (utilized for 
        backtesting).
    
    `bid` : float
        The instrument's bid.

    `ask` : float
        The instrument's ask.

    `mark` : float
        The instrument's mark.

    `spread` : float
        The instrument's spread

    `isSnapshot` : bool
        Whether the object is a snapshot (deepcopy) of another instrument.
        
    Methods
    -------
    `quote()` -> None
        Simultaneously sets the instrument's bid and ask.
    
    `attach_stream()` -> None
        Attaches a stream to continuously update the instrument's quotes.
    
    `snapshot()` -> object
        Returns a deepcopy ("snapshot") of the instrument. The snapshot 
        is  disconnected from any streamed content the original instrument was 
        connected to - ie. all snapshot variables are static until manually 
        changed.
    
    '''

    def __init__(self, 
                 tsym : str | None = None, 
                 qsym : str | None = None, 
                 underlying : object | None = None) -> None:
        '''

        Abstract base class, represents any financial instrument.


        Parameters
        ----------
        `tsym` : str
            Symbol used to place trades on the instrument.

        `qsym` : str
            Symbol used to request quotes on the instrument.

        `underlying` : object | None = None
            The underlying instrument, if any, that this instrument depends on.
            
        Returns
        -------
        `None`
        
        '''
        
        self.bid = None
        self.ask = None
        self.mark = None
        self.spread = None
        
        self.tsym = tsym
        self.qsym = qsym

        self.underlying = underlying
        self.derivatives = []
        
        if not isinstance(underlying, NoneType):
            underlying.derivatives.append(self)

        self.now = None
        
        self.isSnapshot = False

        return None

    @property
    def bid(self) -> float | int:
        return self._bid

    @bid.setter
    def bid(self, bid) -> None:
        
        # null init
        if isinstance(bid, NoneType):
            self._bid = None

        # set bid
        elif isinstance(bid, (float, int)):
            self._bid = bid

            # mark and spread
            if isinstance(self.ask, (float, int)):
                self.mark = (self.bid + self.ask) / 2
                self.spread = self.ask - self.bid

            # update model
            self._update()

            # alert deriviatives
            if len(self.derivatives) != 0:
                for derivatives in self.derivatives:
                    derivatives._update()

        return None

    @property
    def ask(self) -> float | int:
        return self._ask

    @ask.setter
    def ask(self, ask) -> None:

        # null init
        if isinstance(ask, NoneType):
            self._ask = None

        # set ask
        elif isinstance(ask, (float, int)):
            self._ask = ask
            
            # mark and spread
            if isinstance(self.bid, (float, int)):
                self.mark = (self.bid + self.ask) / 2
                self.spread = self.ask - self.bid

            # update model
            self._update()

            # alert deriviatives
            if len(self.derivatives) != 0:
                for derivatives in self.derivatives:
                    derivatives._update()

        return None

    @property
    def now(self) -> datetime.datetime:

        if isinstance(self._now, NoneType):
            return datetime.datetime.now(tz=datetime.UTC)
        
        else:
            return self._now
        
    @now.setter
    def now(self, now : datetime.datetime | None) -> None:

        # if already present, update all
        if "_now" in self.__dir__():
            # set new time
            self._now = now

            # update model
            self._update()

            # alert derivatives
            if len(self.derivatives) != 0:
                for derivative in self.derivatives:
                    derivative._update()

        # else on init, skip update
        else:
            self._now = now

        return None

    def quote(self, bid : float | int, ask : float | int) -> None:
        '''
        
        Simultaneously sets the instrument's bid and ask.


        Parameters
        ----------
        `bid` : float | int
            The bid.

        `ask` : float | int
            The ask.

        Returns
        -------
        `None`
        
        '''

        # set values WITHOUT "setter", avoid double alerting derivatives
        self._bid = bid
        self._ask = ask

        # mark and spread
        if isinstance(self.bid, (float, int)) and isinstance(self.ask, (float, int)):
            self.mark = (self.bid + self.ask) / 2
            self.spread = self.ask - self.bid
        
        elif isinstance(self.bid, NoneType) or isinstance(self.ask, NoneType):
            self.mark = None
            self.spread = None

        # update model
        self._update()

        # alert derivatives
        if len(self.derivatives) != 0:
            for derivative in self.derivatives:
                derivative._update()

        return None

    async def _attach_stream(self, stream : object, poll : int) -> None:
        '''
        
        Wrapper for "self.attach_stream()", asynchronously updates the 
        instruments quotes as they're received from a feed.

        
        Parameters
        ----------
        `stream` : object
            The stream receiving live quotes. The stream object must contain
            a "self._link._loop" attribute representing the "asyncio" loop
            managing the stream (regardless of stream type).
            
        `poll` : int
            The number of seconds between polling for new quotes.
            
        Returns
        -------
        `None`
            
        '''

        # endlessly check for updates
        while stream.isAlive and (not self.isSnapshot):
            
            # asyncio nuance
            await asyncio.sleep(0)

            # pull instrument's quotes
            quotes = stream.quote(self.qsym)

            # if new bid, record
            if isinstance(quotes["bidPrice"], (float, int)) and (isinstance(self._bid, NoneType) or (quotes["bidPrice"] != self.bid)):
                newBid = quotes["bidPrice"]
            else:
                newBid = None

            # if new ask, record
            if isinstance(quotes["askPrice"], (float, int)) and (isinstance(self._ask, NoneType) or (quotes["askPrice"] != self.ask)):
                newAsk = quotes["askPrice"]
            else:
                newAsk = None

            # set new quotes
            if isinstance(newBid, (float, int)) and isinstance(newAsk, (float, int)):
                self.quote(newBid, newAsk)
            
            elif isinstance(newBid, (float, int)):
                self.bid = newBid
            
            elif isinstance(newAsk, (float, int)):
                self.ask = newAsk

            # wait for next poll
            await asyncio.sleep(poll)

        return None

    def attach_stream(self, stream : object, poll : int = 1) -> None:
        '''
        
        Attaches a stream to continuously update the instrument's quotes.

        
        Parameters
        ----------
        `stream` : object
            The stream receiving live quotes. The stream object must contain
            a "self._link._loop" attribute representing the "asyncio" loop
            managing the stream (regardless of stream type).
        
        `poll` : int = 1
            The number of seconds between polling for new quotes.
            
        Returns
        -------
        `None`
            
        '''

        # continuously updates quotes in the background
        asyncio.run_coroutine_threadsafe(self._attach_stream(stream, poll), stream._link._loop)

        return None

    def snapshot(self) -> object:
        '''
        
        Returns a deepcopy ("snapshot") of the instrument. The snapshot 
        is  disconnected from any streamed content the original instrument was 
        connected to - ie. all snapshot variables are static until manually 
        changed.

        
        Parameters
        ----------
        `None`

        Returns
        -------
        `object`
            A static instance of the instrument.
        
        '''

        # snapshot
        snapshot = copy.deepcopy(self)
        
        # disable updates to stream
        snapshot.isSnapshot = True
        
        # disable updates to underlying / derivatives
        if not isinstance(snapshot.underlying, NoneType):
            snapshot.underlying.isSnapshot = True
        
        for deriv in snapshot.derivatives:
            deriv.isSnapshot = True

        return snapshot

    @abc.abstractmethod
    def _update(self) -> None:
        '''
        
        Abstract method. Updates the instrument's modeled attributes.

        
        Parameters
        ----------
        `None`
        
        Returns
        -------
        `None`

        '''

        return None


''' SPOT '''
class FXSpot(BaseInstrument):
    '''
    
    A spot-traded currency pair instrument.

    
    Attributes
    ----------
    `tsym` : str 
        Symbol used to place trades on the instrument.

    `qsym` : str
        Symbol used to request quotes on the instrument.

    `underlying` : object | None = None
        The underlying instrument, if any, that the instance depends on.

    `derivatives` : list | None
        The derivatives, if any, that are based off of the instance.
        
    `now` : datetime.datetime
        The current time from the contract's perspective (utilized for 
        backtesting).
    
    `bid` : float
        The instrument's bid.

    `ask` : float
        The instrument's ask.

    `mark` : float
        The instrument's mark.

    `spread` : float
        The instrument's spread

    `isSnapshot` : bool
        Whether the object is a snapshot (deepcopy) of another instrument.
        
    Methods
    -------
    `quote()` -> None
        Simultaneously sets the instrument's bid and ask.
    
    `attach_stream()` -> None
        Attaches a stream to continuously update the instrument's quotes.
    
    `snapshot()` -> object
        Returns a deepcopy ("snapshot") of the instrument. The snapshot 
        is  disconnected from any streamed content the original instrument was 
        connected to - ie. all snapshot variables are static until manually 
        changed.
    
    '''

    def __init__(self, **kwargs) -> None:
        '''
        
        Initializes the FXSpot object.


        Parameters
        ----------
        `tsym` : str
            Symbol used to place trades on the instrument.

        `qsym` : str
            Symbol used to request quotes on the instrument.

        `underlying` : object | None = None
            The underlying instrument, if any, that this instrument depends on.

        Returns
        -------
        `FXSpot` : object
            The FXSpot instance.
        
        '''

        # inherit children
        super().__init__(**kwargs)

        return None

    def _update(self) -> None:
        '''
        
        Overrides abstract method. Method not applicable to FXSpot class.

        '''

        pass


''' FUTURES '''
class CurrencyFuture(BaseInstrument):
    '''
    
    A futures contract on a spot-traded currency pair.

    *note*  "The theoretical differences between forward and futures prices for 
    contracts which last only a few months are, in most circumstances,
    sufficiently small to be ignored... there are a number of factors, not 
    reflected in theoretical models, that may cause forward and futures prices 
    to be different... despite all these points, in most circumstances, it is 
    reasonable to assume that forward and futures prices are the same."
    - pg. 57, John Hull, "Options, Futures, and Other Derivative Securities, 
    2nd Ed."

    Currency futures are priced via the classic forward equation: 
    F = S * e^((r - q)(T-t))


    Attributes
    ----------
    `rf` : float
        The quoted currency's risk-free rate ("domestic").

    `qf` : float
        The base currency's risk-free rate ("foreign").

    `settle` : datetime.datetime
        The settlement date of the contract.

    `ccr` : float
        The continuously compounded equivalent of the quoted currency's 
        risk-free rate (on an Actual/360 basis).

    `ccq` : float
        The continuously compounded equivalent of the base currency's 
        risk-free rate (on an Actual/360 basis).

    `now` : datetime.datetime
        The current time from the contract's perspective (can be altered for 
        backtesting).

    `r_tenor` : float
        The length of time (as a fraction of years) until the contract's 
        settlement, calculated using the risk-free interest rate's daycount 
        convention.

    `price` : SimpleNamespace
        The modeled price of the contract, with individual variables accessible 
        via dot-notation: [bid, ask, mark, spread]

    `carry` : float
        The market's modeled estimate of the currency pair's cost-of-carry 
        (annualized).
        
    `tsym` : str
        Symbol used to place trades on the instrument.

    `qsym` : str
        Symbol used to request quotes on the instrument.

    `underlying` : object | None = None
        The underlying instrument, if any, that the instance depends on.

    `derivatives` : list | None
        The derivatives, if any, that are based off of the instance.

    `bid` : float
        The instrument's bid.

    `ask` : float
        The instrument's ask.

    `mark` : float
        The instrument's mark.

    `spread` : float
        The instrument's spread

    `isSnapshot` : bool
        Whether the object is a snapshot (deepcopy) of another instrument.
        
    Methods
    -------
    `quote()` -> None
        Simultaneously sets the instrument's bid and ask.
    
    `attach_stream()` -> None
        Attaches a stream to continuously update the instrument's quotes.
    
    `snapshot()` -> object
        Returns a deepcopy ("snapshot") of the instrument. The snapshot 
        is  disconnected from any streamed content the original instrument was 
        connected to - ie. all snapshot variables are static until manually 
        changed.
    
    '''

    def __init__(self, 
                 rf : float,
                 qf : float, 
                 settle : datetime.datetime, 
                 **kwargs) -> None:
        '''
        
        Initializes the CurrencyFuture object.


        Parameters
        ----------
        `rf` : float
            The quoted currency's risk-free rate ("domestic").

        `qf` : float
            The base currency's risk-free rate ("foreign").

        `settle` : datetime.datetime
            The settlement date of the contract.

        `tsym` : str
            Symbol used to place trades on the instrument.

        `qsym` : str
            Symbol used to request quotes on the instrument.

        `underlying` : object | None = None
            The underlying instrument, if any, that this instrument depends on.

        Returns
        -------
        `CurrencyFuture` : object
            The CurrencyFuture instance.
        
        '''

        # inherit children
        super().__init__(**kwargs)

        # initialize variables
        self.rf = None
        self.ccr = None
        self.qf = None
        self.ccq = None
        self.settle = None
        self.carry = None

        # set variables
        self.price = SimpleNamespace(bid=None, ask=None, mark=None, spread=None)
        self.settle = settle
        self.rf = rf    # sets self.ccr internally
        self.qf = qf    # sets self.ccq internally

        return None
    
    @property
    def rf(self) -> float:
        return self._rf

    @rf.setter
    def rf(self, rf : float) -> None:
        
        if isinstance(rf, NoneType):
            self._rf = None
            self.ccr = None

        elif isinstance(rf, (float, int)):
            
            # convert to continuously compounded
            self._rf = rf
            self.ccr = 360 * np.log(1 + self.rf / 360)
            
            # update model
            self._update()

            # update derivatives
            if len(self.derivatives) != 0:
                for derivative in self.derivatives:
                    derivative._update()

        return None
    
    @property
    def qf(self) -> float:
        return self._qf

    @qf.setter
    def qf(self, qf : float) -> None:
        
        if isinstance(qf, NoneType):
            self._qf = None
            self.ccq = None

        elif isinstance(qf, (float, int)):

            # convert to continuously compounded
            self._qf = qf
            self.ccq = 360 * np.log(1 + self.qf / 360)

            # update model
            self._update()

            # update derivatives
            if len(self.derivatives) != 0:
                for derivative in self.derivatives:
                    derivative._update()

        return None

    @property
    def r_tenor(self) -> float:
        return daycount.actual360_T(self.now, self.settle)

    def _update(self) -> None:
        '''
        
        Overrides abstract method. Updates the currency future's modeled price,
        calculates the market's modeled estimate of the currency pair's 
        cost-of-carry (annualized).

        
        Parameters
        ----------
        `None`

        Returns
        -------
        `None`

        '''

        # not all variables present
        if None in [self.ccr, self.ccq, self.settle]:
            pass

        else:
            # ensure underlying available
            if not isinstance(self.underlying, NoneType):
            
                # model bid
                if isinstance(self.underlying.bid, (float, int)):
                    self.price.bid = self.underlying.bid * np.exp((self.ccr - self.ccq)*self.r_tenor)

                # model ask
                if isinstance(self.underlying.ask, (float, int)):
                    self.price.ask = self.underlying.ask * np.exp((self.ccr - self.ccq)*self.r_tenor)

                # calculate mark & spread
                if isinstance(self.price.bid, (float, int)) and isinstance(self.price.ask, (float, int)):
                    self.price.mark = (self.price.bid + self.price.ask) / 2
                    self.price.spread = self.price.ask - self.price.bid    

                # calculate cost-of-carry
                if isinstance(self.underlying.mark, (float, int)) and isinstance(self.mark, (float, int)):
                    # continuously compounded cost-of-carry
                    ccc = np.log(self.mark / self.underlying.mark) / self.r_tenor
                    
                    # annualized cost-of-carry
                    self.carry = (np.exp(ccc / 360) - 1) * 360                

        return None


''' OPTIONS '''
class CurrencyFutureOption(BaseInstrument):

    def __init__(self, 
                 otype : str, 
                 strike : float, 
                 expir : datetime.datetime, 
                 lastVol : float | None = None,
                 **kwargs) -> None:

        # inherit children
        super().__init__(**kwargs)

        # initialize variables
        self.otype = None
        self.strike = None
        self.expir = None

        self.price = SimpleNamespace(bid=None, ask=None, mark=None, spread=None)
        self.vol = lastVol
        self.moneyness = None
        self.probability = None
        self._norm = scipy.stats.norm(0, 1).cdf     # used for "self.probability()" in "_calc_implied()"

        self.delta = None
        self.gamma = None
        self.vega = None
        self.theta = None
        self.rho = None
        self.epsilon = None

        # set variables
        self.strike = strike
        self.expir = expir
        self.otype = otype  # don't move, self._update() blocks until otype set

        return None

    @property
    def vol(self) -> float:
        return self._vol
    
    @vol.setter
    def vol(self, vol : float | None) -> None:
        
        # set new implied volatility
        self._vol = vol

        # update model
        self._manual_vol = True  # prevents implied volatility calculation
        self._update()
        self._manual_vol = False # revert to normal

    @property
    def r_tenor(self) -> float:
        return daycount.actual360_T(self.underlying.now, self.expir)

    @property
    def t_tenor(self) -> float:
        return daycount.trading_T(self.underlying.now, self.expir)

    def _update(self) -> None:
        
        # not all variables present
        if None in [self.underlying.ccr,  self.underlying.ccq, self.otype]:
            pass
        
        # ensure prices available
        elif (isinstance(self.bid, (float, int)) or isinstance(self.ask, (float, int)) ) and isinstance(self.underlying.mark, (float, int)):    
            
            # if "self.vol" setter didn't trigger update, calculated implied vol
            if not self._manual_vol:
                self._calc_implied()
            
            # calculate modeled option price and greeks
            self._calc_price()

        else:
            pass

        return None

    def _newton_implied(self, 
                        vol : float, realPrice : float, otype : str, 
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

    def _corrado_miller_implied(self, 
                                realPrice : float, otype : str, 
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

    def _calc_implied(self) -> None:

        # pull static variables
        otype = self.otype
        strike = self.strike
        t_tenor = self.t_tenor
        r_tenor = self.r_tenor
        f_mark = self.underlying.mark
        discount = np.exp((-self.underlying.ccr) * self.r_tenor)
        ccr = self.underlying.ccr

        # set initial vol estimate
        rerun = False
        if isinstance(self.vol, NoneType):
            
            # will need to rerun entire function once final implied vol calculated,
            # this vol is an initial estimate for bid-ask weights when picking mark
            rerun = True

            # choose nearest mark, consider null contracts 0
            if isinstance(self.bid, NoneType):
                tempMark = self.ask
            elif isinstance(self.ask, NoneType):
                tempMark = self.bid
            else:
                tempMark = (self.bid * .5) + (self.ask * .5)

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
            self._vol = self._corrado_miller_implied(tempPrice, otype, t_tenor, 
                                                     f_mark, strike, discount)

        # estimate standardized moneyness (vol adjusted, time independent):
        if otype == "call":
            self.moneyness = np.log(f_mark / strike) / ( np.sqrt(t_tenor) * self.vol )

        elif otype == "put":
            self.moneyness = np.log(strike / f_mark) / ( np.sqrt(t_tenor) * self.vol )

        # probability of closing ITM
        self.probability = self._norm(self.moneyness)

        # weigh towards bid, more sellers than buyers for ITM
        if self.moneyness >= 0:
            bidAdj = self.probability
            askAdj = 1 - bidAdj

        # weigh towards ask, more buyers than sellers for OTM
        else:
            askAdj = self.probability
            bidAdj = 1 - askAdj

        # consider null contracts 0, adjust for weights this time
        if isinstance(self.bid, NoneType):
            newTempMark = self.ask
        elif isinstance(self.ask, NoneType):
            newTempMark = self.bid
        else:
            newTempMark = (self.bid * bidAdj) + (self.ask * askAdj)

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
        self._vol = scipy.optimize.newton(self._newton_implied, self.vol,
                                          args=(realPrice, otype, ccr, r_tenor, 
                                                t_tenor, f_mark, strike))
        
        # in initializing, rerun with new implied vol to narrow estimates
        if rerun:
            self._calc_implied()
        
        return None

    def _calc_price(self) -> None:

        # Black-76 Variables
        discount = np.exp((-self.underlying.ccr) * self.r_tenor)
        d_plus = (np.log(self.underlying.mark / self.strike) + (self.vol**2 / 2) * self.t_tenor) / (self.vol * np.sqrt(self.t_tenor))
        d_minus = d_plus - self.vol * np.sqrt(self.t_tenor)

        # Black-76 Option Pricing Model (OPM)
        if self.otype == "call":
            self.price = discount * (self.underlying.mark * scipy.stats.norm.cdf(d_plus) - self.strike * scipy.stats.norm.cdf(d_minus))

        elif self.otype == "put":
            self.price = discount * (self.strike * scipy.stats.norm.cdf(-d_minus) - self.underlying.mark * scipy.stats.norm.cdf(-d_plus))

        # Black-76 Greeks
        self._calc_delta(discount, d_plus)
        self._calc_gamma(discount, d_plus)
        self._calc_vega(discount, d_plus)
        self._calc_theta(discount, d_plus, d_minus)
        self._calc_rho(discount, d_minus)
        self._calc_epsilon(d_plus)

        return None

    def _calc_delta(self, discount : float, d_plus : float) -> None:

        if self.otype == "call":
            self.delta = discount * scipy.stats.norm.cdf(d_plus)

        elif self.otype == "put":
            self.delta = discount * (scipy.stats.norm.cdf(d_plus) - 1.0)

        return None

    def _calc_gamma(self, discount : float, d_plus : float) -> None:

        self.gamma = (scipy.stats.norm.pdf(d_plus) * discount) / (self.underlying.mark * self.vol * np.sqrt(self.t_tenor))

        return None

    def _calc_vega(self, discount : float, d_plus : float) -> None:

        self.vega = self.underlying.mark * np.sqrt(self.t_tenor) * scipy.stats.norm.pdf(d_plus) * discount

        return None

    def _calc_theta(self, discount : float, d_plus : float, d_minus : float) -> None:

        if self.otype == "call":
            one = (self.underlying.mark * scipy.stats.norm.pdf(d_plus) * self.vol * discount) / (2.0 * np.sqrt(self.t_tenor))
            two = self.underlying.ccr * self.underlying.mark * scipy.stats.norm.cdf(d_plus) * discount
            three = self.underlying.ccr * self.strike * discount * scipy.stats.norm.cdf(d_minus)

            self.theta = ( (-one) + two - three ) * ( 1 / daycount.trading_days() )  # daily theta

        elif self.otype == "put":
            one = (self.underlying.mark * scipy.stats.norm.pdf(d_plus) * self.vol * discount) / (2.0 * np.sqrt(self.t_tenor))
            two = self.underlying.ccr * self.underlying.mark * scipy.stats.norm.cdf(-d_plus) * discount
            three = self.underlying.ccr * self.strike * discount * scipy.stats.norm.cdf(-d_minus)

            self.theta = ( (-one) - two + three ) * ( 1 / daycount.trading_days() ) # daily theta

        return None

    def _calc_rho(self, discount : float, d_minus : float) -> None:

        if self.otype == "call":
            self.rho = self.strike * self.r_tenor * discount * scipy.stats.norm.cdf(d_minus)

        elif self.otype == "put":
            self.rho = (-self.strike) * self.r_tenor * discount * scipy.stats.norm.cdf(-d_minus)

        return None

    def _calc_epsilon(self, d_plus : float) -> None:
    
        if self.otype == "call":
            self.epsilon = (-self.r_tenor) * self.underlying.mark * np.exp((-self.underlying.ccq) * self.r_tenor) * scipy.stats.norm.cdf(d_plus)

        elif self.otype == "put":
            self.epsilon = self.r_tenor * self.underlying.mark * np.exp((-self.underlying.ccq) * self.r_tenor) * scipy.stats.norm.cdf(-d_plus)
            
        return None






