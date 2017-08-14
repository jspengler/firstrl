import libtcodpy as libtcod
import math
import textwrap
import shelve

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50
MAP_WIDTH = 80
MAP_HEIGHT = 43
LIMIT_FPS = 20
ROOM_MAX_SIZE = 10
ROOM_MIN_SIZE = 6
MAX_ROOMS = 30
FOV_ALGO = 0
FOV_LIGHT_WALLS = True
TORCH_RADIUS = 10
MAX_ROOM_MONSTERS = 2
BAR_WIDTH = 20
PANEL_HEIGHT = 7
PANEL_Y = SCREEN_HEIGHT - PANEL_HEIGHT
MSG_X = BAR_WIDTH + 2
MSG_WIDTH = SCREEN_WIDTH - BAR_WIDTH - 2
MSG_HEIGHT = PANEL_HEIGHT -1
MAX_ROOM_ITEMS = 2
INVENTORY_WIDTH = 50
HEAL_AMOUNT = 30
LIGHTNING_RANGE = 5
LIGHTNING_DAMAGE = 20
CONFUSE_NUM_TURNS = 10
CONFUSE_RANGE = 8
FIREBALL_RADIUS = 3
FIREBALL_DAMAGE= 12
LEVEL_UP_BASE = 200
LEVEL_UP_FACTOR = 150
LEVEL_SCREEN_WIDTH = 40
CHARACTER_SCREEN_WIDTH = 30

game_state = 'playing'
player_action = None
turn_count = 0

color_dark_wall = libtcod.Color(0, 0, 100)
color_light_wall = libtcod.Color(130, 110, 50)
color_dark_ground = libtcod.Color(50, 50, 150)
color_light_ground = libtcod.Color(200, 180, 50)


# --------------------------------------------------------------

class Object:
    # This is a generic object: a player, monster, item, dungeon feature, etc.
    # It is always represented by a character on the screen.
    def __init__(self, x, y, char, name, color, blocks=False, fighter=None, ai=None, death_function = None, item=None, always_visible=False):
        self.x = x
        self.y = y
        self.char = char
        self.color = color
        self.name = name
        self.blocks = blocks
        self.always_visible = always_visible

        # Components
        self.fighter = fighter
        if self.fighter:  # Let the fighter component know who owns it.
            self.fighter.owner = self
        self.ai = ai
        if self.ai:   # Let the AI component know who owns it.
            self.ai.owner = self
        self.item = item
        if self.item: # Let the item component know who owns it
            self.item.owner = self

    def move(self, dx, dy):
        # If the map tile isn't blocked.
        if not is_blocked(self.x + dx, self.y + dy):
            self.x += dx
            self.y += dy

    def draw(self):
        # Set the color and then draw the character that represents this object at its current position.
        if libtcod.map_is_in_fov(fov_map, self.x, self.y) or (self.always_visible and map[self.x][self.y].explored):
            # Before drawing, make sure it's in player's FOV.
            libtcod.console_set_default_foreground(con, self.color)
            libtcod.console_put_char(con, self.x, self.y, self.char, libtcod.BKGND_NONE)

    def clear(self):
        # Erase the character on the screen that represents this object.
        libtcod.console_put_char(con, self.x, self.y, ' ', libtcod.BKGND_NONE)

    def move_towards(self, target_x, target_y):
        # Vector from this object to the target, and distance.
        dx = target_x - self.x
        dy = target_y - self.y
        distance = math.sqrt(dx ** 2 + dy ** 2)

        # Normalize it to length 1 (preserving direction), then round it and convert to integer so the movement is restricted to the map grid.
        dx = int(round(dx / distance))
        dy = int(round(dy / distance))
        self.move(dx, dy)

    def distance_to(self, other):
        # Return the distance to another object.
        dx = other.x - self.x
        dy = other.y - self.y
        return math.sqrt(dx ** 2 + dy ** 2)

    def send_to_back(self):
        # Make this object be drawn first, so all others appear above it if they're in the same tile.
        global objects
        objects.remove(self)
        objects.insert(0, self)

    def distance(self, x, y):
        #return the distance to some coordinates
        return math.sqrt((x - self.x) ** 2 + (y - self.y) ** 2)

class Tile:
    # A tile of the map and its properties.
    def __init__(self, blocked, block_sight = None):
        self.blocked = blocked
        # By default, if the tile is blocked it also blocks sight.
        if block_sight is None: block_sight = blocked
        self.block_sight = block_sight
        self.explored = False

