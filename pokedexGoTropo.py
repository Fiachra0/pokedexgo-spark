import json
import db
import config
from datetime import datetime

import requests
from flask import Flask, render_template, request
from tropo import Tropo, Session

from spark.rooms import Room
from spark.session import Session
from spark.webhooks import Webhook
from spark.messages import Message

import geopy
from geopy.geocoders import Nominatim
import geopy.distance

API_KEY = config.API_KEY
SPARK_HEADERS = config.SPARK_HEADERS
BASE_URL = config.BASE_URL
SPARK_ROOM = config.SPARK_ROOM

with open('locales/pokemon.en.json') as f:
    pokemon_names = json.load(f)

def create_app():
    app = Flask(__name__, template_folder='templates')
    #initialize_sparkhook();
    return app

app= create_app()

@app.route('/')
def tropo_get():
  tropo_session = Tropo()
  tropo_session.say(["Really, it's that easy."])
  return  tropo_session.RenderJson()



#for dealing with default tropo requests
@app.route('/', methods=['POST'])
def tropo_post():
  tropo_session = Tropo()
  request_body = request.get_json(silent=True)
  initialText = request_body['session']['initialText']
  print initialText
  tropo_session.call(to="+14164730026", network = "SMS")
  tropo_session.say("You Texted: " + initialText)
  print  tropo_session.RenderJson()
  return tropo_session.RenderJson()

@app.route('/spark-ajax-rares', methods=['POST'])
def spark_post():
  request_body = request.get_json(silent=True)
  message_id =  request_body['data']['id']

  resp = get_message(message_id) 

  if "!nearby" in resp['text']:
	get_nearby_pokemon(resp)
  elif "!find" in resp['text']:
        get_pokemon_species(resp)
  elif "rare_pokemon_finder" in request_body['data']['personEmail']:
        cache_notification(resp)

  #print response
  return "requested"

def send_message(message, spark_room):
    spark_client = Session('https://api.ciscospark.com', API_KEY)
    try:
        spark_room = Room.get(spark_client, spark_room)
    except ValueError:
        exit("Could not Authenticate Key")
    spark_room.send_message(spark_client,message,'html')
    return "sent"

def get_message(message_id):
    resp = (requests.get(BASE_URL+'/messages/'+message_id, headers=SPARK_HEADERS)).json()
    return resp

def get_nearby_pokemon(message):
    message_text = str(message['text'].replace('!nearby','')).lower()
    message_text = message_text.replace("rare","")

    #reverse lookup for GPS coordinates based on address
    geolocator = Nominatim()
    location = geolocator.geocode(message_text)
    if not location:
       return send_message("Not an Address",SPARK_ROOM)
    origin_point = geopy.Point(location.latitude, location.longitude)

    #query db for recently seen pokemon
    session = db.Session()
    pokemons = db.get_sightings(session)
    session.close()

    found_pokemon = ""

    #search list for pokemon within 500m
    for pokemon in pokemons:
      remote_point = geopy.Point(pokemon.lat, pokemon.lon)
      if geopy.distance.distance(origin_point, remote_point).km < .5:
        latLon = '{},{}'.format(repr(pokemon.lat).strip("'"), repr(pokemon.lon).strip("'"))
        disappear_time = str(datetime.fromtimestamp(pokemon.expire_timestamp).strftime("%I:%M%p").lstrip('0'))
        found_pokemon += ("""<a href = 'http://maps.google.com/maps?q={latLon}'><b>{pokemon_name} </b></a>available until {disappear_time}
""").format(latLon=latLon, pokemon_name=(pokemon_names[str(pokemon.pokemon_id)]).title(),disappear_time=disappear_time)

    if found_pokemon:
      return send_message(found_pokemon,SPARK_ROOM)

    return send_message("Sorry, I cannot find anything.",SPARK_ROOM)




def get_pokemon_species(message):
    message_text = str(message['text'].replace('!find','')).lower()
    message_text = message_text.replace("rare","")


    for pokedex_number, pokemon_name in pokemon_names.items():
        if  str(message['text']) in pokedex_number or pokemon_name.lower() in str(message['text']).lower():
             #query db for recently seen pokemon
    	     session = db.Session()
             pokemons = db.get_sightings_species(session,pokedex_number)
             session.close()
             break
        else:
	     pokemons = []

    found_pokemon = ""

    for pokemon in pokemons:
	latLon = '{},{}'.format(repr(pokemon.lat).strip("'"), repr(pokemon.lon).strip("'"))
        disappear_time = str(datetime.fromtimestamp(pokemon.expire_timestamp).strftime("%I:%M%p").lstrip('0'))
        found_pokemon += ("""<a href = 'http://maps.google.com/maps?q={latLon}'><b>{pokemon_name} </b></a>available until {disappear_time}
""").format(latLon=latLon, pokemon_name=(pokemon_names[str(pokemon.pokemon_id)]).title(),disappear_time=disappear_time)

    if found_pokemon:
      return send_message(found_pokemon,SPARK_ROOM)

    return send_message("Sorry, Can't find anything.",SPARK_ROOM)






def cache_notification(message):
    return "we cached it"


if __name__ == '__main__':
    args = get_args()
    initialize_sparkhook()
    app.run(threaded=True)
