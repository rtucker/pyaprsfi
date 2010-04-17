#!/usr/bin/python
"""
aprs.fi API Interface for Python

Copyright (c) 2010 Ryan S. Tucker

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

import logging
import urllib
import urllib2

try:
    import json
except:
    import simplejson as json

APRSFI_API_URL = "http://aprs.fi/api/get"
VERSION = "0.0.1"

class MissingRequiredArgument(Exception):
    """Raised when a required parameter is missing."""
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class ApiError(Exception):
    """Raised when an aprs.fi API call returns an error."""
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)

class ApiInfo:
    valid_commands  = {}
    valid_params    = {}

class LowerCaseDict(dict):
    def __init__(self, copy=None):
        if copy:
            if isinstance(copy, dict):
                for k,v in copy.items():
                    dict.__setitem__(self, k.lower(), v)
            else:
                for k,v in copy:
                    dict.__setitem__(self, k.lower(), v)

    def __getitem__(self, key):
        return dict.__getitem__(self, key.lower())

    def __setitem__(self, key, value):
        dict.__setitem__(self, key.lower(), value)

    def __contains__(self, key):
        return dict.__contains__(self, key.lower())

    def has_key(self, key):
        return dict.has_key(self, key.lower())

    def get(self, key, def_val=None):
        return dict.get(self, key.lower(), def_val)

    def setdefault(self, key, def_val=None):
        return dict.setdefault(self, key.lower(), def_val)

    def update(self, copy):
        for k,v in copy.items():
            dict.__setitem__(self, k.lower(), v)

    def fromkeys(self, iterable, value=None):
        d = self.__class__()
        for k in iterable:
            dict.__setitem__(d, k.lower(), value)
        return d

    def pop(self, key, def_val=None):
        return dict.pop(self, key.lower(), def_val)

class Api:
    """
    aprs.fi API client class.

    Instantiate with: Api(key)

    Parameters:
        key - your aprs.fi API key (default: None)

    This will interface with the aprs.fi API using JSON, to query its
    database of APRS objects.  See http://aprs.fi/page/api for more
    information.

    Based heavily on the Linode API interface by TJ Fontaine, et al, from
    http://atxconsulting.com/content/linode-api-bindings
    """

    def __init__(self, key):
        self.__key = key
        self.__urlopen = urllib2.urlopen
        self.__request = urllib2.Request

    @staticmethod
    def valid_commands():
        """Returns a list of API commands supported by this class."""
        return ApiInfo.valid_commands.keys()

    @staticmethod
    def valid_params():
        """Returns a list of all parameters used by methods of this class."""
        return ApiInfo.valid_params.keys()

    def __getattr__(self, name):
        """Return a callable for any undefined attribute;
           assume it's an API call.
        """
        def generic_request(*args, **kw):
            request = LowerCaseDict(kw)
            request['what'] = name
            return self.__send_request(request)

        generic_request.__name__ = name
        return generic_request

    def __send_request(self, request):
        request['apikey'] = self.__key
        request['format'] = 'json'

        logging.debug('Parameters: ' + str(request))
        request = urllib.urlencode(request)

        headers = {
            'User-Agent': 'Python-aprsfi/' + VERSION,
        }

        req = self.__request(APRSFI_API_URL + '?' + request, headers=headers)
        response = self.__urlopen(req)
        response = response.read()

        logging.debug('Raw Response: ' + response)

        try:
            s = json.loads(response)
        except Exception, ex:
            print response
            raise ex

        if isinstance(s, dict):
            s = LowerCaseDict(s)
            if s['result'] == 'fail':
                raise ApiError(s['description'])
            return s
        else:
            return s

    def __api_request(required=[], optional=[], returns=[]):
        """Decorator to define required and optional parameters"""
        for k in required:
            k = k.lower()
            if not ApiInfo.valid_params.has_key(k):
                ApiInfo.valid_params[k] = True

        for k in optional:
            k = k.lower()
            if not ApiInfo.valid_params.has_key(k):
                ApiInfo.valid_params[k] = True

        def decorator(func):
            if not ApiInfo.valid_commands.has_key(func.__name__):
                ApiInfo.valid_commands[func.__name__] = True

            def wrapper(self, **kw):
                request = LowerCaseDict()
                request['what'] = func.__name__

                params = LowerCaseDict(kw)

                for k in required:
                    if not params.has_key(k):
                        raise MissingRequiredArgument(k)

                for k in params:
                    request[k] = params[k]

                result = func(self, request)
                if result is not None:
                    request = result

                return self.__send_request(request)

            wrapper.__name__ = func.__name__
            wrapper.__doc__ = func.__doc__
            wrapper.__dict__.update(func.__dict__)

            if (required or optional) and wrapper.__doc__:
                # Generate parameter documentation in docstring
                if len(wrapper.__doc__.split('\n')) is 1:
                    # one-liners need whitespace
                    wrapper.__doc__ += '\n'
                wrapper.__doc__ += '\n    Keyword arguments (* = required):\n'
                wrapper.__doc__ += ''.join(['\t *%s\n' % p for p in required])
                wrapper.__doc__ += ''.join(['\t  %s\n' % p for p in optional])

            if returns and wrapper.__doc__:
                # we either have a list of dicts or a just plain dict
                if len(wrapper.__doc__.split('\n')) is 1:
                    # one-liners need whitespace
                    wrapper.__doc__ += '\n' 
                if isinstance(returns, list):
                    width = max(len(q) for q in returns[0].keys())
                    wrapper.__doc__ += '\n    Returns list of dictionaries:\n\t[{\n'
                    wrapper.__doc__ += ''.join(['\t  %-*s: %s\n' % (width, p, returns[0][p]) for p in returns[0].keys()])
                    wrapper.__doc__ += '\t }, ...]\n'
                else:
                    width = max(len(q) for q in returns.keys())
                    wrapper.__doc__ += '\n    Returns dictionary:\n\t {\n'
                    wrapper.__doc__ += ''.join(['\t  %-*s: %s\n' % (width, p, returns[p]) for p in returns.keys()])
                    wrapper.__doc__ += '\t }\n'
            return wrapper
        return decorator

    @__api_request(required=['name'],
                   returns=[{u'name': 'Callsign of station',
                             u'type': 'a for AIS, l for APRS station, i for APRS item, o for APRS object, w for weather station',
                             u'time': 'timestamp of first report at this position',
                             u'lasttime': 'timestamp of last report at this position',
                             u'lat': 'latitude (decimal degrees, positive north)',
                             u'lng': 'longitude (decimal degrees, positive east)',
                             u'course': 'course over ground (COG), degrees',
                             u'speed': 'speed, km/h',
                             u'altitude': 'altitude, meters',
                             u'symbol': 'aprs symbol table and code',
                             u'srccall': 'source callsign',
                             u'dstcall': 'destination callsign',
                             u'comment': 'APRS comment field',
                             u'path': 'APRS or AIS packet path',
                             u'phg': 'APRS PHG value'}])
    def loc(self, request):
        """Returns a list of location objects for given callsign(s)."""
        pass

    @__api_request(required=['name'],
                   returns=[{u'name': 'Callsign of station',
                             u'temp': 'Temperature, degrees Celsius',
                             u'time': 'Timestamp of last weather report',
                             u'pressure': 'Atmospheric pressure, millibars',
                             u'humidity': 'Relative air humidity, percent',
                             u'wind_direction': 'Average wind direction, degrees',
                             u'wind_speed': 'Average wind speed, meters/sec',
                             u'wind_gust': 'Wind gust, meters/sec',
                             u'rain_1h': 'Rainfall over past hour, mm',
                             u'rain_24h': 'Rainfall over past day, mm',
                             u'rain_mn': 'Rainfall since midnight, mm',
                             u'luminosity': 'Luminosity, W/m^2'
                             }])
    def wx(self, request):
        """Returns a list of weather objects for given callsign(s)."""
        pass