class Rect:
    # A rectangle on the map, used to characterize a room.
    def __init__(self, x, y, w, h):
        self.x1 = x
        self.y1 = y
        self.x2 = x + w
        self.y2 = y + h

    def center(self):
        center_x = (self.x1 + self.x2) / 2
        center_y = (self.y1 + self.y2) / 2
        return(center_x, center_y)

    def intersect(self, other):
        # Returns true if this rectangle instersects with another one.
        return (self.x1 <= other.x2 and self.x2 >= other.x1 and self.y1 <= other.y2 and self.y2 >= other.y1)


class Fighter:
    # Combat related properties and methods.
    def __init__(self, hp, defense, power, xp, death_function=None):
        self.max_hp = hp
        self.hp = hp
        self.defense = defense
        self.power = power
        self.xp = xp
        self.death_function = death_function

    def take_damage(self, damage):
        # Apply damage if possible.
        if damage > 0:
            self.hp -= damage
            # Check for self death after taking damage.
            if self.hp <= 0:
                if self.owner != player:  # Yield experience to the player.
                    player.fighter.xp += self.xp
                function = self.death_function
                if function is not None:
                    function(self.owner)

    def attack(self, target):
        # A simple formula for attack damage.
        damage = libtcod.random_get_int(0, int(self.power/2), self.power) - libtcod.random_get_int(0, 0, target.fighter.defense)
        if damage > 0:
            # Make the target take some damage.
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' for ' +str(damage) + ' hit points.', libtcod.white)
            target.fighter.take_damage(damage)
        else:
            message(self.owner.name.capitalize() + ' attacks ' + target.name + ' but it has no effect.', libtcod.white)

    def heal(self, amount):
        # Heal by the given amount, without going over maximum.
        self.hp += amount
        if self.hp > self.max_hp:
            self.hp = self.max_hp

class BasicMonster:
    # AI for a basic monster.
    def take_turn(self):
        # If the player can see it, it can see the player.
        monster = self.owner
        if libtcod.map_is_in_fov(fov_map, monster.x, monster.y):
            # Move towards the player if far away.
            if monster.distance_to(player) >= 2:
                monster.move_towards(player.x, player.y)
            # If close enough, attack! (As long as the player has hitpoints.)
            elif player.fighter.hp > 0:
                monster.fighter.attack(player)

class Item:
    # An item that can be picked up and used.
    def __init__(self, use_function=None):
        self.use_function = use_function
    def pick_up(self):
        # Add to the player's invetory and remove from the map.
        if len(inventory) >= 26:
            message('Your inventory is full, cannot pick up ' + self.owner.name + '.', libtcod.light_red)
        else:
            inventory.append(self.owner)
            objects.remove(self.owner)
            message('You picked up a ' + self.owner.name + '.', libtcod.light_green)
    def use(self):
        # Just call the use function if it is defined.
        if self.use_function is None:
            message('The ' + self.owner.name + ' cannot be used.')
        else:
            if self.use_function() != 'cancelled':
                inventory.remove(self.owner) # Destroy after use, unless it was cancelled in some way.
    def drop(self):
        # Add to the map and remove from the player's inventory. Also, place it at player's coordinates.
        # Check to make sure there are no other items in the player's space.
        for object in objects:
            if object.x == player.x and object.y == player.y and object.item:
                message('There is already an item on the floor here. Find an enemy location.')
                return
        objects.append(self.owner)
        inventory.remove(self.owner)
        self.owner.x = player.x
        self.owner.y = player.y
        message('You dropped a ' + self.owner.name + '.', libtcod.yellow)

class ConfusedMonster:
    # AI for a confused monster
    def __init__(self, old_ai, num_turns=CONFUSE_NUM_TURNS):
        self.old_ai = old_ai
        self.num_turns = num_turns
    def take_turn(self):
        if self.num_turns > 0: # still confused...
            # Move in a random direction
            self.owner.move(libtcod.random_get_int(0, -1, 1), libtcod.random_get_int(0, -1, 1))
            self.num_turns -= 1
        else: # restor old AI, and this one will be deleted because it's not referenced anymore
            self.owner.ai = self.old_ai
            message('The ' + self.owner.name + ' is no longer confused!', libtcod.red)


# --------------------------------------------------------------

