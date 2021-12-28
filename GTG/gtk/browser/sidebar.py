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


import os
import uuid
from gi.repository import Gtk, Gdk, Gio, GObject, GLib
from gettext import gettext as _
from GTG.core.dirs import UI_DIR
from GTG.core.tags2 import Tag2
from GTG.core.tasks2 import Task2, Status
from GTG.core.requester import Requester
from GTG.gtk.browser import GnomeConfig
from GTG.gtk.browser.tag_editor import TagEditor
from GTG.gtk.browser.tasks_view import unwrap_item, set_recursive_filter
from GTG.gtk.browser.filtering import StatusFilter, TagsFilter
from GTG.gtk.browser.delete_tag import DeleteTagsDialog


class IndentOnlyTreeExpander(Gtk.Box):
    __gtype_name__ = "IndentOnlyExpander"

    ignore_count = GObject.Property(type=int)

    def __init__(self):
        self._list_row = None
        super().__init__(spacing=4)

    @GObject.Property(type=Gtk.TreeListRow)
    def list_row(self):
        return self._list_row

    @list_row.setter
    def list_row(self, value: Gtk.TreeListRow):
        self._list_row = value
        for child in self:
            self.remove(child)
        if self._list_row:
            for x in range(self._list_row.get_depth()-self.ignore_count):
                widget = Gtk.Box(width_request=16)
                self.append(widget)


@Gtk.Template(filename=os.path.join(UI_DIR, "sidebar_tag.ui"))
class GTGSidebarTagRow(Gtk.Box):
    __gtype_name__ = "GTGSidebarTagRow"

    tag = GObject.Property(type=Tag2)
    menu_model = GObject.Property(type=Gio.MenuModel)
    requester = GObject.Property(type=Requester)

    _indent_expander = Gtk.Template.Child()
    _arrow_expander = Gtk.Template.Child()

    def __init__(self, **kwargs):
        self._tree_row = None
        self._tag = None
        self._sr_pr_sig = None
        self._sr_bg_sig = None
        self._sr_ed_sig = None
        self._dt_dr_sig = None
        self._drag_source = Gtk.DragSource(actions=Gdk.DragAction.MOVE)
        self._drop_target = Gtk.DropTarget.new(Tag2, Gdk.DragAction.MOVE)

        super().__init__(**kwargs)

        # GtkWidgetClass.install_action causes weird stuff to happen with python callbacks,
        # as it installs for all instances. So you then randomly
        # call the callbacks of other instances instead.
        group = Gio.SimpleActionGroup()
        for action_disc in [("edit", None, self._on_edit),
                            ("generate_color", None, self._on_generate_color),
                            ("delete", None, self._on_delete)]:
            action = Gio.SimpleAction.new(action_disc[0], action_disc[1])
            action.connect("activate", action_disc[2])
            group.add_action(action)

        self.insert_action_group("tag", group)
        menu_builder = Gtk.Builder()
        menu_builder.add_from_file(GnomeConfig.MENUS_UI_FILE)
        self.menu_model = menu_builder.get_object("tag_context_menu")
        self.add_controller(self._drag_source)
        self.add_controller(self._drop_target)

    def _on_edit(self, action, param):
        if not self.requester or not self.tag:
            return
        tag_editor = TagEditor(self.requester, self.tag)
        tag_editor.set_transient_for(self.get_native())
        tag_editor.present()

    def _on_generate_color(self, action, param):
        if not self.requester or not self.tag:
            return
        tags_tree = self.requester.get_tag_tree()
        color = tags_tree.generate_color()
        # color property is raw string, not with "#"
        self.tag.color = color[1:]

    def _on_delete(self, action, param):
        if not self.tag or not self.requester:
            return
        dialog = DeleteTagsDialog(self.requester, self.get_native())
        dialog.delete_tags_async([self.tag.name])

    def _on_drag_prepare(self, source, *pos):
        if not self.tag:
            return
        value = GObject.Value(Tag2, self.tag)
        return Gdk.ContentProvider.new_for_value(value)

    def _on_drag_begin(self, source, drag):
        self.add_css_class("dragged-tag")
        icon = Gtk.DragIcon.get_for_drag(drag)
        frame = Gtk.Frame()
        frame.add_css_class("tag-frame")
        picture = Gtk.Picture.new_for_paintable(
            Gtk.WidgetPaintable.new(self)
        )
        frame.set_child(picture)
        icon.set_child(frame)

    def _on_drag_end(self, source, drag, delete_tag):
        self.remove_css_class("dragged-tag")

    def _on_drag_drop(self, drop_target, tag, x, y):
        tags_tree = self.requester.get_tag_tree()
        if tag == self.tag:
            return False

        # FIXME: you should be able to parent a task
        # to one of its children
        target_parent = self.tag.parent
        while target_parent is not None:
            if target_parent == tag:
                return False
            target_parent = target_parent.parent

        if tag.parent:
            tags_tree.unparent(tag.id, tag.parent.id)
        tags_tree.parent(tag.id, self.tag.id)
        return True

    @GObject.Property(type=Tag2)
    def tag(self):
        return self._tag

    @tag.setter
    def tag(self, value):
        # Yes, the signals actually cause this to not be GCed, and often
        # there will be lots of this widget
        for sig in [self._sr_pr_sig, self._sr_bg_sig, self._sr_ed_sig, self._dt_dr_sig]:
            if sig:
                self._drag_source.disconnect(sig)
        self._tag = value
        if self._tag:
            self._sr_pr_sig = self._drag_source.connect("prepare", self._on_drag_prepare)
            self._sr_bg_sig = self._drag_source.connect("drag-begin", self._on_drag_begin)
            self._sr_ed_sig = self._drag_source.connect("drag-end", self._on_drag_end)
            self._dt_dr_sig = self._drop_target.connect("drop", self._on_drag_drop)

    @GObject.Property(type=Gtk.TreeListRow)
    def tree_row(self):
        return self._tree_row

    @tree_row.setter
    def tree_row(self, value: Gtk.TreeListRow):
        self._tree_row = value
        self._indent_expander.props.list_row = self._tree_row
        self._arrow_expander.props.list_row = self._tree_row


