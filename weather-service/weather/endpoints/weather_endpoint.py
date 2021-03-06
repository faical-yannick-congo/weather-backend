import simplejson as json

from flask.ext.api import status
import flask as fk

from weatherdb.common import crossdomain
from weather import app, SERVICE_URL, service_response, get_country, get_weather, get_one_number, get_cities, menu
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
from translate import Translator

@app.route(SERVICE_URL + '/menu', methods=['GET','POST','PUT','UPDATE','DELETE'])
@crossdomain(fk=fk, app=app, origin='*')
def service_menu():
    if fk.request.method == 'GET':
        return service_response(200, 'Service Menu', menu())
    else:
        return service_response(405, 'Method not allowed', 'This endpoint supports only a GET method.')

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
            weathers = [c.info() for c in Weather.objects(city=city.lower(), country=country)]
        return service_response(200, 'City: {0} of Country: {1} weather history'.format(city.lower(), country), {'size':len(weathers), 'history':weathers})
    else:
        return service_response(405, 'Method not allowed', 'This endpoint supports only a GET method.')

@app.route(SERVICE_URL + '/today/<country>/<city>', methods=['GET','POST','PUT','UPDATE','DELETE'])
@crossdomain(fk=fk, app=app, origin='*')
def weather_today_city(country, city):
    if fk.request.method == 'GET':
        _country = get_country(country)
        if _country is None:
            return service_response(204, 'Unknown country', 'We could not find this country.')
        else:
            lat = _country["lat"]
            lng = _country["lng"]
            if lat == "":
                lat = 0.00
                lng = 0.00
            tz = tzwhere.tzwhere()
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
                weathers = [c.info() for c in Weather.objects(day=day, city=city.lower(), country=country)]
            return service_response(200, 'City: {0} of Country: {1} weather today: {2}'.format(city.lower(), country, day), {'size':len(weathers), 'today':weathers})
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
        _country = get_country(country)
        if _country is None:
            return service_response(204, 'Unknown country', 'We could not find this country.')
        else:
            lat = _country["lat"]
            lng = _country["lng"]
            if lat == "":
                lat = 0.00
                lng = 0.00
            tz = tzwhere.tzwhere()
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
            pn = phonenumbers.parse(get_one_number(country), None)
            country_code = str(pn.country_code)
            _country_name_short = region_code_for_country_code(pn.country_code)

            if city == 'all':
                cities, language = get_cities(country)
            else:
                ignore, language = get_cities(country)
                cities = [city]

            if country_hour == 21: # We push the sync
                cities_to_sync = []
                for city in cities:
                    check_weather = Weather.objects(country=country, city=city.lower().replace(" ", "-"), day=next_day).first()
                    if check_weather is None:
                        cities_to_sync.append(city.lower().replace(" ", "-"))
                if len(cities_to_sync) == 0:
                    return service_response(204, 'Weather synched already', 'The weather for country: {0} and city: {1} is already synched.'.format(country, city))
                unknown_cities = []
                for city in cities_to_sync:
                    pred_weather = get_weather(city.lower(), _country_name_short)
                    try:
                        if pred_weather['title'] == "":
                            unknown_cities.append(city.lower())
                        else:
                            _weather = Weather(created_at=str(datetime.datetime.utcnow()), country=country, city=city.lower(), day=next_day)
                            if language not in ['en', 'unknown']:
                                translator = Translator(to_lang=language)
                                _data = {'title':translator.translate(pred_weather['title'])}
                                _data['day'] = translator.translate("During the day: {0}".format(pred_weather['day']))
                                _data['night'] = translator.translate("During the night: {0}".format(pred_weather['night']))
                                _weather.predictions = _data
                            else:
                                _weather.predictions = pred_weather
                                _data = {'title':pred_weather['title']}
                                _data['day'] = "During the day: {0}".format(pred_weather['day'])
                                _data['night'] = "During the night: {0}".format(pred_weather['night'])
                                _weather.predictions = _data
                            _weather.save()

                        # if pred_weather['city']['name'].lower() == city.lower():
                        #     _weather = Weather(created_at=str(datetime.datetime.utcnow()), country=country, city=city.lower(), day=next_day)
                        #     predictions = {'03:00:00':{}, '06:00:00':{}, '09:00:00':{}, '12:00:00':{}, '15:00:00':{}, '18:00:00':{}, '21:00:00':{}, '00:00:00':{}}
                        #
                        #     for pred in pred_weather['list']:
                        #         for hour, val in predictions.items():
                        #             filterer = "{0} {1}".format(next_day, hour)
                        #             if pred["dt_txt"] == filterer:
                        #                 clim_content = ', '.join([w["description"] for w in pred["weather"]])
                        #                 if language not in ['en', 'unknown']:
                        #                     translator = Translator(to_lang=language)
                        #                     clim_content = translator.translate(clim_content)
                        #                 # Use the language here later to translate directly the news.
                        #                 predictions[hour]['climate'] = clim_content
                        #                 predictions[hour]['humidity'] = "{0} %".format(pred["main"]["humidity"])
                        #                 predictions[hour]['temp-min'] = "{0} C".format(str(pytemperature.k2c(pred["main"]["temp_min"])).split('.')[0])
                        #                 predictions[hour]['temp-max'] = "{0} C".format(str(pytemperature.k2c(pred["main"]["temp_max"])).split('.')[0])
                        #                 break
                        #     _weather.predictions = predictions
                        #     _weather.save()
                        # else:
                        #     unknown_cities.append(city.lower())
                    except:
                        unknown_cities.append(city.lower())
                data = {'unknown-cities':unknown_cities, 'country-cities':cities, 'cities-to-sync':cities_to_sync}
                data['country'] = country_code
                translator = Translator(to_lang=language)
                data['message'] = translator.translate('Weather in () tomorrow:')
                data['country_code'] = _country_name_short
                return service_response(200, 'Weather sync done.', data)
            else:
                return service_response(204, 'Weather not synched', 'It is not yet time to sync weather. country-time:{0}'.format(country_time))
    else:
        return service_response(405, 'Method not allowed', 'This endpoint supports only a GET method.')


@app.route(SERVICE_URL + '/prediction/pushing/<country>/<city>', methods=['GET','POST','PUT','UPDATE','DELETE'])
@crossdomain(fk=fk, app=app, origin='*')
def weather_pushing_country(country, city):
    if fk.request.method == 'GET':
        _country = get_country(country)
        if _country is None:
            return service_response(204, 'Unknown country', 'We could not find this country.')
        else:
            lat = _country["lat"]
            lng = _country["lng"]
            if lat == "":
                lat = 0.00
                lng = 0.00
            tz = tzwhere.tzwhere()
            timeZoneStr = tz.tzNameAt(lat, lng)
            timeZoneObj = timezone(timeZoneStr)
            now_time = datetime.datetime.now(timeZoneObj)
            day = str(now_time).split(" ")[0]
            date = datetime.datetime.strptime(day, "%Y-%m-%d")
            next_date = date + datetime.timedelta(days=1)
            next_day = datetime.datetime.strftime(next_date, "%Y-%m-%d")

            weather_pulled = Weather.objects(city=city.lower(), country=country, status='pulled', day=next_day).first()

            if weather_pulled:
                weather_pulled.status = 'pushing'
                weather_pulled.save()
                ignore, language = get_cities(country)
                weather_pushing = weather_pulled.info()
                translator = Translator(to_lang=language)
                return service_response(200, translator.translate('Weather in () tomorrow {0}:'.format(next_day)), weather_pushing)
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
