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

def menu(country=None):
    if country in ["212"]:
        return "Bienvenue dans le service de meteo. Nous vous remercions de nous avoir fait confiance dans la prestation de votre meteo quotidienne."
    elif country in ["34"]:
        return "Bienvenido al servicio de mensajeria. Gracias por confiar en nosotros en la entrega de sus noticias diarias."
    elif country in ["33", "226", "227"]:
        return "Bienvenue dans le service de meteo. Nous vous remercions de nous avoir fait confiance dans la prestation de votre meteo quotidienne."
    else:
        return "Welcome to the Weather Messaging Service. Thank you for trusting us in delivering your daily weather alerts."

def get_country(country):
    r = requests.get('http://54.196.141.56:5300/sms/services/sso/v0.1/users/countries')
    response = json.loads(r.text)
    for cnt in response['content']['countries']:
        if int(cnt["code"]) == int(country):
            return cnt
    return None

def get_one_number(country):
    r = requests.get('http://54.196.141.56:5300/sms/services/sso/v0.1/users/country/{0}'.format(country))
    response = json.loads(r.text)
    return response['content']['users'][0]['phone']

def get_cities(country):
    r = requests.get('http://54.196.141.56:5300/sms/services/sso/v0.1/users/cities/{0}'.format(country))
    response = json.loads(r.text)
    return [c['name'] for c in response['content']['cities']]

def get_weather_old(city, country):
    r = requests.get('http://54.196.141.56:5300/sms/services/sso/v0.1/users/cities/{0}'.format(country))
    response = json.loads(r.text)
    return [c['name'] for c in response['content']['cities']]

def fetch_city(city, country):
    r = requests.get('http://autocomplete.wunderground.com/aq?query={0}&c={1}'.format(city, country))
    response = json.loads(r.text)
    results = response["RESULTS"]
    if len(results) == 0:
        return None
    else:
        return {"name":results[0]["name"].split(',')[0], "zmw":results[0]["zmw"]}
    return [c['name'] for c in response['content']['cities']], response['content']['language']

def get_weather(city, country):
    tomorrow = {"title":"", "day":"", "night":""}
    fetched = fetch_city(city, country)
    if fetched:
        # r = requests.get('http://api.openweathermap.org/data/2.5/forecast?q={0},{1}&appid=eb7cda08edf98390707005f5cbde3fe6'.format(city, country))
        r = requests.get('http://api.wunderground.com/api/d62a84b41d6cee51/forecast/q/zmw:{0}.json'.format(fetched["zmw"]))
        response = json.loads(r.text)
        threedays = response["forecast"]["txt_forecast"]["forecastday"]
        for threeday in threedays:
            if threeday["period"] == 2:
                tomorrow["day"] = threeday["fcttext_metric"]
                tomorrow["title"] = "The weather tomorrow {0} in {1}, {2}".format(threeday["title"], city, country)
            if threeday["period"] == 3:
                tomorrow["night"] = threeday["fcttext_metric"]
                break
    return tomorrow

# import all the api endpoints.
import weather.endpoints
