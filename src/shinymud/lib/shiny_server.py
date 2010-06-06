from shinymud.lib.world import World
# Initialize the World
world = World()
from shinymud.lib.connection_handler import ConnectionHandler
from shinymud.lib.statsender import StatSender
from shinymud.lib.setup import initialize_database
from shinymud.models.area import Area
from shinymud.data.config import *

import traceback
import datetime

initialize_database()
world.db.delete('from game_item where (owner is null or owner=\'None\') and container is null')

# load the entities in the world from the database
# This should probably happen inside the world itself...
for area in world.db.select("* from area"):
    world.area_add(Area.create(area))
for area in world.areas.values():
    area.load()

world.default_location = world.get_location(DEFAULT_LOCATION[0],
                                            DEFAULT_LOCATION[1])
# Start listening for connections on a different thread
conn_handler = ConnectionHandler(PORT, HOST, world)
conn_handler.start()

if STATS_ENABLED:
    stat_sender = StatSender(STATS_PORT, HOST, world)
    stat_sender.start()

world.log.info('Started the connection handler. Now listening for Players.')
world.log.debug('The world is about to start turning.')
try:
    world.start_turning()
except:
    with open(ROOT_DIR + "/logs/death_errors.log", 'w') as fp:
        fp.write('\n' + (str(datetime.datetime.today())).center(50, '*') + '\n')
        traceback.print_exc(file=fp)
        fp.write('\n' + ('*' * 50))
    world.log.critical('OH NOES! The server died! More information in the death_errors.log.')
    player_error = "Bloody hell, the game server crashed!\n" +\
    "Don't worry, we've done our best to save your data.\n" +\
    "Try logging on again in a minute or two.\r\n"
    for player in world.player_list.values():
        player.conn.send(player_error)
