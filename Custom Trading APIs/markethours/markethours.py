import datetime
import calendar
import pytz
from types import NoneType
from pandas.tseries.holiday import AbstractHolidayCalendar, Holiday, nearest_workday, \
    USMartinLutherKingJr, USPresidentsDay, GoodFriday, USMemorialDay, \
    USLaborDay, USThanksgivingDay

''' TRADING HOURS '''
class TradingHours():
    '''
    
    An abstract template class used to represent market hours across different 
    timezones. NOT TO BE USED DIRECTLY. Set values for:
        1) TradingHours (change to appropriate class name)
        2) `self.name` within __init__()
        3) `self.zone` within __init__()
        4) hours within is_trading() - set hours to market's local time, 
           `self.TZ.localize` will add tzinfo without changing the time as long
           as the provided datetime is timezone naive. Pick between "vanillaHours"
           and "extendedHours" depending on how the asset trades.

           *note* `*.localize` is used in place of `tzinfo=*` due to lack of
           combatability for many `pytz` timezones with `tzinfo=*` assignment.
    

    Attributes
    ----------
    `market` : str
        The exchange used to trade.

    `zone` : str
        The market's timezone, as listed in the Olson Timezone Database:
        ftp://elsie.nci.nih.gov/pub/tz*.tar.gz

    Methods
    -------
    `is_open()` -> bool
        Whether the exchange is open for trading at a given time.
        
    '''

    def __init__(self) -> None:
        
        self.market = "MARKET NAME HERE"
        self.zone = "TIMEZONE HERE (OLSON FORMAT)"
        self.TZ = pytz.timezone(self.zone)
        
        return None

    def is_trading(self, 
                   currentTime : datetime.datetime = datetime.datetime.now(tz=datetime.UTC)) -> bool:
        '''
        
        Whether the exchange is open for trading at a given time.


        Parameters
        ----------
        `currentTime` : datetime.datetime = datetime.datetime.now(tz=datetime.UTC)
            The time to evaluate trading hours against.

        Returns
        -------
        `bool`
            Whether the exchange is open for trading or not.
        
        '''

        # assumes UTC if no TZ set, ensure all timezones are aware...
        if isinstance(currentTime.tzinfo, NoneType):
            raise ValueError("Datetime provided is timezone naive...")

        # convert to market's timezone
        inMarketTZ = currentTime.astimezone(self.TZ)

        # pull date
        year = inMarketTZ.year
        month = inMarketTZ.month
        day = inMarketTZ.day

        ''' OPTION ONE: Vanilla Hours, no midnight wrap arround'''
        # build market hours for that day
        # {Monday = 0, ..., Sunday = 6 : (open, close) in market's local time}
        vanillaHours = {
                        # Monday
                        0 : (self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)),  # open
                            self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0))), # close
                        
                        # Tuesday
                        1 : (self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)),  # open
                            self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0))), # close
                        
                        # Wednesday
                        2 : (self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)),  # open
                            self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0))), # close
                        
                        # Thursday
                        3 : (self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)),  # open
                            self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0))), # close
                        
                        # Friday
                        4 : (self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)),  # open
                            self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0))),  # close
                        
                        # Saturday
                        5 : (self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)),  # open
                            self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0))), # close
                        
                        # Sunday
                        6 : (self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)),  # open 
                            self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)))  # close
                       }

        # check if market is open
        if (vanillaHours[inMarketTZ.weekday()][0] <= inMarketTZ) and (inMarketTZ < vanillaHours[inMarketTZ.weekday()][1]):
            trading = True
        else:
            trading = False

        ''' OPTION TWO: Extended Hours, midnight wrap arround'''
        extendedHours = {
                             # Monday
                             0 : ((self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0))),          # midnight to close
                                  (self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 23, 59, 59, 999999)))), # open to midnight
                             
                             # Tuesday
                             1 : ((self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0))),          # midnight to close
                                  (self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 23, 59, 59, 999999)))), # open to midnight

                             # Wednesday
                             2 : ((self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0))),          # midnight to close
                                  (self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 23, 59, 59, 999999)))), # open to midnight

                             # Thursday
                             3 : ((self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0))),          # midnight to close
                                  (self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 23, 59, 59, 999999)))), # open to midnight

                             # Friday
                             4 : ((self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0))),          # midnight to close
                                  (self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 23, 59, 59, 999999)))), # open to midnight

                             # Saturday
                             5 : ((self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0))),          # midnight to close
                                  (self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 23, 59, 59, 999999)))), # open to midnight

                             # Sunday
                             6 : ((self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0))),          # midnight to close
                                  (self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 23, 59, 59, 999999)))), # open to midnight
                        }

        # check if market is open (LEAVE LESS THAN ON RIGHTHAND SIDE, DO NOT CHANGE TO LESS THAN-EQUAL TO)
        if ((extendedHours[inMarketTZ.weekday()][0][0] <= inMarketTZ) and (inMarketTZ < extendedHours[inMarketTZ.weekday()][0][1]) or \
            (extendedHours[inMarketTZ.weekday()][1][0] <= inMarketTZ) and (inMarketTZ < extendedHours[inMarketTZ.weekday()][1][1])):
            trading = True
        else:
            trading = False

        return trading

