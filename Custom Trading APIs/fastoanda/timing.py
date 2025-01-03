import datetime

def marketOpen(startDay : int = 6,
               startHour : int = 21,
               startMinute : int = 0,
               endDay : int = 4,
               endHour : int = 21,
               endMinute : int = 0,
               dailyMarket : bool = False,
               customTime : datetime.datetime | None = None) -> tuple[bool, int]:
    
    '''
    
    Determines whether or not the market is open. Returns market status and 
    number of seconds until the market is open next (0 if open, > 0 if closed). 
    *Note* all time parameters are assumed UTC.

    
    Parameters
    ----------
    `startDay` : str = "Sunday"
        Day the market opens:
            
            "Monday"    : 0
            "Tuesday"   : 1
            "Wednesday" : 2
            "Thursday"  : 3
            "Friday"    : 4
            "Saturday"  : 5
            "Sunday"    : 6

    `startHour` : int = 21
        Opening hour of the market.
    
    `startMinute` : int = 0
        Opening minute of the market.

    `endDay` : str = "Friday"
        Day the market closes:
            
            "Monday"    : 0
            "Tuesday"   : 1
            "Wednesday" : 2
            "Thursday"  : 3
            "Friday"    : 4
            "Saturday"  : 5
            "Sunday"    : 6

    `endHour` : int = 21
        Ending hour of the market.
    
    `endMinute` : int = 0
        Ending minute of the market.

    `dailyMarket` : bool = False
        Whether or not the market opens and closes every day at the given
        `startHour` / `startMinute` and `endHour` / `endMinute` (during
        market trading days)

    `customTime` : datetime.datetime | None = None
        The datetime to test against. If `None`, defaults to current time.
        [default=None].
    
    Returns
    -------
    `bool`
        `True` if market is open. `False` if market is close.
    
    `float`
        Number of seconds until the market opens.
        
    '''

    # if provided, use custom datetime for test
    if customTime:
        now = customTime
    
    # otherwise use current time
    else:
        now = datetime.datetime.now()

    # assume market is open
    secondsUntilOpen = 0

    # cache weekday & time
    currentDay = now.weekday()
    currentTime = now.time()

    # market opens and closes on a daily basis (during market trading days)
    if dailyMarket:
        
        # set trading days:
        # markets open every day
        if startDay == endDay:
            tradingDays = [x for x in range(0, 7)]

        # linear open / close bookends
        elif startDay < endDay:
            tradingDays = [x for x in range(startDay, endDay + 1)]
            
        # otherwise, wrapped bookends
        else:
            tradingDays = [x for x in range(startDay, 7)]
            tradingDays.extend([x for x in range(0, endDay + 1)])

        # determine market status:
        # if a trading day in the market
        if (currentDay in tradingDays):

            # if wrapped start / end market hours
            if datetime.time(hour=endHour, minute=endMinute) < datetime.time(hour=startHour, minute=startMinute):

                # and within open hours
                if (datetime.time(hour=startHour, minute=startMinute) <= currentTime) \
                     | (currentTime < datetime.time(hour=endHour, minute=endMinute)):
                    
                    marketIsOpen = True
                
                else:
                    marketIsOpen = False
            
            # else linear start / end market hours
            else:
                if (datetime.time(hour=startHour, minute=startMinute) <= currentTime) \
                 & (currentTime < datetime.time(hour=endHour, minute=endMinute)):
                
                    marketIsOpen = True
                
                else:
                    marketIsOpen = False

        # otherwise, market is closed
        else:
            marketIsOpen = False

    # 24/7 trading during between market bookends
    else:
        
        # 24/7, 365 market - always open
        if (startDay == endDay) and (startHour == endHour) and (startMinute == endMinute):
            marketIsOpen = True

        # linear open / close bookends
        elif startDay <= endDay:

            # if trading day within market's daily linear timeframe
            # exp: Start Mon, End Fri
            # 0 1  2 3  4 5  6
            # M Tu W Th F Sa Su
            # |---------|
            if (startDay <= currentDay) and (currentDay <= endDay):

                # if open and close on same day            
                if (startDay == endDay) and (currentDay == startDay):

                    # open if time is later than or equal to start time
                    if currentTime >= datetime.time(startHour, startMinute):
                        marketIsOpen = True 

                    # or open if time is earlier than end time
                    elif currentTime < datetime.time(endHour, endMinute):
                        marketIsOpen = True

                    # otherwise closed
                    else:
                        marketIsOpen = False

                # if on first day of market
                elif currentDay == startDay:

                    # open if time greater than or equal to start time
                    if currentTime >= datetime.time(startHour, startMinute):
                        marketIsOpen = True
                    
                    # otherwise closed
                    else:
                        marketIsOpen = False    
                
                # if on last day of market
                elif currentDay == endDay:

                    # open if time less than end time
                    if currentTime < datetime.time(endHour, endMinute):
                        marketIsOpen = True

                    # otherwise closed
                    else:
                        marketIsOpen = False

                # otherwise open (somewhere in between start and end times)
                else:
                    marketIsOpen = True

            # otherwise, market is closed
            else:
                marketIsOpen = False

        # wrapping open / close bookends
        else:

            # if trading day within market's daily wrapping timeframe
            # exp: Start Friday, End Wed
            # 0 1  2 3  4 5  6
            # M Tu W Th F Sa Su
            # |----|    |-----|
            if (currentDay <= endDay) or (startDay <= currentDay):

                # if on first day of market
                if currentDay == startDay:

                    # open if time greater than or equal to start time
                    if currentTime >= datetime.time(startHour, startMinute):
                        marketIsOpen = True
                    
                    # otherwise closed
                    else:
                        marketIsOpen = False    
                
                # if on last day of market
                elif currentDay == endDay:

                    # open if time less than end time
                    if currentTime < datetime.time(endHour, endMinute):
                        marketIsOpen = True

                    # otherwise closed
                    else:
                        marketIsOpen = False

                # otherwise open (somewhere in between start and end times)
                else:
                    marketIsOpen = True


            # otherwise, market is closed
            else:
                marketIsOpen = False

    # if market closed, calculate seconds until open
    if not marketIsOpen:

        # calculate time until next daily open
        if dailyMarket:

            # if more than one trading day ahead or market open every day, calculate time until next daily open
            if (currentDay in tradingDays[:-1]) or (startDay == endDay):
                
                #   N  S         E
                # |----|---------|
                if (currentTime < datetime.time(hour=startHour, minute=startMinute)) \
                 & (currentTime >= datetime.time(hour=0, minute=0)):
                    subDailyOffset = datetime.timedelta(hours=startHour, minutes=startMinute) \
                                   - datetime.timedelta(hours=now.hour, minutes=now.minute, seconds=now.second, microseconds=now.microsecond)

                #    E    N    S
                # |--|---------|--|
                elif (datetime.time(hour=endHour, minute=endMinute) <= currentTime) \
                   & (currentTime < datetime.time(hour=startHour, minute=startMinute)):
                    subDailyOffset = datetime.timedelta(hours=startHour, minutes=startMinute) \
                                   - datetime.timedelta(hours=now.hour, minutes=now.minute, seconds=now.second, microseconds=now.microsecond)

                # S         E  N      
                # |---------|----|
                elif (currentTime < datetime.time(hour=endHour, minute=endMinute)) \
                   & (currentTime < datetime.time(hour=23, minute=59, second=59, microsecond=999999)):
                    subDailyOffset = datetime.timedelta(hours=24) \
                                   - datetime.timedelta(hours=now.hour, minutes=now.minute, seconds=now.second, microseconds=now.microsecond)

                else:

                    #   N  S       E
                    # |----|-------|----|
                    if (currentTime < datetime.time(hour=startHour, minute=startMinute)):
                        subDailyOffset = datetime.timedelta(hours=startHour, minutes=startMinute) \
                                       - datetime.timedelta(hours=now.hour, minutes=now.minute, seconds=now.second, microseconds=now.microsecond)
                        
                    #      S       E  N
                    # |----|-------|----|
                    else:
                        subDailyOffset = datetime.timedelta(hours=24) \
                                       - datetime.timedelta(hours=now.hour, minutes=now.minute, seconds=now.second, microseconds=now.microsecond) \
                                       + datetime.timedelta(hours=startHour, minutes=startMinute)
                    
                secondsUntilOpen = subDailyOffset.total_seconds()

            # otherwise, calculate time until next market open
            else:
                # calculate hour / minute offset to open time
                subDailyOffset = datetime.timedelta(hours=startHour, minutes=startMinute) \
                                - datetime.timedelta(hours=now.hour, minutes=now.minute, seconds=now.second, microseconds=now.microsecond)
                
                # calculate days until open
                dailyOffset = datetime.timedelta(days=(7 - (currentDay - startDay)) % 7)

                # calculate total wait time
                secondsUntilOpen = dailyOffset.total_seconds() + subDailyOffset.total_seconds()    


        # otherwise, calculate time until next 24/7 market open
        else:

            # calculate hour / minute offset to open time
            subDailyOffset = datetime.timedelta(hours=startHour, minutes=startMinute) \
                            - datetime.timedelta(hours=now.hour, minutes=now.minute, seconds=now.second, microseconds=now.microsecond)
            
            # calculate days until open
            dailyOffset = datetime.timedelta(days=(7 - (currentDay - startDay)) % 7)

            # calculate total wait time
            secondsUntilOpen = dailyOffset.total_seconds() + subDailyOffset.total_seconds()

    return marketIsOpen, secondsUntilOpen