def handle_keys():
    global game_state
    global fov_recompute
    global key
    global stairs

    # key = libtcod.console_wait_for_keypress(True)

    # Alt+Enter: Toggle fullscreen.
    if key.vk == libtcod.KEY_ENTER and key.lalt:
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
    # Esc: Quit game.
    elif key.vk == libtcod.KEY_ESCAPE:
        return 'exit'

    if game_state == 'playing':
        #movement keys
        if key.vk == libtcod.KEY_UP or key.vk == libtcod.KEY_KP8:
            player_move_or_attack(0, -1)
        elif key.vk == libtcod.KEY_DOWN or key.vk == libtcod.KEY_KP2:
            player_move_or_attack(0, 1)
        elif key.vk == libtcod.KEY_LEFT or key.vk == libtcod.KEY_KP4:
            player_move_or_attack(-1, 0)
        elif key.vk == libtcod.KEY_RIGHT or key.vk == libtcod.KEY_KP6:
            player_move_or_attack(1, 0)
        elif key.vk == libtcod.KEY_HOME or key.vk == libtcod.KEY_KP7:
            player_move_or_attack(-1, -1)
        elif key.vk == libtcod.KEY_PAGEUP or key.vk == libtcod.KEY_KP9:
            player_move_or_attack(1, -1)
        elif key.vk == libtcod.KEY_END or key.vk == libtcod.KEY_KP1:
            player_move_or_attack(-1, 1)
        elif key.vk == libtcod.KEY_PAGEDOWN or key.vk == libtcod.KEY_KP3:
            player_move_or_attack(1, 1)
        elif key.vk == libtcod.KEY_KP5 or chr(key.c) == '.':
            return 'pass-turn'
        else:
            # Test for other keys.
            key_char = chr(key.c)
            if key_char == 'g':
                # Pick up an item.
                for object in objects:  # Look to see if an item is in the player's tile.
                    if object.x == player.x and object.y == player.y and object.item:
                        object.item.pick_up()
                        break
            elif key_char == 'i':
                # Show the inventory.
                chosen_item = inventory_menu('Press the key next to an item to use it, or any other to canccel.\n')
                if chosen_item is not None:
                    chosen_item.use()
            elif key_char == 'd':
                # Show the inventory, if an item is selected then drop it.
                chosen_item = inventory_menu('Press the key next to an item to drop it, or any other to cancel.\n')
                if chosen_item is not None:
                    chosen_item.drop()
            elif key_char == ',':
                # Go down the stairs if the player is on them.
                if stairs.x == player.x and stairs.y == player.y:
                    next_level()
                else:
                    message('No stairs', libtcod.blue)
            elif key_char == 'c':
                # Display character info.
                level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
                msgbox(
                    'Character Information\n' +
                    '\nLevel: ' + str(player.level) +
                    '\nExperience: ' + str(player.fighter.xp) +
                    '\nExperience to level up: ' + str(level_up_xp) +
                    '\n\nMaximum HP: ' + str(player.fighter.max_hp) +
                    '\nAttack: ' + str(player.fighter.power) +
                    '\nDefense: ' + str(player.fighter.defense),
                    CHARACTER_SCREEN_WIDTH)

            return 'didnt-take-turn'

def player_move_or_attack(dx, dy):
    global fov_recompute

    # The target coordinates.
    x = player.x + dx
    y = player.y + dy

    # Try to find an attackable object there.
    target = None
    for object in objects:
        # Make sure it has a fighter component and is in the right spot.
        if object.fighter and object.x == x and object.y == y:
            target = object
            break

    # Attack if target found, move otherwise.
    if target is not None:
        player.fighter.attack(target)
    else:
        player.move(dx, dy)
        fov_recompute = True

def make_map():
    global map, player, objects, stairs

    # Make the objects list with just the player.
    objects = [player]

    # Fill map with "unblocked" tiles
    map = [[ Tile(True) for y in range(MAP_HEIGHT) ] for x in range(MAP_WIDTH) ]

    rooms = []
    num_rooms = 0

    for r in range(MAX_ROOMS):
        # Random width and height.
        w = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        h = libtcod.random_get_int(0, ROOM_MIN_SIZE, ROOM_MAX_SIZE)
        # Random position without going out of the boundaries of the map.
        x = libtcod.random_get_int(0, 0, MAP_WIDTH - w - 1)
        y = libtcod.random_get_int(0, 0, MAP_HEIGHT - h - 1)

        new_room = Rect(x, y, w, h)

        # Run through all other rooms to see if they intersect.
        failed = False
        for other_room in rooms:
            if new_room.intersect(other_room):
                failed = True
                break

        if not failed:
            # If there are no intersections.
            create_room(new_room)

            # Center coordinates of new room, will be useful later for placing players and creating tunnels.
            (new_x, new_y) = new_room.center()

            if num_rooms == 0:
                # If this is the first room, put the player in there.
                player.x = new_x
                player.y = new_y
            else:
                # If it's not the first room, connect it to the previous room with a tunnel.
                # Center coordinates of the previous room.
                (prev_x, prev_y) = rooms[num_rooms-1].center()

                # Flip a coin.
                if libtcod.random_get_int(0, 0, 1) == 1:
                    # First tunnel horizontally, then vertically.
                    create_h_tunnel(prev_x, new_x, prev_y)
                    create_v_tunnel(prev_y, new_y, new_x)
                else:
                    # First tunnel vertically, then horizontally.
                    create_v_tunnel(prev_y, new_y, prev_x)
                    create_h_tunnel(prev_x, new_x, new_y)

            # Place some objects in the room.
            place_objects(new_room)

            # Finally append the new room to the list.
            rooms.append(new_room)
            num_rooms += 1
    # Create stairs at the center of the last room.
    stairs = Object(new_x, new_y, '<', 'stairs', libtcod.white, always_visible=True)
    objects.append(stairs)
    stairs.send_to_back() # So it's drawn below the monsters.