class CMEFX():
    '''
    
    An class used to represent trading hours for currency futures and currency
    future options via the CME exchange.
    

    Attributes
    ----------
    `name` : str
        The exchange used to trade.

    `zone` : str
        The market's timezone, as listed in the Olson Timezone Database:
        ftp://elsie.nci.nih.gov/pub/tz*.tar.gz

    Methods
    -------
    `is_trading()` -> bool
        Whether the exchange is open for trading at a given time.
    
    '''

    def __init__(self) -> None:
        
        self.name = "CME"
        self.zone = "CST6CDT"
        self.TZ = pytz.timezone(self.zone)
        
        return None

    def is_trading(self, currentTime : datetime.datetime = datetime.datetime.now(tz=datetime.UTC)) -> bool:
        '''
        
        Whether the exchange is open for trading at a given time.


        Parameters
        ----------
        `currentTime` : datetime.datetime = datetime.datetime.now(tzinfo=datetime.UTC)
            The time to evaluate trading hours against.

        Returns
        -------
        `bool`
            Whether the exchange is open for trading or not.
        
        '''

        # assumes UTC if no TZ set, ensure all timezones are aware...
        if isinstance(currentTime.tzinfo, NoneType):
            raise ValueError("Datetime provided is timezone naive...")

        # convert to market's timezone
        inMarketTZ = currentTime.astimezone(self.TZ)

        # pull date
        year = inMarketTZ.year
        month = inMarketTZ.month
        day = inMarketTZ.day

        # build market hours for that day
        # {Monday = 0, ..., Sunday = 6 : (open, close) in market's local time}
        extendedHours = {
                             # Monday
                             0 : ((self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 16, 0, 0, 0))),          # midnight to close
                                  (self.TZ.localize(datetime.datetime(year, month, day, 17, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 23, 59, 59, 999999)))), # open to midnight
                             
                             # Tuesday
                             1 : ((self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 16, 0, 0, 0))),          # midnight to close
                                  (self.TZ.localize(datetime.datetime(year, month, day, 17, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 23, 59, 59, 999999)))), # open to midnight

                             # Wednesday
                             2 : ((self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 16, 0, 0, 0))),          # midnight to close
                                  (self.TZ.localize(datetime.datetime(year, month, day, 17, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 23, 59, 59, 999999)))), # open to midnight

                             # Thursday
                             3 : ((self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 16, 0, 0, 0))),           # midnight to close
                                  (self.TZ.localize(datetime.datetime(year, month, day, 17, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 23, 59, 59, 999999)))), # open to midnight

                             # Friday
                             4 : ((self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 16, 0, 0, 0))),          # midnight to close
                                  (self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)))),          # CLOSED

                             # Saturday
                             5 : ((self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0))),           # CLOSED
                                  (self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)))),          # CLOSED

                             # Sunday
                             6 : ((self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 0, 0, 0, 0))),           # CLOSED
                                  (self.TZ.localize(datetime.datetime(year, month, day, 17, 0, 0, 0)), self.TZ.localize(datetime.datetime(year, month, day, 23, 59, 59, 999999)))), # open to midnight
                        }

        # check if market is open (LEAVE LESS THAN ON RIGHTHAND SIDE, DO NOT CHANGE TO LESS THAN-EQUAL TO)
        if ((extendedHours[inMarketTZ.weekday()][0][0] <= inMarketTZ) and (inMarketTZ < extendedHours[inMarketTZ.weekday()][0][1]) or \
            (extendedHours[inMarketTZ.weekday()][1][0] <= inMarketTZ) and (inMarketTZ < extendedHours[inMarketTZ.weekday()][1][1])):
            trading = True
        else:
            trading = False

        return trading

