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

"""Everything related to tasks."""


from gi.repository import GObject, Gio, Gtk
from gettext import gettext as _

from uuid import uuid4, UUID
import logging
from typing import Callable, Any, Optional
from enum import Enum
import re
import xml.sax.saxutils
import datetime
from operator import attrgetter

from lxml.etree import Element, SubElement, CDATA

from GTG.core.base_store import BaseStore, ContrListStore
from GTG.core.tags2 import Tag2, TagStore
from GTG.core.dates import Date

log = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# REGEXES
# ------------------------------------------------------------------------------

TAG_REGEX = re.compile(r'^\B\@\w+(\-\w+)*\,+')
SUB_REGEX = re.compile(r'\{\!.+\!\}')


# ------------------------------------------------------------------------------
# TASK STATUS
# ------------------------------------------------------------------------------

class Status(Enum):
    """Status for a task."""

    ACTIVE = 'Active'
    DONE = 'Done'
    DISMISSED = 'Dismissed'


class Filter(Enum):
    """Types of filters."""

    ACTIVE = 'Active'
    ACTIONABLE = 'Actionable'
    CLOSED = 'Closed'
    STATUS = 'Status'
    TAG = 'Tag'
    PARENT = 'Parent'
    CHILDREN = 'Children'


# ------------------------------------------------------------------------------
# TASK
# ------------------------------------------------------------------------------

