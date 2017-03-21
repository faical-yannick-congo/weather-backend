"""CoRR api module."""
import flask as fk
from weatherdb.common.core import setup_app
from weatherdb.common.models import Weather
import tempfile
from io import StringIO
from io import BytesIO
import os
import simplejson as json
import datetime
import traceback

import requests
from datetime import date, timedelta
from functools import update_wrapper
from calendar import monthrange
import time

import glob

# Flask app instance
app = setup_app(__name__)

# The sms weather service's version
SERVICE_VERSION = 0.1
# The sms weather service base url
SERVICE_URL = '/sms/services/weather/v{0}'.format(SERVICE_VERSION)


def service_response(code, title, content):
    """Provides a common structure to represent the response
    from any api's endpoints.
        Returns:
            Flask response with a prettified json content.
    """
    import flask as fk
    response = {'service':'sms-weather', 'code':code, 'title':title, 'content':content}
    return fk.Response(json.dumps(response, sort_keys=True, indent=4, separators=(',', ': ')), mimetype='application/json')

def data_pop(data=None, element=''):
    """Pop an element of a dictionary.
    """
    if data != None:
        try:
            del data[element]
        except:
            pass

def merge_dicts(*dict_args):
    """
    Given any number of dicts, shallow copy and merge into a new dict,
    precedence goes to key value pairs in latter dicts.
    """
    result = {}
    for dictionary in dict_args:
        result.update(dictionary)
    return result

def menu():
    return "Welcome to the Weather Messaging Service. Thank you for trusting us in delivering your daily weather alerts."

def get_one_number(country):
    r = requests.get('http://54.196.141.56:5300/sms/services/sso/v0.1/users/country/{0}'.format(country))
    response = json.loads(r.text)
    return response['content']['users'][0]['phone']

def get_cities(country):
    r = requests.get('http://54.196.141.56:5300/sms/services/sso/v0.1/users/cities/{0}'.format(country))
    response = json.loads(r.text)
    return [c['name'] for c in response['content']['cities']], response['content']['language']

def get_weather(city, country):
    r = requests.get('http://api.openweathermap.org/data/2.5/forecast?q={0},{1}&appid=eb7cda08edf98390707005f5cbde3fe6'.format(city, country))
    response = json.loads(r.text)
    return response

# import all the api endpoints.
import weather.endpoints