def nearlyTime(hours : list = [hour for hour in range(0, 24)],
               minutes :  list = [0],
               seconds : list = [0],
               customTime : datetime.datetime | None = None) -> tuple[bool, int]:
    '''
    
    Determines whether a new time increment has started. Calculates the
    number of seconds between the time the function is called and the start
    of the next nearest time increment (0 if on current increment, > 0 if not). 
    
    Parameters
    ----------
    `hours` : list = [hour for hour in range(0, 24)]
        A list of hours to validate the time against. Hours must be in
        chronological order [default=[0, ..., 23]]

    `minutes` :  list = [0]
        A list of minutes to validate the time against. Minutes must be
        in chronological order. [default=[0]]

    `seconds` : list = [0]
        A list of seconds to validate the time against. Seconds must be
        in chronological order. [default=[0]]

    `customTime` : datetime.datetime | None = None
        The datetime to test against. If `None`, defaults to current time.
        [default=None].

    Returns
    -------
    `bool`
        `True` if a new time increment has started, `False` if not.
    
    `float`
        Number of seconds until the next time increment starts.
        
    
    '''

    # if provided, use custom datetime for test
    if customTime:
        now = customTime
    
    # otherwise use current time
    else:
        now = datetime.datetime.now()

    # assume on a new increment
    secondsUntilNewIncrement = 0

    # test for increment
    if ((now.hour in hours) & (now.minute in minutes) & (now.second in seconds)):
        
        # on a new increment
        isNewIncrement = True

    # if already past maximums, set to next available increment
    elif (now.hour > max(hours)) | \
         ((now.hour == max(hours)) & (now.minute > max(minutes))) | \
         ((now.hour == max(hours)) & (now.minute == max(minutes)) & (now.second > max(seconds))):
        
        # off a new increment
        isNewIncrement = False

        # next nearest is the start of available increments
        nextHour = hours[0]
        nextMinute = minutes[0]
        nextSecond = seconds[0]

    # otherwise, work our way down - trying to avoid excessive datetime object creation
    else:

        # off a new increment
        isNewIncrement = False

        # if on an increment hour
        if now.hour in hours:
            
            # and on an increment minute
            if now.minute in minutes:

                # find the next nearest second
                laterSeconds = [x for x in seconds if x > now.second]
                if laterSeconds:
                    nextHour = now.hour
                    nextMinute = now.minute
                    nextSecond = laterSeconds[0]
                
                # otherwise find the next nearest minute and second
                else:
                    laterMinutes = [x for x in minutes if x > now.minute]
                    if laterMinutes:
                        nextHour = now.hour
                        nextMinute = laterMinutes[0]
                        nextSecond = seconds[0]

                    # otherwise find the next nearest hour, minute, and second
                    else:
                        laterHours = [x for x in hours if x > now.hour]
                        if laterHours:
                            nextHour = laterHours[0]
                            nextMinute = minutes[0]
                            nextSecond = seconds[0] 

            # otherwise find the next nearest minute and second
            else:
                laterMinutes = [x for x in minutes if x > now.minute]
                if laterMinutes:
                    nextHour = now.hour
                    nextMinute = laterMinutes[0]
                    nextSecond = seconds[0]

                # otherwise find the next nearest hour, minute, and second
                else:
                    laterHours = [x for x in hours if x > now.hour]
                    if laterHours:
                        nextHour = laterHours[0]
                        nextMinute = minutes[0]
                        nextSecond = seconds[0] 
                

        # otherwise find the next nearest hour, minute, and second
        else:
            laterHours = [x for x in hours if x > now.hour]
            nextHour = laterHours[0]
            nextMinute = minutes[0]
            nextSecond = seconds[0]


    # calculate offset seconds
    if not isNewIncrement:

        # set next increment
        nextIncrementTime = datetime.datetime(year=now.year, month=now.month,
                                              day= now.day, hour=nextHour, 
                                              minute=nextMinute, second=nextSecond)
        
        # calculate offset from current time (if not past yet, this will be the offset)
        offset = nextIncrementTime - now

        # if next increment on new day, calculate new offset
        if now.time() > datetime.time(nextHour, nextMinute, nextSecond):

            # determine next day's increment
            nextDaysIncrement = (now + offset) + datetime.timedelta(hours=24)

            # calculate offset
            offset = nextDaysIncrement - now

        secondsUntilNewIncrement = offset.total_seconds()


    return isNewIncrement, secondsUntilNewIncrement