''' EXIRATIONS / SETTLEMENTS '''
class USTradingCalendar(AbstractHolidayCalendar):
    rules = [USMartinLutherKingJr,
             USPresidentsDay,
             GoodFriday,
             USMemorialDay,
             Holiday("Juneteenth", month=6, day=19),
             Holiday('IndependenceDay', month=7, day=4, observance=nearest_workday),
             USLaborDay,
             USThanksgivingDay,
             Holiday('Christmas', month=12, day=25, observance=nearest_workday),
             Holiday('NewYearsEve', month=1, day=1, observance=nearest_workday)]
CAL = USTradingCalendar()

def option_exiration(year, month):
    '''
    
    Identifies a currency future option's expiration date for a given month and 
    year:
    (1) 3rd Wednesday of month (2) Two Fridays back from there.

    
    Parameters
    ----------
    `year` : int
        The year of the expiration, either YYYY or last YY (will be appended by "20")

    `month` : int | str
        The integer month or character month code of the issue:
                [F, G, H, J, K, M, N, Q, U, V, X, Z]

    Returns
    -------
    `datetime.datetime`
        The datetime of the expiration (UTC)
    
    '''
    # contract expiration time adjustments
    CST = pytz.timezone("CST6CDT")

    # month codes
    months = {"F" : 1, "G" : 2, "H" : 3, "J" : 4, "K" : 5, "M" : 6, 
              "N" : 7, "Q" : 8, "U" : 9, "V" : 10, "X" : 11, "Z" : 12}
    
    # formatting
    if isinstance(month, str):
        monthNum = months[month]
    else:
        monthNum = month

    if isinstance(year, str):
        yearNum = int(year)
    else:
        yearNum = year

    if yearNum < 100:
        yearNum += 2000

    # pull calendar years
    daysInMonth = calendar.monthrange(yearNum, monthNum)[1]
    
    # (1) find 3rd Wednesday, (2) back into 2 Fridays before that
    found = False
    wednesdayCount = 0
    for day in range(1, daysInMonth + 1):
        
        today = CST.localize(datetime.datetime(yearNum, monthNum, day, 9))
        
        if today.weekday() == 2:
            wednesdayCount += 1
        
            if wednesdayCount == 3:
                fridayCount = 0
                for d in range(1, day + 1):

                    today = CST.localize(datetime.datetime(yearNum, monthNum, day - d, 9))

                    if today.weekday() == 4:
                        fridayCount += 1

                        if fridayCount == 2:
                            found = True
                            break
                break
    
    if not found:
        raise Exception("Expiration not found...")

    return today.astimezone(datetime.UTC)

def future_exiration(year, month):
    '''
    
    Identifies a currency future's expiration date for a given month and year:
    (1) 3rd Wednesday of month (2) Two business days back from there.

    
    Parameters
    ----------
    `year` : int
        The year of the expiration, either YYYY or last YY (will be appended by "20")

    `month` : int | str
        The integer month or character month code of the issue:
                [F, G, H, J, K, M, N, Q, U, V, X, Z]

    Returns
    -------
    `datetime.datetime`
        The datetime of the expiration (UTC)
    
    '''
    # contract expiration time adjustments
    CST = pytz.timezone("CST6CDT")

    # month codes
    months = {"F" : 1, "G" : 2, "H" : 3, "J" : 4, "K" : 5, "M" : 6, 
              "N" : 7, "Q" : 8, "U" : 9, "V" : 10, "X" : 11, "Z" : 12}
    
    # formatting
    if isinstance(month, str):
        monthNum = months[month]
    else:
        monthNum = month

    if isinstance(year, str):
        yearNum = int(year)
    else:
        yearNum = year

    if yearNum < 100:
        yearNum += 2000

    # pull calendar years
    daysInMonth = calendar.monthrange(yearNum, monthNum)[1]
    
    # pull holidays
    holidays = CAL.holidays(datetime.datetime(yearNum, monthNum, 1), 
                            datetime.datetime(yearNum, monthNum, daysInMonth))
    holidays = [CST.localize(holi) for holi in holidays]

    # (1) find 3rd Wednesday, (2) backtrack to 2 business days before that
    found = False
    wednesdayCount = 0
    for day in range(1, daysInMonth + 1):
        
        today = CST.localize(datetime.datetime(yearNum, monthNum, day, 9, 16))
        
        if today.weekday() == 2:
            wednesdayCount += 1
        
            if wednesdayCount == 3:
                businessCount = 0
                for d in range(1, day + 1):

                    today = CST.localize(datetime.datetime(yearNum, monthNum, day - d, 9, 16))
                    
                    if (today.weekday() not in [5, 6]) and (today not in holidays):
                        
                        businessCount += 1

                        if businessCount == 2:
                            found = True
                            break
                break
    
    if not found:
        raise Exception("Settlement not found...")

    return today.astimezone(datetime.UTC)


