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


from gi.repository import Gtk, GObject, Gio, Gdk, GLib


class ContextMenuBin(Gtk.Widget):
    __gtype_name__ = "ContextMenuBin"

    model = GObject.Property(type=Gio.MenuModel)

    def __init__(self, **kwargs):
        self._child = None
        self._popover = None
        self._key_sigid = None
        self._click_sigid = None

        super().__init__(**kwargs)
        self.set_layout_manager(Gtk.BinLayout())
        # FIXME: doesn't actually work
        self._key_controller = Gtk.EventControllerKey(propagation_phase=Gtk.PropagationPhase.CAPTURE)
        self.add_controller(self._key_controller)
        self._click_gesture = Gtk.GestureClick(
            propagation_phase=Gtk.PropagationPhase.CAPTURE,
            button=Gdk.BUTTON_SECONDARY
        )
        self.add_controller(self._click_gesture)

    # Signal handlers need to be disconnected for this to eventually be GCed and
    # to not leak memory.
    # You would usually do this in do_dispose, but it is broken in PyGObject.
    # map/unmap make sense for these signals, so here instead.
    def do_map(self):
        Gtk.Widget.do_map(self)
        self._key_sigid = self._key_controller.connect("key-pressed", self._on_key_pressed)
        self._click_sigid = self._click_gesture.connect("pressed", self._on_mouse_pressed)

    def do_unmap(self):
        Gtk.Widget.do_unmap(self)
        if self._key_sigid:
            self._key_controller.disconnect(self._key_sigid)
            self._key_sigid = None
        if self._click_sigid:
            self._click_gesture.disconnect(self._click_sigid)
            self._click_sigid = None

    def _on_popover_closed(self, popover):
        # ::close callback is too early to destroy it if you want the buttons in it to
        # work, g_idle_add it to happen soon instead.
        def continue_close():
            self._popover.unparent()
            self._popover = None
        GLib.idle_add(continue_close)

    def _popup_at(self, x, y):
        # Build it on demand to not create useless popovers when there are a lot
        # of such widgets
        if self.model:
            self._popover = Gtk.PopoverMenu(
                menu_model=self.model, halign=Gtk.Align.START, has_arrow=False
            )
            self._popover.connect("closed", self._on_popover_closed)
            self._popover.set_parent(self)
            rect = Gdk.Rectangle()
            rect.x = x
            rect.y = y
            self._popover.set_pointing_to(rect)
            self._popover.popup()

    def _on_key_pressed(self, controller, keyval, keycode, state):
        if ((keyval == Gdk.KEY_F10 and state == Gdk.ModifierType.SHIFT_MASK) or
                keyval == Gdk.KEY_Menu):
            # popup seems to have 2px upper margin
            self._popup_at(0, self.get_allocated_height()-2)
            return True

    def _on_mouse_pressed(self, gesture, n_press, x, y):
        self._popup_at(x, y)

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

    def set_child(self, child: Gtk.Widget):
        self.child = child

    def get_child(self):
        return self.child

    def set_model(self, model: Gio.MenuModel):
        self.model = model

    def get_model(self):
        return self.model

    def do_snapshot(self, snapshot):
        if self._child:
            self.snapshot_child(self._child, snapshot)
        if self._popover:
            self.snapshot_child(self._popover, snapshot)

    def do_unroot(self, *args):
        if self._child:
            self._child.unparent()
        if self._popover:
            self._popover.unparent()

