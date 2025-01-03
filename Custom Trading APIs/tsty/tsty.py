import aiohttp
import asyncio
import threading
import datetime
from urllib.error import HTTPError
import concurrent
from types import NoneType, SimpleNamespace
from typing import Generator, Any

class SimpName(SimpleNamespace):
    '''
    
    Wrapper for `types.SimpleNamespace`, extends functionality to included a 
    generator for iterating over attributes.

    Attributes
    ----------
    Any

    Methods
    -------
    None
    
    '''

    def __init__(self, **kwargs) -> None:
        
        # inherit SimpleNamespace
        SimpleNamespace.__init__(self, **kwargs)

        return None
    
    def __iter__(self) -> Generator[Any, None, None]:
        '''
        
        A simple generator for accessing SimpleNamespace attributes.

        
        Parameters
        ----------
        None

        Returns
        -------
        Any
        
        '''
        for var in self.__dict__.keys():
            yield self.__getattribute__(var)

class Response():
    '''
    
    A thread-safe way to pass "concurrent.futures.Future" HTTP response objects 
    between functions.  This is effectively an "await" call on the given request after 
    it's been sent, but can be run from anywhere in the program without
    concern for the given thread's eventloop.


    Attributes
    ----------
    `_future` : concurrent.futures.Future
        The future object returned from running an "aiohttp" request via
        "asyncio.run_coroutine_threadsafe()".

    `_response` : aiohttp.ClientResponse
        The full HTTPS response of the "self._future" object (empty until self.response()
        is run).

    `_json` : dict
        The body of the HTTPS response of the "self._future" object (empty until 
        populated by "self.json()").

    `_loop` : asyncio.AbstractEventLoop
        The "ayncio" event loop used to make the original request.
        
    Methods
    -------
    `response()` -> aiohttp.ClientResponse
        Simple wrapper for "Future.result()", effectively acts as an "await".
        Caches and returns the "aiohttp.ClientResponse" object, returning cache for 
        every additional call.
    
    `json()` -> dict
        Caches and returns the "aiohttp.ClientResponse"'s HTTPS response body as
        a json (converts to dictionary). Acts as an "await" if first time called, 
        otherwise returns cached results.
    
    '''
 
    def __init__(self, future : concurrent.futures.Future, loop : asyncio.AbstractEventLoop) -> None:
        '''
        
        Initializes the Response() instance.

        
        Parameters
        ----------
        `future` : concurrent.futures.Future
            The future object, representing tentative results.
        
        `loop` : asyncio.AbstractEventLoop
            The original loop used to create the `concurrent.futures.Future` object

        Returns
        -------
        `Response` : obj
            The `Response()` instance
        
        '''

        self._future = future
        self._response = None
        self._json = None
        self._loop = loop

    def response(self) -> aiohttp.ClientResponse:
        '''
        
        Simple wrapper for Future.result(), effectively acts as an "await".
        Caches and returns the aiohttp.ClientResponse object, returning cache for 
        every additional call.


        Parameters
        ----------
        None

        Returns
        -------
        `None`
        
        '''
        if isinstance(self._response, NoneType):
            self._response = self._future.result()
            resp = self._response

        else:
            resp = self._response

        return resp

    def json(self) -> dict:
        '''

        Caches and returns the aiohttp.ClientResponse's HTTPS response body as
        a json (converts to dictionary). Acts as an "await" if first time called, 
        otherwise returns cached results.
        

        Parameters
        ----------
        None

        Returns
        -------
        `dict`
            The dictionary representation of the request's response body.

        '''

        # if future never had result() called, cache result(), then call json() on cache
        if isinstance(self._response, NoneType):
            
            self._response = self._future.result()

            try:
                self._response.raise_for_status()
                payload = asyncio.run_coroutine_threadsafe(self._response.json(), self._loop)
                returnJson = payload.result()
                self._json = returnJson

            except HTTPError as error:
                raise error
            
        # if future had result() called, but payload was never loaded, call json() on cache
        elif isinstance(self._json, NoneType):
            try:
                self._response.raise_for_status()
                payload = asyncio.run_coroutine_threadsafe(self._response.json(), self._loop)
                self._json = payload.result()
                returnJson = self._json

            except HTTPError as error:
                raise error

        # if future had result() called and json() already called, return prior results
        else:
            returnJson = self._json

        return returnJson