def is_blocked(x,y):
    # First test the map tile.
    if map[x][y].blocked:
        return True;

    # Now check for any blocking objects.
    for object in objects:
        if object.blocks and object.x == x and object.y == y:
            return True;

    return False;

def create_room(room):
    global map

    # Go through the tiles in the rectangle and make them passable.
    for x in range(room.x1 + 1, room.x2):
        for y in range(room.y1 + 1, room.y2):
            map[x][y].blocked = False
            map[x][y].block_sight = False

def create_h_tunnel(x1, x2, y):
    global map
    for x in range(min(x1, x2), max(x1,x2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False

def create_v_tunnel(y1, y2, x):
    global map
    for y in range(min(y1, y2), max(y1,y2) + 1):
        map[x][y].blocked = False
        map[x][y].block_sight = False

def place_objects(room):
    # Choose a random number of monsters.
    num_monsters = libtcod.random_get_int(0, 0, MAX_ROOM_MONSTERS)

    for i in range(num_monsters):
        # Chose random spot for this monster.
        x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)

        if not is_blocked(x, y):
            monster_chances = {
                'orc': 80,
                'troll': 20
            }
            choice = random_choice(monster_chances)
            if choice == 'orc':
                # Create an orc.
                fighter_component = Fighter(hp=10, defense=0, power=3, xp=35, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'o', 'orc', libtcod.desaturated_green, blocks=True, fighter=fighter_component, ai=ai_component)
            elif choice == 'troll':
                # Create a troll.
                fighter_component = Fighter(hp=16, defense=1, power=4, xp=100, death_function=monster_death)
                ai_component = BasicMonster()
                monster = Object(x, y, 'T', 'troll', libtcod.darker_green, blocks=True, fighter=fighter_component, ai=ai_component)

            objects.append(monster)

    # Choose a random number of items.
    num_items = libtcod.random_get_int(0, 0, MAX_ROOM_ITEMS)

    for i in range(num_items):
        # Choose random spot for this item.
        x = libtcod.random_get_int(0, room.x1 + 1, room.x2 - 1)
        y = libtcod.random_get_int(0, room.y1 + 1, room.y2 - 1)

        if not is_blocked(x, y):
            dice = libtcod.random_get_int(0, 0, 100)
            if dice < 40:
                # Create a healing potion. (40% chance)
                item_component = Item(use_function=cast_heal)
                item = Object(x, y, '!', 'healing potion', libtcod.violet, item=item_component, always_visible=True)
            elif dice < 40 + 20:
                # Create a lightning bolt scroll. (20% chance)
                item_component = Item(use_function=cast_lightning)
                item = Object(x, y, '?', 'scroll of lightning bolt', libtcod.light_yellow, item=item_component, always_visible=True)
            elif dice < 40 + 20 + 20:
                # Create a confusion scroll (20% chance)
                item_component = Item(use_function=cast_confuse)
                item = Object(x, y, '?', 'scroll of confusion', libtcod.light_yellow, item=item_component, always_visible=True)
            else:
                # Create a fireball scroll (20% chance)
                item_component = Item(use_function=cast_fireball)
                item = Object(x, y, '?', 'scroll of fireball', libtcod.light_yellow, item=item_component, always_visible=True)

            objects.append(item)
            item.send_to_back()  # Items appear below other objects.

def render_all():
    global fov_map, color_dark_wall, color_light_wall
    global color_dark_ground, color_light_ground
    global fov_recompute

    if fov_recompute:
        # Recompute the FOV if needed.
        fov_recompute = False
        libtcod.map_compute_fov(fov_map, player.x, player.y, TORCH_RADIUS, FOV_LIGHT_WALLS, FOV_ALGO)

        # Go through all tiles, set their background color according to FOV.
        for y in range(MAP_HEIGHT):
            for x in range(MAP_WIDTH):
                visible = libtcod.map_is_in_fov(fov_map, x, y)
                wall = map[x][y].block_sight
                if not visible:
                    # It's out of the player's FOV
                    if map[x][y].explored:
                        # Only render if it's been seen before.
                        if wall:
                            libtcod.console_set_char_background(con, x, y, color_dark_wall, libtcod.BKGND_SET)
                        else:
                            libtcod.console_set_char_background(con, x, y, color_dark_ground, libtcod.BKGND_SET)
                else:
                    # It's visible.
                    if wall:
                        libtcod.console_set_char_background(con, x, y, color_light_wall, libtcod.BKGND_SET)
                    else:
                        libtcod.console_set_char_background(con, x, y, color_light_ground, libtcod.BKGND_SET)
                    map[x][y].explored = True

    # Draw all objects in the list.
    for object in objects:
        # Make sure it's not the player, we want to draw them last.
        if object != player:
            object.draw()
    player.draw()

    # Blit the contents of the con console to the main console.
    libtcod.console_blit(con, 0, 0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, 0, 0)

    # prepare to render the GUI panel
    libtcod.console_set_default_background(panel, libtcod.black)
    libtcod.console_clear(panel)

    # show the player's stats
    render_bar(1, 1, BAR_WIDTH, 'HP', player.fighter.hp, player.fighter.max_hp, libtcod.light_red, libtcod.darker_red)

    # Show the dungeon level.
    libtcod.console_print_ex(panel, 1, 3, libtcod.BKGND_NONE, libtcod.LEFT, 'Dungeon Level ' + str(dungeon_level))

    # Display names of objects under the mouse
    libtcod.console_set_default_foreground(panel, libtcod.light_grey)
    libtcod.console_print_ex(panel, 1, 0, libtcod.BKGND_NONE, libtcod.LEFT, get_names_under_mouse())

    # Print messages
    y = 1
    for (line, color) in game_msgs:
        libtcod.console_set_default_foreground(panel, color)
        libtcod.console_print_ex(panel, MSG_X, y, libtcod.BKGND_NONE, libtcod.LEFT, line)
        y += 1

    # blit the contents of "panel" to the root console
    libtcod.console_blit(panel, 0, 0, SCREEN_WIDTH, PANEL_HEIGHT, 0, 0, PANEL_Y)

def player_death(player):
    # The game ends!
    global game_state
    message('You died!', libtcod.red)
    game_state = 'dead'

    # For added effecct, transform the player into a corpse!
    player.char = '%'
    player.color = libtcod.dark_red

def monster_death(monster):
    # Transform it into a nasty corpse! It doesn't block, can't be attacked, doesn't move.
    message(monster.name.capitalize() + ' is dead! (' + str(monster.fighter.xp) + 'xp)', libtcod.orange)
    monster.char = '%'
    monster.color = libtcod.dark_red
    monster.blocks = False
    monster.fighter = None
    monster.ai = None
    monster.name = 'remains of ' + monster.name
    monster.send_to_back()

def render_bar(x, y, total_width, name, value, maximum, bar_color, back_color):
    # Render a bar. First calculate the width of the bar.
    bar_width = int(float(value) / maximum * total_width)
    # Render the background.
    libtcod.console_set_default_background(panel, back_color)
    libtcod.console_rect(panel, x, y, total_width, 1, False, libtcod.BKGND_SCREEN)
    # Render the bar on top
    libtcod.console_set_default_background(panel, bar_color)
    if bar_width > 0:
        libtcod.console_rect(panel, x, y, bar_width, 1, False, libtcod.BKGND_SCREEN)
    # Add some centered text with the values.
    libtcod.console_set_default_foreground(panel, libtcod.white)
    libtcod.console_print_ex(panel, x + total_width / 2, y, libtcod.BKGND_NONE, libtcod.CENTER, name + ': ' + str(value) + '/' + str(maximum))

def message(new_msg, color = libtcod.white):
    # Split the message, if neccessary, among multiple lines.
    new_msg_lines = textwrap.wrap(new_msg, MSG_WIDTH)
    for line in new_msg_lines:
        # If the buffer is full, remove the first line to make room for the new one.
        if len(game_msgs) == MSG_HEIGHT:
            del game_msgs[0]
        # Add the new line as a tuple, with text and color.
        game_msgs.append( (line, color) )

def get_names_under_mouse():
    global mouse
    # Return a string with the names of all objects under the mouse.
    (x, y) = (mouse.cx, mouse.cy)
    # Create a list with the names of all objects at the mouse's coordinates and in FOV
    names = [obj.name for obj in objects if obj.x == x and obj.y == y and libtcod.map_is_in_fov(fov_map, obj.x, obj.y)]
    # Joing the names together with commas.
    names = ', '.join(names)
    return names.capitalize()

def menu(header, options, width):
    if len(options) > 26: raise ValueError('Cannot have a menu with more than 26 options.')

    # Calculate total heigh for the header after auto-wrap and one line per option.
    header_height = libtcod.console_get_height_rect(con, 0, 0, width, SCREEN_HEIGHT, header)
    # Check for no header.
    if header == '':
        header_height = 0
    height = len(options) + header_height

    # Create an off-screen console that represents the menu's window.
    window = libtcod.console_new(width, height)
    # Print the header, with auto-wrap
    libtcod.console_set_default_foreground(window, libtcod.white)
    libtcod.console_print_rect_ex(window, 0, 0, width, height, libtcod.BKGND_NONE, libtcod.LEFT, header)

    # Print all the options
    y = header_height
    letter_index = ord('a')
    for option_text in options:
        text = '(' + chr(letter_index) + ') ' + option_text
        libtcod.console_print_ex(window, 0, y, libtcod.BKGND_NONE, libtcod.LEFT, text)
        y += 1
        letter_index += 1

    # Blit the contents of "window" to the root console.
    x = SCREEN_WIDTH/2 - width/2
    y = SCREEN_HEIGHT/2 - height/2
    libtcod.console_blit(window, 0, 0, width, height, 0, x, y, 1.0, 0.7)

    # Present the root console to the player and wait for a key-press
    libtcod.console_flush()
    key = libtcod.console_wait_for_keypress(True)

    if key.vk == libtcod.KEY_ENTER and key.lalt:  # Special case to toggle fullscreen while a menu is up.
        libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())

    # Convert the ASCII code to an index; if it corresponds to an option, return it.
    index = key.c - ord('a')
    if index >= 0 and index < len(options): return index
    return None

