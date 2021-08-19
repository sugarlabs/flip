# -*- coding: utf-8 -*-
# Copyright (c) 2011-13 Walter Bender
# Ported to GTK3: Ignacio Rodríguez
# <ignaciorodriguez@sugarlabs.org>

# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU General Public License
# along with this library; if not, write to the Free Software
# Foundation, 51 Franklin Street, Suite 500 Boston, MA 02110-1335 USA

import gi
gi.require_version('Gtk', '3.0')

from gi.repository import Gtk
from gi.repository import Gdk

from sugar3.activity import activity
from sugar3 import profile
from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.activity.widgets import ActivityToolbarButton
from sugar3.activity.widgets import StopButton

from toolbar_utils import button_factory, label_factory, separator_factory

from collabwrapper import CollabWrapper

from gettext import gettext as _

from game import Game

import logging
_logger = logging.getLogger('flip-activity')


class FlipActivity(activity.Activity):
    """ Flip puzzle game """

    def __init__(self, handle):
        """ Initialize the toolbars and the game board """
        super(FlipActivity, self).__init__(handle)

        self.nick = profile.get_nick_name()
        if profile.get_color() is not None:
            self.colors = profile.get_color().to_string().split(',')
        else:
            self.colors = ['#A0FFA0', '#FF8080']

        self._setup_toolbars()
        self._setup_dispatch_table()

        # Create a canvas
        canvas = Gtk.DrawingArea()
        canvas.set_size_request(Gdk.Screen.width(),
                                Gdk.Screen.height())
        self.set_canvas(canvas)
        canvas.show()
        self.show_all()

        self._game = Game(canvas, parent=self, colors=self.colors)
        self.connect('shared', self._shared_cb)
        self.connect('joined', self._joined_cb)

        self._collab = CollabWrapper(self)
        self._collab.connect('message', self._message_cb)
        self._collab.connect('joined', self._joined_cb)
        self._collab.setup()

        if 'dotlist' in self.metadata and self._game.gameover_flag is False:
            self._restore()
        else:
            self._game.new_game()

    def _setup_toolbars(self):
        """ Setup the toolbars. """

        self.max_participants = 4

        toolbox = ToolbarBox()

        # Activity toolbar
        activity_button = ActivityToolbarButton(self)

        toolbox.toolbar.insert(activity_button, 0)
        activity_button.show()

        self.set_toolbar_box(toolbox)
        toolbox.show()
        self.toolbar = toolbox.toolbar

        self._new_game_button_h = button_factory(
            'new-game', self.toolbar, self._new_game_cb,
            tooltip=_('Start a game.'))

        self.status = label_factory(self.toolbar, '')

        separator_factory(toolbox.toolbar, True, False)

        self.solver = button_factory(
            'help-toolbar', self.toolbar,
            self._solve_cb,
            tooltip=_('Solve the puzzle'))

        stop_button = StopButton(self)
        stop_button.props.accelerator = '<Ctrl>q'
        toolbox.toolbar.insert(stop_button, -1)
        stop_button.show()

    def _new_game_cb(self, button=None):
        ''' Start a new game. '''
        self._game.new_game()

    def _solve_cb(self, button=None):
        ''' Solve the puzzle '''
        self._game.solve()

    def write_file(self, file_path):
        """ Write the grid status to the Journal """
        (dot_list, move_list, paused_time) = self._game.save_game()
        self.metadata['dotlist'] = ''
        for dot in dot_list:
            self.metadata['dotlist'] += str(dot)
            if dot_list.index(dot) < len(dot_list) - 1:
                self.metadata['dotlist'] += ' '
        self.metadata['movelist'] = ''
        for move in move_list:
            self.metadata['movelist'] += str(move)
            if move_list.index(move) < len(move_list) - 1:
                self.metadata['movelist'] += ' '
        _logger.debug(self.metadata['movelist'])
        self.metadata['paused_time'] = str(paused_time)

    def _restore(self):
        """ Restore the game state from metadata """
        dot_list = []
        dots = self.metadata['dotlist'].split()
        for dot in dots:
            dot_list.append(int(dot))
        if 'movelist' in self.metadata:
            move_list = []
            moves = self.metadata['movelist'].split()
            for move in moves:
                move_list.append(int(move))
        else:
            move_list = None
        _logger.debug(move_list)
        if 'paused_time' in self.metadata:
            paused_time = int(self.metadata['paused_time'])
        else:
            paused_time = 0
        self._game.restore_game(dot_list, move_list, paused_time)

    # Collaboration-related methods

    def set_data(self, data):
        pass

    def get_data(self):
        return None

    def _shared_cb(self, activity):
        """ Either set up initial share..."""
        self.after_share_join(True)

    def _joined_cb(self, activity):
        """ ...or join an exisiting share. """
        self.after_share_join(False)

    def after_share_join(self, sharer):
        self.waiting_for_hand = not sharer
        self._game.set_sharing(True)

    def _setup_dispatch_table(self):
        ''' Associate tokens with commands. '''
        self._processing_methods = {
            'n': [self._receive_new_game, 'get a new game grid'],
            'p': [self._receive_dot_click, 'get a dot click'],
        }

    def _message_cb(self, collab, buddy, msg):
        ''' Data from a tube has arrived. '''
        command = msg.get('command')
        payload = msg.get('payload')
        self._processing_methods[command][0](payload)

    def send_new_game(self):
        ''' Send a new grid to all players '''
        self.send_event('n', self._game.save_game())

    def _receive_new_game(self, payload):
        ''' Sharer can start a new game. '''
        (dot_list, move_list) = payload
        self._game.restore_game(dot_list, move_list)

    def send_dot_click(self, dot):
        ''' Send a dot click to all the players '''
        self.send_event('p', dot)

    def _receive_dot_click(self, payload):
        ''' When a dot is clicked, everyone should change its color. '''
        dot = payload
        self._game.remote_button_press(dot)

    def send_event(self, command, payload):
        """ Send event through the tube. """
        self._collab.post({'command': command, 'payload': payload})
