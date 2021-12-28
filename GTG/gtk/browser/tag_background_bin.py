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


from gi.repository import Gtk, GObject, Gdk, Graphene, GLib
from GTG.gtk.colors import background_color
from GTG.core.requester import Requester
from GTG.core.config import SectionConfig
from GTG.core.tasks2 import Task2


class TagBackgroundBin(Gtk.Widget):
    __gtype_name__ = "TagBackgroundBin"

    task = GObject.Property(type=Task2)
    # We need to have the requester to check well if our functionality is enabled,
    # for the ability to set via UI file it must be a property
    requester = GObject.Property(type=Requester)

    def __init__(self, **kwargs):
        self._child = None
        self.counter = 0
        self._req = None
        self._config = None
        self._config_sigid = None
        self._should_color = False

        super().__init__(**kwargs)
        self.set_layout_manager(Gtk.BinLayout())
        self.add_css_class("tag-background")

    @GObject.Property(type=Requester)
    def requester(self):
        return self._req

    @requester.setter
    def requester(self, value: Requester):
        if self._config_sigid:
            self._config.disconnect(self._config_sigid)
            self._config_sigid = None
        self._req = value
        if self._req:
            self._config = self._req.get_global_config()
            self._config_sigid = self._config.connect("config-changed", self._sync_with_config)
            self._sync_with_config()

    @GObject.Property(type=Gtk.Widget)
    def child(self):
        return self._child

    @child.setter
    def child(self, child: Gtk.Widget):
        self._child = child
        if self._child:
            self._child.set_parent(self)
        else:
            self._child.unparent()

    def _sync_with_config(self, config=None, option=None):
        # This actually makes a massive performance difference,
        # as otherwise we would for example redraw on window resizes.
        if option and option != "bg_color_enable":
            return
        self._should_color = self._req.get_config("browser").get("bg_color_enable")
        self.queue_draw()

    def set_child(self, child: Gtk.Widget):
        self.child = child

    def get_child(self):
        return self.child

    def do_snapshot(self, snapshot):
        if self.task and self._should_color:
            tags_bg_color_str = background_color(self.task.tags, None, 0.5)
            if tags_bg_color_str:
                color = Gdk.RGBA()
                color.parse(tags_bg_color_str)
                rect = Graphene.Rect.alloc().init(
                    0, 0,
                    self.get_allocated_width(), self.get_allocated_height()
                )
                snapshot.append_color(color, rect)
        if self._child:
            self.snapshot_child(self._child, snapshot)

    def do_unroot(self, *args):
        if self._child:
            self._child.unparent()