''' Timezones

"Africa/Abidjan",
"Africa/Accra",
"Africa/Addis_Ababa",
"Africa/Algiers",
"Africa/Asmara",
"Africa/Asmera",
"Africa/Bamako",
"Africa/Bangui",
"Africa/Banjul",
"Africa/Bissau",
"Africa/Blantyre",
"Africa/Brazzaville",
"Africa/Bujumbura",
"Africa/Cairo",
"Africa/Casablanca",
"Africa/Ceuta",
"Africa/Conakry",
"Africa/Dakar",
"Africa/Dar_es_Salaam",
"Africa/Djibouti",
"Africa/Douala",
"Africa/El_Aaiun",
"Africa/Freetown",
"Africa/Gaborone",
"Africa/Harare",
"Africa/Johannesburg",
"Africa/Juba",
"Africa/Kampala",
"Africa/Khartoum",
"Africa/Kigali",
"Africa/Kinshasa",
"Africa/Lagos",
"Africa/Libreville",
"Africa/Lome",
"Africa/Luanda",
"Africa/Lubumbashi",
"Africa/Lusaka",
"Africa/Malabo",
"Africa/Maputo",
"Africa/Maseru",
"Africa/Mbabane",
"Africa/Mogadishu",
"Africa/Monrovia",
"Africa/Nairobi",
"Africa/Ndjamena",
"Africa/Niamey",
"Africa/Nouakchott",
"Africa/Ouagadougou",
"Africa/Porto-Novo",
"Africa/Sao_Tome",
"Africa/Timbuktu",
"Africa/Tripoli",
"Africa/Tunis",
"Africa/Windhoek",
"America/Adak",
"America/Anchorage",
"America/Anguilla",
"America/Antigua",
"America/Araguaina",
"America/Argentina/Buenos_Aires",
"America/Argentina/Catamarca",
"America/Argentina/ComodRivadavia",
"America/Argentina/Cordoba",
"America/Argentina/Jujuy",
"America/Argentina/La_Rioja",
"America/Argentina/Mendoza",
"America/Argentina/Rio_Gallegos",
"America/Argentina/Salta",
"America/Argentina/San_Juan",
"America/Argentina/San_Luis",
"America/Argentina/Tucuman",
"America/Argentina/Ushuaia",
"America/Aruba",
"America/Asuncion",
"America/Atikokan",
"America/Atka",
"America/Bahia",
"America/Bahia_Banderas",
"America/Barbados",
"America/Belem",
"America/Belize",
"America/Blanc-Sablon",
"America/Boa_Vista",
"America/Bogota",
"America/Boise",
"America/Buenos_Aires",
"America/Cambridge_Bay",
"America/Campo_Grande",
"America/Cancun",
"America/Caracas",
"America/Catamarca",
"America/Cayenne",
"America/Cayman",
"America/Chicago",
"America/Chihuahua",
"America/Ciudad_Juarez",
"America/Coral_Harbour",
"America/Cordoba",
"America/Costa_Rica",
"America/Creston",
"America/Cuiaba",
"America/Curacao",
"America/Danmarkshavn",
"America/Dawson",
"America/Dawson_Creek",
"America/Denver",
"America/Detroit",
"America/Dominica",
"America/Edmonton",
"America/Eirunepe",
"America/El_Salvador",
"America/Ensenada",
"America/Fort_Nelson",
"America/Fort_Wayne",
"America/Fortaleza",
"America/Glace_Bay",
"America/Godthab",
"America/Goose_Bay",
"America/Grand_Turk",
"America/Grenada",
"America/Guadeloupe",
"America/Guatemala",
"America/Guayaquil",
"America/Guyana",
"America/Halifax",
"America/Havana",
"America/Hermosillo",
"America/Indiana/Indianapolis",
"America/Indiana/Knox",
"America/Indiana/Marengo",
"America/Indiana/Petersburg",
"America/Indiana/Tell_City",
"America/Indiana/Vevay",
"America/Indiana/Vincennes",
"America/Indiana/Winamac",
"America/Indianapolis",
"America/Inuvik",
"America/Iqaluit",
"America/Jamaica",
"America/Jujuy",
"America/Juneau",
"America/Kentucky/Louisville",
"America/Kentucky/Monticello",
"America/Knox_IN",
"America/Kralendijk",
"America/La_Paz",
"America/Lima",
"America/Los_Angeles",
"America/Louisville",
"America/Lower_Princes",
"America/Maceio",
"America/Managua",
"America/Manaus",
"America/Marigot",
"America/Martinique",
"America/Matamoros",
"America/Mazatlan",
"America/Mendoza",
"America/Menominee",
"America/Merida",
"America/Metlakatla",
"America/Mexico_City",
"America/Miquelon",
"America/Moncton",
"America/Monterrey",
"America/Montevideo",
"America/Montreal",
"America/Montserrat",
"America/Nassau",
"America/New_York",
"America/Nipigon",
"America/Nome",
"America/Noronha",
"America/North_Dakota/Beulah",
"America/North_Dakota/Center",
"America/North_Dakota/New_Salem",
"America/Nuuk",
"America/Ojinaga",
"America/Panama",
"America/Pangnirtung",
"America/Paramaribo",
"America/Phoenix",
"America/Port-au-Prince",
"America/Port_of_Spain",
"America/Porto_Acre",
"America/Porto_Velho",
"America/Puerto_Rico",
"America/Punta_Arenas",
"America/Rainy_River",
"America/Rankin_Inlet",
"America/Recife",
"America/Regina",
"America/Resolute",
"America/Rio_Branco",
"America/Rosario",
"America/Santa_Isabel",
"America/Santarem",
"America/Santiago",
"America/Santo_Domingo",
"America/Sao_Paulo",
"America/Scoresbysund",
"America/Shiprock",
"America/Sitka",
"America/St_Barthelemy",
"America/St_Johns",
"America/St_Kitts",
"America/St_Lucia",
"America/St_Thomas",
"America/St_Vincent",
"America/Swift_Current",
"America/Tegucigalpa",
"America/Thule",
"America/Thunder_Bay",
"America/Tijuana",
"America/Toronto",
"America/Tortola",
"America/Vancouver",
"America/Virgin",
"America/Whitehorse",
"America/Winnipeg",
"America/Yakutat",
"America/Yellowknife",
"Antarctica/Casey",
"Antarctica/Davis",
"Antarctica/DumontDUrville",
"Antarctica/Macquarie",
"Antarctica/Mawson",
"Antarctica/McMurdo",
"Antarctica/Palmer",
"Antarctica/Rothera",
"Antarctica/South_Pole",
"Antarctica/Syowa",
"Antarctica/Troll",
"Antarctica/Vostok",
"Arctic/Longyearbyen",
"Asia/Aden",
"Asia/Almaty",
"Asia/Amman",
"Asia/Anadyr",
"Asia/Aqtau",
"Asia/Aqtobe",
"Asia/Ashgabat",
"Asia/Ashkhabad",
"Asia/Atyrau",
"Asia/Baghdad",
"Asia/Bahrain",
"Asia/Baku",
"Asia/Bangkok",
"Asia/Barnaul",
"Asia/Beirut",
"Asia/Bishkek",
"Asia/Brunei",
"Asia/Calcutta",
"Asia/Chita",
"Asia/Choibalsan",
"Asia/Chongqing",
"Asia/Chungking",
"Asia/Colombo",
"Asia/Dacca",
"Asia/Damascus",
"Asia/Dhaka",
"Asia/Dili",
"Asia/Dubai",
"Asia/Dushanbe",
"Asia/Famagusta",
"Asia/Gaza",
"Asia/Harbin",
"Asia/Hebron",
"Asia/Ho_Chi_Minh",
"Asia/Hong_Kong",
"Asia/Hovd",
"Asia/Irkutsk",
"Asia/Istanbul",
"Asia/Jakarta",
"Asia/Jayapura",
"Asia/Jerusalem",
"Asia/Kabul",
"Asia/Kamchatka",
"Asia/Karachi",
"Asia/Kashgar",
"Asia/Kathmandu",
"Asia/Katmandu",
"Asia/Khandyga",
"Asia/Kolkata",
"Asia/Krasnoyarsk",
"Asia/Kuala_Lumpur",
"Asia/Kuching",
"Asia/Kuwait",
"Asia/Macao",
"Asia/Macau",
"Asia/Magadan",
"Asia/Makassar",
"Asia/Manila",
"Asia/Muscat",
"Asia/Nicosia",
"Asia/Novokuznetsk",
"Asia/Novosibirsk",
"Asia/Omsk",
"Asia/Oral",
"Asia/Phnom_Penh",
"Asia/Pontianak",
"Asia/Pyongyang",
"Asia/Qatar",
"Asia/Qostanay",
"Asia/Qyzylorda",
"Asia/Rangoon",
"Asia/Riyadh",
"Asia/Saigon",
"Asia/Sakhalin",
"Asia/Samarkand",
"Asia/Seoul",
"Asia/Shanghai",
"Asia/Singapore",
"Asia/Srednekolymsk",
"Asia/Taipei",
"Asia/Tashkent",
"Asia/Tbilisi",
"Asia/Tehran",
"Asia/Tel_Aviv",
"Asia/Thimbu",
"Asia/Thimphu",
"Asia/Tokyo",
"Asia/Tomsk",
"Asia/Ujung_Pandang",
"Asia/Ulaanbaatar",
"Asia/Ulan_Bator",
"Asia/Urumqi",
"Asia/Ust-Nera",
"Asia/Vientiane",
"Asia/Vladivostok",
"Asia/Yakutsk",
"Asia/Yangon",
"Asia/Yekaterinburg",
"Asia/Yerevan",
"Atlantic/Azores",
"Atlantic/Bermuda",
"Atlantic/Canary",
"Atlantic/Cape_Verde",
"Atlantic/Faeroe",
"Atlantic/Faroe",
"Atlantic/Jan_Mayen",
"Atlantic/Madeira",
"Atlantic/Reykjavik",
"Atlantic/South_Georgia",
"Atlantic/St_Helena",
"Atlantic/Stanley",
"Australia/ACT",
"Australia/Adelaide",
"Australia/Brisbane",
"Australia/Broken_Hill",
"Australia/Canberra",
"Australia/Currie",
"Australia/Darwin",
"Australia/Eucla",
"Australia/Hobart",
"Australia/LHI",
"Australia/Lindeman",
"Australia/Lord_Howe",
"Australia/Melbourne",
"Australia/NSW",
"Australia/North",
"Australia/Perth",
"Australia/Queensland",
"Australia/South",
"Australia/Sydney",
"Australia/Tasmania",
"Australia/Victoria",
"Australia/West",
"Australia/Yancowinna",
"Brazil/Acre",
"Brazil/DeNoronha",
"Brazil/East",
"Brazil/West",
"CET",
"CST6CDT",
"Canada/Atlantic",
"Canada/Central",
"Canada/Eastern",
"Canada/Mountain",
"Canada/Newfoundland",
"Canada/Pacific",
"Canada/Saskatchewan",
"Canada/Yukon",
"Chile/Continental",
"Chile/EasterIsland",
"Cuba",
"EET",
"EST",
"EST5EDT",
"Egypt",
"Eire",
"Etc/GMT",
"Etc/GMT+0",
"Etc/GMT+1",
"Etc/GMT+10",
"Etc/GMT+11",
"Etc/GMT+12",
"Etc/GMT+2",
"Etc/GMT+3",
"Etc/GMT+4",
"Etc/GMT+5",
"Etc/GMT+6",
"Etc/GMT+7",
"Etc/GMT+8",
"Etc/GMT+9",
"Etc/GMT-0",
"Etc/GMT-1",
"Etc/GMT-10",
"Etc/GMT-11",
"Etc/GMT-12",
"Etc/GMT-13",
"Etc/GMT-14",
"Etc/GMT-2",
"Etc/GMT-3",
"Etc/GMT-4",
"Etc/GMT-5",
"Etc/GMT-6",
"Etc/GMT-7",
"Etc/GMT-8",
"Etc/GMT-9",
"Etc/GMT0",
"Etc/Greenwich",
"Etc/UCT",
"Etc/UTC",
"Etc/Universal",
"Etc/Zulu",
"Europe/Amsterdam",
"Europe/Andorra",
"Europe/Astrakhan",
"Europe/Athens",
"Europe/Belfast",
"Europe/Belgrade",
"Europe/Berlin",
"Europe/Bratislava",
"Europe/Brussels",
"Europe/Bucharest",
"Europe/Budapest",
"Europe/Busingen",
"Europe/Chisinau",
"Europe/Copenhagen",
"Europe/Dublin",
"Europe/Gibraltar",
"Europe/Guernsey",
"Europe/Helsinki",
"Europe/Isle_of_Man",
"Europe/Istanbul",
"Europe/Jersey",
"Europe/Kaliningrad",
"Europe/Kiev",
"Europe/Kirov",
"Europe/Kyiv",
"Europe/Lisbon",
"Europe/Ljubljana",
"Europe/London",
"Europe/Luxembourg",
"Europe/Madrid",
"Europe/Malta",
"Europe/Mariehamn",
"Europe/Minsk",
"Europe/Monaco",
"Europe/Moscow",
"Europe/Nicosia",
"Europe/Oslo",
"Europe/Paris",
"Europe/Podgorica",
"Europe/Prague",
"Europe/Riga",
"Europe/Rome",
"Europe/Samara",
"Europe/San_Marino",
"Europe/Sarajevo",
"Europe/Saratov",
"Europe/Simferopol",
"Europe/Skopje",
"Europe/Sofia",
"Europe/Stockholm",
"Europe/Tallinn",
"Europe/Tirane",
"Europe/Tiraspol",
"Europe/Ulyanovsk",
"Europe/Uzhgorod",
"Europe/Vaduz",
"Europe/Vatican",
"Europe/Vienna",
"Europe/Vilnius",
"Europe/Volgograd",
"Europe/Warsaw",
"Europe/Zagreb",
"Europe/Zaporozhye",
"Europe/Zurich",
"GB",
"GB-Eire",
"GMT",
"GMT+0",
"GMT-0",
"GMT0",
"Greenwich",
"HST",
"Hongkong",
"Iceland",
"Indian/Antananarivo",
"Indian/Chagos",
"Indian/Christmas",
"Indian/Cocos",
"Indian/Comoro",
"Indian/Kerguelen",
"Indian/Mahe",
"Indian/Maldives",
"Indian/Mauritius",
"Indian/Mayotte",
"Indian/Reunion",
"Iran",
"Israel",
"Jamaica",
"Japan",
"Kwajalein",
"Libya",
"MET",
"MST",
"MST7MDT",
"Mexico/BajaNorte",
"Mexico/BajaSur",
"Mexico/General",
"NZ",
"NZ-CHAT",
"Navajo",
"PRC",
"PST8PDT",
"Pacific/Apia",
"Pacific/Auckland",
"Pacific/Bougainville",
"Pacific/Chatham",
"Pacific/Chuuk",
"Pacific/Easter",
"Pacific/Efate",
"Pacific/Enderbury",
"Pacific/Fakaofo",
"Pacific/Fiji",
"Pacific/Funafuti",
"Pacific/Galapagos",
"Pacific/Gambier",
"Pacific/Guadalcanal",
"Pacific/Guam",
"Pacific/Honolulu",
"Pacific/Johnston",
"Pacific/Kanton",
"Pacific/Kiritimati",
"Pacific/Kosrae",
"Pacific/Kwajalein",
"Pacific/Majuro",
"Pacific/Marquesas",
"Pacific/Midway",
"Pacific/Nauru",
"Pacific/Niue",
"Pacific/Norfolk",
"Pacific/Noumea",
"Pacific/Pago_Pago",
"Pacific/Palau",
"Pacific/Pitcairn",
"Pacific/Pohnpei",
"Pacific/Ponape",
"Pacific/Port_Moresby",
"Pacific/Rarotonga",
"Pacific/Saipan",
"Pacific/Samoa",
"Pacific/Tahiti",
"Pacific/Tarawa",
"Pacific/Tongatapu",
"Pacific/Truk",
"Pacific/Wake",
"Pacific/Wallis",
"Pacific/Yap",
"Poland",
"Portugal",
"ROC",
"ROK",
"Singapore",
"Turkey",
"UCT",
"US/Alaska",
"US/Aleutian",
"US/Arizona",
"US/Central",
"US/East-Indiana",
"US/Eastern",
"US/Hawaii",
"US/Indiana-Starke",
"US/Michigan",
"US/Mountain",
"US/Pacific",
"US/Samoa",
"UTC",
"Universal",
"W-SU",
"WET",
"Zulu"

'''