from shinymud.models.area import Area
from shinymud.models.room import Room
from shinymud.models.item import Item
from shinymud.models.npc import Npc
from shinymud.lib.world import World
from shinymud.data.config import AREAS_IMPORT_DIR, AREAS_EXPORT_DIR, VERSION

import os
import re
import logging
import simplejson as json

class SPort(object):
    """Export and import areas (and their objects) to a file."""
    def __init__(self):
        self.log = logging.getLogger('SPort')
        self.world = World.get_world()
        error = self.check_export_path()
        if error:
            return error
    
    def export_to_shiny(self, area):
        """Export an area to a text file in ShinyAreaFormat.
        area -- the area object to be exported
        """
        shiny_area = '[ShinyMUD Version "%s"]\n' % VERSION
        d = area.to_dict()
        del d['dbid']
        shiny_area += '\n[Area]\n' + json.dumps(d) + '\n[End Area]\n'
        
        s_list = []
        for script in area.scripts.values():
            d = script.to_dict()
            del d['dbid']
            s_list.append(d)
        shiny_area += '\n[Scripts]\n' + json.dumps(s_list) + '\n[End Scripts]\n'
        
        item_list = []
        itypes_list = []
        
        for item in area.items.values():
            d = item.to_dict()
            del d['dbid']
            item_list.append(d)
            for key,value in item.item_types.items():
                d = value.to_dict()
                d['item'] = item.id
                del d['dbid']
                d['item_type'] = key
                itypes_list.append(d)
        shiny_area += '\n[Items]\n' + json.dumps(item_list) + '\n[End Items]\n'
        shiny_area += '\n[Item Types]\n' + json.dumps(itypes_list) + '\n[End Item Types]\n'
        
        npc_list = []
        npc_elist = []
        
        for npc in area.npcs.values():
            d = npc.to_dict()
            del d['dbid']
            npc_list.append(d)
            for event in npc.events.values():
                d = event.to_dict()
                del d['dbid']
                d['prototype'] = npc.id
                d['script'] = event.script.id
                npc_elist.append(d)
        shiny_area += '\n[Npcs]\n' + json.dumps(npc_list) + '\n[End Npcs]\n'
        shiny_area += '\n[Npc Events]\n' + json.dumps(npc_elist) + '\n[End Npc Events]\n'
        
        r_list = []
        r_exits = []
        r_resets = {} # r_resets is a dictionary of lists of dictionaries!
        for room in area.rooms.values():
            d = room.to_dict()
            # d['room'] = room.id
            del d['dbid']
            r_list.append(d)
            r_resets[room.id] = []
            for exit in room.exits.values():
                if exit:
                    d = exit.to_dict()
                    d['room'] = room.id
                    d['to_id'] = exit.to_room.id
                    d['to_area'] = exit.to_room.area.name
                    d['to_room'] = None
                    del d['dbid']
                    r_exits.append(d)
            for reset in room.resets.values():
                d = reset.to_dict()
                r_resets[room.id].append(d)
        shiny_area += '\n[Rooms]\n' + json.dumps(r_list) + '\n[End Rooms]\n'
        shiny_area += '\n[Room Exits]\n' + json.dumps(r_exits) + '\n[End Room Exits]\n'
        shiny_area += '\n[Room Resets]\n' + json.dumps(r_resets) + '\n[End Room Resets]\n'
        
        return self.save_to_file(shiny_area, area.name + '.txt')
    
    def import_from_shiny(self, areaname):
        """Import an area from a text file in ShinyAreaFormat."""
        txt = self.get_import_data(areaname + '.txt')
        # Assemble the data structures from the file text
        area = json.loads(self.match_shiny_tag('Area', txt))
        scripts = json.loads(self.match_shiny_tag('Scripts', txt))
        items = json.loads(self.match_shiny_tag('Items', txt))
        itypes = json.loads(self.match_shiny_tag('Item Types', txt))
        npcs = json.loads(self.match_shiny_tag('Npcs', txt))
        npc_events = json.loads(self.match_shiny_tag('Npc Events', txt))
        rooms = json.loads(self.match_shiny_tag('Rooms', txt))
        room_exits = json.loads(self.match_shiny_tag('Room Exits', txt))
        room_resets = json.loads(self.match_shiny_tag('Room Resets', txt))
        # Build the area from the assembled dictionary data
        try:
            new_area = Area.create(**area)
            for script in scripts:
                new_area.new_script(script)
            for item in items:
                new_area.new_item(item)
            for itype in itypes:
                # Get this itype's item by that item's id
                my_item = new_area.get_item(itype['item'])
                my_item.add_type(itype['item_type'], itype)
            for npc in npcs:
                new_area.new_npc(npc)
            for event in npc_events:
                my_script = new_area.get_script(str(event['script']))
                event['script'] = my_script
                my_npc = new_area.get_npc(event['prototype'])
                my_npc.new_event(event)
            for room in rooms:
                new_room = new_area.new_room(room)
                my_resets = room_resets.get(new_room.id)
                if my_resets:
                    new_room.load_resets(my_resets)
            for exit in room_exits:
                self.log.debug(exit['room'])
                my_room = new_area.get_room(str(exit['room']))
                my_room.new_exit(**exit)
        except Exception, e:
            # if anything went wrong, make sure we destroy whatever parts of
            # the area that got created.  This way, we won't run into problems
            # if they try to import it again, and we won't leave orphaned or
            # erroneous data in the db.
            self.log.error(str(e))
            self.world.destroy_area(areaname, 'SPort Error')
            raise SPortImportError('There was a horrible error on import! '
                                   'Aborting! Check logfile for details.')
        
        return 'Area %s has been successfully imported.' % new_area.name
    
    def match_shiny_tag(self, tag, text):
        """Match a ShinyTag from the ShinyAreaFormat.
        tag -- the name of the tag you wish to match
        text -- the text to be searched for the tags
        Returns the string between the tag and its matching end-tag.
        Raises an exception if the tag is not found.
        """
        exp = r'\[' + tag + r'\](\n)?(?P<tag_body>.*?)(\n)?\[End ' + tag +\
              r'\](\n)?'
        match = re.search(exp, text, re.I | re.S)
        if not match:
            raise SPortImportError('Corrupted file: missing or malformed %s tag.' % tag)
        return match.group('tag_body')
    
    @classmethod
    def list_importable_areas(cls):
        if not os.path.exists(AREAS_IMPORT_DIR):
            return 'There are no area files in your import directory.'
        # Give the user a list of names of all the area files in their import directory
        # and trim off the .xml extension for readibility. Ignore all files that aren't xml
        # files
        alist = [area.replace('.txt', '') for area in os.listdir(AREAS_IMPORT_DIR) if area.endswith('.txt')]
        if alist:
            string = ' Available For Import '.center(50, '-')
            string += '\n' + '\n'.join(alist) + '\n' + ('-' * 50)
            return string
        else:
            return 'There are no area files in your import directory.'
    
    def check_export_path(self):
        """Make sure the path to the export directory exists. If it doesn't,
        create it and return an empty string. If there's an error, log it and
        return an error message."""
        if not os.path.exists(AREAS_EXPORT_DIR):
            try:
                os.mkdir(AREAS_EXPORT_DIR)
            except Exception, e:
                self.log.error('EXPORT FAILED: ' + str(e))
                # TODO: reraise an SPortExportError here...
                return 'Export failed; something went wrong accessing the export directory for areas.'
        return ''
    
    def get_import_data(self, filename):
        """Retrieve the area data from the file specified by filename.
        Raise an SPortImportError if the file doesn't exist or opening the file
        fails.
        filename -- the name of the file the area data should be read from
        """
        filepath = os.path.join(AREAS_IMPORT_DIR, filename)
        if not os.path.exists(filepath):
            raise SPortImportError('Error: %s does not exist.' % filename)
            
        try:
            f = open(filepath, 'r')
        except IOError, e:
            self.log.debug(str(e))
            raise SPortImportError('Error: opening the area file failed. '
                                   'Check the logfile for details.')
        else:
            area_txt = f.read()
        finally: 
            f.close()
            
        return area_txt
    
    def save_to_file(self, file_content, file_name):
        """Write out the file contents under the given file_name."""
        filepath = os.path.join(AREAS_EXPORT_DIR, file_name)
        try:
            f = open(filepath, 'w')
        except IOError, e:
            self.log.debug(str(e))
            raise SPExportError('Error writing your area to file. '
                                'Check the logfile for details')
        else:
            f.write(file_content)
        finally:
            f.close()
        return 'Export complete! Your area can be found at:\n%s' % filepath
    

class SPortImportError(Exception):
    """The umbrella exception for errors that occur during area import.
    """
    pass
    

class SPortExportError(Exception):
    """The umbrella exception for errors that occur during area export.
    """
    pass
        