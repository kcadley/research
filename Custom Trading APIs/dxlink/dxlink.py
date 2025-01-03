from __future__ import annotations
import asyncio
import threading
from websockets import client
import json
import numpy as np
import pandas as pd
import datetime
import concurrent
from types import NoneType
import sys
sys.path.append("<path here>")
import markethours

class Stream():
    '''
    
    A class used to encapsulate instrument quote streams - a `Stream()` instance 
    points directly to the DXLink virtual channel used to begin the stream feed,
    allowing isolated streaming management.

    
    Attributes
    ----------
    `isAlive` : bool
        Whether the channel streaming data is still open.
    
    `_link` : DXLink
        The `DXLink()` object hosting the channel (used to start the stream).
    
    `_stream` : dict
        The streamed content.
    
    `_closeRequest` : str
        A prefabricated "close request" - triggered on `self.close()`, the request
        tells DXLink to close the virtual channel (and stop sending streamed content).

    Methods
    -------    
    `quote()` -> dict
        Retrieves the stream's most recent quote(s).
    
    `_close()` -> None
        Asynchronously closes the stream's connection.

    `close()` -> None
        Wrapper for async function `_close()`, closes the stream's connection.
        
    '''

    def __init__(self, 
                 dxInstance : DXLink, 
                 channel : int, 
                 closeRequest : str) -> None:
        '''
        
        Initializes the `Stream()` instance.

        
        Parameters
        ----------
        `dxInstance` : DXLink
            The `DXLink()` object hosting the stream (if multiple, the one used 
            to start the stream).
        
        `channel` : int
            The virtual channel number used for the stream.
        
        `closeRequest` : str
            A prefabricated "close request" for the channel.

        Returns
        -------
        `None`
        
        '''

        self.isAlive = True
        self._link = dxInstance
        self._stream = dxInstance._streams[channel]
        self._closeRequest = closeRequest
        
        return None

    def quote(self, symbol : str | None = None) -> None:
        '''
        
        Retrieves the stream's most recent quote(s).

        
        Parameters
        ----------
        `symbol` : str | None = None
            The instrument to retrieve the most recent quote for. If "None"
            (default), returns all symbol quotes within the stream.

        Returns
        -------
        `None`
        
        '''
        
        if isinstance(symbol, NoneType):
            return self._stream
        else:
            return self._stream[symbol]
    
    async def _close(self) -> None:
        '''

        Asynchronously closes the stream's connection.

        
        Parameters
        ----------
        None

        Returns
        -------
        `None`
        
        '''
        # send request, ignore response
        asyncio.create_task(self._link._quick_send(self._closeRequest))

        return None

    def close(self) -> None:
        '''
        
        Wrapper for async function `_close()`, closes the stream's channel 
        (prevents any additional streamed content).

        
        Parameters
        ----------
        None

        Returns
        -------
        `None`
        
        '''
        # close channel
        asyncio.run_coroutine_threadsafe(self._close(), self._link._loop)

        self.isAlive = False

        return None
    