def inventory_menu(header):
    # Show a menu with each itme of the inventory as an option.
    if len(inventory) == 0:
        options = ['Inventory is empty.']
    else:
        options = [item.name for item in inventory]

    index = menu(header, options, INVENTORY_WIDTH)

    # If an item is chosen, return it.
    if index is None or len(inventory) == 0: return None
    return inventory[index].item

def cast_heal():
    # Heal the player
    if player.fighter.hp >= player.fighter.max_hp:
        message('You don\'t need healing.', libtcod.light_red)
        return 'cancelled'
    message('Your wounds start to feel better!', libtcod.light_violet)
    player.fighter.heal(HEAL_AMOUNT)

def cast_lightning():
    # Find closest enemy (inside a maximum range) and damage it.
    monster = closest_monster(LIGHTNING_RANGE)
    if monster is None: # no enemy found
        message('No enemy is close enough to strike.', libtcod.light_red)
        return 'cancelled'
    # Zap!
    message('A lightning bolt strikes the ' + monster.name + '! You deal ' + str(LIGHTNING_DAMAGE) + ' damage.', libtcod.light_blue)
    monster.fighter.take_damage(LIGHTNING_DAMAGE)

def closest_monster(max_range):
    # Find the closest enemy up to a maximum range in the player's FOV
    closest_enemy = None
    closest_dist = max_range + 1 # Start with (slightly more than) max range.

    for object in objects:
        if object.fighter and not object == player and libtcod.map_is_in_fov(fov_map, object.x, object.y):
            # Calculate distance between object and player.
            dist = player.distance_to(object)
            if dist < closest_dist: # It's closer, so remember it
                closest_enemy = object
                closest_dist = dist

    return closest_enemy

