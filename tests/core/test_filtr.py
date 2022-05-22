
# -----------------------------------------------------------------------------
# Getting Things GNOME! - a personal organizer for the GNOME desktop
# Copyright (c) 2008-2015 - Lionel Dricot & Bertrand Rousseau
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see <http://www.gnu.org/licenses/>.
# -----------------------------------------------------------------------------

from unittest import TestCase
import configparser

from mock import patch, mock_open, Mock
from gi.repository import Gtk

from GTG.core.config import open_config_file, SectionConfig
from GTG.core.tasks2 import TaskStore
from GTG.core.filterview import FilterStore

class TestFilteredView(TestCase):
    def test_basic(self):
        store = TaskStore()
        filtered_store = FilterStore(
            store=store,
            filter=Gtk.CustomFilter.new(lambda item : "1" in item.title),
            blocking=True
        )

        ytask = store.new("1")
        cyntask = store.new("0")
        cyytask = store.new("1")
        cnytask = store.new("1")
        ntask = store.new("0")

        # Separate?
        parytask = store.new("1")
        store.parent(parytask.id, ytask.id)
        store.unparent(parytask.id, ytask.id)

        store.parent(cyntask.id, ytask.id)
        store.parent(cyytask.id, ytask.id)
        store.parent(cnytask.id, ntask.id)
        self.assertEquals(repr(filtered_store), f"""\
 └ Task: 1 ({ytask.id})
    └ Task: 1 ({cyytask.id})
 └ Task: 1 ({parytask.id})\n"""
        )

    def test_non_blocking(self):
        store = TaskStore()
        # Damage tracking logic
        filter_store_partial = FilterStore(
            store=store,
            filter=Gtk.CustomFilter.new(lambda item : "1" in item.title),
            blocking=False
        )
        ptask = store.new("0")
        yctask = store.new("1")
        ycctask = store.new("1")
        store.parent(ycctask.id, yctask.id)
        store.parent(yctask.id, ptask.id)
        # Initial sync logic
        filter_store_initial = FilterStore(
            store=store,
            filter=Gtk.CustomFilter.new(lambda item : "1" in item.title),
            blocking=False
        )
        self.assertEquals(repr(filter_store_partial), f"""\
 └ Task: 1 ({yctask.id})
    └ Task: 1 ({ycctask.id})\n"""
        )
        self.assertEquals(repr(filter_store_initial), f"""\
 └ Task: 1 ({yctask.id})
    └ Task: 1 ({ycctask.id})\n"""
        )

    def test_nested_basic(self):
        store = TaskStore()
        filter_store_1 = FilterStore(
            store=store,
            blocking=True
        )
        filter_store_2 = FilterStore(
            store=filter_store_1,
            blocking=True
        )
        ytask = store.new("1")
        cytask = store.new("1")
        store.parent(cytask.id, ytask.id)
        #print(repr(filter_store_2))
        return


