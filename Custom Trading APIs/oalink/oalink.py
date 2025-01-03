from __future__ import annotations
import aiohttp
import asyncio
import threading
import datetime
import json
import copy
import pandas as pd

class Stream():
    '''
    
    A class used to encapsulate instrument quote streams - a `Stream()` instance 
    points directly to the OALink object used to begin the stream's feed.

    
    Attributes
    ----------
    `isAlive` : bool
        Whether the channel streaming data is still open.
    
    `_link` : DXLink
        The `DXLink()` object hosting the channel (used to start the stream).

    `_symbol` : dict
        The symbol used to start the stream.

    `_stream` : dict
        The streamed content.

    Methods
    -------    
    `quote()` -> dict
        Retrieves the stream's most recent quote.

    `close()` -> None
        Wrapper for async function `_close()`, closes the stream's connection.

    `_clean()` -> None
        Contiuously removes prior content from the stream - done to limit 
        excessive memory build-up when stream is run for a long period of time 
        (tokens / channels max out at 24h, regardless, but this is done for good 
        measure anyway).
    
    `_close()` -> None
        Asynchronously closes the stream's connection.
    
    '''

    def __init__(self, 
                 symbol : str,
                 OAInstance : OALink) -> None:
        '''
        
        Initializes the `Stream()` instance.

        
        Parameters
        ----------
        `symbol` : str
            The symbol used to start the stream.

        `OAInstance` : OALink
            The `OALink()` object hosting the stream (if multiple, the one used 
            to start the stream).

        Returns
        -------
        `None`
        
        '''

        self.isAlive = True
        self._link = OAInstance
        self._symbol = symbol
        self._stream = OAInstance._streams[symbol][1]

        # begin flushing memory (deletes old stream values)
        asyncio.run_coroutine_threadsafe(self._clean(), self._link._loop)
        
        return None
    
    async def _clean(self) -> None:
        '''

        Contiuously removes prior messages from the stream - this is
        done to limit excessive memory build-up when the stream is run for 
        a long period of time.

        
        Parameters
        ----------
        None

        Returns
        -------
        `None`
        
        '''
        while self.isAlive:
            
            await asyncio.sleep(0)

            # remove prior stream messages to preserve memory
            streamLen = len(self._stream)
            if streamLen > 1:
                for i in range(0, streamLen - 1):
                    _ = self._stream.pop(0)
                    del(_)
        
            # flush every 15s
            await asyncio.sleep(15)

        return None

    def quote(self, symbol : str | None = None) -> None:
        '''
        
        Retrieves the stream's most recent quote(s).

        
        Parameters
        ----------
        `symbol` : str | None = None            
            Dummy variable for alternate streaming combatability. Do not change.

        Returns
        -------
        `None`
        
        '''
        
        # current quotes
        snapshot = self._stream[-1]
        
        # format for streaming
        snapshot["bidPrice"] = snapshot["closeoutBid"]
        snapshot["askPrice"] = snapshot["closeoutAsk"]

        return snapshot

    def close(self) -> None:
        '''
        
        Closes the stream (prevents any additional streamed content).

        
        Parameters
        ----------
        None

        Returns
        -------
        `None`
        
        '''
        # close channel
        self._link._streams[self._symbol][0] = False
        
        # stop flushing memory
        self.isAlive = False
        
        return None

