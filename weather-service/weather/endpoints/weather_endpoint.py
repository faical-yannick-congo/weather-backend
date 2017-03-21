import simplejson as json

from flask.ext.api import status
import flask as fk

from weatherdb.common import crossdomain
from weather import app, SERVICE_URL, service_response, get_weather, get_one_number, get_cities
from weatherdb.common.models import Weather
from time import gmtime, strftime

import mimetypes
import traceback
import datetime
import random
import string
from io import StringIO
import hashlib
import phonenumbers
from phonenumbers.phonenumberutil import region_code_for_country_code
from phonenumbers.phonenumberutil import region_code_for_number
import pycountry

from geopy import geocoders
from tzwhere import tzwhere
from pytz import timezone
import pytemperature

@app.route(SERVICE_URL + '/history/<country>/<city>', methods=['GET','POST','PUT','UPDATE','DELETE'])
@crossdomain(fk=fk, app=app, origin='*')
def weather_by_city(country, city):
    if fk.request.method == 'GET':
        if city == 'all':
            if country == 'all':
                weathers = [c.info() for c in Weather.objects()]
            else:
                weathers = [c.info() for c in Weather.objects(country=country)]
        else:
            weathers = [c.info() for c in Weather.objects(city=city, country=country)]
        return service_response(200, 'City: {0} of Country: {1} weather history'.format(city, country), {'size':len(weathers), 'history':weathers})
    else:
        return service_response(405, 'Method not allowed', 'This endpoint supports only a GET method.')

@app.route(SERVICE_URL + '/today/<country>/<city>', methods=['GET','POST','PUT','UPDATE','DELETE'])
@crossdomain(fk=fk, app=app, origin='*')
def weather_today_city(country, city):
    if fk.request.method == 'GET':
        pn = phonenumbers.parse(get_one_number(country), None)
        _country_object = pycountry.countries.get(alpha_2=region_code_for_number(pn))
        g = geocoders.GoogleV3()
        tz = tzwhere.tzwhere()
        place, (lat, lng) = g.geocode(_country_object.name)
        timeZoneStr = tz.tzNameAt(lat, lng)
        timeZoneObj = timezone(timeZoneStr)
        now_time = datetime.datetime.now(timeZoneObj)
        day = str(now_time).split(" ")[0]
        if city == 'all':
            if country == 'all':
                weathers = [c.info() for c in Weather.objects(day=day)]
            else:
                weathers = [c.info() for c in Weather.objects(day=day, country=country)]
        else:
            weathers = [c.info() for c in Weather.objects(day=day, city=city, country=country)]
        return service_response(200, 'City: {0} of Country: {1} weather today: {2}'.format(city, country, day), {'size':len(weathers), 'today':weathers})
    else:
        return service_response(405, 'Method not allowed', 'This endpoint supports only a GET method.')

@app.route(SERVICE_URL + '/prediction/delete/<weather_id>', methods=['GET','POST','PUT','UPDATE','DELETE'])
@crossdomain(fk=fk, app=app, origin='*')
def delete_weather(weather_id):
    if fk.request.method == 'GET':
        _weather = Weather.objects.with_id(weather_id)
        if _weather:
            _weather.delete()
            return service_response(200, 'Deletion succeeded', 'Weather {0} deleted.'.format(weather_id))
        else:
            return service_response(204, 'Unknown weather', 'No corresponding weather found.')
    else:
        return service_response(405, 'Method not allowed', 'This endpoint supports only a GET method.')

