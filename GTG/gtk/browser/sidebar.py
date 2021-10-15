from gi.repository import Gtk, Gdk
from GTG.gtk.browser.tag_context_menu import TagContextMenu


# NOTE: This is heavily WIP and broken code. 
# And super disorganized. It will eventually get better :)


class Sidebar():
    
    def __init__(self, app, builder):
        super().__init__()

        self.app = app
        self.builder = builder

        listbox = builder.get_object('sidebar_list')

        box = Gtk.Box() 
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_left(12)
        box.set_margin_right(12)

        icon = Gtk.Image.new_from_icon_name(
            'emblem-documents-symbolic', 
            Gtk.IconSize.MENU
        )
        
        icon.set_margin_right(6)
        box.add(icon)

        name = Gtk.Label()
        name.set_halign(Gtk.Align.START)
        name.set_text('All Tasks')
        box.add(name)

        listbox.add(box)


        box = Gtk.Box() 
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_left(12)
        box.set_margin_right(12)

        icon = Gtk.Image.new_from_icon_name(
            'task-past-due-symbolic', 
            Gtk.IconSize.MENU
        )
        
        icon.set_margin_right(6)
        box.add(icon)

        name = Gtk.Label()
        name.set_halign(Gtk.Align.START)
        name.set_text('Tasks with no tags')
        box.add(name)

        listbox.add(box)

        box = Gtk.Box() 
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_left(12)
        box.set_margin_right(12)

        icon = Gtk.Image.new_from_icon_name(
            'system-search-symbolic', 
            Gtk.IconSize.MENU
        )
        
        icon.set_margin_right(6)
        box.add(icon)

        name = Gtk.Label()
        name.set_halign(Gtk.Align.START)
        name.set_text('Saved Searches')
        box.add(name)

        listbox.add(box)

        separator = Gtk.Separator()
        separator.set_sensitive(False)
        listbox.add(separator)

        for tag in app.ds.tags.data:
            listbox.add(TagSidebarRow(tag))

        listbox.show_all()


class TagSidebarRow(Gtk.ListBoxRow):
    
    __gtype_name__ = 'gtg_TagSidebarRow'

    def __init__(self, tag):
        super().__init__()

        self.box = Gtk.Box()
        self.box.set_margin_top(8)
        self.box.set_margin_bottom(8)
        self.box.set_margin_left(12)
        self.box.set_margin_right(12)

        # TODO:
        # Add expander for children
        # Add callbacks to open tag editor, etc.

        if tag.children:
            expander = Gtk.ToggleButton()
            expander.get_style_context().add_class('flat')

            icon = Gtk.Image.new_from_icon_name(
                'pan-end-symbolic', 
                Gtk.IconSize.MENU
            )

            expander.add(icon)

            self.box.add(expander)


        if tag.icon:
            icon = Gtk.Label()
            icon.set_justify(Gtk.Justification.LEFT)
            icon.set_text(tag.icon)
            icon.set_margin_right(6)
            self.box.add(icon)
        elif tag.color:
            color = Gdk.RGBA()
            color.parse(f'#{tag.color}')
            hex = color.to_string()
            color_btn = Gtk.Button()
            color_btn.get_style_context().add_class('flat')
            background = str.encode('* { background: ' + hex + ' ; padding: 0; min-height: 16px; min-width: 16px;}')

            cssProvider = Gtk.CssProvider()
            cssProvider.load_from_data(background)


            color_btn.set_sensitive(False)
            color_btn.set_margin_right(6)
            color_btn.set_valign(Gtk.Align.CENTER)
            color_btn.set_halign(Gtk.Align.CENTER)
            color_btn.set_vexpand(False)
            color_btn.get_style_context().add_provider(cssProvider, 
                                                   Gtk.STYLE_PROVIDER_PRIORITY_USER)

            self.box.pack_start(color_btn, False, False, 0)

        name = Gtk.Label()
        name.set_halign(Gtk.Align.START)
        name.set_text(tag.name)
        self.box.add(name)

        self.add(self.box)


