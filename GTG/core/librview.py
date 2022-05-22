# -----------------------------------------------------------------------------
# Getting Things GNOME! - a personal organizer for the GNOME desktop
# Copyright (c) The GTG Team
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

""" Everthing related to filtering support """

from gi.repository import GObject, Gio, Gtk, GLib
from enum import Enum
from uuid import uuid4, UUID
from liblarch import TreeNode
from GTG.core.base_store import BaseStore


class LarchTreeItem(GObject.Object):
    __gtype_name__ = "LarchTreeItem"

    def __eq__(self, other) -> bool:
        """Equivalence."""
        if isinstance(other, LarchTreeItem):
            return self.get_item().get_id() == other.get_item().get_id()

    def __repr__(self):
        return str(self._item)

    def __init__(self, item: TreeNode, id: UUID):
        self.id = id
        self._item = item
        self.parent = None
        self.children = Gio.ListStore()
        super().__init__()

    @GObject.Property(type=GObject.Object)
    def item(self):
        return self._item

    def get_item(self):
        return self.item


class LibrStore(BaseStore):
    # CONSTRUCT ONLY, but that doesn't work

    def __init__(self, viewtree):
        super().__init__()
        self._tree = viewtree
        self._tree.register_cllbck('node-added-inview', self._on_base_added)
        self._tree.register_cllbck('node-deleted-inview', self._on_base_removed)
        self._tree.register_cllbck('node-modified-inview', self._on_base_updated)
        self._tree.get_current_state()

    def get_pathp(self, liblarch_path: tuple):
        try:
            end_parent = liblarch_path[-2]
        except IndexError:
            end_parent = None
        if end_parent is None:
            return None
        for item in self.lookup.values():
            if item.get_item().get_id() == liblarch_path[-2]:
                return item

    def _on_base_added(self, node_id, path):
        expected_parent = self.get_pathp(path)
        litem = LarchTreeItem(self._tree.get_node(node_id), uuid4())
        if expected_parent:
            self.add(litem, expected_parent.id)
        else:
            self.add(litem)

    def _on_base_removed(self, node_id, path):
        for item in self.lookup.values():
            if item.get_item().get_id() == node_id:
                self.remove(item.id)
                return

    def _on_base_updated(self, node_id, path):
        try:
            item = self.get(UUID(node_id))
        except KeyError:
            # We cannot assume that the node is in the tree because
            # update is asynchronus
            # Also, we should consider that missing an update is not critical
            # and ignoring the case where there is no iterator
            return
        else:
            par = item.parent
            self.remove(item.id)
            self.add(item, par.id)
