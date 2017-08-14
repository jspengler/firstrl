import libtcodpy as libtcod

def render_messages():
    libtcod.console_print_ex(con, 0, 0, libtcod.BKGND_NONE, libtcod.LEFT, 'PRESS A KEY TO GET ITS CODE')

    y = 1
    for msg in msgs:
        libtcod.console_print_ex(con, 2, 1+y, libtcod.BKGND_NONE, libtcod.LEFT, msg)
        y += 1
        if y >= 47:
            break

    libtcod.console_blit(con, 0, 0, 80, 48, 0, 0, 0)
    libtcod.console_flush()

### MAIN LOOP ###
libtcod.console_set_custom_font('terminal16x16_gs_ro.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_ASCII_INROW)
libtcod.console_init_root(80, 48, 'Libtcod Key Tester', False)
con = libtcod.console_new(80, 48)
libtcod.console_set_default_foreground(con, libtcod.white)
libtcod.console_set_default_background(con, libtcod.black)
libtcod.sys_set_fps(20)
msgs = []
loop = True
while loop:
    key = libtcod.console_check_for_keypress()
    if key.vk != libtcod.KEY_NONE:
        if key.vk == libtcod.KEY_ESCAPE:
            loop = False
        else:
            msgs.insert(0, 'Ord: ' + str(key.c) + ' | Chr: ' + chr(key.c))
    render_messages()



"""
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
        # Movement
        if key.vk == libtcod.KEY_UP:
            player_move_or_attack(0, -1)
        elif key.vk == libtcod.KEY_DOWN:
            player_move_or_attack(0, 1)
        elif key.vk == libtcod.KEY_LEFT:
            player_move_or_attack(-1, 0)
        elif key.vk == libtcod.KEY_RIGHT:
            player_move_or_attack(1, 0)
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
"""