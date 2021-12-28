# -----------------------------------------------------------------------------
# Getting Things GNOME! - a personal organizer for the GNOME desktop
# Copyright (c) - The Getting Things GNOME Team
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


import locale
from GTG.core.tasks2 import Task2
import GTG.gtk.browser.tasks_view as tv
from gi.repository import Gtk, GObject


# GtkColumnView usually reverses the order itself when sorting
# the other way, it then cannot know about trees and they become
# upside-down.
# We patch GTK so that it moves the responsibility of reversing the sort order
# to the sorter instead.
# This is a simple implementation of that, that inverts it based on its
# inverted property that you bind to the column's inverted property.
class GTGInversibleSorter(Gtk.Sorter):
    inverted = GObject.Property(type=bool, default=False)

    def __init__(self, compare_func):
        super().__init__()
        self._compare_func = compare_func
        # Informing that we got inverted is needed,
        # for the thing using the sorter to invalidate itself.
        # Without this, expanding/unexpanding behaves very weirdly in inverted
        # trees.
        self.connect(
            "notify::inverted", lambda *_ : self.emit("changed", Gtk.SorterChange.INVERTED)
        )

    def do_compare(self, first_item, second_item):
        ordering = self._compare_func(first_item, second_item)
        if self.inverted:
            if ordering == Gtk.Ordering.LARGER:
                return Gtk.Ordering.SMALLER
            elif ordering == Gtk.Ordering.SMALLER:
                return Gtk.Ordering.LARGER
            else:
                return ordering
        else:
            return ordering


class DateSorter(GTGInversibleSorter):
    __gtype_name__ = "DateSorter"

    def __init__(self, date_type: str):
        super().__init__(self._compare_func)
        self.date_type = date_type

    def _compare_func(self, first_item, second_item):
        # can be useful to sort trees directly
        first_item = tv.unwrap_item(first_item, Task2)
        second_item = tv.unwrap_item(second_item, Task2)

        first_item_date = first_item.get_property(tv.DATE_TYPE_MAP[self.date_type])
        second_item_date = second_item.get_property(tv.DATE_TYPE_MAP[self.date_type])
        if first_item_date == second_item_date:
            return Gtk.Ordering.EQUAL
        elif first_item_date < second_item_date:
            return Gtk.Ordering.SMALLER
        elif first_item_date > second_item_date:
            return Gtk.Ordering.LARGER


class NameSorter(GTGInversibleSorter):
    # Basically a reimplementation of Gtk.StringSorter that
    # only works on GTG Task names as Gtk.Expression is broken
    # in PyGObject which is required to use the superior
    # Gtk.StringSorter
    __gtype_name__ = "NameSorter"

    def __init__(self):
        super().__init__(self._compare_func)

    def _compare_func(self, first_item, second_item):
        # can be useful to sort trees directly
        first_item = tv.unwrap_item(first_item, Task2)
        second_item = tv.unwrap_item(second_item, Task2)

        # Strip "@" and convert everything to lowercase to allow fair comparisons;
        # otherwise, Capitalized Tasks get sorted after their lowercase equivalents,
        # and tasks starting with a tag would get sorted before everything else.
        t1 = first_item.title.replace("@", "").lower()
        t2 = second_item.title.replace("@", "").lower()

        result = locale.strcoll(t1, t2)
        if result == 0:
            return Gtk.Ordering.EQUAL
        if result < 0:
            return Gtk.Ordering.SMALLER
        if result > 0:
            return Gtk.Ordering.LARGER