def cast_confuse():
    # Find closest enemy in range and confuse it.
    message('Left click an enemy to confuse it, or right click to cancel.', libtcod.light_cyan)
    monster = target_monster(CONFUSE_RANGE)
    if monster is None: return 'cancelled'
    else:
        old_ai = monster.ai
        monster.ai = ConfusedMonster(old_ai)
        monster.ai.owner = monster # Tell the new component who owns it
        message('The eyes of the ' + monster.name + ' look vacant as he starts to stumble around!', libtcod.light_green)

def target_tile(max_range=None):
    # Return the position of a tile left-clicked in player's FOV (optionally in a range) or (none, none) if right clicked.
    global key, mouse
    while True:
        # Render the screen. This erases the inventory and shows the names of objects under the mouse.
        libtcod.console_flush()
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE, key, mouse)
        render_all()
        (x, y) = (mouse.cx, mouse.cy)

        if (mouse.lbutton_pressed and libtcod.map_is_in_fov(fov_map, x, y) and (max_range is None or player.distance(x,y) <= max_range)):
            return (x, y)
        if mouse.rbutton_pressed or key.vk == libtcod.KEY_ESCAPE:
            return (None, None)

def cast_fireball():
    # Ask the player for a target tile to throw a fireball at.
    message('Left click a target tiel for the fireball, or right click to cancel.', libtcod.light_cyan)
    (x, y) = target_tile()
    if x is None: return 'cancelled'
    message('The fireball explodes, burning everything within ' + str(FIREBALL_RADIUS) + ' tiles!', libtcod.orange)

    for obj in objects: # Damage every fighter in range, including the player
        if obj.distance(x, y) <= FIREBALL_RADIUS and obj.fighter:
            message('The ' + obj.name + ' takes ' + str(FIREBALL_DAMAGE) + ' damage.', libtcod.orange)
            obj.fighter.take_damage(FIREBALL_DAMAGE)

