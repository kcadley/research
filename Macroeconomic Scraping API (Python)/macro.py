import pandas as pd
import yfinance
from full_fred.fred import Fred
from io import StringIO
import xml.etree.ElementTree as ET
import asyncio
import threading
import aiohttp
import datetime
from types import NoneType
import gzip
import json

class Macro:
    '''
    
    Simple wrapper for fred, yfinance, eurostat (custom), ecb (custom),
    and bis (custom). Provides a centralized interface for querying macro / 
    financial data.


    Attributes
    ----------
    None

    Methods
    -------
    `fred` -> pd.DataFrame
        Federal Reserve Economic Data (FRED) from St. Louis Fred:

        (DATABASE) https://fred.stlouisfed.org

        (API) https://github.com/7astro7/full_fred

    `eurostat` -> pd.DataFrame
        Statistics and datasets on Europe:
        
        (DATABASE) https://ec.europa.eu/eurostat/web/main/data/database

        (API) https://pypi.org/project/eurostat/

    `yf` -> pd.DataFrame
        Provides access to yahoo finance quotes and option chains:
    
        (DATABASE) https://finance.yahoo.com

        (API) https://pypi.org/project/yfinance/

    `ecb` -> pd.DataFrame
        Custom implementation of European Central Bank API, provides 
        additional access to stastics and datasets on Eurozone:

        (DATABASE) https://sdw.ecb.europa.eu/browse.do?node=9689727

        (API) https://data.ecb.europa.eu/help/api/overview
            

    `bis` -> pd.DataFrame
        Custom implementation of Bank of International Settlements API,
        profides accees to global statistics and datasets:
        
        (DATABASE) https://data.bis.org/topics/LBS/data

        (API) https://stats.bis.org/api-doc/v1/

    '''
  
    def __init__(self) -> None:

        # wrapper for fred
        self.fred = Fred("<key here>")
        self.fred.get_api_key_file()

        # wrapper for yfinance
        self.yf = yfinance

        # internal event loop
        self._loop = asyncio.new_event_loop()
        self._eventLoop = threading.Thread(target=self._loop.run_forever)
        self._eventLoop.daemon = True
        self._eventLoop.start()
        
        # configure ECB session
        baseURL = "https://data-api.ecb.europa.eu"
        baseHeaders = {"Content-Type" : "application/json",
                       "Accept" : "text/csv",
                       "AcceptDatetimeFormat" : "RFC3339"}
        future = asyncio.run_coroutine_threadsafe(self._get_sess(url=baseURL, headers=baseHeaders), self._loop)
        self._ecbSess = future.result()

        # configure BIS session
        baseURL = "https://stats.bis.org"
        baseHeaders = {"Content-Type" : "application/json",
                       "Accept" : "application/vnd.sdmx.data+csv;version=1.0.0",
                       "AcceptDatetimeFormat" : "RFC3339"}
        future = asyncio.run_coroutine_threadsafe(self._get_sess(url=baseURL, headers=baseHeaders), self._loop)
        self._bisSess = future.result()

        # configure EUROSTAT session
        baseURL = "https://ec.europa.eu"
        baseHeaders = {"Content-Type" : "application/json"}
        future = asyncio.run_coroutine_threadsafe(self._get_sess(url=baseURL, headers=baseHeaders), self._loop)
        self._eurostatSess = future.result()

        return None

    async def _get_sess(self, url, headers) -> aiohttp.ClientSession:
        '''

        Forms a persistent HTTP session for access to Oanda endpoints.

        
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

    def _ecb_request(self, **kwargs) -> dict:
        '''
        
        Asynchronously sends any general HTTP request to ECB servers.

        
        Parameters
        ----------
        `method` : str
            The HTTP method to use: ["GET", "POST", "PUT", "DELETE", "PATCH"]
        
        `url` : str
            The endpoint to hit.
        
        `params` : dict
            Key-Value pairs to be sent as parameters in the query string of the new request.
        
        `data` : dict 
            The data to send in the body of the request.

        `json` : dict 
            Any json compatible python object. 
            
            *note* `json` and `data` parameters can not be used at the same time.

        `headers` : dict
            Addtional HTTP Headers to send with the request (in addition to 
            default set for session).

        *many more options*
            https://docs.aiohttp.org/en/stable/client_reference.html

        Returns
        -------
        `str`
            The requested data.
        
        '''

        # send request
        future = asyncio.run_coroutine_threadsafe(self._ecbSess.request(**kwargs), self._loop)
        payload = future.result()

        # unpack json
        future = asyncio.run_coroutine_threadsafe(payload.text(), self._loop)
        payloadContent = future.result()

        return payloadContent

    def ecb(self,
            key : str, 
            start : datetime.datetime | None = None,
            end : datetime.datetime | None = None,
            count : int | None = None,
            verbose : bool = False,
            name : str | None = None) -> pd.DataFrame:
        '''
        
        Custom implementation of European Central Bank (ECB)'s API:

        (DATABASE) https://sdw.ecb.europa.eu/browse.do?node=9689727

        (API) https://data.ecb.europa.eu/help/api/overview


        Parameters
        ----------
        `key` : str
            The complete unique identifier of the data requested (including
            the initial class: "CLASS.X.X.X.X"). Classes can 
            be explored from the left hand column, full keys can be found 
            within each class: https://data.ecb.europa.eu/data/datasets

            Highly used keys can be used with abbreviations (case-insensitive):

            "ESTR" : daily short-term overnight rate (EST.B.EU000A2X2A25.WT)

        `start` : datetime.datetime | None = None
            The start date of the query. If "None" (default), is set to today (UTC).

        `end` : datetime.datetime | None = None
            The end date of the query. If "None" (default), is set to today (UTC).

        `count` : int | None = None
            The number of periods to request. If provided, only one of "start"
            or "end" parameters may be passed (if neither, defaults to "end").
            If "start", will fetch number of periods after "start". If "end",
            will fetch number of periods before "end".

        `verbose` : bool = False
            Whether to include "attributes", in addition to the time series and data.

        `name` : str | None = None
            An optional column name to tag the data with. Defaults to "OBS_VALUE"
            or key name if in highly-used key list (see "key" above).

        Returns
        -------
        `pd.DataFrame`
            The data in pandas DataFrame format.
        
        '''

        # conversions for highly used keys
        highlyUsed = {"ESTR" : "EST.B.EU000A2X2A25.WT"}

        if key.upper() in highlyUsed.keys():
            name = key
            key = highlyUsed[key]

        # format request
        resource, dataID = key.split(".", 1)
        target = "/service/data/{}/{}".format(resource, dataID)

        # configure parameters
        if isinstance(start, NoneType):
            start = datetime.datetime.now(tz=datetime.UTC)

        params = {"startPeriod" : start.date().isoformat(),
                  "format" : "csvdata"}

        if isinstance(end, datetime.datetime):
            params["endPeriod"] = end.date().isoformat()
        
        if isinstance(count, int):
            if isinstance(end, datetime.datetime):
                params["lastNObservations"] = count

            elif isinstance(start, datetime.datetime):
                params["firstNObservations"] = count

        if verbose:
            params["detail"] = "full"
        else:
            params["detail"] = "dataonly"

        # send request
        resp = self._ecb_request(method="GET", url=target, params=params)

        # formating
        payload = StringIO(resp)
        df = pd.read_csv(payload, sep=",", parse_dates=True).set_index("TIME_PERIOD")
        df = df[["OBS_VALUE"]]
        df.index = pd.to_datetime(df.index)
        df.index.name = "datetime"

        if name:
            df.columns = [name]

        return df

    def _bis_request(self, **kwargs) -> dict:
        '''
        
        Asynchronously sends any general HTTP request to BIS's servers.

        
        Parameters
        ----------
        `method` : str
            The HTTP method to use: ["GET", "POST", "PUT", "DELETE", "PATCH"]
        
        `url` : str
            The endpoint to hit.
        
        `params` : dict
            Key-Value pairs to be sent as parameters in the query string of the new request.
        
        `data` : dict 
            The data to send in the body of the request.

        `json` : dict 
            Any json compatible python object. 
            
            *note* `json` and `data` parameters can not be used at the same time.

        `headers` : dict
            Addtional HTTP Headers to send with the request (in addition to 
            default set for session).

        *many more options*
            https://docs.aiohttp.org/en/stable/client_reference.html

        Returns
        -------
        `str`
            The requested data.
        
        '''

        # send request
        future = asyncio.run_coroutine_threadsafe(self._bisSess.request(**kwargs), self._loop)
        payload = future.result()

        # unpack json
        future = asyncio.run_coroutine_threadsafe(payload.text(), self._loop)
        payloadContent = future.result()

        return payloadContent

    def bis(self,
            source : str,
            key : str, 
            start : datetime.datetime | None = None,
            end : datetime.datetime | None = None,
            count : int | None = None,
            verbose : bool = False,
            name : str | None = None) -> pd.DataFrame:
            '''

            Custom implementation of Bank of International Settlements (BIS) API:

            (DATABASE) https://data.bis.org/topics/LBS/data

            (API) https://stats.bis.org/api-doc/v1


            Parameters
            ----------
            `source` : str
                The original source of the data (BIS aggregates). Sources can be 
                found on the data's page in the format "XXX,XXX,XXX": "BIS,WS_EER,1.0"

            `key` : str
                The complete unique identifier of the data requested: 
                "INTERVAL.X.X.X.X". Identifiers can only be explored below. Their
                first letter is the interval of the quote (D = Daily, etc): 
                https://data.bis.org/topics/LBS/data

                Highly used keys can be used with abbreviations (case-insensitive):

            `start` : datetime.datetime | None = None
                The start date of the query. If "None" (default), is set to today (UTC).

            `end` : datetime.datetime | None = None
                The end date of the query. If "None" (default), is set to today (UTC).

            `count` : int | None = None
                The number of periods to request. If provided, only one of "start"
                or "end" parameters may be passed (if neither, defaults to "end").
                If "start", will fetch number of periods after "start". If "end",
                will fetch number of periods before "end".

            `verbose` : bool = False
                Whether to include "attributes", in addition to the time series and data.

            `name` : str = None
                An optional column name to tag the data with. Defaults to "OBS_VALUE"
                or key name if in highly-used key list (see "key" above).

            Returns
            -------
            `pd.DataFrame`
                The data in pandas DataFrame format.
            
            '''

            # conversions for highly used keys
            highlyUsed = {}

            if key.upper() in highlyUsed.keys():
                name = key
                key = highlyUsed[key]

            # format request
            target = "/api/v1/data/{}/{}/all".format(source, key)

            # configure parameters
            if isinstance(start, NoneType):
                start = datetime.datetime.now(tz=datetime.UTC)

            params = {"startPeriod" : start.date().isoformat()}

            if isinstance(end, datetime.datetime):
                params["endPeriod"] = end.date().isoformat()
            
            if isinstance(count, int):
                if isinstance(end, datetime.datetime):
                    params["lastNObservations"] = count

                elif isinstance(start, datetime.datetime):
                    params["firstNObservations"] = count

            if verbose:
                params["detail"] = "full"
            else:
                params["detail"] = "dataonly"

            # send request
            resp = self._bis_request(method="GET", url=target, params=params)
    
            # formating
            payload = StringIO(resp)
            df = pd.read_csv(payload, sep=",", parse_dates=True).set_index("TIME_PERIOD")
            df = df[["OBS_VALUE"]]
            df.index = pd.to_datetime(df.index)
            df.index.name = "datetime"

            if name:
                df.columns = [name]

            return df

    def _eurostat_request(self, **kwargs) -> dict:
        '''
        
        Asynchronously sends any general HTTP request to EUROSTAT servers.

        
        Parameters
        ----------
        `method` : str
            The HTTP method to use: ["GET", "POST", "PUT", "DELETE", "PATCH"]
        
        `url` : str
            The endpoint to hit.
        
        `params` : dict
            Key-Value pairs to be sent as parameters in the query string of the new request.
        
        `data` : dict 
            The data to send in the body of the request.

        `json` : dict 
            Any json compatible python object. 
            
            *note* `json` and `data` parameters can not be used at the same time.

        `headers` : dict
            Addtional HTTP Headers to send with the request (in addition to 
            default set for session).

        *many more options*
            https://docs.aiohttp.org/en/stable/client_reference.html

        Returns
        -------
        `str`
            The requested data.
        
        '''

        # send request
        future = asyncio.run_coroutine_threadsafe(self._eurostatSess.request(**kwargs), self._loop)
        payload = future.result()

        # unpack payload
        future = asyncio.run_coroutine_threadsafe(payload.read(), self._loop)
        payloadContent = gzip.decompress(future.result())

        # requested database contents
        if payload.content_type == "application/vnd.sdmx.data+csv":
            csvStr = StringIO(str(payloadContent, "utf-8"))
            df = pd.read_csv(csvStr, sep=",")
            df = df.drop(columns=["STRUCTURE", "STRUCTURE_ID", "OBS_FLAG"]).sort_values("TIME_PERIOD", ascending=True)

        # requested database filtering options
        elif payload.content_type == "application/vnd.sdmx.structure+xml":
            
            # convert for XML parsing
            data_xml = StringIO(str(payloadContent, "utf-8"))
            xmlparse = ET.parse(data_xml)
            root = xmlparse.getroot()

            # create container for dataset filter options, format namespace string for following loop
            options = {}
            ns = root.tag.split("Structure")[0].replace("message", "structure")
            
            # loop over XML for Key-Value pairs (filter options)
            for child in root.iter(ns + "KeyValue"):
                
                # create option filter entry
                key = "c[{}]".format(child.attrib["id"])
                options[key] = []

                # if time period option filter, only take first and last entries
                if child.attrib["id"] == "TIME_PERIOD":
                    
                    firstDateFound = False  # flag

                    for value in child:
                        val = value.text
                        if not firstDateFound:
                            options[key].append(val) # first datetime
                            firstDateFound = True # flag - iterates until last datetime from here

                    options[key].append(val) # set last datetime

                # record all other option values
                else:
                    for value in child:
                        options[key].append(value.text)

            # "options" is actually a dict, assigning to "df" for "return df" simplicity
            df = options

        # requested eurostat table of contents
        elif payload.content_type == "application/json":
            
            # load data to dict
            payloadContent = json.loads(payloadContent)
            
            # iterate over entries, record the unique code ("id"), the last entry, and dataset description ("label")
            rows = []
            for item in payloadContent["link"]["item"]:
                code = item["extension"]["id"]
                label = item["label"]
                latest = [i["date"] for i in item["extension"]["annotation"] if i["type"] == "UPDATE_DATA"][0]
                entry = [code, latest, label]
                rows.append(entry)

            # convert to dataframe
            df = pd.DataFrame(rows, columns=["code", "updated", "about"]).sort_values("code")
            df["updated"] = pd.to_datetime(df["updated"])

        return df

    def eurostat(self,
                 code : str | None = None,
                 filter : dict | str | None = None,
                 start : datetime.datetime | None = None,
                 end : datetime.datetime | None = None) -> pd.DataFrame:
            '''

            Custom implementation of EUROSTAT API. If NO parameters passed,
            returns a "table of contents" for all possible EUROSTAT databases.


            Parameters
            ----------
            `code` : str | None = None
                The target database. If passed with no other parameters ("filter", 
                "start", or "end"), returns a list of options and values to filter 
                the database against. 
                
                *note* If used for querying options, time options are returned 
                as a 2 item list: first item is earliest possible entry date, 
                second item is last possible entry date. Single item lists 
                indicate only one possible date.

            `filter` : dict | str | None = None
                The database filter to apply. Filters take the form of:
                {"c[<filter>]" : [<value>, <value>, <value>]}. Time filters are
                processed as date ranges, only include the start and end date
                if manually entering "c[TIME_PERIOD]" (see "start" and "end"
                below as alternative).
                
                *note* If no filters are required, pass: filter="ALL".

            `start` : datetime.datetime | None = None
                Inclusive start date to retrieve data from. If "None" (default),
                uses start of database history. Overrides any "c[TIME_PERIOD]" 
                arguments passed within "filter" parameter.

            `end` : datetime.datetime | None = None
                Inclusive end date to retrieve data up until. If "None" (default), 
                uses UTC "today". Overrides any "c[TIME_PERIOD]" arguments passed 
                within "filter" parameter.

            Returns
            -------
            `pd.DataFrame`
                The data in pandas DataFrame format.
            
            '''

            # data request
            if isinstance(code, str) and isinstance(filter, (dict, str)):
                target = "/eurostat/api/dissemination/sdmx/3.0/data/dataflow/ESTAT/{}/1.0".format(code)

                # configure parameters
                params = {"format" : "csvdata",
                          "formatVersion" : "2.0",
                          "compress" : "true"}
                
                # set filters
                if isinstance(filter, dict):
                    params.update({key : ",".join(val) for key, val in filter.items()})

                    # set custom start / end filters
                    if isinstance(start, datetime.datetime) or isinstance(end, datetime.datetime):
                        
                        timeFilter = {"c[TIME_PERIOD]" : ""}
                        
                        # set start time
                        if isinstance(start, datetime.datetime):
                            
                            timeStart = "ge:{}".format(start.date().isoformat())
                            
                            timeFilter["c[TIME_PERIOD]"] = timeStart

                        # set end time
                        if isinstance(end, datetime.datetime):

                            timeEnd = "le:{}".format(end.date().isoformat())

                            # start time included
                            if len(timeFilter["c[TIME_PERIOD]"]) > 0:
                                timeFilter["c[TIME_PERIOD]"] += "+{}".format(timeEnd)
                            
                            # otherwise, just end time
                            else:
                                timeFilter["c[TIME_PERIOD]"] = timeEnd

                        params.update(timeFilter)

                    # use default filters (if already provided)
                    elif "c[TIME_PERIOD]" in params.keys():
                    
                        # if only one date, use it as start
                        if len(params["c[TIME_PERIOD]"]) == 1:
                            
                            params["c[TIME_PERIOD]"] = "ge:{}".format(params["c[TIME_PERIOD]"])
                        
                        # otherwise, use start to end
                        else:
                            sTime, eTime = params["c[TIME_PERIOD]"].split(",")
                            params["c[TIME_PERIOD]"] = "ge:{}+le:{}".format(sTime, eTime)

                elif filter == "ALL":
                    pass

            # options request
            elif isinstance(code, str) and isinstance(filter, NoneType):
                target = "/eurostat/api/dissemination/sdmx/3.0/structure/dataconstraint/ESTAT/{}/1.0".format(code)

                # configure parameters
                params = {"compress" : "true"}
            
            # table of contents request
            else:
                target = "/eurostat/api/dissemination/sdmx/2.1/dataflow/ESTAT/all"

                # configure parameters
                params = {"format" : "JSON",
                          "compressed" : "true"}

            # send request
            df = self._eurostat_request(method="GET", url=target, params=params)

            return df

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
        
        Closes all HTTPS sessions, cancels all pending asyncio 
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
        future = asyncio.run_coroutine_threadsafe(self._ecbSess.close(), self._loop)
        complete = future.result()
        future = asyncio.run_coroutine_threadsafe(self._bisSess.close(), self._loop)
        complete = future.result()

        # cancel all remaining tasks
        future = asyncio.run_coroutine_threadsafe(self._kill_stragglers(), self._loop)
        complete = future.result()      # wait for this final task to complete

        # stop the loop, join the thread, close the loop
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._eventLoop.join()
        self._loop.close()

        return None
    