@app.route(SERVICE_URL + '/prediction/sync/<country>/<city>', methods=['GET','POST','PUT','UPDATE','DELETE'])
@crossdomain(fk=fk, app=app, origin='*')
def sync_cover(country, city):
    if fk.request.method == 'GET':
        pn = phonenumbers.parse(get_one_number(country), None)
        _country_object = pycountry.countries.get(alpha_2=region_code_for_number(pn))
        g = geocoders.GoogleV3()
        tz = tzwhere.tzwhere()
        place, (lat, lng) = g.geocode(_country_object.name)
        timeZoneStr = tz.tzNameAt(lat, lng)
        timeZoneObj = timezone(timeZoneStr)
        now_time = datetime.datetime.now(timeZoneObj)
        day = str(now_time).split(" ")[0]
        date = datetime.datetime.strptime(day, "%Y-%m-%d")
        next_date = date + datetime.timedelta(days=1)
        next_day = datetime.datetime.strftime(next_date, "%Y-%m-%d")
        if "-" in str(now_time).split(" ")[1]:
            country_time = str(now_time).split(" ")[1].split("-")[0]
        if "+" in str(now_time).split(" ")[1]:
            country_time = str(now_time).split(" ")[1].split("+")[0]
        country_hour = int(country_time.split(":")[0])
        country_code = str(pn.country_code)

        if city == 'all':
            cities = get_cities(country)
        else:
            cities = [city]

        if country_hour == 13: # We push the sync
            cities_to_sync = []
            for city in cities:
                check_weather = Weather.objects(country=country, city=city, day=next_day).first()
                if check_weather is None:
                    cities_to_sync.append(city)
            if len(cities_to_sync) == 0:
                return service_response(200, 'Weather synched already', 'The weather for country: {0} and city: {1} is already synched.'.format(country, city))
            predictions = []
            unknown_cities = []
            for city in cities_to_sync:
                pred_weather = get_weather(city, country_code)
                try:
                    if pred_weather['city']['name'] == city:
                        _weather = Weather(created_at=str(datetime.datetime.utcnow()), country=country, city=city, day=next_day)
                        predictions = {'6:00:00':{}, '9:00:00':{}, '12:00:00':{}, '15:00:00':{}, '18:00:00':{}, '21:00:00':{}, '00:00:00':{}}

                        for pred in pred_weather['list']:
                            for hour, val in enumerate(predictions):
                                filterer = "{0} {1}".format(next_day, hour)
                                if pred["dt_txt"] == filterer:
                                    predictions[hour]['climate'] = pred["weather"]["description"]
                                    predictions[hour]['humidity'] = "{0}%".format(pred["main"]["humidity"])
                                    predictions[hour]['temp-min'] = "{0}C".format(pytemperature.k2c(pred["main"]["temp_min"]))
                                    predictions[hour]['temp-max'] = "{0}C".format(pytemperature.k2c(pred["main"]["temp_max"]))
                                    break
                        _weather.predictions = predictions
                        _weather.save()
                    else:
                        unknown_cities.append(city)
                except:
                    unknown_cities.append(city)
            data = {'unknown-cities':unknown_cities, 'country-cities':cities, 'cities-to-sync':cities_to_sync}
            data['country'] = country_code
            return service_response(200, 'Weather sync done.', data)
        else:
            return service_response(204, 'Weather not synched', 'It is not yet time to sync weather. country-time:{0}'.format(country_time))
    else:
        return service_response(405, 'Method not allowed', 'This endpoint supports only a GET method.')


@app.route(SERVICE_URL + '/prediction/pushing/<country>/<city>', methods=['GET','POST','PUT','UPDATE','DELETE'])
@crossdomain(fk=fk, app=app, origin='*')
def weather_pushing_country(country, city):
    if fk.request.method == 'GET':
        pn = phonenumbers.parse(get_one_number(country), None)
        _country_object = pycountry.countries.get(alpha_2=region_code_for_number(pn))
        g = geocoders.GoogleV3()
        tz = tzwhere.tzwhere()
        place, (lat, lng) = g.geocode(_country_object.name)
        timeZoneStr = tz.tzNameAt(lat, lng)
        timeZoneObj = timezone(timeZoneStr)
        now_time = datetime.datetime.now(timeZoneObj)
        day = str(now_time).split(" ")[0]

        weather_pulled = Weather.objects(city=city, country=country, status='pulled', day=day).first()

        if weather_pulled:
            weather_pulled.satus = 'pushing'
            weather_pulled.save()
            weather_pushing = weather_pulled.info()
            return service_response(200, 'Weather to send', weather_pushing.info())
        else:
            return service_response(204, 'No weather to send', "no weather at this point.")
    else:
        return service_response(405, 'Method not allowed', 'This endpoint supports only a GET method.')

@app.route(SERVICE_URL + '/prediction/pushed/<weather_id>', methods=['GET','POST','PUT','UPDATE','DELETE'])
@crossdomain(fk=fk, app=app, origin='*')
def pushed_weather(weather_id):
    if fk.request.method == 'GET':
        _weather = Weather.objects.with_id(weather_id)
        if _weather:
            _weather.status = 'pushed'
            _weather.save()
            return service_response(200, 'Weather pushed', 'Weather {0} was confimed pushed.'.format(weather_id))
        else:
            return service_response(204, 'Unknown weather', 'No corresponding weather found.')
    else:
        return service_response(405, 'Method not allowed', 'This endpoint supports only a GET method.')
