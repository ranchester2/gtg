
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
import random

from mock import patch, mock_open, Mock
from gi.repository import Gtk, GObject, GLib

from GTG.core.config import open_config_file, SectionConfig
from liblarch import Tree, TreeNode
from GTG.core.librview import FilterStore
from GTG.gtk.browser.tasks_view import unwrap_item

class TaskNode(TreeNode, GObject.Object):
    tid = GObject.Property(type=str)
    __gtype_name__ = "TaskNode"

    def __init__(self, tid, label, viewtree):
        TreeNode.__init__(self, tid)
        GObject.Object.__init__(self)
        self.label = label
        self.tid = tid
        self.vt = viewtree

    def get_label(self):
        return "%s (%s children)" % (
            self.label, self.vt.node_n_children(self.tid, recursive=True))


class TestFilteredView(TestCase):
    def test_basic(self):
        def on_activate(app):
            tree = Tree()

            librstore = FilterStore(
                tree.get_viewtree()
            )
            tasks_ids = []
            prefix = random.randint(1, 1000) * 100000
            for i in range(300):
                t_id = str(prefix + i)
                t_title = t_id
                task = TaskNode(t_id, t_title, tree.get_viewtree())

                # There is 25 % chance to adding as a sub_task
                if tasks_ids != [] and random.randint(0, 100) < 90:
                    parent = random.choice(tasks_ids)
                    tree.add_node(task, parent_id=parent)
                else:
                    tree.add_node(task)

                tasks_ids.append(t_id)
            librstore.print_tree()

            def create_func(item, data):
                return item.children

            window = Gtk.ApplicationWindow(application=app)
            treelistmodel = Gtk.TreeListModel.new(librstore, False, True, create_func, None)
            treelistmodel.a = create_func
            factory = Gtk.BuilderListItemFactory.new_from_bytes(None, GLib.Bytes.new(str.encode("""\
<?xml version="1.0" encoding="UTF-8"?>
<interface>
  <template class="GtkListItem">
    <property name="child">
      <object class="GtkTreeExpander" id="expander">
        <binding name="list-row">
          <lookup name="item">GtkListItem</lookup>
        </binding>
        <property name="child">
          <object class="GtkLabel">
            <property name="halign">start</property>
            <binding name="label">
                <lookup name="tid" type="TaskNode">
                    <lookup name="item" type="LarchTreeItem">
                        <lookup name="item">expander</lookup>
                    </lookup>
                </lookup>
            </binding>
          </object>
        </property>
      </object>
    </property>
  </template>
</interface>""")))
            listview = Gtk.ListView(model=Gtk.SingleSelection(model=treelistmodel), factory=factory)
            window.set_child(Gtk.ScrolledWindow(child=listview))
            window.present()

        app = Gtk.Application(application_id="org.gnome.GTGDevel")
        app.connect("activate", on_activate)
        app.run(None)