class OALink():
    '''
    
    A network class used to interact with OANDA. Built on top of
    `aiohttp`, utilizes `asyncio` to send / receive RESTful HTTP requests to 
    access various endpoints.

    
    Attributes
    ----------    
    `_streams` : dict
        A dictionary keyed by instrument symbol, with values (bool, list[dict]) 
        values ("buckets") that hold all quotes related to the corresponding 
        stream - buckets are periodicially flushed up until the last entry
        to preserve memory.

    `_loop` : asyncio.AbstractEventLoop
        The asyncio event loop used to queue HTTP requests.

    `_eventLoop` : threading.Thread
        The thread used to indefinitely run the asyncio event loop.

    `_sess` : aiohttp.ClientSession
        The HTTP session used to interact with OANDA endpoints.

    `_streamURL` : str
        The OANDA endpoint used to stream data.

    `_candelURL` : str
        The OANDA endpoint used to retrieve candles.
        
    `_lastLogin` : datetime.datetime
        The date and time of the session's start.

    `_account` : str
        The OANDA accountID used for queries.
        
    Methods
    -------
    `stream()` -> Stream
        Asynchronously begins a data stream, continuously receiving an 
        instrument's most recent "quote" details.

    `candles()` -> pd.DataFrame
        Asynchronously retrieves candlestick data.

    `_get_sess()` -> aiohttp.ClientSession
        Forms a persistent HTTP session to access OANDA endpoints.
    
    `_to_objects()` -> dict
        Converts eligible string values to python datatypes (does NOT throw 
        errors on any failed conversions, value will just remain a string). Used as 
        an argument for json.loads() object hook conversions: 
        json.loads(<data>, object_hook=_to_objects). Supported conversion: [int, 
        float, datetime.datetime]

    `_to_real_strings()` -> dict
        Pre-formats server requests, recursively replaces objects
        with their  string equivalents (datetime.datetime objects are formatted as 
        RCF3339 in UTC). *Note* Times will be converted to UTC prior to conversion -
        ensure timezones are properly assigned within datetime objects if operating 
        in a different timezone.

    `_to_strings()` -> dict
        Recursively replaces a dictionary's non-iterables with their string 
        equivalents. *Note* This is a simple wrapper for `_to_strings()`.

    `_start_stream()` -> None
        Starts a data stream for the given symbol and stream type.
    
    `_kill_stragglers()` -> None
        Cancels all pending asyncio tasks (except for the task that is running 
        this function).

    `close()` -> None
        Closes the DXLink websocket connection, cancels all pending
        asyncio tasks, stops the asyncio event loop, then finally `*.joins()` 
        the threading running the asyncio loop.

    '''

    def __init__(self, live : bool = False) -> None:

        # internal event loop
        self._loop = asyncio.new_event_loop()
        self._eventLoop = threading.Thread(target=self._loop.run_forever)
        self._eventLoop.daemon = True
        self._eventLoop.start()
        
        # point at correct server
        if live:
            
            with open("<key here>") as file:
                account = file.readline()
                token = file.readline()

            self._streamURL = "https://stream-fxtrade.oanda.com"
            self._candleURL = "https://api-fxtrade.oanda.com"
            
        else:

            with open("<key here>") as file:
                account = file.readline()
                token = file.readline()

            self._streamURL = "https://stream-fxpractice.oanda.com"
            self._candleURL = "https://api-fxpractice.oanda.com"

        # set mandatory headers
        baseHeaders = {"Authorization" : "Bearer {}".format(token), 
                       "Content-Type" : "application/json",
                       "AcceptDatetimeFormat" : "RFC3339"}

        future = asyncio.run_coroutine_threadsafe(self._get_sess(headers=baseHeaders), self._loop)
        self._sess = future.result()       # `await` results

        # record login
        self._lastLogin = datetime.datetime.now()

        # build stream container (stream template below)
        self._streams = {"" : [False, []]}

        # record account ID
        self._account = account

        return None
        
    async def _get_sess(self, headers) -> aiohttp.ClientSession:
        '''

        Forms a persistent HTTP session for access to Oanda endpoints.

        
        Parameters
        ----------
        `headers` : dict
            Default headers to use throughout the session.

        Returns
        -------
        aiohttp.ClientSession : object
            A persistent HTTP session that supports `asyncio` calls.

        '''

        return aiohttp.ClientSession(headers=headers)

    def _to_objects(self, iterable : dict | list) -> dict:
        '''
        
        Converts eligible string values to python datatypes (does NOT throw 
        errors on any failed conversions, value will just remain a string). Used as 
        an argument for json.loads() object hook conversions: 
        json.loads(<data>, object_hook=_to_objects). Supported conversion: [int, 
        float, datetime.datetime]
        

        Parameters
        ----------
        `iterable` : dict
            The iterable to convert.

        Returns
        -------
        `dict`
            A dictionary with all values converted to their appropriate 
            objects.
        
        '''

        # iterate over dictionaries
        if isinstance(iterable, dict):
            
            for key in iterable.keys():

                # convert strings
                if isinstance(iterable[key], str):
                    
                    # likely a float or RCF3339 time if string contains "."
                    if "." in iterable[key]:
                        # more often than not it's a float
                        try: 
                            iterable[key] = float(iterable[key])
                        except:
                            # could also be RCF3339 time
                            try:
                                iterable[key] = datetime.datetime.fromisoformat(iterable[key])
                            
                            # if neither, should remain a string
                            except:
                                pass
                    
                    # otherwise, try convert to integer
                    else:
                        try: 
                            iterable[key] = int(iterable[key])
                        except:
                            pass
                
                # recurse as needed
                elif isinstance(iterable[key], (dict, list)):
                    iterable[key] = self._to_objects(iterable[key])

        # iterate over lists
        elif isinstance(iterable, list):

            for item in iterable:

                # convert strings
                if isinstance(item, str):
                    
                    # likely a float or RCF3339 time if string contains "."
                    if "." in item:
                        # more often than not, it's a float
                        try: 
                            item = float(item)
                        except:
                            # otherwise typically RCF3339 time
                            try:
                                item = datetime.datetime.fromisoformat(item)
                            # if neither, should likely remain a string
                            except:
                                pass
                    
                    # try converting integers, as well
                    else:
                        try: 
                            item = int(item)
                        except:
                            pass
                
                # recurse as needed
                elif isinstance(item, (dict, list)):
                    item = self._to_objects(item)

        return iterable

    async def _start_stream(self, symbol : str) -> Stream:
        '''
        
        Starts a data stream for the given symbol.


        Parameters
        ----------
        `symbol` : str
            The symbol(s) to stream data for.

        Returns
        -------
        `None`
        
        '''

        # stream endpoint
        target = self._streamURL + "/v3/accounts/{}/pricing/stream".format(self._account)

        # start the stream
        async with self._sess.request(method="GET", url=target, params={"instruments" : symbol}) as resp:

            # load content as received
            async for line in resp.content:
                
                # built-in to stop stream - will be set to "False" on self.close()
                if not self._streams[symbol][0]:
                    break
                
                # otherwise, stream is live
                else:
                    quote = json.loads(line.decode(), object_hook=self._to_objects)
                    
                    if quote["type"] == "PRICE":
                        self._streams[symbol][1].append(quote)

        return None

    def stream(self, symbol : str) -> None:
        '''

        Asynchronously begins a data stream, continuously receiving the 
        instrument's live quotes. 

        
        Parameters
        ----------
        `symbol` : str
            The symbol to stream data on.

        Returns
        -------
        `Stream` : object
            A stream object directly linked to its corresponding OALink stream.

        '''

        self._streams[symbol] = [True, []]

        asyncio.run_coroutine_threadsafe(self._start_stream(symbol), self._loop)

        return Stream(symbol, self)

    def _real_to_strings(self, obj : dict) -> dict:
        '''
        
        Pre-formats server requests, recursively replaces objects
        with their  string equivalents (datetime.datetime objects are formatted as 
        RCF3339 in UTC). *Note* Times will be converted to UTC prior to conversion -
        ensure timezones are properly assigned within datetime objects if operating 
        in a different timezone.
        
        Parameters
        ----------
        `obj` : dict
            The dictionary to recurse over.

        Returns
        -------
        `dict`
            A dictionary with all eligible values (recursively) formatted as 
            strings (or None).

        '''

        # recurse down list
        if isinstance(obj, list):
            for entry in range(0, len(obj)):
                obj[entry] = self._to_strings(obj[entry])

        # recurse down dictionary
        elif isinstance(obj, dict):
            for key in obj:
                obj[key] = self._to_strings(obj[key])

        # check if object is a datetime (and convert / format if it is)
        elif isinstance(obj, datetime.datetime):
            obj = obj.astimezone(datetime.UTC).isoformat().replace("+00:00", "Z")
            if obj[-1] != "Z":
                obj = obj + "Z"

        # otherwise, check if object is a string (and convert if not)
        elif not isinstance(obj, str):
            obj = str(obj)

        return obj

    def _to_strings(self, dictionary : dict) -> dict:
        '''

        Recursively replaces a dictionary's non-iterables with their string 
        equivalents. *Note* This is a simple wrapper for `_to_strings()`.

        Parameters
        ----------
        `dictionary` : dict
            The dictionary to recurse over.

        Returns
        -------
        `dict`
            A dictionary with all non-iterables converted to strings.

        '''

        newDict = copy.deepcopy(dictionary)

        return self._real_to_strings(newDict)

    def candles(self,
                    pair : str,
                    price : str = "M",
                    granularity : str = "D",
                    count : int | str | None = None,
                    fromTime : datetime.datetime | str | None = None,
                    toTime : datetime.datetime | str | None = None,
                    smooth : bool = False,
                    includeFirst : bool | None = None,
                    dailyAlignment : int | str = 17,
                    alignmentTimezone : str = "America/New_York",
                    weeklyAlignment : str = "Friday") -> pd.DataFrame:
        ''' 
        
        Asynchronously retrieves candlestick data.
        

        Parameters
        ----------
        `pair` : str
            The currency pair to request candles for.

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
                "Monday"	: Monday
                "Tuesday"	: Tuesday
                "Wednesday"	: Wednesday
                "Thursday"	: Thursday
                "Friday"	: Friday
                "Saturday"	: Saturday
                "Sunday"	: Sunday
                
        Returns
        -------
        `pandas.DataFrame`
            The requested candles.
        
        '''

        # build endpoint
        target = self._candleURL + "/v3/instruments/{}/candles".format(pair)

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
        
        # clear out None(s) (aiohttp library does not handle these in the same way as requests library does)
        params = {k : v for k, v in params.items() if v is not None}

        resp = asyncio.run_coroutine_threadsafe(self._sess.request(method="GET", url=target, params=self._to_strings(params)), loop=self._loop)
        candlesResponse = resp.result()

        try:
            candlesResponse.raise_for_status()

            # work around for object_hook support: https://github.com/aio-libs/aiohttp/issues/3667
            candles = asyncio.run_coroutine_threadsafe(candlesResponse.json(loads=json.JSONDecoder(object_hook=self._to_objects).decode), loop=self._loop).result()

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

        except Exception as e:
            dfQuotes = False

        return dfQuotes

    async def _kill_stragglers(self) -> None:
        '''
        
        Cancels all pending asyncio tasks (except for the task that is running 
        this function).


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
        
        Closes the HTTPS session with OANDA, cancels all pending asyncio 
        tasks, stops the asyncio event loop, then finally `*.joins()` the 
        threading running the asyncio loop.
        

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
        complete = future.result()      # wait for this final task to complete

        # stop the loop, join the thread, close the loop
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._eventLoop.join()
        self._loop.close()

        return None
    
