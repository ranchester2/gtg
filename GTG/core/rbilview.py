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

from gi.repository import GObject, Gio, Gtk
from enum import Enum
from uuid import uuid4, UUID
from liblarch import TreeNode, Tree
from GTG.core.base_store import BaseStore
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

class RbilViewNode(TreeNode, GObject.Object):
    def __eq__(self, other) -> bool:
        """Equivalence."""
        if isinstance(other, RbilViewNode):
            return self.get_item() == other.get_item()

    def __repr__(self):
        return repr(self._item)

    def __str__(self):
        return str(self._item)

    def __init__(self, item: GObject.Object, id: str):
        self._item = item
        TreeNode.__init__(self, id)
        GObject.Object.__init__(self)

    @GObject.Property(type=GObject.Object)
    def item(self):
        return self._item

    def get_item(self):
        return self.item


class RbilTree(Tree):
    # CONSTRUCT ONLY, but that doesn't work

    def __init__(self, store):
        super().__init__()
        self._store = store
        self._store.connect("added", self._on_base_added)
        self._store.connect("removed", self._on_base_removed)
        self._store.connect("parent-change", self._on_base_parent_change)
        self._store.connect("parent-removed", self._on_base_parent_remove)
        if self._store.get_n_items():
            logger.warn(f"rbil tree with non-initial tree is unsupported")

    def _on_base_added(self, store, item):
        logger.debug("add %s" % item)
        ritem = RbilViewNode(item, item.id)
        # I think the order of parent-remove and base-added emissions is wrong, so we need this check
        if not self.has_node(item.id):
            self.add_node(ritem)

    def _on_base_removed(self, store, item_id, original_position, was_toplevel, prepar):
        logger.debug("rem %s" % item_id)
        self.del_node(item_id)

    def _on_base_parent_change(self, store, item, parent):
        logger.debug("par-change %s->%s" % (item, parent))
        # It is removed completely in _on_base_removed before being added here
        ritem = RbilViewNode(item, item.id)
        self.add_node(ritem)
        ritem.add_parent(parent.id)

    def _on_base_parent_remove(self, store, item, parent):
        logger.debug("par-rem %s<-%s" % (item, parent))
        self.get_node(item.id).remove_parent(parent.id)