class GTGSidebarEntry(GObject.Object):
    __gtype_name__ = "GTGSidebarEntry"

    id = GObject.Property(type=str)
    title = GObject.Property(type=str) # Human readable id
    icon_name = GObject.Property(type=str)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


@Gtk.Template(filename=os.path.join(UI_DIR, "sidebar_entry.ui"))
class GTGSidebarEntryRow(Gtk.Box):
    __gtype_name__ = "GTGSidebarEntryRow"

    entry = GObject.Property(type=GTGSidebarEntry)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_state_flags(Gtk.StateFlags.SELECTED, True)


class GTGSidebarCategory(GObject.Object):
    __gtype_name__ = "GTGSidebarCategory"

    title = GObject.Property(type=str)
    visible = GObject.Property(type=bool, default=True)
    model = GObject.Property(type=Gio.ListModel)

    def __init__(self, title: str, visible: bool, model: Gio.ListModel):
        super().__init__()
        self.title = title
        self.visible = visible
        self.model = model
        self.model.connect("items-changed", self._on_model_items_changed)
        self._on_model_items_changed()

    def _on_model_items_changed(self, model=None, pos=None, rem=None, add=None):
        self.visible = self.model.get_n_items()


@Gtk.Template(filename=os.path.join(UI_DIR, "sidebar_category.ui"))
class GTGSidebarCategoryRow(Gtk.Box):
    __gtype_name__ = "GTGSidebarCategoryRow"

    category = GObject.Property(type=GTGSidebarCategory)

    _arrow = Gtk.Template.Child()
    _label = Gtk.Template.Child()

    def __init__(self, **kwargs):
        self._expanded = False
        self._category = None
        self._title_binding = None
        self._expanded_binding = None
        self._row = None
        self._row_binding = None

        super().__init__(spacing=6, **kwargs)

        # Why not use list activation to handle this?
        # Because then we would need single-click-activate which
        # breaks ListView in terms of behaving like a sane sidebar would
        self._click_gesture = Gtk.GestureClick()
        self._click_gesture.connect("pressed", self._on_pressed)
        self.add_controller(self._click_gesture)


    def _on_pressed(self, gesture, n_press, x, y):
        self.expanded = not self.expanded


    @GObject.Property(type=Gtk.TreeListRow)
    def row(self):
        return self._row

    @row.setter
    def row(self, value: Gtk.TreeListRow):
        self._row = value
        if self._row:
            self._row_binding = self._row.bind_property(
                "expanded",
                self,
                "expanded",
                GObject.BindingFlags.SYNC_CREATE|GObject.BindingFlags.BIDIRECTIONAL
            )
        elif self._row_binding:
            self._row_binding.unbind()

    @GObject.Property(type=bool, default=False)
    def expanded(self):
        return self._expanded

    @expanded.setter
    def expanded(self, value: bool):
        self._expanded = value
        if self._expanded:
            self._arrow.set_state_flags(Gtk.StateFlags.CHECKED, False)
        else:
            self._arrow.unset_state_flags(Gtk.StateFlags.CHECKED)


