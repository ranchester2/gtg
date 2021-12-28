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

"""
A nice general purpose interface for the datastore and tagstore
"""
import logging
import os
from gi.repository import GObject

from GTG.core.tag import Tag, SEARCH_TAG_PREFIX
from GTG.core.dirs import DATA_DIR

log = logging.getLogger(__name__)


class Requester(GObject.GObject):
    """ A view on a GTG datastore.

    L{Requester} is a stateless object that simply provides a nice API for
    user interfaces to use for datastore operations.

    Multiple L{Requester}s can exist on the same datastore, so they should
    never have state of their own.
    """
    __gsignals__ = {'status-changed': (GObject.SignalFlags.RUN_FIRST, None, (str, str,))}

    def __init__(self, datastore, global_conf):
        """Construct a L{Requester}."""
        super().__init__()
        self.ds = datastore
        self._config = global_conf
        self._get_displayed_tasks_view_func = None

    # Tasks Tree ######################
    def get_tasks_tree(self):
        return self.ds.tasks

    def set_get_displayed_tasks_view_func(self, func):
        """
        Set a function that takes no arguments and causes users of the requester
        to get the TasksView that is currently displayed in the window.
        """
        self._get_displayed_tasks_view_func = func

    def get_displayed_tasks_view(self):
        """
        Get the currently utilised TasksView
        """
        return self._get_displayed_tasks_view_func()

    def apply_tag_filter(self, filter, alternative_flat_filt=None):
        """
        This method also update the viewcount of tags
        TODO(jakubbrindza): Evaluate if this is used somewhere before release
        """
        view = self._get_displayed_tasks_view_func()

        if view.is_flat and alternative_flat_filt:
            view.set_tags_filter(alternative_flat_filt, view.is_flat)
            return
        view.set_tags_filter(filter, view.is_flat)

    def apply_search_filter(self, filter, alternative_flat_filt=None):
        """
        TODO(jakubbrindza): Evaluate if this is used somewhere before release
        """
        view = self._get_displayed_tasks_view_func()
        if view.is_flat and alternative_flat_filt:
            view.set_search_filter(alternative_flat_filt, view.is_flat)
            return
        view.set_search_filter(filter, view.is_flat)

    # Tasks ##########################
    def has_task(self, tid):
        """Does the task 'tid' exist?"""
        return tid in self.ds.tasks.lookup

    def get_task(self, tid):
        """Get the task with the given C{tid}.

        If no such task exists, create it and force the tid to be C{tid}.

        @param tid: The task id.
        @return: A task.
        """
        task = self.ds.tasks.get(tid)
        return task

    def new_task(self, tags=None, title="", parent=None, newtask=True):
        """Create a new task.

        Note: this modifies the datastore.

        @param pid: The project where the new task will be created.
        @param tags: The tags for the new task. If not provided, then the
            task will have no tags. Tags must be an iterator type containing
            the tags tids
        @param newtask: C{True} if this is creating a new task that never
            existed, C{False} if importing an existing task from a backend.
        @return: A task from the data store
        """
        task = self.ds.tasks.new(title, parent)
        if tags:
            for t in tags:
                assert(not isinstance(t, Tag))
                tag_obj = self.ds.tags.new(t, None)
                task.add_tag(tag_obj)
        return task

    def delete_task(self, tid, recursive=True):
        """Delete the task 'tid' and, by default, delete recursively
        all the childrens.

        Note: this modifies the datastore.

        @param tid: The id of the task to be deleted.
        """
        # send the signal before actually deleting the task !
        log.debug("deleting task %s", tid)
        self.ds.tasks.remove(tid)

    def get_task_id(self, task_title):
        """ Heuristic which convert task_title to a task_id

        Return a first task which has similar title """

        task_title = task_title.lower()
        tasks = self.get_tasks_tree('active', False).get_all_nodes()
        tasktree = self.get_main_view()
        for task_id in tasks:
            task = tasktree.get_node(task_id)
            if task_title == task.get_title().lower():
                return task_id

        return None

    # Searches ########################
    def get_saved_searches_tree(self):
        return self.ds.saved_searches

    # Tags ##########################
    def get_tag_tree(self):
        return self.ds.tags

    def new_tag(self, tagname):
        """Create a new tag called 'tagname'.

        Note: this modifies the datastore.

        @param tagname: The name of the new tag.
        @return: The newly-created tag.
        """
        return self.ds.tags.new(tagname)

    def new_search_tag(self, query):
        """
        Create a new search tag from search query

        Note: this modifies the datastore.

        @param query: Query will be parsed using search parser
        @return:      tag_id
        """
        # ! at the beginning is reserved keyword for liblarch
        if query.startswith('!'):
            label = '_' + query
        else:
            label = query

        # find possible name collisions
        name, number = label, 1
        already_search = False
        while True:
            tag = self.get_tag(SEARCH_TAG_PREFIX + name)
            if tag is None:
                break

            if tag.is_search_tag() and tag.get_attribute("query") == query:
                already_search = True
                break

            # this name is used, adding number
            number += 1
            name = label + ' ' + str(number)

        if not already_search:
            tag = self.ds.new_search_tag(name, query)

        return SEARCH_TAG_PREFIX + name

    def remove_tag(self, name):
        """ calls datastore to remove a given tag """
        self.ds.remove_tag(name)

    def rename_tag(self, oldname, newname):
        self.ds.rename_tag(oldname, newname)

    def get_tag(self, tagname):
        try:
            return self.ds.tags.find(tagname)
        except KeyError:
            return None

    def get_used_tags(self):
        """Return tags currently used by a task.

        @return: A list of tag names used by a task.
        """
        tagstore = self.ds.get_tagstore()
        view = tagstore.get_viewtree(name='tag_completion', refresh=False)
        tags = view.get_all_nodes()
        tags.sort(key=str.lower)
        return tags

    def get_all_tags(self):
        """
        Gets all tags from all tasks
        """
        return self.ds.get_tagstore().get_main_view().get_all_nodes()

    def delete_tag(self, tagname):
        my_tag = self.get_tag(tagname)
        for task in self.ds.tasks.lookup.values():
            if my_tag in task.tags:
                task.remove_tag(my_tag.name)
        # Non recursive, save parents
        for child in my_tag.children:
            self.ds.tags.unparent(child.id, my_tag.id)
        self.ds.tags.remove(my_tag.id)

    # Backends #######################
    def get_all_backends(self, disabled=False):
        return self.ds.get_all_backends(disabled)

    def register_backend(self, dic):
        return self.ds.register_backend(dic)

    def flush_all_tasks(self, backend_id):
        return self.ds.flush_all_tasks(backend_id)

    def get_backend(self, backend_id):
        return self.ds.get_backend(backend_id)

    def set_backend_enabled(self, backend_id, state):
        return self.ds.set_backend_enabled(backend_id, state)

    def remove_backend(self, backend_id):
        return self.ds.remove_backend(backend_id)

    def backend_change_attached_tags(self, backend_id, tags):
        return self.ds.backend_change_attached_tags(backend_id, tags)

    def save_datastore(self, quit=False):
        return self.ds.save_file(os.path.join(DATA_DIR, "gtg_data.xml"))

    # Config ############################
    def get_config(self, system):
        """ Returns configuration object for subsytem, e.g. browser """
        return self._config.get_subconfig(system)

    def get_global_config(self):
        """ Returns the global persistent configuration, e.g. for connecting to signals """
        return self._config

    def get_task_config(self, task_id):
        """ Returns configuration object for task """
        return self._config.get_task_config(task_id)
