import time


from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String


try:
    import config
    DB_ENGINE = config.DB_ENGINE
except ImportError, AttributeError:
    DB_ENGINE = 'sqlite:///db.sqlite'

def alchemyencoder(obj):
    """JSON encoder function for SQLAlchemy special classes."""
    if isinstance(obj, datetime.date):
        return obj.isoformat()
    elif isinstance(obj, decimal.Decimal):
        return float(obj)

def get_engine():
    return create_engine(DB_ENGINE)

Base = declarative_base()


class Sighting(Base):
    __tablename__ = 'sightings'

    id = Column(Integer, primary_key=True)
    pokemon_id = Column(Integer)
    spawn_id = Column(String(32))
    expire_timestamp = Column(Integer)
    normalized_timestamp = Column(Integer)
    lat = Column(String(16))
    lon = Column(String(16))


Session = sessionmaker(bind=get_engine())


def normalize_timestamp(timestamp):
    return int(float(timestamp) / 120.0) * 120


def add_sighting(session, spawn_id, pokemon):
    obj = Sighting(
        pokemon_id=pokemon['id'],
        spawn_id=spawn_id,
        expire_timestamp=pokemon['disappear_time'],
        normalized_timestamp=normalize_timestamp(pokemon['disappear_time']),
        lat=pokemon['lat'],
        lon=pokemon['lng'],
    )
    # Check if there isn't the same entry already
    existing = session.query(Sighting) \
        .filter(Sighting.pokemon_id == obj.pokemon_id) \
        .filter(Sighting.spawn_id == obj.spawn_id) \
        .filter(Sighting.expire_timestamp > obj.expire_timestamp - 10) \
        .filter(Sighting.expire_timestamp < obj.expire_timestamp + 10) \
        .filter(Sighting.lat == obj.lat) \
        .filter(Sighting.lon == obj.lon) \
        .first()
    if existing:
        return
    session.add(obj)
    notifier.pokemon_found(obj)

def get_sightings(session):
    return session.query(Sighting) \
        .filter(Sighting.expire_timestamp > time.time()) \
        .all()

def get_sightings_species(session,pokedex_id):
    return session.query(Sighting) \
         .filter(Sighting.pokemon_id == pokedex_id) \
         .filter(Sighting.expire_timestamp > time.time()) \
         .all()

def get_pokemon_history(session, pokedex_entry):
    return session.query(Sighting) \
	.filter(Sighting.pokemon_id == pokedex_entry) \
	.order_by(Sighting.expire_timestamp) \
	.limit(400) 

def get_session_stats(session):
    min_max_query = session.execute('''
        SELECT
            MIN(expire_timestamp) ts_min,
            MAX(expire_timestamp) ts_max,
            COUNT(*)
        FROM `sightings`;
    ''')
    min_max_result = min_max_query.first()
    length_hours = (min_max_result[1] - min_max_result[0]) // 3600
    # Convert to datetime
    return {
        'start': datetime.fromtimestamp(min_max_result[0]),
        'end': datetime.fromtimestamp(min_max_result[1]),
        'count': min_max_result[2],
        'length_hours': length_hours,
        'per_hour': min_max_result[2] / length_hours,
    }

def get_nonexistent_pokemon(session):
    result = []
    query = session.execute('SELECT DISTINCT pokemon_id FROM sightings')
    db_ids = [r[0] for r in query.fetchall()]
    for pokemon_id in range(1, 152):
        if pokemon_id not in db_ids:
            result.append(pokemon_id)
    return result

def get_top_pokemon(session, count=30, order='DESC',order_by='how_many'):
    query = session.execute("SELECT pokemon_id, COUNT(*) how_many FROM sightings GROUP BY pokemon_id ORDER BY {order_by} {order} LIMIT {count}".format(order=order, count=count, order_by=order_by))
    pokemons = [dict(r) for r in query.fetchall()]
    return pokemons

def get_common_spawns(session, count=100, order='DESC'):
    query = session.execute(u'''
        SELECT lat, lon, count(*) how_many
	FROM sightings
	GROUP BY lat,lon
	ORDER BY how_many {order}
	LIMIT {count};
    '''.format(order=order, count=count))
    pokemons = [dict(r) for r in query.fetchall()]
    return pokemons

def get_pokemon_spawned_at(session, lat, lon):
    query = session.execute(u"""
        SELECT pokemon_id, count(*) how_many
	FROM sightings
	WHERE lat = '{lat}' AND lon ='{lon}'
	GROUP BY pokemon_id;
    """.format(lat=lat, lon=lon))
    pokemons = [dict(r) for r in query.fetchall()]
    return pokemons

def get_common_pokemon_spawns(session, pokemon_id, order='DESC',count=100):
    query = session.execute('SELECT pokemon_id, lat, lon, count(*) how_many FROM sightings where pokemon_id = {pokemon_id} GROUP BY lat, lon ORDER BY how_many {order} LIMIT {count};'.format(pokemon_id=pokemon_id, order=order, count=count))
    pokemons = [dict(r) for r in query.fetchall()]
    return pokemons

