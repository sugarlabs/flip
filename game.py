# -*- coding: utf-8 -*-
# Copyright (c) 2011 Walter Bender
# Ported to GTK3:
# Ignacio Rodríguez <ignaciorodriguez@sugarlabs.org> 2012!

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU General Public License
# along with this library; if not, write to the Free Software
# Foundation, 51 Franklin Street, Suite 500 Boston, MA 02110-1335 USA

from gi.repository import Gdk, GdkPixbuf, Gtk, GObject
import cairo

import os
import time
from math import sqrt
from random import uniform
from gettext import gettext as _

import logging
_logger = logging.getLogger('reflection-activity')

try:
    from sugar3.graphics import style
    GRID_CELL_SIZE = style.GRID_CELL_SIZE
except ImportError:
    GRID_CELL_SIZE = 0

from sprites import Sprites, Sprite
from sugar3.activity.activity import get_activity_root

# Grid dimensions must be even
MAX = 7
WHITE = 2
DOT_SIZE = 80
MAX_COUNT = 3


class Game():

    def __init__(self, canvas, parent=None, colors=['#A0FFA0', '#FF8080']):
        self._activity = parent
        self._colors = [colors[0]]
        self._colors.append(colors[1])
        self._colors.append('#D0D0D0')
        self._colors.append('#000000')

        self._canvas = canvas
        if parent is not None:
            parent.show_all()
            self._parent = parent

        self._canvas.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self._canvas.connect("draw", self.__draw_cb)
        self._canvas.connect("button-press-event", self._button_press_cb)

        self._width = Gdk.Screen.width()
        self._height = Gdk.Screen.height() - (GRID_CELL_SIZE * 1.5)
        self._scale = self._width / (10 * DOT_SIZE * 1.2)
        self._dot_size = int(DOT_SIZE * self._scale)
        self._space = int(self._dot_size / 5.)
        self.we_are_sharing = False
        self._edge = 4
        self._move_list = []
        self.best_time = self.load_best_time()
        self.paused_time = 0
        self.gameover_flag = None
        self.count = 1

        # Generate the sprites we'll need...
        self._sprites = Sprites(self._canvas)
        self._dots = []
        self._gameover = []
        self._your_time = []
        self._best_time = []
        self._levelup = []
        self._generate_grid()

    def _generate_grid(self):
        ''' Make a new set of dots for a grid of size edge '''
        i = 0
        for y in range(self._edge):
            for x in range(self._edge):
                xoffset = int((self._width - self._edge * self._dot_size -
                               (self._edge - 1) * self._space) / 2.)
                if i < len(self._dots):
                    self._dots[i].move(
                        (xoffset + x * (self._dot_size + self._space),
                         y * (self._dot_size + self._space)))
                else:
                    self._dots.append(
                        Sprite(self._sprites,
                               xoffset + x * (self._dot_size + self._space),
                               y * (self._dot_size + self._space),
                               self._new_dot(self._colors[0])))
                self._dots[i].type = 0
                self._dots[-1].set_label_attributes(40)
                i += 1

        # and initialize a few variables we'll need.
        self._all_clear()

    def _all_clear(self):
        ''' Things to reinitialize when starting up a new game. '''

        self._move_list = []

        # Clear dots
        for gameover_shape in self._gameover:
            gameover_shape.hide()
        for your_time_shape in self._your_time:
            your_time_shape.hide()
        for best_time_shape in self._best_time:
            best_time_shape.hide()
        for dot in self._dots:
            dot.type = 0
            dot.set_shape(self._new_dot(self._colors[0]))
            dot.set_label('')
            dot.set_layer(100)
        if self.count == 0:
            for levelup_shape in self._levelup:
                levelup_shape.hide()

    def _initiating(self):
        return self._activity._collab.props.leader

    def more_dots(self):
        ''' Enlarge the grid '''
        self.count += 1
        if self._edge < MAX and self.count > MAX_COUNT:
            self._edge += 1
            self.count = 0
        else:
            self._edge = 4
        self._generate_grid()
        self.new_game()

    def new_game(self):
        ''' Start a new game. '''
        self._all_clear()
        self.gameover_flag = False
        # Fill in a few dots to start
        for i in range(MAX * 2):
            self._flip_them(int(uniform(0, self._edge * self._edge)))

        if self.we_are_sharing:
            _logger.debug('sending a new game')
            self._parent.send_new_game()

        self.game_start_time = time.time()

    def restore_game(self, dot_list, move_list, paused_time):
        ''' Restore a game from the Journal or share '''
        edge = int(sqrt(len(dot_list)))
        if edge > MAX:
            edge = MAX
        while self._edge < edge:
            self.more_dots()
        for i, dot in enumerate(dot_list):
            self._dots[i].type = dot
            self._dots[i].set_shape(self._new_dot(
                self._colors[self._dots[i].type]))
        if move_list is not None:
            self._move_list = move_list[:]
        self.game_start_time = time.time()
        self.paused_time = paused_time

    def save_game(self):
        ''' Return dot list, move_list for saving to Journal or
        sharing '''
        dot_list = []
        for dot in self._dots:
            dot_list.append(dot.type)
        self.game_stop_time = time.time()
        paused_time = abs(int(self.game_stop_time - self.game_start_time))
        return (dot_list, self._move_list, paused_time)

    def gameover(self):
        best_seconds = (self.best_time[self._edge-4]) % 60
        best_minutes = (self.best_time[self._edge-4]) // 60
        self.elapsed_time = int(self.game_stop_time
                                - self.game_start_time) + self.paused_time
        second = self.elapsed_time % 60
        minute = self.elapsed_time // 60
        for dot in self._dots:
            dot.hide()
        yoffset = int(self._space / 4.)
        xoffset = int((self._width - 6 * self._dot_size -
                       5 * self._space) / 2.)
        y = 1
        for x in range(2, 6):
            self._gameover.append(
                Sprite(self._sprites,
                       xoffset + (x - 0.25) * (self._dot_size - 10),
                       y * (self._dot_size - 90 + self._space) + yoffset,
                       self._new_dot(color=self._colors[0])))
            self._gameover[-1].type = -1  # No image
            self._gameover[-1].set_label_attributes(72)
        text = [
            "☻",
            "  Game  ",
            "  Over  ",
            "☻"
        ]
        self.rings(len(text), text, self._gameover)
        y = 2
        for x in range(2, 5):
            self._your_time.append(
                Sprite(self._sprites,
                       xoffset + (x + 0.25) * (self._dot_size - 10),
                       y * (self._dot_size - 30 + self._space) + yoffset,
                       self._new_dot(color=self._colors[0])))
            self._your_time[-1].type = -1  # No image
            self._your_time[-1].set_label_attributes(72)
        text = [
            "  your  ",
            " time:  ",
            (' {:02d}:{:02d} '.format(minute, second))
        ]
        self.rings(len(text), text, self._your_time)
        y = 3

        for x in range(2, 5):
            self._best_time.append(
                Sprite(self._sprites,
                       xoffset + (x + 0.25) * (self._dot_size - 10),
                       y * (self._dot_size - 20 + self._space) + yoffset,
                       self._new_dot(color=self._colors[0])))
            self._best_time[-1].type = -1
            self._best_time[-1].set_label_attributes(72)
            if self.elapsed_time <= self.best_time[self._edge-4]:
                self.best_time[self._edge-4] = self.elapsed_time
                best_seconds = second
                best_minutes = minute
        text = [
            "  best  ",
            " time:  ",
            (' {:02d}:{:02d} '.format(best_minutes, best_seconds))
        ]
        self.rings(len(text), text, self._best_time)

        if self.count == MAX_COUNT:
            y = 4
            for x in range(2, 6):
                self._levelup.append(
                    Sprite(self._sprites,
                           xoffset + (x - 0.25) * (self._dot_size - 10),
                           y * (self._dot_size - 10 + self._space) + yoffset,
                           self._new_dot(color=self._colors[0])))
                self._levelup[-1].type = -1  # No image
                self._levelup[-1].set_label_attributes(72)
            text = [
                "☻",
                "  Level  ",
                "  Up!  ",
                "☻"
            ]
            self.rings(len(text), text, self._levelup)
        self.save_best_time()
        self.paused_time = 0
        GObject.timeout_add(3000, self.more_dots)

    def rings(self, num, text, shape):
        i = 0
        for x in range(num):
            shape[x].type = -1
            shape[x].set_shape(self._new_dot(
                        self._colors[0]))
            shape[x].set_label(text[i])
            shape[x].set_layer(100)
            i += 1

    def _set_label(self, string):
        ''' Set the label in the toolbar or the window frame. '''
        self._activity.status.set_label(string)

    def _button_press_cb(self, win, event):
        win.grab_focus()
        x, y = list(map(int, event.get_coords()))

        spr = self._sprites.find_sprite((x, y))
        if spr is None:
            return

        if spr.type is not None:
            self._flip_them(self._dots.index(spr))
            self._test_game_over()

            if self.we_are_sharing:
                _logger.debug('sending a click to the share')
                self._parent.send_dot_click(self._dots.index(spr))
        return True

    def solve(self):
        ''' Solve the puzzle by undoing moves '''
        if self._move_list == []:
            return
        self._flip_them(self._move_list.pop(), append=False)
        GObject.timeout_add(750, self.solve)

    def _flip_them(self, dot, append=True):
        ''' flip the dot and its neighbors '''
        if append:
            self._move_list.append(dot)
        x, y = self._dot_to_grid(dot)
        self._flip(self._dots[dot])
        if x > 0:
            self._flip(self._dots[dot - 1])
        if y > 0:
            self._flip(self._dots[dot - self._edge])
        if x < self._edge - 1:
            self._flip(self._dots[dot + 1])
        if y < self._edge - 1:
            self._flip(self._dots[dot + self._edge])

    def _flip(self, spr):
        ''' flip a dot '''
        spr.type += 1
        spr.type %= 2
        spr.set_shape(self._new_dot(self._colors[spr.type]))

    def remote_button_press(self, dot):
        ''' Receive a button press from a sharer '''
        self._flip_them(dot)
        self._test_game_over()

    def set_sharing(self, share=True):
        _logger.debug('enabling sharing')
        self.we_are_sharing = share

    def _smile(self):
        for dot in self._dots:
            dot.set_label(':)')

    def _test_game_over(self):
        ''' Check to see if game is over: all dots the same color '''
        match = self._dots[0].type
        for y in range(self._edge):
            for x in range(self._edge):
                if self._dots[y * self._edge + x].type != match:
                    self._set_label(_('keep trying'))
                    return False
        self._set_label(_('good work'))
        self._smile()
        self.game_stop_time = time.time()
        self.gameover_flag = True
        GObject.timeout_add(2000, self.gameover)
        return True

    def _grid_to_dot(self, pos):
        ''' calculate the dot index from a column and row in the grid '''
        return pos[0] + pos[1] * self._edge

    def _dot_to_grid(self, dot):
        ''' calculate the grid column and row for a dot '''
        return [dot % self._edge, int(dot / self._edge)]

    def __draw_cb(self, canvas, cr):
        self._sprites.redraw_sprites(cr=cr)

    def do_expose_event(self, event):
        ''' Handle the expose-event by drawing '''
        # Restrict Cairo to the exposed area
        cr = self._canvas.window.cairo_create()
        cr.rectangle(event.area.x, event.area.y,
                     event.area.width, event.area.height)
        cr.clip()
        # Refresh sprite list
        self._sprites.redraw_sprites(cr=cr)

    def _destroy_cb(self, win, event):
        Gtk.main_quit()

    def _new_dot(self, color):
        ''' generate a dot of a color color '''
        self._dot_cache = {}
        if color not in self._dot_cache:
            self._stroke = color
            self._fill = color
            self._svg_width = self._dot_size
            self._svg_height = self._dot_size
            pixbuf = svg_str_to_pixbuf(
                self._header() +
                self._circle(self._dot_size / 2., self._dot_size / 2.,
                             self._dot_size / 2.) +
                self._footer())

            surface = cairo.ImageSurface(cairo.FORMAT_ARGB32,
                                         self._svg_width, self._svg_height)
            context = cairo.Context(surface)
            Gdk.cairo_set_source_pixbuf(context, pixbuf, 0, 0)
            context.rectangle(0, 0, self._svg_width, self._svg_height)
            context.fill()
            self._dot_cache[color] = surface

        return self._dot_cache[color]

    def _header(self):
        return '<svg\n' + 'xmlns:svg="http://www.w3.org/2000/svg"\n' + \
            'xmlns="http://www.w3.org/2000/svg"\n' + \
            'xmlns:xlink="http://www.w3.org/1999/xlink"\n' + \
            'version="1.1"\n' + 'width="' + str(self._svg_width) + '"\n' + \
            'height="' + str(self._svg_height) + '">\n'

    def _circle(self, r, cx, cy):
        return '<circle style="fill:' + str(self._fill) + ';stroke:' + \
            str(self._stroke) + ';" r="' + str(r - 0.5) + '" cx="' + \
            str(cx) + '" cy="' + str(cy) + '" />\n'

    def _footer(self):
        return '</svg>\n'

    def read_best_time(self):
        best_time = [180, 180, 180, 180]
        file_path = os.path.join(get_activity_root(), 'data', 'save_best_time')
        if os.path.exists(file_path):
            with open(file_path, "r") as fp:
                best_time = fp.readline()
        return best_time

    def save_best_time(self):
        file_path = os.path.join(get_activity_root(), 'data', 'save_best_time')
        best_time = self.read_best_time()
        if isinstance(best_time, str):
            best_time = self.convert_to_int_list(best_time)
        if not best_time[self._edge-4] <= self.elapsed_time:
            best_time[self._edge-4] = self.elapsed_time
        with open(file_path, "w") as fp:
            fp.write(str(best_time))

    def load_best_time(self):
        best_time = self.read_best_time()
        if isinstance(best_time, str):
            best_time = self.convert_to_int_list(best_time)
        try:
            return best_time
        except (ValueError, IndexError) as e:
            logging.exception(e)
            return 0
        return 0

    def convert_to_int_list(self, str_data):
        list_int = []
        str_data = str_data[1:len(str_data)-1].split(", ")
        for i in range(len(str_data)):
            list_int.append(int(str_data[i]))
        return list_int


def svg_str_to_pixbuf(svg_string):
    """ Load pixbuf from SVG string """
    pl = GdkPixbuf.PixbufLoader.new_with_type('svg')
    pl.write(svg_string.encode())
    pl.close()
    pixbuf = pl.get_pixbuf()
    return pixbuf
