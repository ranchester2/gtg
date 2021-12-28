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

from gi.repository import GObject, Gtk, Gsk, Gdk, Graphene, Pango
from GTG.core.tags2 import Tag2
from GTG.core.tasks2 import Task2

# This should really not be a GtkBox subclass, but either
# a GtkWidget subclass with a BoxLayout (however you can't implement
# dispose in PyGObject), or an AdwBin when we have Libadwaita
class TagsDisplay(Gtk.Box):
    __gtype_name__ = "TagsDisplay"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._task = None
        self._children = []
        self._tags_changed_sigid = 0

    def _sync_display(self, model=None, position=None, removed=None, added=None):
        if self._task:
            for index, tag in enumerate(self._task.tags):
                try:
                    pill = self._children[index]
                except IndexError:
                    pill = TagPill(tag=tag)
                    self.append(pill)
                    self._children.append(pill)
                finally:
                    pill.set_property("tag", tag)

            while len(self._children) > len(self._task.tags):
                self._children[-1].set_property("tag", None)
                self.remove(self._children[-1])
                del self._children[-1]

    def do_unroot(self):
        # Explicitly needed to get the pills GCed.
        for pill in self._children:
            pill.set_property("tag", None)
            self.remove(pill)

    @GObject.Property(type=Task2)
    def task(self):
        return self._task

    @task.setter
    def task(self, value: Task2):
        if self._task and self._tags_changed_sigid:
            self._task.tags.disconnect(self._tags_changed_sigid)
        self._task = value
        if self._task:
            self._tags_changed_sigid = self._task.tags.connect("items-changed", self._sync_display)
            self._sync_display()


class TagPill(Gtk.Widget):
    __gtype_name__ = "TagPill"

    PILL_SIZE = 16
    BORDER_RADIUS = 4

    def __init__(self, **kwargs):
        self._tag = None
        self._color_watch_sigid = None
        super().__init__(**kwargs)

    def _on_color_changed(self, tag, param):
        self.queue_draw()

    @GObject.Property(type=Tag2)
    def tag(self):
        return self._tag

    @tag.setter
    def tag(self, value: Tag2):
        if self._tag and self._color_watch_sigid:
            self._tag.disconnect(self._color_watch_sigid)
            self._color_watch_sigid = None
        self._tag = value
        if self._tag:
            self._color_watch_sigid = self._tag.connect(
                "notify::color", self._on_color_changed
            )
        self.queue_draw()

    def do_snapshot(self, snapshot: Gtk.Snapshot):
        if self._tag:
            # center drawing
            snapshot.save()
            point = Graphene.Point.alloc().init(
                (self.get_allocated_width() - self.PILL_SIZE) / 2,
                (self.get_allocated_height() - self.PILL_SIZE) / 2,
            )
            snapshot.translate(point)

            bounding = Graphene.Rect().alloc().init(0, 0, self.PILL_SIZE, self.PILL_SIZE)
            size = Graphene.Size.alloc().init(self.BORDER_RADIUS, self.BORDER_RADIUS)
            outline = Gsk.RoundedRect()
            outline.init(bounding, size, size, size, size)

            def draw_outline():
                brgba = Gdk.RGBA()
                brgba.parse("#00000033")
                snapshot.append_border(outline, [1, 1, 1, 1], [brgba, brgba, brgba, brgba])

            if self._tag.color:
                crgba = Gdk.RGBA()
                crgba.parse(f"#{self._tag.color}")

                snapshot.push_rounded_clip(outline)
                snapshot.append_color(crgba, bounding)
                draw_outline()
                snapshot.pop()
            elif self._tag.icon:
                layout = Pango.Layout(self.get_pango_context())
                layout.set_text(self._tag.icon)

                # Correct for weird icon misalignment (same values as used in the
                # legacy cairo cell_renderer)
                snapshot.save()
                snapshot.translate(Graphene.Point.alloc().init(
                    -1, 1)
                )

                snapshot.append_layout(layout, self.get_style_context().get_color())
                snapshot.restore()
            else:
                draw_outline()

            snapshot.restore()

    def do_measure(self, orienatation: Gtk.Orientation, for_size: int):
        return 16, 16, -1, -1