class Tasty():
    '''
    
    A network class used to interact with Tasty Trade. Built on top of
    `aiohttp`, utilizes `asyncio` to send / receive RESTful HTTP requests to 
    access various endpoints (to include personal account details, product 
    offerings, and trade execution).


    Attributes
    ----------
    `accountID` : str
        The TastyTrade accountID.
        
    `sessionToken` : str
        The session token used to authenticate each HTTP request (provided
        after official auth with user / password)

    `rememberToken` : str
        A remember token that may be used in place of a password at the next
        official auth - these are "one-time-use", need to record each new one
        after each official auth.

    `marketToken` : str
        The market token used to auth with DXLink (TastyTrade's market data
        provider).

    `marketURL` : str
        DXLink's endpoint url (for market data requests).

    `lastLogin` : datetime.datetime
        The date and time of the session's start - used to bookmark the session's
        lifecycle (tokens are only good for 24h at a time before refresh needed).

    `_loop` : asyncio.AbstractEventLoop
        The asyncio event loop used to queue HTTP requests.

    `_eventLoop` : threading.Thread
        The thread used to indefinitely run the asyncio event loop.
    
    `_sess` : aiohttp.ClientSession
        The HTTP session used to interact with TastyTrade endpoints.

    Methods
    -------
    `request()` : func
        Asyncrounously sends any general HTTP request to TastyTrade's servers.
    
    `get_balance()` : func
        Retrieves current account balance details.

    `get_positions()` : func
        Retriives current account position details.
    
    `meta_futures()` : func
        Lists meta-data on all future products offered by TastyTrade. Contract
        months listed may or may not be actively trading (or even issued),
        the meta-data describes the product attributes, not specific contracts.
    
    `active_futures()` : func
        Lists all actively trading future contracts offered by TastyTrade for 
        the given list of product codes. 
    
    `get_futures()` : func
        Retrieves the given futures contract details (must be actively
        trading). 
    
    `meta_options()` : func
        Lists meta-data on all FUTURE-OPTIONS PRODUCTS (ONLY) offered by TastyTrade.
        Contract months listed may or may not be actively trading (or even issued),
        the meta-data describes the product attributes, not specific contracts.
    
    `active_options()` : func
        Lists all actively trading futures-options / equity-options contracts 
        offered by TastyTrade for the given product code (symbol). 
    
    `get_options()` : func
        Retrieves the given future-options / equity-options contract(s) details.

    `close()` : func
        Closes the HTTPS session with TastyTrade, cancels all pending asyncio 
        tasks, stops the asyncio event loop, then finally `*.joins()` the 
        threading running the asyncio loop.

    `_get_sess()` : func
        Forms a persistent HTTP session for easy access to TastyTrade endpoints.
    
    `_kill_stragglers()` : func
        Cancels all pending asyncio tasks (except for the task running this 
        function).
    '''

    def __init__(self, 
                 password : str = "", 
                 requestMarket : bool = False,
                 live : bool = False) -> None:
        '''
        
        Initializes a Tasty() instance.

        
        Parameters
        ----------
        `password` : str = ""
            The user's TastyTrade password. If omitted, authenticates with
            prior session's "rememberToken". Tokens are one-time use and valid
            for only 30 days - a new token will be automaticlaly recorded for 
            every new authentication, regardless of authentication type.

        `requestMarket` : bool = False
            Whether to request a DXLink token for retrieving market data.

        `live` : bool = False
            Whether this session will be used for live trading or paper trading  
            (determines the endpoint for all subsequent API  calls).

        Returns
        -------
        `Tasty` : obj
            The Tasty() instance.
        
        '''

        # internal event loop
        self._loop = asyncio.new_event_loop()
        self._eventLoop = threading.Thread(target=self._loop.run_forever)
        self._eventLoop.daemon = True
        self._eventLoop.start()

        # build a session
        if live:
            baseURL = "https://api.tastyworks.com"
            baseURI = "wss://streamer.tastyworks.com"
        else:
            baseURL = "https://api.cert.tastyworks.com"
            baseURI = "wss://streamer.cert.tastyworks.com"

        baseHeaders = {"Content-Type" : "application/json",
                       "Accept" : "application/json"}
        future = asyncio.run_coroutine_threadsafe(self._get_sess(url=baseURL, headers=baseHeaders), self._loop)
        self._sess = future.result()       # `await` results

        # configure login creds
        target = "/sessions"
        loginPayload = {"login" : "<user here>",
                        "remember-me" : True}
        
        # either use password
        if password:
            loginPayload["password"] = password
        
        # or pull appropriate token
        else:
            if live:
                with open("<key here>") as file:
                    rememberToken = file.read()
            else:
                with open("<key here>") as file:
                    rememberToken = file.read()
            # set token
            loginPayload["remember-token"] = rememberToken
            
        # auth
        self.lastLogin = datetime.datetime.now()
        resp = self.request(method="POST", url=target, json=loginPayload).json() # adding self.json() is like "await"
        
        # pull auth tokens
        self.sessionToken = resp["data"]["session-token"]
        self.rememberToken = resp["data"]["remember-token"]

        # record token
        if live:
            with open("<key here>", "w") as file:
                file.write(self.rememberToken)
        else:
            with open("<key here>", "w") as file:
                file.write(self.rememberToken)

        # load session header
        authHeader = {"Authorization" : self.sessionToken}
        self._sess.headers.update(authHeader)

        # pull account data
        resp = self.request(method="GET", url="/customers/me/accounts").json() # adding self.json() is like "await"
        self.accountID = resp["data"]["items"][0]["account"]["account-number"]
        
        # request market token
        if requestMarket:
            target = "/api-quote-tokens"
            resp = self.request(method="GET", url=target).json()        # adding self.json() is like "await"
            self.marketToken = resp["data"]["token"]
            self.marketURL = resp["data"]["dxlink-url"]

            # record new market token
            with open("<key here>", "w") as file:
                file.write(self.marketToken)
        
        else:
            self.marketToken = None
            self.marketURL = None

        return None

    ''' SESSION '''
    async def _get_sess(self, url, headers):
        '''

        Forms a persistent HTTP session for easy access to TastyTrade endpoints.

        
        Parameters
        ----------
        `url` : str
            A default base url to use throughout the session - all additional
            calls will be prepended with this URL (can pass just file paths
            from here-on-out).

        `headers` : dict
            Default headers to use throughout the session.

        Returns
        -------
        aiohttp.ClientSession : object
            A persistent HTTP session that supports `asyncio` calls.

        '''
        
        return aiohttp.ClientSession(base_url=url, headers=headers)

    def request(self, **kwargs) -> Response:
        '''
        
        Asyncrounously sends any general HTTP request to TastyTrade's servers.

        
        Parameters
        ----------
        `method` : str
            The HTTP method to use: ["GET", "POST", "PUT", "DELETE", "PATCH"]
        
        `url` : str
            Endpoint to query from.
            
            *note* Use target path only, not FQDN - base URL is set when the
            session is created: for instance, use "/customer/me/account", not 
            "https://tastytrade.com/customer/me/account"
        
        `params` : dict
            Key-Value pairs to be sent as parameters in the query string of the new request.
        
        `data` : dict 
            The data to send in the body of the request.

        `json` : dict 
            Any json compatible python object. 
            
            *note* `json` and `data` parameters can not be used at the same time.

        `headers` : dict
            HTTP Headers to send with the request.

        *many more options*
            https://docs.aiohttp.org/en/stable/client_reference.html

        Returns
        -------
        `Response` : obj
            A Reponse() instance containing a concurrent.futures.Future, which
            contains with the HTTPS response payload. Calling *.json() for the 
            HTTPS body or *.reponse() for the entire aiohttp.ClientResponse payload 
            acts as an "await" on the Future:

            >>> response = self.request()
            >>> payload = response.json()
            
        '''

        future = asyncio.run_coroutine_threadsafe(self._sess.request(**kwargs), self._loop)

        return Response(future, self._loop)

    async def _kill_stragglers(self) -> None:
        '''
        
        Cancels all pending asyncio tasks (except for the task running this 
        function).


        Parameters
        ----------
        None

        Returns
        -------
        `None`
        
        '''
        
        # sets THIS task's name
        thisTask = asyncio.current_task()
        thisTask.set_name("kill_stragglers")

        # cancel all pending tasks besides this one
        for task in asyncio.all_tasks():
            if task.get_name() != "kill_stragglers":
                task.cancel()

        return None

    def close(self) -> None:
        '''
        
        Closes the HTTPS session.


        Parameters
        ----------
        None

        Returns
        -------
        `None`
        
        '''

        # close the websocket
        future = asyncio.run_coroutine_threadsafe(self._sess.close(), self._loop)
        complete = future.result()

        # cancel all remaining tasks
        future = asyncio.run_coroutine_threadsafe(self._kill_stragglers(), self._loop)
        complete = future.result()

        # stop the loop, join the thread, close the loop
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._eventLoop.join()
        self._loop.close()

        return None

    ''' ACCOUNT '''
    def balance(self) -> dict:
        '''
        
        Retrieves the account's current balance details.


        Parameters
        ----------
        None

        Returns
        -------
        `dict`
            The account's current balance details.

        '''

        target = "/accounts/{}/balances".format(self.accountID)

        resp = self.request(method="GET", url=target).json()

        return resp["data"]

    def positions(self) -> dict:
        '''
        
        Retrieves the account's current position details.


        Parameters
        ----------
        None


        Returns
        -------
        `dict`
            The account's current position details.
        
        '''

        target = "/accounts/{}/positions".format(self.accountID)

        resp = self.request(method="GET", url=target).json()

        positions = {pos["symbol"] : pos for pos in resp["data"]["items"]}

        # quantities are positive, reverse sign
        for key, value in positions.items():
            if value["quantity-direction"] == "Short":
                positions[key]["quantity"] *= -1

        return positions

    ''' INSTRUMENTS '''
    def products(self) -> SimpName:
        '''
        
        Retrieves product details on all futures & future options available
        from participating exchanges. Not to be confused with `self.contracts()`, 
        `self.products()` returns meta-data and standardized issuance information
        of listed products, as opposed to specifications on actively trading 
        issuances.

        *note* defer to `self.contracts()` for actively trading contract 
        specifications.
        

        Parameters
        ----------
        `None`

        Returns
        -------
        `SimpName`
            The future and future option product details.

            *note* "SimpName" is just a wrapper for "types.SimpleNamespace", but
            includes a custom iterator extension.
        
        '''

        # pull contract details
        target1 = "/instruments/future-products"
        resp1 = self.request(method="GET", url=target1).json()

        target2 = "/instruments/future-option-products"
        resp2 = self.request(method="GET", url=target2).json()


        # (1) parse futures
        futures = SimpName()
        for product in resp1["data"]["items"]:
            
            # sort by market sector
            marketSector = product["market-sector"].replace(" ", "")
            if marketSector not in futures.__dict__.keys():
                futures.__setattr__(marketSector, SimpName())
                futures.__getattribute__(marketSector).__setattr__("codes", [])
                futures.__getattribute__(marketSector).__setattr__("specs", {})
                        
            # generic issuance specifications
            code = product["code"]
            futures.__getattribute__(marketSector).__getattribute__("codes").append(code)
            futures.__getattribute__(marketSector).__getattribute__("specs")[code] = product

        
        # (2) parse options
        options = SimpName()
        for product in resp2["data"]["items"]:
            
            # sort by market sector
            marketSector = product["market-sector"].replace(" ", "")
            if marketSector not in options.__dict__.keys():
                options.__setattr__(marketSector, SimpName())
                options.__getattribute__(marketSector).__setattr__("codes", [])
                options.__getattribute__(marketSector).__setattr__("specs", {})
            
            # generic issuance specifications
            code = product["code"]
            options.__getattribute__(marketSector).__getattribute__("codes").append(code)
            options.__getattribute__(marketSector).__getattribute__("specs")[code] = product
        
        return SimpName(futures=futures, options=options)

    def contracts(self, code : str) -> SimpName:
        '''
        
        Retrieves actively trading contract specifications for a given product. 
        Specifications are included for both futures and corresponding options.


        Parameters
        ----------
        `code` : str
            The product code to query active contracts against. Product
            codes may be identified by exploring `self.products()` results.
            
            *note* use codes, not root-symbols for queries (ie: do not include 
            leading slashes: "/6E" -> "6E")

        Returns
        -------
        `SimpName`
            Specifications on future and future options contracts actively
            trading for the given instrument.

            *note* "SimpName" is just a wrapper for "types.SimpleNamespace", but
            includes a custom iterator extension.
        
        '''

        # pull contract details
        params = {"product-code[]" : [code]}
        
        target1 = "/instruments/futures"
        resp1 =  self.request(method="GET", url=target1, params=params).json()

        target2 = "/futures-option-chains/{}/nested".format(code)
        resp2 = self.request(method="GET", url=target2).json()


        # (1) parse active futures
        
        # sort by expiration
        contracts = []
        for contract in resp1["data"]["items"]:
            contracts.append(contract["expiration-date"])
        contracts.sort()

        # active issuance specifications
        futures = SimpName(symbols=[], specs={})
        for contract in contracts:
            for conts in resp1["data"]["items"]:
                if conts["expiration-date"] == contract:
                    futures.symbols.append(conts["symbol"])
                    futures.specs[conts["symbol"]] = conts


        # (2) parse active options

        # parse supplemental info
        underlyings = {val["symbol"] : val for val in resp2["data"]["futures"]}
        exerciseStyle = resp2["data"]["option-chains"][0]["exercise-style"]
        
        # sort options by expiration
        expirations = []
        for expiration in resp2["data"]["option-chains"][0]["expirations"]:
            expirations.append(expiration["expiration-date"])
        expirations.sort()

        # active issuance specifications
        options = SimpName(symbols=[], specs={}, strikes={})
        for expiration in expirations:
            for exprs in resp2["data"]["option-chains"][0]["expirations"]:
                
                if exprs["expiration-date"] == expiration:    
                    
                    # contract specs
                    symb = exprs["option-contract-symbol"]
                    options.symbols.append(symb)
                    options.specs[symb] = {key : value for key, value in exprs.items() if key != "strikes"} # option specs
                    options.specs[symb]["underlying"] = underlyings[exprs["underlying-symbol"]]             # brief underlying specs
                    options.specs[symb]["exercise-style"] = exerciseStyle                                   # supplementary info

                    # sort strikes by price
                    strikes = []
                    for strike in exprs["strikes"]:
                        strikes.append(strike["strike-price"])
                    strikes.sort()

                    # active strikes for issuance
                    options.strikes[symb] = {} 
                    for strike in strikes:
                        for strs in exprs["strikes"]:
                            if strs["strike-price"] == strike:
                                options.strikes[symb][strike] = strs

        return SimpName(futures=futures, options=options)

    def specs(self, symbol : str) -> SimpName:
        '''
        
        Retrieves specifications on a single actively trading contract.


        Parameters
        ----------
        `symbol` : str
            The contract's symbol. Symbols must be in TastyTrade's symbology. 
            Examples:

            FUTURES:  "/6EU4"
            OPTIONS: "./6EU4 EUUU4 240906C1.28"

        Returns
        -------
        `dict`
            The contract's specifications.
        

        '''

        params = {"symbol[]" : [symbol]}

        # query an option
        if "." in symbol:
            target = "/instruments/future-options"

        # querying a future
        else:
            target = "/instruments/futures"

        resp = self.request(method="GET", url=target, params=params).json()

        return resp["data"]["items"][0]

    ''' ORDERS '''
    def routing(self, 
                status : list | str = "ALL",
                fromTime : datetime.datetime | None = None, 
                toTime : datetime.datetime | None = None) -> dict:
        '''
        
        Retrieves order routing details (returns up to 100 orders per query):
        
        https://developer.tastytrade.com/order-flow/

        
        Parameters
        ----------
        `status` : list | str = "ALL"
            The status of orders to filter by, may be individual or list:

            "ALL"               All of the below (Default).
            "Received"	        Initial order state.
            "Routed"	        Order is on its way out of tastytrade's system.
            "In Flight"	        Order is en route to the exchange.
            "Live"	            Order is live at the exchange.
            "Cancel Requested"	Customer has requested to cancel the order. Awaiting a 'cancelled' message from the exchange.
            "Replace Requested"	Customer has submitted a replacement order. This order is awaiting a 'cancelled' message from the exchange.
            "Contingent"	    This means the order is awaiting a status update of a related order. This pertains to replacement orders and complex OTOCO orders.
            "Filled"	        Order has been fully filled.
            "Cancelled"	        Order is cancelled.
            "Expired"	        Order has expired. Usually applies to an option order.
            "Rejected"	        Order has been rejected by either tastytrade or the exchange.
            "Removed"	        Administrator has manually removed this order from customer account.
            "Partially"         Removed	Administrator has manually removed part of this order from customer account.

        `fromTime` : datetime.datetime | None = None
            Start range for order filtering. (Default=None, defaults to 24h ago)

            *note* will be converted to UTC
        
        `toTime` : datetime.datetime | None = None
            End range for order filtering. (Default=None, defaults to current UTC time)

            *note* will be converted to UTC
            
        
        Returns
        -------
        `dict`
            All filtered orders, keyed by various routing statuses.
        
        '''

        target = "/accounts/{}/orders".format(self.accountID)

        # requests Futures AND Future Options
        params = {"underlying-instrument-type" : "Future",
                  "per-page" : 100}

        # only filter as needed
        if status != "ALL":
            
            # convert to list for parameter parsing
            if isinstance(status, str):
                params["status[]"] = [status]
            else:
                params["status[]"] = status

        # set default from-time (24h ago)
        if isinstance(fromTime, NoneType):
            yesterday = datetime.datetime.now(tz=datetime.UTC) - datetime.timedelta(days=1)
            params["start-at"] = yesterday.isoformat().split(".")[0]
        
        # otherwise, set user specified from-time
        else:
            params["start-at"] = fromTime.astimezone(datetime.UTC).isoformat().split(".")[0]

        # set to-time as needed
        if isinstance(toTime, datetime.datetime):
            params["end-at"] = toTime.astimezone(datetime.UTC).isoformat().split(".")[0]

        resp = self.request(method="GET", url=target, params=params).json()
        
        orders = resp["data"]["items"]

        # sort orders by routing status
        sortedOrders = {}
        for order in orders:
            if order["status"] not in sortedOrders.keys():
                sortedOrders[order["status"]] = [order]
            else:
                sortedOrders[order["status"]].append(order)

        return sortedOrders

    def status(self, id : int) -> dict:
        '''
        
        Retrieves an individual order's details.


        Parameters
        ----------
        `id` : int
            The order's unique ID.

        Returns
        -------
        `dict`
            The individual order's details.
        
        '''

        target = "/accounts/{}/orders/{}".format(self.accountID, id)
        
        resp = self.request(method="GET", url=target).json()

        return resp["data"]

    def cancel(self, id : int) -> dict:
        '''
        
        Cancels an individual order.


        Parameters
        ----------
        `id` : int
            The order's unique ID.

        Returns
        -------
        `dict`
            The order's cancellation confirmation.
        
        '''

        target = "/accounts/{}/orders/{}".format(self.accountID, id)
        
        resp = self.request(method="DELETE", url=target).json()

        return resp["data"]



























