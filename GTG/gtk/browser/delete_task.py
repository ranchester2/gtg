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


from gi.repository import Gtk

from gettext import gettext as _, ngettext
from GTG.gtk import ViewConfig


class DeletionUI():

    MAXIMUM_TIDS_TO_SHOW = 5

    def __init__(self, req, window):
        self.req = req
        self.tids_todelete = []

        # Tags which must be updated
        self.update_tags = []
        self.window = window

    def on_response(self, dialog, response, tasklist, callback):
        dialog.destroy()

        if response == Gtk.ResponseType.YES:
            self.on_delete_confirm()
        elif response == Gtk.ResponseType.CANCEL:
            tasklist = []

        if callback:
            callback(tasklist)

    def on_delete_confirm(self):
        """if we pass a tid as a parameter, we delete directly
        otherwise, we will look which tid is selected"""

        for tid in self.tids_todelete:
            if self.req.has_task(tid):
                self.req.delete_task(tid, recursive=True)

        self.tids_todelete = []
        self.update_tags = []

    def recursive_list_tasks(self, tasklist, root):
        """Populate a list of all the subtasks and
           their children, recursively.

           Also collect the list of affected tags
           which should be refreshed"""

        if root not in tasklist:
            tasklist.append(root)

            [self.update_tags.append(tag.name)
             for tag in root.tags
             if tag.name not in self.update_tags]

            [self.recursive_list_tasks(tasklist, i)
             for i in root.children if i not in tasklist]


    def show_async(self, tids=None, callback=None):
        self.tids_todelete = tids or self.tids_todelete

        if not self.tids_todelete:
            # We must at least have something to delete!
            return []

        # Get full task list to delete
        tasklist = []
        self.update_tags = []

        for tid in self.tids_todelete:
            task = self.req.get_task(tid)
            self.recursive_list_tasks(tasklist, task)

        # Prepare Labels
        singular = len(tasklist)

        cancel_text = ngettext("Keep selected task", "Keep selected tasks", singular)

        delete_text = ngettext("Permanently remove task", "Permanently remove tasks", singular)

        label_text = ngettext("Deleting a task cannot be undone, "
                              "and will delete the following task: ",
                              "Deleting a task cannot be undone, "
                              "and will delete the following tasks: ",
                              singular)

        label_text = label_text[0:label_text.find(":") + 1]

        missing_titles_count = len(tasklist) - self.MAXIMUM_TIDS_TO_SHOW

        if missing_titles_count >= 2:
            tasks = tasklist[: self.MAXIMUM_TIDS_TO_SHOW]
            titles_suffix = _("\nAnd {missing_titles_count:d} more tasks")
            titles_suffix = titles_suffix.format(missing_titles_count=missing_titles_count)
        else:
            tasks = tasklist
            titles_suffix = ""

        titles = "".join("\n• " + task.title for task in tasks)

        # Build and run dialog
        dialog = Gtk.MessageDialog(transient_for=self.window, modal=True)
        dialog.add_button(cancel_text, Gtk.ResponseType.CANCEL)

        delete_btn = dialog.add_button(delete_text, Gtk.ResponseType.YES)
        delete_btn.add_css_class("destructive-action")

        dialog.props.use_markup = True
        # Decrease size of title to workaround not being able to put two texts in GTK4
        dialog.props.text = "<span size=\"small\" weight=\"bold\">" + label_text + "</span>"

        dialog.props.secondary_text = titles + titles_suffix

        dialog.connect("response", self.on_response, tasklist, callback)
        dialog.present()
