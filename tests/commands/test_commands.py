from shinymud.lib.world import *
from shinymud.models.area import *
from shinymud.data.config import *
from shinymud.models.player import *
from shinymud.commands import *
from unittest import TestCase
from shinymud.lib.db import DB
from shinymud.models.schema import initialize_database

# Test all of the general commands!

class TestGeneralCommands(TestCase):
    def setUp(self):
        self.world = World()
        self.world.db = DB(':memory:')
        initialize_database(self.world.db.conn)
    
    def tearDown(self):
        World._instance = None
    
    def test_command_register(self):
        cmds = CommandRegister()
        self.assertEqual(cmds['supercalifragilisticexpieladocious'], None, 
                    "Command Register is returning things it doesn't have!")
        cmds.register((lambda : 3), ['bob', 'sam'])
        self.assertEqual(cmds['bob'](), 3, 
                         "Registered command 'bob' returned wrong value.")
        self.assertEqual(cmds['sam'](), 3,
                         "Registered command 'sam' returned wrong value.")
        self.assertEqual(cmds['bob'], cmds['sam'],
                         "Registered aliases 'bob' and 'sam' did not return same function.")
    
    def test_chat_command(self):
        bob = Player(('bob', 'bar'))
        alice = Player(('alice', 'bar'))
        sam = Player(('sam', 'bar'))
        bob.mode = None
        bob.playerize(name='bob')
        bob.outq = []
        sam.mode = None
        sam.playerize(name='sam')
        sam.outq = []
        self.world.player_add(bob)
        self.world.player_add(sam)
        self.world.player_add(alice)
        
        Chat(bob, 'lol, hey guys!', 'chat').run()
        chat = chat_color + 'Bob chats, "lol, hey guys!"' + clear_fcolor + '\r\n'
        self.assertTrue(chat in sam.outq)
        self.assertTrue(chat in bob.outq)
        self.assertFalse(chat in alice.outq)
        
        sam.channels['chat'] = False
        sam.outq = []
        bob.outq = []
        alice.outq = []
        
        Chat(bob, 'lol, hey guys!', 'chat').run()
        self.assertFalse(chat in sam.outq)
        self.assertTrue(chat in bob.outq)
        self.assertFalse(chat in alice.outq)
    
    def test_give_command(self):
        area = Area.create('blarg')
        room = area.new_room()
        bob = Player(('bob', 'bar'))
        bob.mode = None
        bob.playerize(name='bob')
        alice = Player(('alice', 'bar'))
        alice.mode = None
        alice.playerize(name='alice')
        self.world.player_add(bob)
        self.world.player_add(alice)
        
        room.player_add(bob)
        room.player_add(alice)
        alice.location = room
        bob.location = room
        proto_npc = area.new_npc()
        npc = proto_npc.load()
        room.npc_add(npc)
        
        item = area.new_item()
        item.set_keywords('bauble', bob)
        item.set_name('a bauble', bob)
        bob.item_add(item.load())
        
        self.assertEqual(len(bob.inventory), 1)
        Give(bob, 'bauble to alice', 'give').run()
        self.assertEqual(len(bob.inventory), 0)
        self.assertEqual(len(alice.inventory), 1)
        to_alice = 'Bob gives you a bauble.\r\n'
        self.assertTrue(to_alice in alice.outq)
        to_bob = 'You give a bauble to Alice.\r\n'
        self.assertTrue(to_bob in bob.outq)
        
        Give(alice, 'bauble to shiny', 'give').run()
        self.assertEqual(len(alice.inventory), 0)
        self.assertEqual(len(npc.inventory), 1)
        to_alice = 'You give a bauble to %s.\r\n' % npc.name
        alice.log.debug(alice.outq)
        self.assertTrue(to_alice in alice.outq)
        to_shiny = 'Alice gives you a bauble.'
        self.assertTrue(to_shiny in npc.actionq)
    
    def test_set_command(self):
        bob = Player(('bob', 'bar'))
        bob.mode = None
        bob.playerize(name='bob')
        
        # Test setting e-mail
        Set(bob, 'email bob@bob.com', 'set').run()
        self.assertEqual('bob@bob.com', bob.email)
        
        # Test setting title
        Set(bob, 'title is the best EVAR', 'set').run()
        self.assertEqual('is the best EVAR', bob.title)
        
        # Try to set goto_appear and goto_disappear (both should fail
        # since this player shouldn't have permissions)
        Set(bob, 'goto_appear Bob pops in from nowhere.', 'set').run()
        eresult = 'You don\'t have the permissions to set that.\r\n'
        self.assertTrue(eresult in bob.outq)
        bob.outq = []
        Set(bob, 'goto_disappear foo', 'set').run()
        self.assertTrue(eresult in bob.outq)
        
        bob.permissions = bob.permissions | BUILDER
        
        # Try to set goto_appear and goto_disappear (both should now
        # succeed now that the player has adequate permissions)
        Set(bob, 'goto_appear Bob pops in from nowhere.', 'set').run()
        self.assertEqual('Bob pops in from nowhere.', bob.goto_appear)
        bob.outq = []
        Set(bob, 'goto_disappear foo', 'set').run()
        self.assertEqual('foo', bob.goto_disappear)
    
    def test_goto_command(self):
        blarg_area = Area.create('blarg')
        foo_area = Area.create('foo')
        blarg_room = blarg_area.new_room()
        foo_room = foo_area.new_room()
        bob = Player(('bob', 'bar'))
        bob.mode = None
        bob.playerize(name='bob')
        self.world.player_add(bob)
        bob.permissions = bob.permissions | BUILDER
        generic_fail = 'Type "help goto" for help with this command.\r\n'
        
        # We should fail if we only specify a room number when we aren't in
        # an area 
        Goto(bob, '%s' % foo_room.id, 'goto').run()
        self.assertEqual(bob.location, None)
        bob.log.debug(bob.outq)
        self.assertTrue(generic_fail in bob.outq)
        
        # We should fail if we try to go to a room in an area that doesn't 
        # exist
        message = 'Area "food" doesn\'t exist.\r\n'
        Goto(bob, '1 food', 'goto').run()
        self.assertEqual(bob.location, None)
        bob.log.debug(bob.outq)
        self.assertTrue(message in bob.outq)
        
        # We should fail if we try to go to a room that doesn't exist (in an
        # area that does)
        message = 'Room "4005" doesn\'t exist in area blarg.\r\n'
        Goto(bob, '4005 blarg', 'goto').run()
        self.assertEqual(bob.location, None)
        bob.log.debug(bob.outq)
        self.assertTrue(message in bob.outq)
        
        # We should succeed in going to a room and area that exists
        Goto(bob, '%s %s' % (foo_room.id, foo_room.area.name), 'goto').run()
        self.assertEqual(bob.location, foo_room)
        
        Goto(bob, '%s %s' % (blarg_room.id, blarg_room.area.name), 'goto').run()
        self.assertEqual(bob.location, blarg_room)
        
        blarg_r2 = blarg_area.new_room()
        Goto(bob, '%s' % (blarg_r2.id), 'goto').run()
        self.assertEqual(bob.location, blarg_r2)
        
        # We should get a help message if there is only white space given
        bob.outq = []
        Goto(bob, '   ', 'goto').run()
        fail = 'Type "help goto" for help with this command.\r\n'
        self.assertTrue(fail in bob.outq)
    