class Task2(GObject.Object):
    """A single task."""

    __gtype_name__ = 'gtg_Task'
    __gsignals__ = {
        # HACK:
        # GtkFilterListModel does not support changing items, so we must indicate somehow
        # to the store that is storing us that we changed in such a way, so that it could
        # fire an items-changed signal with a fake addition/removal for the Gtk Filters
        # to run again
        'filter_dependant_changed': (GObject.SignalFlags.RUN_FIRST, None, ())
    }
    __slots__ = ['id', 'raw_title', 'tags',
                 'children', 'child_filters', 'status', 'parent',
                 '_date_added', '_date_due', '_date_start', '_date_closed',
                 '_date_modified']

    def __init__(self, id: UUID, title: str) -> None:
        super().__init__()
        self.id = id
        self.raw_title = "" # GOBJECT TEMP
        self.title = title.strip('\t\n')
        self.tags = Gio.ListStore.new(Tag2)
        self.tags.connect("items-changed", self._on_tags_changed)
        self.children = ContrListStore(
            self._children_add_func, self._children_rem_func
        )
        self.child_filters = {}
        self.status = Status.ACTIVE
        self.parent = None
        # for users to store property bindings for easy
        # unbinding
        self.bindings = {}

        self._content = ''
        self._date_added = Date.no_date()
        self._date_due = Date.no_date()
        self._date_start = Date.no_date()
        self._date_closed = Date.no_date()
        self._date_modified = Date(datetime.datetime.now())

    def _children_add_func(self, item):
        for name, filtermodel in self.child_filters.items():
            child_filter = Gtk.FilterListModel.new(item.children, filtermodel.get_filter())
            item.child_filters[name] = child_filter
        item.__container_reserved_watch_sigid = item.connect(
            'filter_dependant_changed', self._on_child_filter_dependant_change)

    def _children_rem_func(self, item):
        item.disconnect(item.__container_reserved_watch_sigid)

    def _on_child_filter_dependant_change(self, item):
        # it is not a python list, getting the index is a bit harder
        for idx, l_item in enumerate(self.children):
            if l_item == item:
                index = idx
                break
        self.children.items_changed(index, 1, 1)

    def _on_tags_changed(self, model, position, removed, added):
        self.emit("filter_dependant_changed")

    def is_actionable(self) -> bool:
        """Determine if this task is actionable."""
        actionable_tags = all(t.actionable for t in self.tags)
        active_children = all(t.status != Status.ACTIVE for t in self.children)
        days_left = self._date_start.days_left()
        can_start = True if not days_left else days_left <= 0

        return (self.status == Status.ACTIVE
                and self._date_due != Date.someday()
                and actionable_tags
                and active_children
                and can_start)


    def toggle_status(self, propagate: bool = True) -> None:
        """Toggle between possible statuses."""

        if self.status is Status.ACTIVE:
            self.status = Status.DONE
            self.date_closed = Date.today()

        else:
            self.status = Status.ACTIVE
            self.date_closed = Date.no_date()

            if self.parent and self.parent.status is not Status.ACTIVE:
                self.parent.toggle_status(propagate=False)

        if propagate:
            for child in self.children:
                child.toggle_status()
        self.emit("filter_dependant_changed")


    def dismiss(self) -> None:
        """Set this task to be dismissed."""

        self.set_status(Status.DISMISSED)


    def set_status(self, status: Status, propogate: bool = True) -> None:
        """Set status for task."""

        self.status = status

        if self.status == Status.ACTIVE and self.parent:
            self.parent.set_status(Status.ACTIVE, propogate=False)

        if propogate:
            for child in self.children:
                child.set_status(status)
        self.emit("filter_dependant_changed")


    @GObject.property(type=Date)
    def date_due(self) -> Date:
        return self._date_due


    @date_due.setter
    def date_due(self, value: Date) -> None:
        self._date_due = value

        if not value or value.is_fuzzy():
            return

        for child in self.children:
            if (child.date_due
               and not child.date_due.is_fuzzy()
               and child.date_due > value):

                child.date_due = value

        if (self.parent
           and self.parent.date_due
           and self.parent.date_due.is_fuzzy()
           and self.parent.date_due < value):
            self.parent.date_due = value


    @GObject.Property(type=Date)
    def date_added(self) -> Date:
        return self._date_added


    @date_added.setter
    def date_added(self, value: Any) -> None:
        self._date_added = Date(value)


    @GObject.Property(type=Date)
    def date_start(self) -> Date:
        return self._date_start


    @date_start.setter
    def date_start(self, value: Any) -> None:
        self._date_start = Date(value)


    @GObject.Property(type=Date)
    def date_closed(self) -> Date:
        return self._date_closed


    @date_closed.setter
    def date_closed(self, value: Any) -> None:
        self._date_closed = Date(value)


    @GObject.Property(type=Date)
    def date_modified(self) -> Date:
        return self._date_modified


    @date_modified.setter
    def date_modified(self, value: Any) -> None:
        self._date_modified = Date(value)


    @GObject.Property(type=str)
    def title(self) -> str:
        return self.raw_title

    @title.setter
    def title(self, value) -> None:
        self.raw_title = value.strip('\t\n') or _('(no title)')

    @GObject.Property(type=str)
    def content(self) -> str:
        return self._content

    @content.setter
    def content(self, value) -> None:
        self._content = value
        self.notify('excerpt')

    @GObject.property(type=str)
    def excerpt(self) -> str:
        lines = 1
        char = 80
        # defensive programmation to avoid returning None
        if self.content:
            txt = self.content

            txt = txt.strip()

            for tag in [tag.name for tag in self.tags]:
                txt = (txt.replace(f'@{tag}, ', '')
                          .replace(f'@{tag},', '')
                          .replace(f'@{tag}', ''))

            txt = re.sub(SUB_REGEX, '', txt)

            # Strip blank lines and get desired amount of lines
            txt = [line for line in txt.splitlines() if line]
            txt = txt[:lines]
            txt = '\n'.join(txt)

            # We keep the desired number of char
            if char > 0:
                txt = txt[:char]
            return f'{txt}…'
        else:
            return ''

        # Strip tags
        txt = re.sub(TAG_REGEX, '', self.content)
        print(txt)

        # Strip subtasks
        txt = SUB_REGEX.sub('', txt)

        # Strip blank lines and set within char limit
        return txt.partition("\n")[0][:80]


    def add_tag(self, tag: Tag2) -> None:
        """Add a tag to this task."""

        if isinstance(tag, Tag2):
            if tag not in self.tags:
                self.tags.append(tag)
        else:
            raise ValueError


    def remove_tag(self, tag_name: str) -> None:
        """Remove a tag from this task."""

        for t in self.tags:
            # FIXME: one item is none
            if not t:
                continue
            if t.name == tag_name:
                self.tags.remove(self.tags.find(t)[1])
                (self.content.replace(f'{tag_name}\n\n', '')
                             .replace(f'{tag_name},', '')
                             .replace(f'{tag_name}', ''))


    @property
    def days_left(self) -> Optional[Date]:
        return self.date_due.days_left()


    def update_modified(self) -> None:
        """Update the modified property."""

        self.modified = Date(datetime.datetime.now())


    def __str__(self) -> str:
        """String representation."""

        return f'Task: {self.title} ({self.id})'


    def __repr__(self) -> str:
        """String representation."""

        tags = ', '.join([t.name for t in self.tags])
        return (f'Task "{self.title}" with id "{self.id}".'
                f'Status: {self.status}, tags: {tags}')


    def __eq__(self, other) -> bool:
        """Equivalence."""

        return self.id == other.id


    def __hash__(self) -> int:
        """Hash (used for dicts and sets)."""

        return hash(self.id)