class DXLink():
    '''
    
    A network class designed to retrieve market data from DXLink. Built
    on top of `websockets`, utilizes `asyncio` to establish a main websocket
    connection to DXLink, then creates isolated "channels"
    within the connection to request / receive market data over. Must be
    "restarted" once every 24 hours with a new authentication token, as per
    DXLink's specification (this is the same with TastyTrade).

    
    Attributes
    ----------
    `cme` : CMEFX
        An object used to determine if CME is actively trading currency 
        derivatives. Dictates whether live or last stream quotes should be used.

    Methods
    -------
    `get_candles()` : func
        Retreives candlestick data for a given symbol, candlestick span, and
        historic startpoint.
    
    `get_quotes()` : func
        Asynchronously begins a data stream, continuously receiving an 
        instrument's most recent "quote" details. 

    `close()` : func
        Closes the DXLink websocket connection, cancels all pending
        asyncio tasks, stops the asyncio event loop, then finally `*.joins()` 
        the threading running the asyncio loop.

    '''

    def __init__(self, auth : str | None = None, afterHours : bool = False) -> None:
        '''
        
        Initializes the DXLink object.

        
        Parameters
        ----------
        `auth` : str | None = None
            The DXLink authentication token provided by TastyTrade, given 
            hitting TastyTrade's "/api-quote-tokens" endpoint. If "None" (default),
            uses cached file location for token.

        `afterHours` : bool = False
            If CME is technically open for trading, but the live market data is 
            still stale, sets stream to "last trade" instead (as if market is 
            closed).
        
        Returns
        -------
        `object` : DXLink
            The DXLink object.
        
        '''

        # CME hours
        self.cme = markethours.CMEFX()
        self.afterHours = afterHours

        # content containers
        self._channelLock = threading.Lock()
        self._streams = {0 : []}
        self._candles = {0 : []}

        # create an event loop (avoiding asyncio.run(), etc)
        # begins indefinite event loop - the loop is running WITHIN another
        # thread, must be accessed using `asyncio.run_coroutine_threadsafe`
        # from now on (creates concurrent tasks)
        self._loop = asyncio.new_event_loop()
        self._eventLoop = threading.Thread(target=self._loop.run_forever)
        self._eventLoop.daemon = True
        self._eventLoop.start()
    
        # create web socket (don't fully begin loop yet - need socket first)
        # `client.connect` is an awaitable, that's the only reason we're doing this...
        future = asyncio.run_coroutine_threadsafe(self._get_ws("wss://tasty-openapi-ws.dxfeed.com/realtime"), self._loop)
        self._ws = future.result()

        # run receiver in background
        asyncio.run_coroutine_threadsafe(self._receive(), self._loop)

        # use cached token if none provided
        if isinstance(auth, NoneType):
            with open("<key here>") as file:
                auth = file.read()

        # initial auth
        future = asyncio.run_coroutine_threadsafe(self._auth(auth), self._loop)
        complete = future.result()   # wait for setup and authentication

        # run keep-alives in background
        asyncio.run_coroutine_threadsafe(self._keepalive(), self._loop)
        
        return None

    async def _get_ws(self, uri) -> client.WebSocketClientProtocol:
        '''

        Forms the main websocket connection with DXLink. Requires `await` for 
        results (ie this is a wrapper function to be executed outside of 
        asyncio.run() environment)

        
        Parameters
        ----------
        `uri` : str
            DXLink's market data uri.
            (typically "wss://tasty-openapi-ws.dxfeed.com/realtime")

        Returns
        -------
        `client.WebSocketClientProtocol` : obj
            The main websocket connecting us to DXLink.

        '''
        
        # sending "KEEP-ALIVE"(s) independently, ignore ping settings
        return await client.connect(uri, ping_timeout=None, ping_interval=None)

    async def _auth(self, auth : str) -> None:
        '''
        
        Configures initial websocket settings once connected to DXLink, then 
        authenticates (seems out of order, but those are their specifications).
        
        
        Parameters
        ----------
        `auth` : str
            The DXLink authentication token provided by TastyTrade, given 
            hitting TastyTrade's "/api-quote-tokens" endpoint.

        Returns
        -------
        `None`
        
        '''
        
        # configure websocket connection
        setupPayload = json.dumps({"type": "SETUP",
                                   "channel": 0,
                                   "keepaliveTimeout": 300,
                                   "acceptKeepaliveTimeout": 300,
                                   "version": "0.1-js/1.0.0"})
        await self._ws.send(setupPayload)

        # auth with dxlink
        authPayload = json.dumps({"type": "AUTH",
                                  "channel": 0,
                                  "token": auth})
        await self._ws.send(authPayload)

        return None

    async def _process(self, message : str) -> None:
        '''
        
        Converts any DXLink response into a dictionary object, then 
        places it in the appropriate channel storage location (`self._channels[X]`)

        
        Parameters
        ----------
        `message` : str
            The DXLink message

        Return
        ------
        `None`
        
        '''
        message = json.loads(message)
        
        if (message["channel"] in self._streams.keys()) and (message["type"] == "FEED_DATA"):
            
            # timestamp message arrival
            stamp = datetime.datetime.now(tz=datetime.UTC)

            # sort by market status (avoids calling cme.is_trading(), datetime calculations expensive)
            if len(message["data"][1]) > 5:
                if isinstance(message["data"][1][5], str) and (message["data"][1][5] != "NaN"):
                    marketOpen = True
                else:
                    marketOpen = False
            else:
                if len(message["data"][1]) % 2 == 1:
                    marketOpen = True
                else:
                    marketOpen = False

            # if market open, live quote message: [symbol, bid, bidSize, ask, askSize] (odd number)
            if marketOpen:

                # for each symbol in the stream, record the current bid, ask and respective sizes
                for i in range(0, len(message["data"][1]), 5):
                    
                        self._streams[message["channel"]][message["data"][1][i]] = {"eventTime" : stamp,
                                                                                    "bidPrice" : message["data"][1][i+1],
                                                                                    "bidSize" : message["data"][1][i+2],
                                                                                    "askPrice" : message["data"][1][i+3],
                                                                                    "askSize" : message["data"][1][i+4]}

            # market closed, record last trades: [symbol, lastPrice, dailyVolume, dailyTurnover] (even number)
            else:
             
                # for each symbol in the stream, record the prior session's closing details
                for i in range(0, len(message["data"][1]), 4):
                    self._streams[message["channel"]][message["data"][1][i]] = {"eventTime" : stamp,
                                                                                "bidPrice" : message["data"][1][i+1],
                                                                                "askPrice" : message["data"][1][i+1],
                                                                                "volume" : message["data"][1][i+2],
                                                                                "turnover" : message["data"][1][i+3]}

        elif (message["channel"] in self._candles.keys()) and (message["type"] == "FEED_DATA"):

            # timestamp message arrival
            stamp = datetime.datetime.now(tz=datetime.UTC)

            # only one candle ID per candle channel
            candleID = list(self._candles[message["channel"]].keys())[0]
            for i in range(0, len(message["data"][1]), 5):
                
                # only accept relevant data (dxlink starts to stream live after sending historic)
                # greater than or equal to "from time", ealier than or equal to "request time"
                if (candleID[2] <= message["data"][1][i]) and (message["data"][1][i] <= candleID[3]):
                    
                    # appends all payloads to single candle list even if received in different messages
                    entry = message["data"][1][i:i+5]
                    self._candles[message["channel"]][candleID].append(entry)

                    # if final candle, convert to numpy - type() will be used to identify when ready to convert to dataframe
                    if candleID[2] == message["data"][1][i]:
                        self._candles[message["channel"]][candleID] = np.array(self._candles[message["channel"]][candleID]).astype(float)

        return None

    async def _receive(self) -> None:
        '''
        
        Listens indefinitely for any messages from DXLink, passing them
        to `self._process` as they come in.
        
        Parameters
        ----------
        None

        Return
        ------
        `None`
        
        '''

        async for message in self._ws:
            # for each message, process it in background (allows multiple
            # message to be processed as they come in)
            asyncio.create_task(self._process(message))
        
        return None

    async def _keepalive(self) -> None:
        '''
        
        Indefinitely sends periodic "keep-alive" messages to DXLink every 10
        seconds (a DXLink specifications, as opposed to regular "pings").
        Cleans up prior "Keep-Alives" in memory.
        
        Parameters
        ----------
        None

        Return
        ------
        `None`
        
        '''
        
        # keep-alive message
        keepAliveMsg = json.dumps({"type": "KEEPALIVE", "channel": 0})

        while True:
            
            # send keep-alive as-per DXLink docs (don't wait for response)
            asyncio.create_task(self._quick_send(keepAliveMsg))

            # wait to send next round of keep-alives
            await asyncio.sleep(15)

        return None

    async def _quick_send(self, messages : str | list[str]) -> None:
        '''
        
        Sends a message(s) to DXLink with no regard for task completion - ie
        send it and forget it:

        Parent Function:
        `asyncio.run_coroutine_threadsafe(self._quick_send("msg"), self._loop)`
        

        Parameters
        ----------
        `messages` : str | list[str]
            A single string message or list of single string messages to
            send.

        Return
        ------
        `None`
        
        '''

        if isinstance(messages, str):
            asyncio.create_task(self._ws.send(messages))

        else:
            for message in messages:
                asyncio.create_task(self._ws.send(message))

        return None

    async def _sync_send(self, messages : str | list[str]) -> None:
        '''
        
        Sends a message(s) to DXLink with but await task completion - ie
        send it and confirm sent:

        Parent Function:
        `task = asyncio.run_coroutine_threadsafe(self._sync_send("msg"), self._loop)`
        `complete = task.result()`      # equivalent to `await`
        
        
        Parameters
        ----------
        `messages` : str | list[str]
            A single string message or list of single string messages to
            send.

        Return
        ------
        `None`
        
        '''

        if isinstance(messages, str):
            await self._ws.send(messages)
        
        else:
            async with asyncio.TaskGroup() as tg:
                for message in messages:
                    tg.create_task(self._ws.send(message))

        return None

    async def _request_channel(self, newChannel : int | list[int]) -> None:
        '''
        
        Requests a new channel(s) from DXLink.

        
        Parameters
        ----------
        `newChannel` : int | list[str]
            The new channel(s) to request. 

            *note* If only a single integer is passed, a channel is set up
            for quote streaming. If a list of integers is passed, multiple
            channels are set up to receive historic candlestick data.

        Return
        ------
        `None`
        
        '''

        # starting a stream
        if isinstance(newChannel, int):

            # set up channel
            channelRequest = json.dumps({"type": "CHANNEL_REQUEST",
                                         "channel": newChannel,
                                         "service": "FEED",
                                         "parameters": {"contract": "AUTO"}})

            # wait until channel request complete
            await self._sync_send(channelRequest)

            # configure feed according to data availability
            if self.cme.is_trading() and (not self.afterHours):
                    
                # configure feed for quote streaming
                feedSetup = json.dumps({"type": "FEED_SETUP",
                                        "channel": newChannel,
                                        "acceptAggregationPeriod": 1,
                                        "acceptDataFormat": "COMPACT",
                                        "acceptEventFields": {"Quote": ["eventSymbol",
                                                                        "bidPrice",
                                                                        "bidSize",
                                                                        "askPrice",
                                                                        "askSize"]}})
            else:
                # configure feed for last traded quote / daily volume / daily turnover during open hours
                feedSetup = json.dumps({"type": "FEED_SETUP",
                                        "channel": newChannel,
                                        "acceptAggregationPeriod": 1,
                                        "acceptDataFormat": "COMPACT",
                                        "acceptEventFields": {"Trade" : ["eventSymbol", 
                                                                         "price", 
                                                                         "dayVolume",
                                                                         "dayTurnover"]}})

            # wait until feed configuration complete
            await self._sync_send(feedSetup)

        # requesting candlestick data
        else:

            # set up channels
            channelRequests = []
            for i in newChannel:
                channelRequest = json.dumps({"type": "CHANNEL_REQUEST",
                                             "channel": i,
                                             "service": "FEED",
                                             "parameters": {"contract": "AUTO"}})
                channelRequests.append(channelRequest)

            # wait until channel requests are complete
            async with asyncio.TaskGroup() as tg:
                for channelRequest in channelRequests:
                    tg.create_task(self._ws.send(channelRequest))

            # configure feeds for candlestick data
            feedSetups = []
            for i in newChannel:
                feedSetup = json.dumps({"type": "FEED_SETUP",
                                        "channel": i,
                                        "acceptAggregationPeriod": 1,
                                        "acceptDataFormat": "COMPACT",
                                        "acceptEventFields": {"Candle": ["time",
                                                                         "open", 
                                                                         "high", 
                                                                         "low", 
                                                                         "close",
                                                                         "impVolatility"]}})
                feedSetups.append(feedSetup)

            # wait until feed configurations are complete
            async with asyncio.TaskGroup() as tg:
                for feedSetup in feedSetups:
                    tg.create_task(self._ws.send(feedSetup))

        return None

    async def _process_candles(self, newChannels : list[int]) -> pd.DataFrame:
        '''

        Parses multiple channels (each with datetime aligned candlestick data),
        extracting the historic data and converting it to an aggregated pandas 
        dataframe. Used to combine a triple channel request - mark, bid, and ask
        - into a single pandas response.
        
        
        Parameters
        ----------
        `channel` : list[int]
            The channels to extract and combine data from.

        Return
        ------
        `pd.DataFrame`
            An instruments aggregate candlestick data ("bid", "mark", and "ask")
        
        '''

        collected = {}
        timeout = datetime.datetime.now()

        # key value of channel and candle IDs (used for iterating)
        candleIDs = {i : list(self._candles[i].keys())[0] for i in newChannels}

        counter = 0
        while counter < 3:

            # async while loop nuance
            await asyncio.sleep(0)

            for channel, candleID in candleIDs.items():

                # if numpy array, all frames have been received
                if isinstance(self._candles[channel][candleID], np.ndarray) and (candleID not in collected.keys()):
                    collected[candleID] = self._candles[channel][candleID]
                    counter += 1

                # 5 second timeout
                elif (datetime.datetime.now() - timeout) > datetime.timedelta(seconds=5):
                    
                    # load any data received
                    for chan, candID in candleIDs.items():
                        
                        # convert and record any unprocessed candles
                        if (candID not in collected.keys()) and self._candles[chan][candID]:
                            collected[candID] = np.array(self._candles[chan][candID]).astype(float)

                    # break out of for- and while- loops
                    counter = 3
                    break

        # convert to pandas
        candles = None

        for key, val in collected.items():
            if isinstance(candles, NoneType):
                columns = pd.MultiIndex.from_product([[key[1]], ["open", "high", "low", "close"]])
                index = [datetime.datetime.fromtimestamp(int(stamp), tz=datetime.UTC) for stamp in val[:, 0] / 1000]
                candles = pd.DataFrame(val[:, 1:].astype(float), index=index, columns=columns)
            
            else:
                columns = pd.MultiIndex.from_product([[key[1]], ["open", "high", "low", "close"]])
                index = [datetime.datetime.fromtimestamp(int(stamp), tz=datetime.UTC) for stamp in val[:, 0] / 1000]
                additionals = pd.DataFrame(val[:, 1:].astype(float), index=index, columns=columns)
                candles = candles.join(additionals, how="outer")
        
        candles.index.name = "datetime"
        
        # flip such that ordered from latest to earliest
        candles = candles[::-1]

        # often times, the "from time" requested will not align with a
        # candle period - this results in a oneliner of NAs. Clean this up.
        if all(candles.iloc[0].isna()):
            candles.drop(candles.index[0], inplace=True)
        if all(candles.iloc[-1].isna()):
            candles.drop(candles.index[-1], inplace=True)

        return candles

    async def _get_candles(self, symbol : str, span : str, fromTime : datetime.datetime, regular : bool) -> pd.DataFrame:
        '''
        
        Asynchronously retreives candlestick data for a given symbol, 
        candlestick span, and historic startpoint.
        
        
        Parameters
        ----------
        `symbol` : str
            The instrument symbol to collect data on.
        
        `span` : str
            The candlestick span used to aggregate individual quotes:
                <#>s - second
                <#>m - minute
                <#>h - hour
                <#>d - day
                <#>w - week
                <#>mo - month
        
        `fromTime` : datetime.datetime
            The starting point to begin data collection on - this may or
            may not be inclusive. If `fromTime` aligns perfectly with a
            `span` increment, the `fromTime` candle will be included - otherwise,
            `fromTime` will be skipped, and the earliest candle retrieved will
            be the first period after the `fromTime` that aligns with a `span`
            increment.

        `regular` : bool
            Whether to collect candles from within exclusively "regular" trading 
            hours.

        Returns
        -------
        `pd.DataFrame`
            The instrument's historic candlestick data.
        
        '''

        # convert time to epoch (with trailing 000s as per DXLink's specifications)
        fromTimeEpoch = int(fromTime.timestamp() * 1000)
        requestTimeEpoch = int(datetime.datetime.now(datetime.UTC).timestamp() * 1000)   # only available up until "now"

        # get next odd channel available, use lock to make sure no other
        # threads request same channels
        with self._channelLock:

            lastChannel = max(*self._candles.keys(), *self._streams.keys())
            
            # dxlink requires odd channels
            if lastChannel % 2 == 0:
                startChannel = lastChannel + 1
            else:
                startChannel = lastChannel + 2

            # set alternating channels for mark, bid, and ask
            # why alternating? unclear - suspect server side reserves 
            # nearby channels for comms back to us
            newChannels = [startChannel, startChannel + 2, startChannel + 4]
            
            # create containers to receive channel feeds
            prices = ["bid", "mark", "ask"]
            i = 0
            for channel in newChannels:
                self._candles[channel] = {(symbol, prices[i], fromTimeEpoch, requestTimeEpoch) : []}
                i += 1

        # request 3 new channels
        complete = await self._request_channel(newChannels)

        # hold request payloads
        candleRequests = []
        closeRequests = []

        # `i` for quotes, `j` for channels
        i = 0
        # create request to be sent over each channel
        for j in newChannels:

            # "tho=true", regular hours only (do not included "a=s" for alignments, makes no difference in actual data, only mixes up DTS)
            if regular:
                target = "{}".format(symbol) + "{=" + "{}".format(span) + ",price={},tho=true".format(prices[i]) + "}"
            else:
                target = "{}".format(symbol) + "{=" + "{}".format(span) + ",price={}".format(prices[i]) + "}"
            
            candle = {"type" : "Candle", 
                      "symbol" : target, 
                      "fromTime": fromTimeEpoch}
            
            candleRequest = json.dumps({"type": "FEED_SUBSCRIPTION",
                                        "channel": j,
                                        "add": [candle]})
            
            closeRequest = json.dumps({"type": "CHANNEL_CANCEL",
                                       "channel": j})
            
            candleRequests.append(candleRequest)
            closeRequests.append(closeRequest)

            # increment `i` separately
            i += 1

        # request candles
        complete = await self._sync_send(candleRequests)

        # process candles
        candles = await self._process_candles(newChannels)

        # close channels
        asyncio.create_task(self._quick_send(closeRequests))

        # can use up to channel number 2147483647 - this means can request about
        # (4142 * 3) new channels every second... instead of worrying about
        # race conditions or stray data with re-use, consider each channel 
        # a "one-time-use", and simply flushing data afterwards to preserve memory
        for channel in newChannels:
            self._candles[channel] = []

        if candles.index[0] > candles.index[-1]:
            candles = candles[::-1]

        # occassionaly will struggle with one of bid, ask, or mark:
        found = candles.columns.get_level_values(0)
        if ("bid" not in found)  and ("ask" in found) and ("mark" in found):
            candles = candles.join(pd.concat({"bid" : candles["mark"] * 2 - candles["ask"]}, axis=1))

        elif ("ask" not in found) and ("bid" in found) and ("mark" in found):
            candles = candles.join(pd.concat({"ask" : candles["mark"] * 2 - candles["bid"]}, axis=1))

        elif ("mark" not in found) and ("ask" in found) and ("bid" in found):
            candles = candles.join(pd.concat({"mark" : (candles["bid"] + candles["ask"]) / 2}, axis=1))

        ### daily  adjustments, DXLink handles timezones poorly:
        # adjust index alignment to standard trading hours (0930 CST)
        if "d" in span:
            if regular:
                candles.index = candles.index + datetime.timedelta(hours=8, minutes=30)
            
            # otherwise extended hours, adjust back to midnight UTC
            else:
                newIndex = []
                for i in candles.index:
                    newIndex.append(i.replace(hour=0))
                candles.index = newIndex

        return candles[["bid", "ask", "mark"]]
    
    def candles(self, symbol : str, span : str, fromTime : datetime.datetime, regular : bool) -> concurrent.futures.Future:
        '''
        
        Retreives candlestick data for a given symbol, candlestick span, and
        historic startpoint. Results are a `concurrent.futures.Future` object, which will
        will return a `pd.DataFrame` of candles whenever `*.result()` is
        called (effectively blocking if the candles have yet to be retrieved).

        *Note* DXlink considers the extended open as 0000 - 0000 UTC, whereas 
        "regular" trading hours are 0930-1600 EST (NOT CST)
        
        
        Parameters
        ----------
        `symbol` : str
            The instrument symbol to collect data on.
        
        `span` : str
            The candlestick span used to aggregate individual quotes:
                <#>s - second
                <#>m - minute
                <#>h - hour
                <#>d - day
                <#>w - week
                <#>mo - month
        
        `fromTime` : datetime.datetime
            The starting point to begin data collection on - this may or
            may not be inclusive. If `fromTime` aligns perfectly with a
            `span` increment, the `fromTime` candle will be included - otherwise,
            `fromTime` will be skipped, and the earliest candle retrieved will
            be the first period after the `fromTime` that aligns with a `span`
            increment.

        `regular` : bool
            Whether to collect candles from within exclusively "regular" trading 
            hours.

        Returns
        -------
       `concurrent.futures.Future` : obj
            The instrument's historic candlestick data represented as an 
            `Future` object. Access results via `*.result()`.
        
        '''

        return asyncio.run_coroutine_threadsafe(self._get_candles(symbol, span, fromTime, regular), self._loop)
 
    async def _start_stream(self, symbol : str | list[str]) -> Stream:
        '''
        
        Starts a data stream for the given symbol(s).


        Parameters
        ----------
        `symbol` : str | list[str]
            The symbol(s) to stream data for.

        Returns
        -------
        `Stream` : obj
            A stream object directly linked its corresponding DXLink feed.
        
        '''
        
        # utilize lock to prevent duplicate channel requests
        with self._channelLock:

            # get next available channel
            lastChannel = max(*self._candles.keys(), *self._streams.keys())
            
            # dxlink requires odd channels
            if lastChannel % 2 == 0:
                newChannel = lastChannel + 1
            else:
                newChannel = lastChannel + 2

            # create container to receive channel feed
            self._streams[newChannel] = {}

        # request new channel
        await self._request_channel(newChannel)

        # create streaming request according to data availability
        if self.cme.is_trading() and (not self.afterHours):
                
            # create streaming request for live quotes
            if isinstance(symbol, list):
                streamRequest = [{"type" : "Quote", "symbol" : s} for s in symbol]

            elif isinstance(symbol, str):
                streamRequest = [{"type" : "Quote",
                                "symbol" : symbol}]
            
        else:
            # create streaming request for last traded quote / daily volume / daily turnover during open hours
            if isinstance(symbol, list):
                streamRequest = [{"type" : "Trade", "symbol" : s} for s in symbol]

            elif isinstance(symbol, str):
                streamRequest = [{"type" : "Trade",
                                "symbol" : symbol}]

        feedRequest = json.dumps({"type": "FEED_SUBSCRIPTION",
                                  "channel": newChannel,
                                  "add": streamRequest})
        
        await self._sync_send(feedRequest)


        # craft close request to be used for whenever stream is no longer needed
        closeRequest = json.dumps({"type": "CHANNEL_CANCEL",
                                   "channel": newChannel})

        # create streamer        
        stream = Stream(self, newChannel, closeRequest)

        return stream

    def stream(self, symbol : str | list[str]) -> Stream:
        '''

        Asynchronously begins a data stream, continuously receiving instrument(s) 
        live quotes. 


        Parameters
        ----------
        `symbol` : str | list[str]
            A single symbol or list of symbols using the equity, futures, or 
            option's OCC / TW symbology convention.

        Returns
        -------
        `Stream` : object
            A stream object directly linked to its corresponding DXLink stream.

        '''

        return asyncio.run_coroutine_threadsafe(self._start_stream(symbol), self._loop).result()
    
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

        # gather all tasks except this one
        tasks = [asyncio.ensure_future(task) for task in asyncio.all_tasks() if task.get_name() != "kill_stragglers"]

        # cancel all tasks
        for task in tasks:
            task.cancel()

        # wait for loop to iterate over each task (cancel() flags tasks, loop needs to see it to cancel)
        await asyncio.sleep(2)

        return None

    def close(self) -> None:
        '''
        
        Closes the DXLink websocket connection, cancels all pending
        asyncio tasks, stops the asyncio event loop, then finally `*.joins()` 
        the threading running the asyncio loop.
        

        Parameters
        ----------
        None

        Returns
        -------
        `None`
        
        '''

        # close the websocket
        future = asyncio.run_coroutine_threadsafe(self._ws.close(), self._loop)

        # cancel all remaining tasks
        future = asyncio.run_coroutine_threadsafe(self._kill_stragglers(), self._loop)
        complete = future.result()      # wait for this final task to complete

        # stop the loop, join the thread, close the loop
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._eventLoop.join()
        self._loop.close()

        return None




