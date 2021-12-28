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


import GTG.gtk.browser.tasks_view as tv
from GTG.core.tasks2 import Task2, Status
from GTG.core.search import search_filter
from gi.repository import Gtk


class StatusFilter(Gtk.Filter):
    __gtype_name__ = "StatusFilter"

    def __init__(self, *stati: Status):
        super().__init__()
        self.stati = stati

    def do_match(self, item):
        item = tv.unwrap_item(item, Task2)
        return item.status in self.stati


class ActionableFilter(Gtk.Filter):
    __gtype_name__ = "ActionableFilter"

    def __init__(self):
        super().__init__()

    def do_match(self, item):
        item = tv.unwrap_item(item, Task2)
        return item.is_actionable()

class TagsFilter(Gtk.Filter):
    __gtype_name__ = "TagsFilter"

    def __init__(self, recursive: bool, *tags):
        super().__init__()
        self._tags = tags
        self._recursive = recursive

    def do_match(self, item, alt_tags=None):
        task = tv.unwrap_item(item, Task2)
        m_tags = self._tags if alt_tags is None else alt_tags

        if self._recursive:
            # Show a task if a child matches
            # If we used child_filters, this wouldn't work
            # correctly when switching directly between different
            # TagsFilters instead of setting to None first.
            for child in task.children:
                if self.do_match(child):
                    return True
        if self._tags:
            if any(x in m_tags for x in task.tags):
                return True
            # A parent tag matches if any of its children cause a match
            for tag in m_tags:
                if self.do_match(task, tag.children):
                    return True
        else:
            return not task.tags


class SearchFilter(Gtk.Filter):
    __gtype_name__ = "SearchFilter"

    def __init__(self, query_rep: dict, recursive: dict):
        super().__init__()
        self._recursive = recursive
        self._query_rep = query_rep

    def do_match(self, item):
        task = tv.unwrap_item(item, Task2)
        if self._recursive:
            for child in task.children:
                if self.do_match(child):
                    return True
        return search_filter(task, self._query_rep)

