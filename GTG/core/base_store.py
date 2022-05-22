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

"""Base for all store classes."""


from gi.repository import GObject, Gio, Gtk

from uuid import UUID
import logging

from lxml.etree import Element
from typing import List, Any, Dict


log = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# OVERRIDEN GLISTSTORE
# -----------------------------------------------------------------------------

class ContrListStore(Gio.ListStore):
    """
    A GListModelImplementation where you can easily do additional
    stuff when an item has been added/removed
    """
    def __init__(self, add_func, remove_func):
        super().__init__()
        self._add_func = add_func
        self._rem_func = remove_func

    def append(self, item):
        self._add_func(item)
        Gio.ListStore.append(self, item)

    def insert(self, position, item):
        Gio.ListStore.insert(self, position, item)

    def splice(self, position, n_removals, additions):
        for x in range(n_removals):
            self._rem_func(self.get_item(position + x))
        Gio.ListStore.splice(self, position, n_removals, additions)
        for addition in additions:
            self._add_func(addition)

    def remove(self, position):
        self._rem_func(self.get_item(position))
        Gio.ListStore.remove(self, position)

    def remove_all(self):
        for item in self:
            self._rem_func(item)
        Gio.ListStore.remove_all(self)


class BaseStore(GObject.Object, Gio.ListModel):
    """Base class for data stores."""

    def __repr__(self):
        repr_result = ""

        def recursive_print(tree: List, indent: int) -> None:
            """Inner print function. """

            tab =  '   ' * indent if indent > 0 else ''

            for node in tree:
                nonlocal repr_result
                repr_result += f'{tab} └ {node}\n'

                if node.children:
                    recursive_print(node.children, indent + 1)

        recursive_print(self.data, 0)
        return repr_result

    def __init__(self, **kwargs) -> None:
        self.lookup: Dict[UUID, Any] = {}
        self.data: List[Any] = []

        super().__init__(**kwargs)

    # --------------------------------------------------------------------------
    # GLISTMODEL
    # --------------------------------------------------------------------------

    # Why not just use find_with_equal_func:
    # https://gitlab.gnome.org/GNOME/pygobject/-/issues/493
    def _find_item_with_glist(self, list: Gio.ListModel, item: GObject.Object):
        for i, listitem in enumerate(list):
            if item == listitem:
                return i

    def do_get_item(self, position: int) -> Any:
        if position >= len(self):
            return None
        return self.data[position]

    def do_get_item_type(self) -> GObject.GType:
        return self.data[0].__gtype__

    def do_get_n_items(self) -> int:
        return len(self.data)

    # --------------------------------------------------------------------------
    # BASIC MANIPULATION
    # --------------------------------------------------------------------------

    def new(self) -> Any:
        raise NotImplemented


    def get(self, key: str) -> Any:
        """Get an item by id."""

        return self.lookup[key]


    def add(self, item: Any, parent_id: UUID = None) -> None:
        """Add an existing item to the store."""

        if item.id in self.lookup.keys():
            log.warn('Failed to add item with id %s, already added!',
                     item.id)

            raise KeyError

        # The store handles this only for toplevels, the items handle it for their
        # children
#        else:
#            if hasattr(item, "child_filters") and self.data:
#                # We should automatically copy the existing filters if
#                # possible
#                reference = self.data[0]
#                for name, filtermodel in reference.child_filters.items():
#                    item.child_filters[name] = Gtk.FilterListModel.new(
#                        item.children, filtermodel.get_filter()
#                    )

        self.data.append(item)
        self.lookup[item.id] = item

        self.emit('added', item)

        if parent_id:
            try:
                self.parent(item.id, parent_id)
            except KeyError:
                log.warn(('Failed to add item with id %s to parent %s, '
                         'parent not found!'), item.id, parent_id)
                raise

        log.debug('Added %s', item)

    def _on_item_filter_dependant_change(self, item):
        if item in self.data:
            index = self.data.index(item)
            self.items_changed(index, 1, 1)

    @GObject.Signal(name='added', arg_types=(object,))
    def add_signal(self, item):
        """Signal to emit when adding a new item."""
        self.items_changed(self.data.index(item), 0, 1)


    @GObject.Signal(name='removed', arg_types=(object,int,bool,bool))
    def remove_signal(self, item_id, item_position, was_toplevel, prepar):
        """Signal to emit when removing a new item."""
        self.items_changed(item_position, 1, 0)

    @GObject.Signal(name='parent-change', arg_types=(object, object))
    def parent_change_signal(self, *_):
        """Signal to emit when an item parent changes."""


    @GObject.Signal(name='parent-removed', arg_types=(object, object))
    def parent_removed_signal(self, *_):
        """Signal to emit when an item's parent is removed."""


    def remove(self, item_id: UUID) -> None:
        """Remove an existing item from the store."""

        original_position = 0
        # Instead of not giving original position, as signal
        # int arguments must be unsigned ints.
        was_toplevel = False
        item = self.lookup[item_id]
        parent = item.parent
        if not parent:
            original_position = self.data.index(self.lookup[item_id])
            was_toplevel = True

        def rec_del_func(item):
            for child in item.children:
                rec_del_func(child)
                del self.lookup[child.id]
        rec_del_func(item)

        if parent:
            parent.children.remove(self._find_item_with_glist(parent.children, item))
            del self.lookup[item_id]
        else:
            self.data.remove(item)
            del self.lookup[item_id]

        try:
            item.disconnect(item.__store_reserved_watch_sigid)
        # Does not have filter dependant changability
        except AttributeError:
            pass

        self.emit('removed', item_id, original_position, was_toplevel, False)


    # --------------------------------------------------------------------------
    # PARENTING
    # --------------------------------------------------------------------------

    def parent(self, item_id: UUID, parent_id: UUID) -> None:
        """Add a child to an item."""

        try:
            item = self.lookup[item_id]
        except KeyError:
            raise

        try:
            original_position = self.data.index(item)
            self.data.remove(item)
            self.emit('removed', item.id, original_position, True, True)
            self.lookup[parent_id].children.append(item)
            item.parent = self.lookup[parent_id]

            self.emit('parent-change', item, self.lookup[parent_id])
        except KeyError:
            raise


    def unparent(self, item_id: UUID, parent_id: UUID) -> None:
        """Remove child item from a parent."""

        for child in self.lookup[parent_id].children:
            if child.id == item_id:
                self.data.append(child)
                self.lookup[parent_id].children.remove(
                    self._find_item_with_glist(self.lookup[parent_id].children, child)
                )
                child.parent = None
                self.emit('added', child)

                self.emit('parent-removed',
                          self.lookup[item_id],
                          self.lookup[parent_id])
                return

        raise KeyError


    # --------------------------------------------------------------------------
    # SERIALIZING
    # --------------------------------------------------------------------------

    def from_xml(self, xml: Element) -> Any:
        raise NotImplemented


    def to_xml(self) -> Element:
        raise NotImplemented


    # --------------------------------------------------------------------------
    # UTILITIES
    # --------------------------------------------------------------------------

    def count(self, root_only: bool = False) -> int:
        """Count all the items in the store."""

        if root_only:
            return len(self.data)
        else:
            return len(self.lookup)


    def print_list(self) -> None:
        """Print the entre list of items."""

        print(self)

        for node in self.lookup.values():
            print(f'- {node}')


    def print_tree(self) -> None:
        """Print the all the items as a tree."""
        print(repr(self))
