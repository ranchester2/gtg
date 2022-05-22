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
from GTG.core.base_store import BaseStore


class VisibilityType(Enum):
    FMATCH = 0
    NPMATCH = 1
    NMATCH = 2

def visibility_func(item, filter):
    if not filter:
        return VisibilityType.FMATCH
    if not filter.match(item):
        return VisibilityType.NMATCH
    else:
        if item.parent and visibility_func(item.parent, filter) != VisibilityType.FMATCH:
            return VisibilityType.NPMATCH
        else:
            return VisibilityType.FMATCH


class FilterTreeItem(GObject.Object):
    def __eq__(self, other) -> bool:
        """Equivalence."""

        return self.get_item().id == other.get_item().id

    def __repr__(self):
        return str(self._item)

    def __init__(self, item: GObject.Object, id: UUID, filter, blocking, add_func, rem_func):
        super().__init__()
        self.id = id
        self._item = item
        self.filter = filter
        self.blocking = blocking
        self._add_func = add_func
        self._rem_func = rem_func
        self.parent = None
        self.children = Gio.ListStore()

    def resync(self, model=None, position=None, removed=None, added=None):
        # It is removed by the toplevel sync as remove is recursive
        #for child in self.children:
        #    self._rem_func(child.id)
        for real_child in self._item.children:
            vis_type = visibility_func(real_child, self.filter)
            if vis_type != VisibilityType.NMATCH:
                if vis_type == VisibilityType.FMATCH:
                    fitem = FilterTreeItem(real_child, uuid4(), self.filter, self.blocking, self._add_func, self._rem_func)
                    self._add_func(fitem, self.id)
                    fitem.resync()
                elif not self.blocking and vis_type == VisibilityType.NPMATCH:
                    fitem = FilterTreeItem(real_child, uuid4(), self.filter, self.blocking, self._add_func, self._rem_func)
                    self._add_func(fitem, None)
                    fitem.resync()

    def get_item(self):
        return self._item


class FilterStore(BaseStore):
    # CONSTRUCT ONLY, but that doesn't work
    store = GObject.Property(type=BaseStore)

    def __init__(self, **kwargs):
        self._blocking = True
        self._filter = None
        self._filter_changed_sigid = None
        # Avoid unnecesary multi resync during initial asignment of
        self._finit_complete = False
        super().__init__(**kwargs)
        self._finit_complete = True
        self.store.connect("added", self._on_base_added)
        self.store.connect("removed", self._on_base_removed)
        self.store.connect("parent-change", self._on_base_parent_change)
        self.store.connect("parent-removed", self._on_base_parent_remove)
        self._resync()

    @GObject.Property(type=Gtk.Filter)
    def filter(self):
        return self._filter

    @filter.setter
    def set_filter(self, value):
        if self._filter_changed_sigid:
            self._filter.disconnect(self._filter_changed_sigid)
            self._filter_changed_sigid = None
        self._filter = value
        for fitem in self.lookup.values():
            fitem.filter = self._filter
        if self._filter:
            self._filter_changed_sigid = self._filter.connect("changed", self._on_filter_changed)
        if self._finit_complete:
            self._resync()

    @GObject.Property(type=bool, default=True)
    def blocking(self):
        return self._blocking

    @blocking.setter
    def blocking(self, value: bool):
        self._blocking = value
        for fitem in self.lookup.values():
            fitem.blocking = self._blocking
        if self._finit_complete:
            self._resync()

    def _resync(self):
        # The extra list copy is because when removing like this, the gliststore gets
        # modified while we are still iterating, which causes weird behavior
        for item in list(self):
            self.remove(item.id)

        if self._blocking:
            for item in self.store:
                if visibility_func(item, self._filter) == VisibilityType.FMATCH:
                    fitem = FilterTreeItem(item, uuid4(), self._filter, self._blocking, self.add, self.remove)
                    self.add(fitem, None)
                    fitem.resync()
        else:
            f_r_id_map = {}
            for fitem in self.lookup.values():
                f_r_id_map[fitem.get_item().id] = fitem.id

            for item in self.store.lookup.values():
                vis_type = visibility_func(item, self._filter)
                if vis_type == VisibilityType.NMATCH:
                    return
                fitem = FilterTreeItem(item, uuid4(), self._filter, self._blocking, self.add, self.remove)
                if vis_type == VisibilityType.NPMATCH and item.parent.id not in f_r_id_map:
                    if item.parent.id in f_r_id_map:
                        self.add(fitem, f_r_id_map[item.parent.id])
                    else:
                        self.add(fitem, None)
                elif vis_type == VisibilityType.FMATCH:
                    self.add(fitem, None)
                    if item.parent.id in f_r_id_map:
                        self.add(fitem, f_r_id_map[item.parent.id])
                    else:
                        self.add(fitem, None)

    def _on_base_added(self, store, item):
        if visibility_func(item, self._filter) == VisibilityType.FMATCH:
            fitem = FilterTreeItem(item, uuid4(), self._filter, self._blocking, self.add, self.remove)
            self.add(fitem, None)
            # NEEDED? We may need to add new items that have never bene added before, though
            # this will definetely impact performance with lots of nested tasks
            fitem.resync()

    def _on_base_removed(self, store, item_id, original_position, was_toplevel, prepar):
        f_r_id_map = {}
        for fitem in self.lookup.values():
            f_r_id_map[fitem.get_item().id] = fitem.id
        if item_id in f_r_id_map:
            if not prepar:
                self.remove(f_r_id_map[item_id])
            else:
                original_position = self.data.index(self.get(f_r_id_map[item_id]))
                self.data.remove(self.get(f_r_id_map[item_id]))
                self.emit('removed', item_id, original_position, True, True)

    def _on_base_parent_change(self, store, item, parent):
        f_r_id_map = {}
        for fitem in self.lookup.values():
            f_r_id_map[fitem.get_item().id] = fitem.id
        vis_type = visibility_func(item, self._filter)
        if not self._blocking and vis_type == VisibilityType.NPMATCH and parent.id not in f_r_id_map:
            fitem = FilterTreeItem(item, uuid4(), self._filter, self._blocking, self.add, self.remove)
            self.add(item, None)
        elif vis_type == VisibilityType.NMATCH:
            return
        elif parent.id in f_r_id_map:
            fitem = FilterTreeItem(item, uuid4(), self._filter, self._blocking, self.add, self.remove)
            self.add(fitem, f_r_id_map[parent.id])

    def _on_base_parent_remove(self, store, item, parent):
        # For some reason in GTG these are sometimes randomly strs, not UIDS, which break the "in" operator,
        # interestingly in tests this doesn't happen
        item_id = UUID(str(item.id))
        parent_id = UUID(str(parent.id))

        f_r_id_map = {}
        for fitem in self.lookup.values():
            f_r_id_map[UUID(str(fitem.get_item().id))] = fitem.id
        if parent_id in f_r_id_map and item_id in f_r_id_map:
            # Manual child removal implementation as unparent will also remove it again
            fitem_parent = self.lookup[f_r_id_map[parent_id]]
            fitem = self.get(f_r_id_map[item_id])
            fitem.parent = None
            fitem_parent.children.remove(
                self._find_item_with_glist(fitem_parent.children, fitem)
            )
            self.emit('parent-removed', self.lookup[f_r_id_map[item_id]], self.lookup[f_r_id_map[parent_id]])

    def _on_filter_changed(self, filter, change):
        self._resync()