def target_monster(max_range=None):
    # Returns a clicked monster inside FOV up to a range, or None if right clicked
    while True:
        (x, y) = target_tile(max_range)
        if x is None: # player cancelled
            return None

        # Return the first clicked monster, otherwise keep looping.
        for obj in objects:
            if obj.x == x and obj.y == y and obj.fighter and obj != player:
                return obj

def new_game():
    global player, inventory, game_msgs, game_state, dungeon_level

    # Create an object representing the player.
    fighter_component = Fighter(hp=30, defense=2, power=5, xp=0, death_function=player_death)
    player = Object(0, 0, '@', 'player', libtcod.white, blocks=True, fighter=fighter_component)
    player.level = 1

    # Generate a map (at this point it's not drawn to the screen)
    dungeon_level = 1
    make_map()
    initialize_fov()

    game_state = 'playing'
    inventory = []

    # Create the list of game messages and their colors, starts empty.
    game_msgs = []

    # A warm welcoming message!
    message('Welcome stranger! Prepare to perish in the Tombs of the Ancient Kings.', libtcod.red)


def initialize_fov():
    global fov_recompute, fov_map
    fov_recompute = True

    # Clear the screen totally.
    libtcod.console_clear(con)

    # Create the FOV map, according to the generated map.
    fov_map = libtcod.map_new(MAP_WIDTH, MAP_HEIGHT)
    for y in range(MAP_HEIGHT):
        for x in range(MAP_WIDTH):
            libtcod.map_set_properties(fov_map, x, y, not map[x][y].block_sight, not map[x][y].blocked)

def play_game():
    global key, mouse

    player_action = None

    mouse = libtcod.Mouse()
    key = libtcod.Key()
    while not libtcod.console_is_window_closed():
        # Render the screen.
        libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE,key,mouse)
        render_all()

        libtcod.console_flush()

        check_level_up()

        # Erase all objects at their old locations, before they move.
        for object in objects:
            object.clear()

        # Handle keys and exit game if needed.
        player_action = handle_keys()
        if player_action == 'exit':
            save_game()
            break

        # Let monsters take their turn.
        if game_state == 'playing' and player_action != 'didnt-take-turn':
            for object in objects:
                if object.ai:
                    object.ai.take_turn()

def main_menu():
    img = libtcod.image_load('menu_background1.png')
    libtcod.image_blit_2x(img, 0, 0, 0)

    # Make a new mini-game-loop.
    while not libtcod.console_is_window_closed():
        # Show the background image, at twice the regular console resolution.
        # libtcod.image_blit_2x(img,0,0,0)

        # Show the game's title and some credits.
        libtcod.console_set_default_foreground(0, libtcod.light_yellow)
        libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT/2-4, libtcod.BKGND_NONE, libtcod.CENTER, 'TOMBS OF THE ANCIENT KINGS')
        libtcod.console_print_ex(0, SCREEN_WIDTH/2, SCREEN_HEIGHT-2, libtcod.BKGND_NONE, libtcod.CENTER, 'By Jotaf and W. Stacks')

        # Show options and wait for the player's choice
        choice = menu('',['Play a new game', 'Continue last game', 'Quit'], 24)

        if choice == 0:  # Index of "play a new game"
            new_game()
            play_game()
        elif choice == 1:  # Load last game
            try:
                load_game()
            except:
                msgbox('\n No saved game to load.\n', 24)
                continue
            play_game()
        elif choice == 2:  # Quit
            break

def msgbox(text, width=50):
    menu(text, [], width)  # Use the menu function as a message box.