class GTGSidebar(Gtk.Widget):
    __gtype_name__ = "GTGSidebar"

    def __init__(self, req, **kwargs):
        self.set_css_name("gtgsidebar")
        super().__init__(**kwargs)
        self.set_layout_manager(Gtk.BinLayout())

        self._scroller = None
        self._req = req

        # Change flat/non flat filtering
        self._req.get_displayed_tasks_view().connect("notify::is-flat", self._on_flat_changed)

        self._featured_tags = []
        tasks_tree = self._req.get_tasks_tree()
        self._fid = uuid.uuid4()
        self._open_filter = StatusFilter(Status.ACTIVE)
        # We need to ensure our filter is applied to all new items
        tasks_tree.connect(
            "added",
            lambda tree, item : set_recursive_filter(
                self._open_filter, item.child_filters[self._fid], self._fid
            )
        )
        self._tasks_filter_model = Gtk.FilterListModel.new(self._req.get_tasks_tree(), None)
        set_recursive_filter(self._open_filter, self._tasks_filter_model, self._fid)
        self._open_tasks = Gtk.TreeListModel.new(
            self._tasks_filter_model, True, True, self._tasks_cr_mod_func, None
        )
        self._tasks_filter_model.connect("items-changed", self._update_tags_show)

        self._scroller = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
        self._scroller.set_parent(self)
        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_setup)
        factory.connect("bind", self._on_bind)
        factory.connect("unbind", self._on_unbind)
        factory.connect("teardown", self._on_teardown)

        self._category_model = Gio.ListStore.new(GTGSidebarCategory)
        self._entry_model = Gio.ListStore.new(GTGSidebarEntry)
        self._tag_model = self._req.get_tag_tree()
        self._saved_searches_model = self._req.get_saved_searches_tree()
        self._tree_model = Gtk.TreeListModel.new(
            self._category_model, False, True, self._model_create_func
        )
        self._category_filter_model = Gtk.FilterListModel.new(
            self._tree_model, Gtk.CustomFilter.new(self._category_visibility_match_func)
        )
        self._tag_filter_model = Gtk.FilterListModel.new(
            self._category_filter_model, Gtk.CustomFilter.new(self._tag_active_match_func)
        )
        self._selection_model = Gtk.SingleSelection.new(self._tag_filter_model)
        self._selection_model.connect("selection-changed", self._on_selection_changed)
        # FIXME: take it from configuration
        GLib.idle_add(lambda *_ : self._selection_model.select_item(0, True) and 0)

        for i, disc in enumerate([("", False, self._entry_model),
                    (_("All "), True, self._saved_searches_model),
                    (_("Tags"), True, self._tag_model)]):
            category = GTGSidebarCategory(disc[0], disc[1], disc[2])
            # When visibility changes, we fake an items-changed to get the Filter
            # to rerun.
            category.connect(
                "notify::visible",
                lambda *_ : self._category_model.items_changed(i, 1, 1)
            )
            self._category_model.append(category)

        self._entry_model.append(GTGSidebarEntry(
            id="all", title=_("All Tasks"), icon_name="emblem-documents-symbolic")
        )
        self._entry_model.append(GTGSidebarEntry(
            id="none", title=_("Tasks with No Tags"), icon_name="task-past-due-symbolic")
        )

        self._listview = Gtk.ListView(
            model=self._selection_model, factory=factory
        )
        listview_drop_target = Gtk.DropTarget.new(Tag2, Gdk.DragAction.MOVE)
        listview_drop_target.connect("drop", self._on_toplevel_tag_drop)
        self._listview.add_controller(listview_drop_target)
        self._listview.add_css_class("navigation-sidebar")
        self._scroller.set_child(self._listview)

        self._update_tags_show()

    def _on_toplevel_tag_drop(self, drop_target, tag, x, y):
        if tag.parent:
            self._tag_model.unparent(tag.id, tag.parent.id)
            return True
        else:
            return False

    def _on_flat_changed(self, view, param):
        self._req.apply_tag_filter(None)
        self._on_selection_changed()

    def _on_selection_changed(self, model=None, pos=None, n_items=None):
        item = self._selection_model.get_selected_item()
        tag = unwrap_item(item, Tag2)
        if tag:
            self._req.apply_tag_filter(TagsFilter(True, tag), TagsFilter(False, tag))
            return
        entry = unwrap_item(item, GTGSidebarEntry)
        if entry:
            if entry.id == "all":
                self._req.apply_tag_filter(None)
            elif entry.id == "none":
                self._req.apply_tag_filter(TagsFilter(True), TagsFilter(False))

    def _tasks_cr_mod_func(self, item, data):
        try:
            return item.child_filters[self._fid]
        # As a fallback on failure deeper in the stack
        except KeyError:
            item.child_filters[self._fid] = Gtk.FilterListModel.new(
                item.children, self._open_filter
            )
            return item.child_filters[self._fid]

    def _update_tags_show(self, model=None, position=None, removed=None, added=None):
        self._featured_tags.clear()
        for task in self._open_tasks:
            self._featured_tags.extend(task.tags)
        self._tag_model.items_changed(
            0, len(self._tag_model), len(self._tag_model)
        )

    def _tag_active_match_func(self, item):
        tag = unwrap_item(item, Tag2)
        if not tag:
            return True

        if tag in self._featured_tags:
            return True
        # Parents should be visible if they have any visible children
        for child_tag in tag.children:
            if self._tag_active_match_func(child_tag):
                return True
        return False

    def _category_visibility_match_func(self, item):
        item = unwrap_item(item, GTGSidebarCategory)
        return not (item and not item.visible)

    def _model_create_func(self, item):
        if isinstance(item, GTGSidebarCategory):
            return item.model
        elif isinstance(item, Tag2):
            return item.children

    def _on_setup(self, factory, listitem):
        pass

    def _on_bind(self, factory, listitem):
        item = unwrap_item(listitem, GTGSidebarCategory, GTGSidebarEntry, Tag2)
        if isinstance(item, GTGSidebarCategory):
            row = GTGSidebarCategoryRow(category=item, row=listitem.get_item())
            listitem.set_selectable(False)
            listitem.set_child(row)
            # Must be on the GtkListItemWidget, not our widget to disable
            # the stupid hover effect
            row.get_parent().add_css_class("category")
        elif isinstance(item, GTGSidebarEntry):
            row = GTGSidebarEntryRow(entry=item)
            listitem.set_child(row)
        elif isinstance(item, Tag2):
            row = GTGSidebarTagRow(
                tag=item, tree_row=listitem.get_item(), requester=self._req
            )
            listitem.set_child(row)

    def _on_unbind(self, factory, listitem):
        if listitem.get_child():
            listitem.get_child().get_parent().remove_css_class("category")
        listitem.set_selectable(True)
        listitem.set_child(None)

    def _on_teardown(self, factory, listitem):
        listitem.set_child(None)

    def do_unroot(self, widget):
        if self._scroller:
            self._scroller.unparent()

