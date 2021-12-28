# -----------------------------------------------------------------------------
# Getting Things GNOME! - a personal organizer for the GNOME desktop
# Copyright (c) 2008-2013 - Lionel Dricot & Bertrand Rousseau
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
import os
import uuid
from uuid import UUID
from datetime import datetime

from gi.repository import GObject, GLib, Gio, Gtk, Gdk

from GTG.core.dirs import UI_DIR
from GTG.core.search import parse_search_query, search_filter
from GTG.core.tasks2 import Task2
from GTG.core.requester import Requester
from gettext import gettext as _
from GTG.gtk.browser.context_menu_bin import ContextMenuBin
from GTG.gtk.browser.tag_background_bin import TagBackgroundBin
from GTG.gtk.browser.tags_display import TagsDisplay
from GTG.gtk.browser.sorting import DateSorter, NameSorter
from GTG.core.dates import Date


DATE_TYPE_MAP = {
    "due": "date-due",
    "closed": "date-closed",
    "start": "date-start"
}


def unwrap_item(item, *core_types):
    """
    Unwrap a tree item to get the underlying item.
    item: the item you want to unwrap,
    core_type: the expected type of the base item.
    Returns either the base item, or None if this none
    exists (sometiems the case when collapsing trees)
    """
    while not (type(item) in core_types):
        try:
            item = item.get_item()
        except AttributeError:
            return None
    return item


def set_recursive_filter(filter: Gtk.Filter, model: Gtk.FilterListModel, fid: UUID):
    model.set_filter(filter)
    for item in model:
        try:
            item.child_filters[fid]
        except:
            item.child_filters[fid] = Gtk.FilterListModel.new(item.children)
        set_recursive_filter(filter, item.child_filters[fid], fid)


# Why a row and not a BuilderSignalListItemFactory?
# The big problem with that is how to give the requester
# to the tagbackgroundbin, as we cannot reasonably have
# it as a property on any relevant object.
# So we need a SignalListItemFactory to set it as a property
# on this intermediate row object.
@Gtk.Template(filename=os.path.join(UI_DIR, "list_tags.ui"))
class TagsRow(Gtk.Box):
    __gtype_name__ = "TagsRow"

    task = GObject.Property(type=Task2)
    requester = GObject.Property(type=Requester)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@Gtk.Template(filename=os.path.join(UI_DIR, "list_task.ui"))
class TaskRow(Gtk.Box):
    __gtype_name__ = "TaskRow"

    task = GObject.Property(type=Task2)
    list_row = GObject.Property(type=Gtk.TreeListRow)
    menu_model = GObject.Property(type=Gio.MenuModel)
    description_visible = GObject.Property(type=bool, default=False)

    def __init__(self, **kwargs):
        self._req = None
        self._config = None
        self._config_sigid = None
        super().__init__(**kwargs)

    @GObject.Property(type=Requester)
    def requester(self):
        return self._req

    @requester.setter
    def requester(self, value):
        if self._config_sigid:
            self._config.disconnect(self._config_sigid)
            self._config_sigid = None
        self._req = value
        if self._req:
            self._config = self._req.get_global_config()
            self._config_sigid = self._config.connect("config-changed", self._sync_with_config)
            self._sync_with_config()

    def _sync_with_config(self, config=None, option=None):
        if option and option != "contents_preview_enable":
            return
        self.description_visible = self._req.get_config("browser").get(
            "contents_preview_enable"
        )


# While this is a quite simple row, when I tried doing it manually
# I couldn't figure out how to stop that it kept leaking memory
# and disconnecting the signal handler just wasn't helping (which was
# needed to set to a property of a property)
# Using GtkExpression in UI file just works in terms of not leaking memory.
# The readable_string wrapper property because:
#   - It allows to easily make all date columns share a UI file
#   - Date doesn't have a readable string property
@Gtk.Template(filename=os.path.join(UI_DIR, "list_date.ui"))
class DateRow(Gtk.Box):
    __gtype_name__ = "DateRow"

    menu_model = GObject.Property(type=Gio.MenuModel)
    requester = GObject.Property(type=Requester)

    def __init__(self, date_type: str, **kwargs):
        self._date_type = date_type
        self._task = None
        self._date_watch_sigid = None
        super().__init__(**kwargs)

    @GObject.Property(type=Task2)
    def task(self):
        return self._task

    @task.setter
    def task(self, value):
        if self._date_watch_sigid:
            self._task.disconnect(self._date_watch_sigid)
            self._date_watch_sigid = None
        self._task = value
        if self._task:
            self._date_watch_sigid = self._task.connect(
                f"notify::{DATE_TYPE_MAP[self._date_type]}",
                lambda *_ : self.notify("readable-date")
            )
            self.notify("readable-date")

    @GObject.Property(type=str)
    def readable_date(self):
        if self._task:
            date = self._task.get_property(DATE_TYPE_MAP[self._date_type])
            return date.to_readable_string()