# ------------------------------------------------------------------------------
# STORE
# ------------------------------------------------------------------------------

class TaskStore(BaseStore):
    """A tree of tasks."""

    __gtype_name__ = 'gtg_TaskStore'

    #: Tag to look for in XML
    XML_TAG = 'task'

    def __init__(self) -> None:
        super().__init__()


    def __str__(self) -> str:
        """String representation."""

        return f'Task Store. Holds {len(self.lookup)} task(s)'


    def get(self, tid: UUID) -> Task2:
        """Get a task by name."""

        return self.lookup[tid]


    def new(self, title: str, parent: UUID = None) -> Task2:
        """Create a new task and add it to the store."""

        tid = uuid4()
        task = Task2(id=tid, title=title)

        self.add(task, parent)

        #if parent:
        #    self.add(task, parent)
        #else:
        #    self.data.append(task)
        #    self.lookup[tid] = task

        #self.emit('added', task)
        return task


    def from_xml(self, xml: Element, tag_store: TagStore) -> None:
        """Load up tasks from a lxml object."""

        elements = list(xml.iter(self.XML_TAG))

        for element in elements:
            tid = element.get('id')
            title = element.find('title').text
            status = element.get('status')

            task = Task2(id=tid, title=title)

            dates = element.find('dates')

            modified = dates.find('modified').text
            task.date_modified = Date(datetime.datetime.fromisoformat(modified))

            added = dates.find('added').text
            # HACK
            if not added:
                added = datetime.datetime.now().isoformat()
            task.date_added = Date(datetime.datetime.fromisoformat(added))

            if status == 'Done':
                task.status = Status.DONE
            elif status == 'Dismissed':
                task.status = Status.DISMISSED

            # Dates
            try:
                closed = Date.parse(dates.find('done').text)
                task.date_closed = closed
            except AttributeError:
                pass

            fuzzy_due_date = Date.parse(dates.findtext('fuzzyDue'))
            due_date = Date.parse(dates.findtext('due'))

            if fuzzy_due_date:
                task._date_due = fuzzy_due_date
            elif due_date:
                task._date_due = due_date

            fuzzy_start = dates.findtext('fuzzyStart')
            start = dates.findtext('start')

            if fuzzy_start:
                task.date_start = Date(fuzzy_start)
            elif start:
                task.date_start = Date(start)

            taglist = element.find('tags')

            if taglist is not None:
                for t in taglist.iter('tag'):
                    try:
                        tag = tag_store.get(t.text)
                        task.tags.append(tag)
                    except KeyError:
                        pass

            # Content
            content = element.find('content').text or ''
            content = content.replace(']]&gt;', ']]>')
            task.content = content

            self.add(task)

            log.debug('Added %s', task)


        # All tasks have been added, now we parent them
        for element in elements:
            parent_tid = element.get('id')
            subtasks = element.find('subtasks')

            for sub in subtasks.findall('sub'):
                self.parent(sub.text, parent_tid)


    def to_xml(self) -> Element:
        """Serialize the taskstore into a lxml element."""

        root = Element('tasklist')

        for task in self.lookup.values():
            element = SubElement(root, self.XML_TAG)
            element.set('id', str(task.id))
            element.set('status', task.status.value)

            title = SubElement(element, 'title')
            title.text = task.title

            tags = SubElement(element, 'tags')

            for t in task.tags:
                tag_tag = SubElement(tags, 'tag')
                tag_tag.text = str(t.id)

            dates = SubElement(element, 'dates')

            added_date = SubElement(dates, 'added')
            added_date.text = str(task.date_added)

            modified_date = SubElement(dates, 'modified')
            modified_date.text = str(task.date_modified)

            done_date = SubElement(dates, 'done')
            done_date.text = str(task.date_closed)

            due_date = task.date_due
            due_tag = 'fuzzyDue' if due_date.is_fuzzy() else 'due'
            due = SubElement(dates, due_tag)
            due.text = str(due_date)

            start_date = task.date_start
            start_tag = 'fuzzyStart' if start_date.is_fuzzy() else 'start'
            start = SubElement(dates, start_tag)
            start.text = str(start_date)

            subtasks = SubElement(element, 'subtasks')

            for subtask in task.children:
                sub = SubElement(subtasks, 'sub')
                sub.text = str(subtask.id)

            content = SubElement(element, 'content')
            text = task.content

            # Poor man's encoding.
            # CDATA's only poison is this combination of characters.
            text = text.replace(']]>', ']]&gt;')
            content.text = CDATA(text)

        return root


    def filter(self, filter_type: Filter, arg = None) -> list:
        """Filter tasks according to a filter type."""

        def filter_tag(tag: str) -> list:
            """Filter tasks that only have a specific tag."""

            output = []

            for t in self.data:
                tags = [_tag for _tag in t.tags]

                # Include the tag's childrens
                for _tag in t.tags:
                    for child in _tag.children:
                        tags.append(child)

                if tag in tags:
                    output.append(t)

            return output


        if filter_type == Filter.STATUS:
            return [t for t in self.data if t.status == arg]

        elif filter_type == Filter.ACTIVE:
            return [t for t in self.data if t.status == Status.ACTIVE]

        elif filter_type == Filter.CLOSED:
            return [t for t in self.data if t.status != Status.ACTIVE]

        elif filter_type == Filter.ACTIONABLE:
            return [t for t in self.data if t.is_actionable()]

        elif filter_type == Filter.PARENT:
            return [t for t in self.lookup.values() if not t.parent]

        elif filter_type == Filter.CHILDREN:
            return [t for t in self.lookup.values() if t.parent]

        elif filter_type == Filter.TAG:
            if type(arg) == list:
                output = []

                for t in arg:
                    if output:
                        output = list(set(output) & set(filter_tag(t)))
                    else:
                        output = filter_tag(t)


                return output

            else:
                return filter_tag(arg)


    def filter_custom(self, key: str, condition: Callable) -> list:
        """Filter tasks according to a function."""

        return [t for t in self.lookup.values() if condition(getattr(t, key))]


    def sort(self, tasks: list = None,
             key: str = None, reverse: bool = False) -> None:
        """Sort a list of tasks in-place."""

        tasks = tasks or self.data
        key = key or 'date_added'

        for t in tasks:
            # TOOD: use glib comparefunc as this will probably be a GListstore
            return
            t.children.sort(key=attrgetter(key), reverse=reverse)

        tasks.sort(key=attrgetter(key), reverse=reverse)
