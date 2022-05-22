
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

from gi.repository import Gtk

from GTG.core.tasks2 import TaskStore
from GTG.core.rbilview import RbilTree
from GTG.core.librview import LibrStore


class TestRbilTree(TestCase):
    def test_basic(self):
      store = TaskStore()
      rbil = RbilTree(store)
      librl = LibrStore(rbil.get_viewtree())

      top1 = store.new("t1")
      top2 = store.new("t2")
      chi = store.new("c1", top1.id)
      store.unparent(chi.id, chi.parent.id)
      store.parent(chi.id, top2.id)
      librl.print_tree()