class TasksView(Gtk.ColumnView):
    context_menu_model = GObject.Property(type=Gio.MenuModel)
    is_flat = GObject.Property(type=bool, default=False)

    def __init__(self, requester, config):
        super().__init__()
        self._req = requester
        self.add_css_class("tasks-list")

        tasks_tree = self._req.get_tasks_tree()
        tasks_tree.connect("added", self._on_base_tree_added)
        self._req_filter = None
        self._req_status_filter = None
        self._req_tags_filter = None
        self._req_search_filter = None
        self._req_filter_model = Gtk.FilterListModel.new(self._req.get_tasks_tree(), None)
        self._fid = uuid.uuid4()
        set_recursive_filter(None, self._req_filter_model, self._fid)
        self._tree_model = Gtk.TreeListModel.new(
            self._req_filter_model, False, True, self._tasks_model_create_func
        )
        self._sort_model = Gtk.SortListModel.new(self._tree_model, self.get_sorter())
        self._sort_model.set_sorter(self.get_sorter())
        self._tree_status_filter_model = Gtk.FilterListModel.new(self._sort_model, None)
        self._tree_tags_filter_model = Gtk.FilterListModel.new(self._tree_status_filter_model, None)
        self._tree_search_filter_model = Gtk.FilterListModel.new(self._tree_tags_filter_model, None)
        self._selection_model = Gtk.MultiSelection.new(self._tree_search_filter_model)
        self.set_model(self._selection_model)

        tag_factory = Gtk.SignalListItemFactory()
        tag_factory.connect("setup", self._tags_setup)
        tag_factory.connect("bind", self._tags_bind)
        tag_factory.connect("unbind", self._tags_unbind)
        tag_factory.connect("teardown", self._tags_teardown)
        tag_column = Gtk.ColumnViewColumn(factory=tag_factory)
        self.append_column(tag_column)

        task_factory = Gtk.SignalListItemFactory()
        task_factory.connect("setup", self._tasks_setup)
        task_factory.connect("bind", self._tasks_bind)
        task_factory.connect("unbind", self._tasks_unbind)
        task_factory.connect("teardown", self._tasks_teardown)
        tasks_raw_sorter = NameSorter()
        tasks_sorter = Gtk.TreeListRowSorter.new(tasks_raw_sorter)
        tasks_column = Gtk.ColumnViewColumn(
            title=_("Tasks"),
            factory=task_factory,
            expand=True,
            sorter=tasks_sorter
        )
        tasks_column.bind_property("inverted", tasks_raw_sorter, "inverted")
        self.append_column(tasks_column)

        start_raw_sorter = DateSorter("start")
        start_sorter = Gtk.TreeListRowSorter.new(start_raw_sorter)
        self._start_column = Gtk.ColumnViewColumn(
            title=_("Start Date"), factory=self._create_date_factory("start"), sorter=start_sorter
        )
        self._start_column.bind_property("inverted", start_raw_sorter, "inverted")
        self.append_column(self._start_column)

        due_raw_sorter = DateSorter("due")
        due_sorter = Gtk.TreeListRowSorter.new(due_raw_sorter)
        self._due_column = Gtk.ColumnViewColumn(
            title=_("Due"), factory=self._create_date_factory("due"), sorter=due_sorter
        )
        self._due_column.bind_property("inverted", due_raw_sorter, "inverted")
        self.append_column(self._due_column)

        closed_raw_sorter = DateSorter("closed")
        closed_sorter = Gtk.TreeListRowSorter.new(closed_raw_sorter)
        self._closed_column = Gtk.ColumnViewColumn(
            title=_("Closed Date"), factory=self._create_date_factory("closed"), sorter=closed_sorter
        )
        self._closed_column.bind_property("inverted", closed_raw_sorter, "inverted")
        self.append_column(self._closed_column)

        view_drop_target = Gtk.DropTarget.new(Task2, Gdk.DragAction.MOVE)
        view_drop_target.connect("accept", self._on_drag_accept)
        view_drop_target.connect("drop", self._on_drag_drop, True)
        # We want the drop effect to be on the list, which is our second child,
        # as columnview:
        #       - header
        #       - listview
        # And for some reason the style doesn't work on the columnview
        self.get_first_child().get_next_sibling().add_controller(view_drop_target)

    def _on_base_tree_added(self, tree, item: Task2):
        set_recursive_filter(self._req_filter, item.child_filters[self._fid], self._fid)

    def _tasks_model_create_func(self, item):
        return item.child_filters[self._fid]

    # Dates

    def _date_setup(self, factory, listitem, date_type: str):
        row = DateRow(date_type)
        listitem.set_child(row)

    def _date_bind(self, factory, listitem, date_type: str):
        row = listitem.get_child()
        row.__factory_reserved_menu_bind = self.bind_property(
            "context-menu-model", row, "menu-model", GObject.BindingFlags.SYNC_CREATE
        )
        row.set_property("task", unwrap_item(listitem, Task2))
        row.set_property("requester", self._req)

    def _date_unbind(self, factory, listitem, date_type: str):
        row = listitem.get_child()
        row.__factory_reserved_menu_bind.unbind()
        row.set_property("task", None)
        row.set_property("requester", None)

    def _date_teardown(self, factory, listitem, date_type: str):
        listitem.set_child(None)

    # Tasks

    def _tasks_setup(self, factory, listitem):
        row = TaskRow()
        listitem.set_child(row)

    def _on_drag_prepare(self, source, x, y, task):
        if self.is_flat:
            return
        value = GObject.Value(Task2, task)
        return Gdk.ContentProvider.new_for_value(value)

    def _on_drag_begin(self, source, drag):
        listitem = source.get_widget()
        listitem.add_css_class("dragged-task")
        dragicon = Gtk.DragIcon.get_for_drag(drag)
        frame = Gtk.Frame()
        frame.add_css_class("square-frame")
        frame.set_child(
            Gtk.Picture.new_for_paintable(
                Gtk.WidgetPaintable.new(source.get_widget())
            )
        )
        dragicon.set_child(frame)

    def _on_drag_end(self, source, drag, delete_data):
        listitem = source.get_widget()
        if listitem:
            listitem.remove_css_class("dragged-task")

    def _on_drag_accept(self, drop_target, drop):
        if self.is_flat:
            return False
        return drop.get_formats().contain_gtype(Task2)

    def _on_drag_drop(self, drop_target, task, x, y, on_list=False):
        tasks_tree = self._req.get_tasks_tree()

        if on_list:
            if task.parent:
                tasks_tree.unparent(task.id, task.parent.id)
                return True
            else:
                return False

        ## MASSIVE HACK:
        # Since the DropTarget is on the GtkListItemWidget,
        # it is quite hard to figure out what Task this has.
        # Traverse the widget tree down until we encounter
        # something with the "task" property and get it from
        # there.
        child = drop_target.get_widget()
        while not hasattr(child.props, "task"):
            child = child.get_first_child()
        target_task = child.get_property("task")

        if task == target_task:
            return False
        # FIXME: you should be able to parent a task
        # to one of its children
        target_parent = target_task.parent
        while target_parent is not None:
            if target_parent == task:
                return False
            target_parent = target_parent.parent

        if task.parent:
            tasks_tree.unparent(task.id, task.parent.id)
        tasks_tree.parent(task.id, target_task.id)

        return True

    def _tasks_bind(self, factory, listitem):
        item = unwrap_item(listitem, Task2)
        row = listitem.get_child()
        row.__factory_reserved_menu_bind = self.bind_property(
            "context-menu-model", row, "menu-model", GObject.BindingFlags.SYNC_CREATE
        )
        row.set_property("task", item)
        row.set_property("list-row", listitem.get_item())
        row.set_property("requester", self._req)

        row.__factory_reserved_drag_source = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
        row.__factory_reserved_drag_source.connect("prepare", self._on_drag_prepare, item)
        row.__factory_reserved_drag_source.connect("drag-begin", self._on_drag_begin)
        row.__factory_reserved_drag_source.connect("drag-end", self._on_drag_end)
        row.__factory_reserved_drop_target = Gtk.DropTarget.new(Task2, Gdk.DragAction.MOVE)
        row.__factory_reserved_drop_target.connect("drop", self._on_drag_drop)
        row.__factory_reserved_drop_target.connect("accept", self._on_drag_accept)

        listitemwidget = row.get_parent().get_parent()
        listitemwidget.add_controller(row.__factory_reserved_drag_source)
        listitemwidget.add_controller(row.__factory_reserved_drop_target)

    def _tasks_unbind(self, factory, listitem):
        row = listitem.get_child()
        row.__factory_reserved_menu_bind.unbind()
        row.set_property("task", None)
        row.set_property("list-row", None)
        row.set_property("requester", None)
        listitemwidget = row.get_parent().get_parent()
        listitemwidget.remove_controller(row.__factory_reserved_drag_source)
        listitemwidget.remove_controller(row.__factory_reserved_drop_target)

    def _tasks_teardown(self, factory, listitem):
        listitem.set_child(None)

    # Tags

    def _tags_setup(self, factory, listitem):
        row = TagsRow()
        listitem.set_child(row)

    def _tags_bind(self, factory, listitem):
        row = listitem.get_child()
        row.set_property("task", unwrap_item(listitem, Task2))
        row.set_property("requester", self._req)

    def _tags_unbind(self, factory, listitem):
        row = listitem.get_child()
        row.set_property("task", None)
        row.set_property("requester", None)

    def _tags_teardown(self, factory, listitem):
        listitem.set_child(None)

    def _create_date_factory(self, date_type: str) -> Gtk.SignalListItemFactory:
        date_factory = Gtk.SignalListItemFactory()
        date_factory.connect("setup", self._date_setup, date_type)
        date_factory.connect("bind", self._date_bind, date_type)
        date_factory.connect("unbind", self._date_unbind, date_type)
        date_factory.connect("teardown", self._date_teardown, date_type)
        return date_factory

    # API

    def enable_flat_mode(self):
        for column in self.get_columns():
            sorter = column.get_sorter()
            if isinstance(sorter, Gtk.TreeListRowSorter):
                original_sorter = sorter.get_sorter()
                column.set_sorter(original_sorter)
        self.add_css_class("flat-tree")
        self.is_flat = True

    def disable_flat_mode(self):
        for column in self.get_columns():
            sorter = column.get_sorter()
            if sorter and not isinstance(sorter, Gtk.TreeListRowSorter):
                tree_sorter = Gtk.TreeListRowSorter.new(sorter)
                column.set_sorter(tree_sorter)
        self.remove_css_class("flat-tree")
        self.is_flat = False

    def show_dates(self, start: bool, due: bool, closed: bool):
        """
        Set which dates should be visible in the TaskView.
        arguments: start date, due date, closed date
        """
        (self._start_column.props.visible, self._due_column.props.visible,
            self._closed_column.props.visible
        ) = start, due, closed

    def _sync_req_filtering(self):
        if (not self._req_status_filter and not self._req_tags_filter
             and not self._req_search_filter):
            self._req_filter = None
            set_recursive_filter(self._req_filter, self._req_filter_model, self._fid)
        else:
            self._req_filter = Gtk.EveryFilter()
            if self._req_status_filter:
                self._req_filter.append(self._req_status_filter)
            if self._req_tags_filter:
                self._req_filter.append(self._req_tags_filter)
            if self._req_search_filter:
                print(self._req_search_filter)
                self._req_filter.append(self._req_search_filter)
            set_recursive_filter(self._req_filter, self._req_filter_model, self._fid)

    def _set_both_filter(self, filter, type, flat):
        type_map = {
            # The reason for this "type" thing instead of passing the req filter as
            # an argument, is because if it is None, then it doesn't work like a reference,
            # but like a copy.
            "status": (self._tree_status_filter_model, "_req_status_filter"),
            "tags": (self._tree_tags_filter_model, "_req_tags_filter"),
            "search": (self._tree_search_filter_model, "_req_search_filter")
        }

        if flat:
            setattr(self, type_map[type][1], None)
            self._sync_req_filtering()
            type_map[type][0].set_filter(filter)
        else:
            setattr(self, type_map[type][1], filter)
            self._sync_req_filtering()
            type_map[type][0].set_filter(None)

    def set_status_filter(self, filter: Gtk.Filter, flat: bool):
        self._set_both_filter(
            filter, "status", flat
        )

    def set_tags_filter(self, filter: Gtk.Filter, flat: bool):
        self._set_both_filter(
            filter, "tags", flat
        )

    def set_search_filter(self, filter: Gtk.Filter, flat: bool):
        self._set_both_filter(
            filter, "search", flat
        )