def save_game():
    # Open a new empty shelf (possibly overwriting an old one) to write game data
    file = shelve.open('savegame', 'n')
    file['map'] = map
    file['objects'] = objects
    file['player_index'] = objects.index(player) #Index of the player in objects list
    file['inventory'] = inventory
    file['game_msgs'] = game_msgs
    file['game_state'] = game_state
    file['stairs_index'] = objects.index(stairs)
    file['dungeon_level'] = dungeon_level
    file.close()

def load_game():
    # Open the previously saved shelve and load the game data.
    global map, objects, player, inventory, game_msgs, game_state, stairs, dungeon_level
    file = shelve.open('savegame', 'r')
    map = file['map']
    objects = file['objects']
    player = objects[file['player_index']] # Get index of player in objects list and access it.
    inventory = file['inventory']
    game_msgs = file['game_msgs']
    game_state = file['game_state']
    stairs = objects[file['stairs_index']]
    dungeon_level = file['dungeon_level']
    file.close()
    initialize_fov()

def next_level():
    global dungeon_level
    # Advance to the next level.
    message('You take a moment to rest and recover your strength.', libtcod.light_violet)
    player.fighter.heal(player.fighter.max_hp / 2)  # Heal the player by 50%.
    message('You descend deeper into the heart of the dungeon...', libtcod.red)
    dungeon_level += 1
    make_map()  # Create a fresh level.
    initialize_fov()

def check_level_up():
    # See if the player's experience is enough to level-up.
    level_up_xp = LEVEL_UP_BASE + player.level * LEVEL_UP_FACTOR
    if player.fighter.xp >= level_up_xp:
        # Ding!
        player.level += 1
        player.fighter.xp -= level_up_xp
        message('You grow stronger! You reached level ' + str(player.level) + '!', libtcod.yellow)
        choice = None
        while choice == None: # Keep asking until a choice is made.
            choice = menu('Level up! Choose a stat to raise:\n',
                          ['Constitution (+20 HP)',
                           'Strength (+1 attack)',
                           'Agility (+1 defense)'],
                          LEVEL_SCREEN_WIDTH)
            if choice == 0:
                player.fighter.max_hp += 20
                player.fighter.hp += 20
            elif choice == 1:
                player.fighter.power += 1
            elif choice == 2:
                player.fighter.defense += 1

def random_choice_index(chances):
    # Choose one option from a list of weighted choices, return its index.
    dice = libtcod.random_get_int(0, 1, sum(chances))
    # Go through all chances, keeping the sum so far.
    running_sum = 0
    choice = 0
    for w in chances:
        running_sum += w
        # See if the dice landed in the part that corresponds to this choice.
        if dice <= running_sum:
            return choice
        choice =+ 1

def random_choice(chances_dictionary):
    # Choose one option from dictionary of chances, returning its key.
    chances = chances_dictionary.values()
    strings = chances_dictionary.keys()
    return strings[random_choice_index(chances)]

######################################
# --- INITIALIZATION AND MAIN LOOP ---
######################################

libtcod.console_set_custom_font('arial10x10.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
libtcod.console_init_root(SCREEN_WIDTH, SCREEN_HEIGHT, 'python/libtcod tutorial', False)
con = libtcod.console_new(SCREEN_WIDTH, SCREEN_HEIGHT)
panel = libtcod.console_new(SCREEN_WIDTH, PANEL_HEIGHT)
libtcod.sys_set_fps(LIMIT_FPS)

# Create dummy objects.
# player = Object(SCREEN_WIDTH/2, SCREEN_HEIGHT/2, '@', libtcod.white)
#fighter_component = Fighter(hp=30, defense=2, power=5, death_function=player_death)
#player = Object(25, 23, '@', 'player', libtcod.white, blocks=True, fighter=fighter_component)
#objects = [player]
# Generate the map.
#make_map()

main_menu()

"""
# --- GAME LOOP ---

while not libtcod.console_is_window_closed():
    global turn_count
    turn_count += 1

    # Check for the mouse and any clicks.
    libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS|libtcod.EVENT_MOUSE,key,mouse)

    # Draw all objects to con.
    render_all()

    libtcod.console_flush()

    # Clear out old positions of objects before they move.
    for object in objects:
        object.clear()

    # Handle keys.
    player_action = handle_keys()
    # Quit if handle_keys returns True. (Esc is pressed.)
    if player_action == 'exit':
        break

    # Let monsters take their turn.
    if game_state == 'playing' and player_action != 'didnt-take-turn':
        for object in objects:
            if object.ai:
                object.ai.take_turn()
"""

