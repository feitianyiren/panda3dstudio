from .base import *
from .menu import Menu
from tkinter import Tk


class TextControl(object):

    _shown_caret = None

    @classmethod
    def __blink_caret(cls, task):

        caret = cls._shown_caret

        if not caret:
            return task.again

        if caret.is_hidden():
            caret.show()
        else:
            caret.hide()

        return task.again

    @classmethod
    def init(cls):

        delay = Skin["options"]["inputfield_caret_blink_delay"]
        Mgr.add_task(delay, cls.__blink_caret, "blink_input_caret")

    def __init__(self, field, font, color, cull_bin=("gui", 3)):

        self._field = field
        self._font = font if font else Skin["text"]["input"]["font"]
        self._color = color
        self._text = ""
        self._label = None
        self._label_offset = 0
        self._char_positions = []
        self._char_pos_stale = False
        self._selection_anchor = 0
        cm = CardMaker("text_control")
        cm.set_frame(0, 1., -1., 0)
        w, h = field.get_size()
        self._root = root = Mgr.get("gui_root").attach_new_node("text_control_root")
        self._quad = quad = root.attach_new_node(cm.generate())
        quad.set_scale(w, 1., h)
        bin_name, bin_sort = cull_bin
        quad.set_bin(bin_name, bin_sort)
        self._tex = tex = Texture("text_control")
        tex.set_minfilter(SamplerState.FT_nearest)
        tex.set_magfilter(SamplerState.FT_nearest)
        quad.set_texture(tex)
        root.hide()
        self._image = PNMImage(w, h, 4)
        cm.set_name("input_caret")
        w_c = Skin["options"]["inputfield_caret_width"]
        h_c = Skin["options"]["inputfield_caret_height"]
        self._caret_offset_node = offset_node = root.attach_new_node("offset_node")
        margin = Skin["options"]["inputfield_margin"]
        y = (h - h_c) // 2
        l = -w_c // 2
        r = l + w_c
        offset_node.set_pos(margin, 0., -y)
        offset_node.set_texture_off()
        cm.set_frame(l, r, -h_c, 0)
        self._caret = caret = offset_node.attach_new_node(cm.generate())
        caret.set_bin(bin_name, bin_sort + 1)
        self._caret_tex = tex = Texture("caret_tex")
        tex.set_minfilter(SamplerState.FT_nearest)
        tex.set_magfilter(SamplerState.FT_nearest)
        caret.set_texture(tex)
        self._caret_pos = 0
        self.__update_image()
        self.__update_caret()

    def destroy(self):

        self._field = None
        self._root.remove_node()
        self._root = None
        self._quad = None
        self._caret = None
        self._caret_offset_node = None

    def set_size(self, size):

        w, h = size
        self._quad.set_scale(w, 1., h)
        self._field.update_images()
        self.__update_image()

    def __update_caret(self):

        w, h = self._field.get_size()
        margin = Skin["options"]["inputfield_margin"]
        w -= margin
        x = self._font.calc_width(self._text[:self._caret_pos])
        caret = self._caret
        caret.set_x(x)
        w_c = Skin["options"]["inputfield_caret_width"]
        h_c = Skin["options"]["inputfield_caret_height"]
        x, y, z = caret.get_pos(self._root)
        x = int(x) - w_c // 2
        y = int(-z)
        img1 = PNMImage(w_c, h_c)
        img1.fill(1., 1., 1.)
        img2 = PNMImage(img1)
        img2.copy_sub_image(self._image, 0, 0, x, y, w_c, h_c)
        # invert the image colors
        img1 -= img2
        self._caret_tex.load(img1)
        caret.show()

    def set_scissor_effect(self, effect):

        if effect:
            self._root.set_effect(effect)

    def set_pos(self, pos):

        x, y = pos
        self._root.set_pos(x, 0, -y)

    def clear(self):

        self._text = ""
        self._label = None
        self._label_offset = 0
        self._caret_pos = 0
        self._caret_offset_node.set_x(Skin["options"]["inputfield_margin"])
        self._char_positions = []
        self._char_pos_stale = False
        self._selection_anchor = 0
        self.__scroll()
        self.__update_image()
        self.__update_caret()

    def set_color(self, color):

        self._color = color

    def get_color(self):

        return self._color

    def __scroll(self):

        w, h = self._field.get_size()
        margin = Skin["options"]["inputfield_margin"]
        w_ = w - margin * 2
        w_t = self._font.calc_width(self._text[:self._caret_pos])
        label_offset = self._label_offset

        if label_offset <= w_t <= label_offset + w_:
            return False

        if label_offset > w_t:
            label_offset = w_t
        else:
            label_offset = max(0, w_t - w_)

        self._label_offset = label_offset
        self._caret_offset_node.set_x(margin - label_offset)

        return True

    def set_text(self, text):

        self._text = text
        self._selection_anchor = self._caret_pos = len(text)
        self._caret_offset_node.set_x(Skin["options"]["inputfield_margin"])
        self._char_pos_stale = True
        self._label_offset = 0
        self.create_label()
        self.__scroll()
        self.__update_image()
        self.__update_caret()

    def write(self, text):

        start_pos = min(self._caret_pos, self._selection_anchor)
        end_pos = max(self._caret_pos, self._selection_anchor)
        self._caret_pos = start_pos
        self.__scroll()
        start = self._text[:start_pos]
        end = self._text[end_pos:]
        self._text = "".join((start, text, end))
        self._selection_anchor = self._caret_pos = start_pos + len(text)
        self._char_pos_stale = True
        self.create_label()
        self.__scroll()
        self.__update_image()
        self.__update_caret()

    def delete(self):

        caret_pos = start_pos = min(self._caret_pos, self._selection_anchor)
        end_pos = max(start_pos + 1, self._caret_pos, self._selection_anchor)
        start = self._text[:start_pos]
        end = self._text[end_pos:]
        text = "".join((start, end))

        if self._text != text:
            self._text = text
            self._selection_anchor = self._caret_pos = caret_pos
            self._char_pos_stale = True
            self.create_label()
            self.__update_image()
            self.__update_caret()

    def backspace(self):

        update = False

        if self._caret_pos != self._selection_anchor:

            caret_pos = start_pos = min(self._caret_pos, self._selection_anchor)
            end_pos = max(start_pos + 1, self._caret_pos, self._selection_anchor)
            start = self._text[:start_pos]
            end = self._text[end_pos:]
            update = True

        else:

            caret_pos = max(0, self._caret_pos - 1)

            if self._caret_pos != caret_pos:
                start = self._text[:caret_pos]
                end = self._text[self._caret_pos:]
                update = True

        if update:
            self._text = "".join((start, end))
            self._selection_anchor = self._caret_pos = caret_pos
            self._char_pos_stale = True
            self.create_label()
            self.__scroll()
            self.__update_image()
            self.__update_caret()

    def __get_char_positions(self):

        if self._char_pos_stale:

            char_positions = []
            font = self._font
            text = self._text

            for i in range(len(text) + 1):
                char_positions.append(font.calc_width(text[:i]))

            self._char_positions = char_positions
            self._char_pos_stale = False

        return self._char_positions[:]

    def move_caret(self, amount=0, is_offset=True, select=False):

        if not self._text:
            return

        c_pos = self._caret_pos
        sel_anchor = self._selection_anchor

        if is_offset:

            offset = amount

        else:

            char_positions = self.__get_char_positions()
            right_edge = char_positions[-1]
            pixels = amount - self._caret_offset_node.get_x()

            if pixels <= 0:
                pos = 0
            elif pixels >= right_edge:
                pos = len(char_positions) - 1
            else:
                char_positions.append(pixels)
                char_positions.sort()
                index = char_positions.index(pixels)
                pos_left = char_positions[index - 1]
                pos_right = char_positions[index + 1]
                pos = index - 1 if pixels < (pos_left + pos_right) / 2 else index

            offset = pos - c_pos

        if offset:

            caret_pos = min(len(self._text), max(0, c_pos + offset))

            if not select:
                if is_offset and self._selection_anchor != c_pos:
                    if offset < 0:
                        caret_pos = min(self._selection_anchor, c_pos)
                    else:
                        caret_pos = max(self._selection_anchor, c_pos)

        else:

            caret_pos = c_pos

        if not select:
            self._selection_anchor = caret_pos

        caret_moved = c_pos != caret_pos
        sel_range_change = caret_moved or self._selection_anchor != sel_anchor
        sel_still_empty = caret_pos - self._selection_anchor == c_pos - sel_anchor == 0
        selection_change = sel_range_change and not sel_still_empty
        self._caret_pos = caret_pos

        if selection_change:

            self.create_label()

            if not caret_moved:
                self.__update_image()

        if caret_moved:

            if self.__scroll() or selection_change:
                self.__update_image()

            self.__update_caret()

    def move_caret_to_start(self, select=False):

        self.move_caret(-self._caret_pos, select=select)

    def move_caret_to_end(self, select=False):

        self.move_caret(len(self._text) - self._caret_pos, select=select)

    def select_all(self):

        if not self._text:
            return

        caret_pos = len(self._text)

        if self._caret_pos != caret_pos or self._selection_anchor != 0:

            self._caret_pos = caret_pos
            self._selection_anchor = 0

            if self._caret_pos > 0:
                self.create_label()
                self.__scroll()
                self.__update_image()
                self.__update_caret()

    def get_text(self):

        return self._text

    def get_selected_text(self):

        start_pos = min(self._caret_pos, self._selection_anchor)
        end_pos = max(start_pos + 1, self._caret_pos, self._selection_anchor)

        return self._text[start_pos:end_pos]

    def copy_text(self):

        r = Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(self.get_selected_text())
        r.update()
        r.destroy()

    def cut_text(self):

        self.copy_text()
        self.delete()

    def paste_text(self):

        r = Tk()
        r.withdraw()
        r.update()

        try:
            text = r.selection_get(selection="CLIPBOARD")
        except:
            r.destroy()
            return

        r.destroy()

        if text and type(text) == str:
            self.write(text)

    def __update_image(self):

        w, h = self._field.get_size()
        image = PNMImage(w, h, 4)
        r, g, b, a = Skin["colors"]["inputfield_background"]
        image.fill(r, g, b)
        image.alpha_fill(a)
        label = self._label

        if label:
            w_l, h_l = label.get_x_size(), label.get_y_size()
            x = margin = Skin["options"]["inputfield_margin"]
            y = (h - h_l) // 2
            w_ = w - margin * 2
            image.blend_sub_image(label, x, y, self._label_offset, 0, w_, h_l)

        img_offset_x, img_offset_y = self._field.get_image_offset()
        image.blend_sub_image(self._field.get_border_image(), img_offset_x, img_offset_y, 0, 0)
        self._image = image
        self._tex.load(image)

    def create_label(self, text=None):

        txt = self._text if text is None else text

        if txt:
            label = self._font.create_image(txt, self._color)
        else:
            label = None

        if text is None:

            self._label = label

            if self._caret_pos - self._selection_anchor:
                start_pos = min(self._caret_pos, self._selection_anchor)
                end_pos = max(self._caret_pos, self._selection_anchor)
                x = self._font.calc_width(self._text[:start_pos])
                txt = self._text[start_pos:end_pos]
                color_fg = Skin["text"]["input_selection"]["color"]
                color_bg = Skin["colors"]["input_selection_background"]
                label_sel = self._font.create_image(txt, color_fg, color_bg)
                label.copy_sub_image(label_sel, x, 0, 0, 0)

        return label

    def get_label(self):

        return self._font.create_image(self._text, self._color)

    def hide(self):

        self._root.hide()
        TextControl._shown_caret = None
        self.move_caret_to_start()

    def show(self, pos):

        self.select_all()
        x, y = pos
        self._root.set_pos(x, 0, -y)
        self._root.show()
        TextControl._shown_caret = self._caret


class InputField(Widget):

    _active_field = None
    _default_input_parsers = {}
    _default_value_parsers = {}
    _default_text_color = (0., 0., 0., 1.)
    _default_back_color = (1., 1., 1., 1.)
    _height = 0
    # create a mouse region "mask" to disable interaction with all widgets (and the
    # viewport) - except input fields - whenever an input field is active
    _mouse_region_mask = None
    _mouse_region_masks = {}
    # make sure each MouseWatcher has a unique name;
    # each time region masks are needed, check for each existing MouseWatcher if its name is in
    # the above dict; if so, retrieve the previously created region mask, otherwise create a
    # region mask for it and add it to the dict;
    # the sort of the region mask for the MouseWatcher named "panel_stack" needs to be 105, the
    # sort of the other region masks must be lower than 100
    _mouse_watchers = None
    _listener = DirectObject()
    _ref_node = NodePath("input_ref_node")
    _edit_menu = None
    _entered_suppressed_state = False

    @classmethod
    def init(cls):

        TextControl.init()

        d = 100000
        cls._mouse_region_mask = MouseWatcherRegion("inputfield_mask", -d, d, -d, d)
        cls._mouse_region_mask.set_sort(90)

        cls._default_text_color = Skin["text"]["input"]["color"]
        cls._default_back_color = Skin["colors"]["inputfield_background"]
        cls._height = Skin["options"]["inputfield_height"]

        def accept_input():

            if cls._active_field:
                cls._active_field._on_accept_input()

        def reject_input():

            if cls._active_field and cls._active_field.allows_reject():
                cls._active_field._on_reject_input()

        Mgr.expose("active_input_field", lambda: cls._active_field)
        Mgr.accept("accept_field_input", accept_input)
        Mgr.accept("reject_field_input", reject_input)

        def parse_to_string(input_text):

            return input_text

        def parse_to_int(input_text):

            try:
                return int(eval(input_text))
            except:
                return None

        def parse_to_float(input_text):

            try:
                return float(eval(input_text))
            except:
                return None

        cls._default_input_parsers["string"] = parse_to_string
        cls._default_input_parsers["int"] = parse_to_int
        cls._default_input_parsers["float"] = parse_to_float

        def parse_from_string(value):

            return value

        def parse_from_int(value):

            return str(value)

        def parse_from_float(value):

            return "{:.5f}".format(value)

        cls._default_value_parsers["string"] = parse_from_string
        cls._default_value_parsers["int"] = parse_from_int
        cls._default_value_parsers["float"] = parse_from_float

        def edit_text(edit_op):

            if cls._active_field:

                txt_ctrl = cls._active_field.get_text_control()

                if edit_op == "cut":
                    txt_ctrl.cut_text()
                elif edit_op == "copy":
                    txt_ctrl.copy_text()
                elif edit_op == "paste":
                    txt_ctrl.paste_text()
                elif edit_op == "select_all":
                    txt_ctrl.select_all()

        cls._edit_menu = menu = Menu()
        menu.add("cut", "Cut", lambda: edit_text("cut"))
        menu.set_item_hotkey("cut", None, "Ctrl+X")
        menu.add("copy", "Copy", lambda: edit_text("copy"))
        menu.set_item_hotkey("copy", None, "Ctrl+C")
        menu.add("paste", "Paste", lambda: edit_text("paste"))
        menu.set_item_hotkey("paste", None, "Ctrl+V")
        menu.add("select_all", "Select All", lambda: edit_text("select_all"))
        menu.set_item_hotkey("select_all", None, "Ctrl+A")
        menu.update()

        Mgr.accept("accept_field_events", cls.__accept_events)
        Mgr.accept("ignore_field_events", cls.__ignore_events)

    @classmethod
    def __accept_events(cls):

        if cls._active_field:
            cls._active_field.accept_events()

    @classmethod
    def __ignore_events(cls):

        if cls._active_field:
            cls._active_field.ignore_events()

    @staticmethod
    def __enter_suppressed_state():

        cls = InputField

        if not cls._entered_suppressed_state:
            Mgr.enter_state("suppressed")
            cls._entered_suppressed_state = True

    @staticmethod
    def __exit_suppressed_state():

        cls = InputField

        if cls._entered_suppressed_state:
            Mgr.exit_state("suppressed")
            cls._entered_suppressed_state = False

    @classmethod
    def _get_mouse_watchers(cls):

        if cls._mouse_watchers is None:
            return GlobalData["mouse_watchers"] 

        return cls._mouse_watchers

    @classmethod
    def _on_accept_input(cls):

        active_field = cls._active_field
        cls.set_active_input_field(None)

        cls.__exit_suppressed_state()
        cls._listener.ignore_all()

        for watcher in cls._get_mouse_watchers():
            region_mask = cls._get_mouse_region_mask(watcher.get_name())
            region_mask.set_active(False)
            watcher.remove_region(region_mask)

        active_field.accept_input()

    @classmethod
    def _on_reject_input(cls):

        active_field = cls._active_field
        cls.set_active_input_field(None)

        cls.__exit_suppressed_state()
        cls._listener.ignore_all()

        for watcher in cls._get_mouse_watchers():
            region_mask = cls._get_mouse_region_mask(watcher.get_name())
            region_mask.set_active(False)
            watcher.remove_region(region_mask)

        active_field.reject_input()

    @classmethod
    def _get_mouse_region_mask(cls, mouse_watcher_name):

        if mouse_watcher_name in cls._mouse_region_masks:
            return cls._mouse_region_masks[mouse_watcher_name]

        if mouse_watcher_name == "panel_stack":
            mouse_region_mask = MouseWatcherRegion(cls._mouse_region_mask)
            mouse_region_mask.set_sort(105)
        else:
            mouse_region_mask = cls._mouse_region_mask

        cls._mouse_region_masks[mouse_watcher_name] = mouse_region_mask

        return mouse_region_mask

    @staticmethod
    def set_active_input_field(input_field):

        InputField._active_field = input_field

    @staticmethod
    def update_active_text_pos():

        if InputField._active_field:
            InputField._active_field.update_text_pos()

    @staticmethod
    def set_default_value_parser(value_type, parser):

        InputField._default_value_parsers[value_type] = parser

    @staticmethod
    def set_default_input_parser(value_type, parser):

        InputField._default_input_parsers[value_type] = parser

    def __init__(self, parent, border_gfx_data, width, text_color=None, back_color=None,
                 sort=110, cull_bin=("gui", 3), on_accept=None, on_reject=None,
                 on_key_enter=None, on_key_escape=None, allow_reject=True):

        Widget.__init__(self, "input_field", parent, gfx_data={}, stretch_dir="horizontal")

        self.get_mouse_region().set_sort(sort)

        self._text_ctrls = {}
        self._width = int(width * Skin["options"]["inputfield_width_scale"])
        size = (self._width, self._height)
        self.set_size(size, is_min=True)
        self._border_gfx_data = border_gfx_data
        self._border_image = self.__create_border_image()
        self._delay_card_update = False
        self._scissor_effect = None

        self._text_color = text_color if text_color else self._default_text_color
        self._back_color = back_color if back_color else self._default_back_color

        self._cull_bin = cull_bin
        self._on_accept = on_accept
        self._on_reject = on_reject
        self._on_key_enter = on_key_enter if on_key_enter else lambda: None
        self._on_key_escape = on_key_escape if on_key_escape else lambda: None
        self._allows_reject = allow_reject
        self._is_text_shown = True
        self._selecting_text = False
        self._texts = {}
        self._value_id = None
        self._value_types = {}
        self._value_handlers = {}
        self._value_parsers = {}
        self._input_parsers = {}
        self._input_init = {}

        self._popup_menu = None
        self._manage_popup_menu = True
        self._popup_handler = lambda: None

    def destroy(self):

        Widget.destroy(self)

        for txt_ctrl in self._text_ctrls.values():
            txt_ctrl.destroy()

        self._text_ctrls = {}
        self._value_handlers = {}
        self._value_parsers = {}
        self._input_parsers = {}
        self._input_init = {}
        self._on_accept = lambda: None
        self._on_reject = lambda: None
        self._on_key_enter = lambda: None
        self._on_key_escape = lambda: None
        self._popup_handler = lambda: None

        if self._popup_menu and self._manage_popup_menu:
            self._popup_menu.destroy()

        self._popup_menu = None

    def __create_border_image(self):

        w, h = self.get_size()
        l, r, b, t = self.get_outer_borders()
        borders_h = l + r
        borders_v = b + t
        width = w + borders_h
        height = h + borders_v
        gfx_data = {"": self._border_gfx_data}
        tmp_widget = Widget("tmp", self.get_parent(), gfx_data, stretch_dir="both", has_mouse_region=False)
        tmp_widget.set_size((width, height), is_min=True)
        tmp_widget.update_images()
        image = tmp_widget.get_image()
        tmp_widget.destroy()

        return image

    def allow_reject(self, allow_reject=True):

        self._allows_reject = allow_reject

    def allows_reject(self):

        return self._allows_reject

    def get_text_control(self, value_id=None):

        return self._text_ctrls[self._value_id if value_id is None else value_id]

    def set_scissor_effect(self, effect):

        self._scissor_effect = effect

        for txt_ctrl in self._text_ctrls.values():
            txt_ctrl.set_scissor_effect(effect)

    def set_size(self, size, includes_borders=True, is_min=False):

        w, h = Widget.set_size(self, size, includes_borders, is_min)
        size = (w, self._height)

        for txt_ctrl in self._text_ctrls.values():
            txt_ctrl.set_size(size)

    def delay_card_update(self, delay=True):

        self._delay_card_update = delay

    def is_card_update_delayed(self):

        return self._delay_card_update

    def __card_update_task(self):

        if self.is_hidden():
            return

        image = self.get_image(composed=False, draw_border=True, crop=True)

        if image:
            w, h = image.get_x_size(), image.get_y_size()
            self.get_card().copy_sub_image(self, image, w, h)

    def __update_card_image(self):

        task = self.__card_update_task

        if self._delay_card_update:
            task_id = "update_card_image"
            PendingTasks.add(task, task_id, sort=1, id_prefix=self.get_widget_id(),
                             batch_id="widget_card_update")
        else:
            task()

    def update_images(self, recurse=True, size=None):

        w, h = self.get_size()

        if "" in self._images:

            img = self._images[""]

            if img.get_x_size() == w and img.get_y_size() == h:
                return

        Widget.update_images(self, recurse, size)

        self._border_image = self.__create_border_image()
        image = PNMImage(w, h, 4)
        r, g, b, a = self._back_color
        image.fill(r, g, b)
        image.alpha_fill(a)
        self._images = {"": image}

        return self._images

    def get_border_image(self):

        return self._border_image

    def get_image(self, state=None, composed=True, draw_border=True, crop=False):

        image = Widget.get_image(self, state, composed)

        if not image:
            return

        if self._value_id and self._is_text_shown:

            if self is self._active_field:
                text = self._texts[self._value_id]
                label = self._text_ctrls[self._value_id].create_label(text)
            else:
                label = self._text_ctrls[self._value_id].get_label()

            if label:
                w, h = self.get_size()
                w_l, h_l = label.get_x_size(), label.get_y_size()
                x = margin = Skin["options"]["inputfield_margin"]
                y = (h - h_l) // 2
                w_ = w - margin * 2
                image.blend_sub_image(label, x, y, 0, 0, w_, h_l)

        if draw_border:

            border_img = self._border_image
            img_offset_x, img_offset_y = self.get_image_offset()

            if crop:
                image.blend_sub_image(border_img, img_offset_x, img_offset_y, 0, 0)
                img = image
            else:
                w, h = border_img.get_x_size(), border_img.get_y_size()
                img = PNMImage(w, h, 4)
                img.copy_sub_image(image, -img_offset_x, -img_offset_y, 0, 0)
                img.blend_sub_image(border_img, 0, 0, 0, 0)

        else:

            img = image

        return img

    def update_text_pos(self):

        pos = self.get_pos(ref_node=self._ref_node)
        self._text_ctrls[self._value_id].set_pos(pos)

    def __set_caret_to_mouse_pos(self, select=False):

        mouse_pointer = Mgr.get("mouse_pointer", 0)
        mouse_x = mouse_pointer.get_x()
        x, y = self.get_pos(ref_node=self._ref_node)
        self._text_ctrls[self._value_id].move_caret(mouse_x - x, is_offset=False, select=select)

    def __select_text(self, task):

        self.__set_caret_to_mouse_pos(select=True)

        return task.again

    def accept_events(self):

        txt_ctrl = self._text_ctrls[self._value_id]

        def write_keystroke(char):

            val = ord(char)

            if val == 1:
                txt_ctrl.select_all()
            if val == 3:
                txt_ctrl.copy_text()
            if val == 24:
                txt_ctrl.cut_text()
            elif val in range(32, 255):
                txt_ctrl.write(char)

        def on_key_enter():

            Mgr.do("accept_field_input")
            self._on_key_enter()

        def on_key_escape():

            Mgr.do("reject_field_input")
            self._on_key_escape()

        def is_shift_down():

            return Mgr.get("mouse_watcher").is_button_down(KeyboardButton.shift())

        listener = self._listener
        listener.accept("gui_arrow_left", lambda: txt_ctrl.move_caret(-1, select=is_shift_down()))
        listener.accept("gui_arrow_right", lambda: txt_ctrl.move_caret(1, select=is_shift_down()))
        listener.accept("gui_arrow_left-repeat", lambda: txt_ctrl.move_caret(-1, select=is_shift_down()))
        listener.accept("gui_arrow_right-repeat", lambda: txt_ctrl.move_caret(1, select=is_shift_down()))
        listener.accept("gui_home", lambda: txt_ctrl.move_caret_to_start(select=is_shift_down()))
        listener.accept("gui_end", lambda: txt_ctrl.move_caret_to_end(select=is_shift_down()))
        listener.accept("gui_delete", txt_ctrl.delete)
        listener.accept("gui_backspace", txt_ctrl.backspace)
        listener.accept("gui_delete-repeat", txt_ctrl.delete)
        listener.accept("gui_backspace-repeat", txt_ctrl.backspace)
        listener.accept("keystroke", write_keystroke)
        listener.accept("gui_enter", on_key_enter)
        listener.accept("gui_escape", on_key_escape)

    def ignore_events(self):

        listener = self._listener
        for event_id in ("gui_arrow_left", "gui_arrow_right", "gui_arrow_left-repeat",
                         "gui_arrow_right-repeat", "gui_home", "gui_end", "gui_delete",
                         "gui_backspace", "gui_delete-repeat", "gui_backspace-repeat",
                         "keystroke", "gui_enter", "gui_escape"):
            listener.ignore(event_id)

    def on_left_down(self):

        if self._active_field is self:
            shift_down = Mgr.get("mouse_watcher").is_button_down(KeyboardButton.shift())
            self.__set_caret_to_mouse_pos(select=shift_down)
            Mgr.add_task(.05, self.__select_text, "select_text")
            self._selecting_text = True
            return

        if self._active_field:

            self._active_field.accept_input()
            self.set_active_input_field(self)

        else:

            if Mgr.get_state_id() != "suppressed":
                self.__enter_suppressed_state()

            self.set_active_input_field(self)

            for watcher in self._get_mouse_watchers():
                region_mask = self._get_mouse_region_mask(watcher.get_name())
                region_mask.set_active(True)
                watcher.add_region(region_mask)

        txt_ctrl = self._text_ctrls[self._value_id]
        text = self._texts[self._value_id]
        txt_ctrl.set_text(text)
        pos = self.get_pos(ref_node=self._ref_node)
        txt_ctrl.show(pos)
        self._input_init[self._value_id]()

        listener = self._listener
        listener.accept("gui_mouse1-up", self.__on_left_up)
        listener.accept("focus_loss", lambda: Mgr.do("reject_field_input"))
        self.accept_events()

        if self.get_mouse_watcher().get_over_region() != self.get_mouse_region():
            Mgr.set_cursor("input_commit")

    def __on_left_up(self):

        if self._selecting_text:

            Mgr.remove_task("select_text")

            if self.get_mouse_watcher().get_over_region() != self.get_mouse_region():
                Mgr.set_cursor("input_commit")

            self._selecting_text = False

    def on_right_down(self):

        if self._active_field is self:
            self._edit_menu.show_at_mouse_pos()
            return

        Mgr.do("reject_field_input")
        self._popup_handler()

    def on_enter(self):

        if PLATFORM_ID == "Windows":
            cursor_id = "i_beam"
        else:
            cursor_id = "caret"

        Mgr.set_cursor(cursor_id)

    def on_leave(self):

        if not self._selecting_text:
            if self._active_field and not Menu.is_menu_shown():
                Mgr.set_cursor("input_commit")
            else:
                Mgr.set_cursor("main")

    def set_input_init(self, value_id, input_init):

        self._input_init[value_id] = input_init

    def set_input_parser(self, value_id, parser):

        self._input_parsers[value_id] = parser

    def __parse_input(self, value_id, input_text):

        val_type = self._value_types[value_id]
        default_parser = self._default_input_parsers.get(val_type)
        parser = self._input_parsers.get(value_id, default_parser)

        return parser(input_text) if parser else None

    def set_value_parser(self, value_id, parser):

        self._value_parsers[value_id] = parser

    def __parse_value(self, value_id, value):

        val_type = self._value_types[value_id]
        default_parser = self._default_value_parsers.get(val_type)
        parser = self._value_parsers.get(value_id, default_parser)

        return parser(value) if parser else None

    def add_value(self, value_id, value_type="float", handler=None, font=None):

        self._value_types[value_id] = value_type
        txt_ctrl = TextControl(self, font, self._text_color, self._cull_bin)
        txt_ctrl.set_scissor_effect(self._scissor_effect)
        self._text_ctrls[value_id] = txt_ctrl
        self._texts[value_id] = ""
        self._input_init[value_id] = lambda: None

        if handler:
            self._value_handlers[value_id] = handler
        else:
            self._value_handlers[value_id] = lambda value_id, value: None

    def __reset_cursor(self):

        over_field = False

        for watcher in self._get_mouse_watchers():

            region = watcher.get_over_region()

            if region:

                name = region.get_name()

                if name.startswith("widget_"):

                    widget_id = int(name.replace("widget_", ""))
                    widget = Widget.registry.get(widget_id)

                    if widget and "field" in widget.get_widget_type():
                        over_field = True
                        break

        if not over_field:
            Mgr.set_cursor("main")

    def accept_input(self, text_handler=None):

        txt_ctrl = self._text_ctrls[self._value_id]
        old_text = self._texts[self._value_id]
        input_text = txt_ctrl.get_text()

        value = self.__parse_input(self._value_id, input_text)
        valid = False

        if value is None:

            val_str = old_text

        else:

            val_str = self.__parse_value(self._value_id, value)

            if val_str is None:
                val_str = old_text
            else:
                valid = True

        self._texts[self._value_id] = val_str

        if valid:

            txt_ctrl.set_text(val_str)

            if self._is_text_shown:
                self.__update_card_image()

            self._value_handlers[self._value_id](self._value_id, value)

            if text_handler:
                text_handler(val_str)

        else:

            txt_ctrl.set_text(old_text)

        txt_ctrl.hide()
        self.__reset_cursor()

        if self._on_accept:
            self._on_accept()

        return valid

    def reject_input(self):

        txt_ctrl = self._text_ctrls[self._value_id]
        old_text = self._texts[self._value_id]
        input_text = txt_ctrl.get_text()

        if input_text != old_text:
            if old_text:
                txt_ctrl.set_text(old_text)
            else:
                txt_ctrl.clear()

        txt_ctrl.hide()
        self.__reset_cursor()

        if self._on_reject:
            self._on_reject()

    def set_value(self, value_id, value, text_handler=None, handle_value=False):

        val_str = self.__parse_value(value_id, value)

        if val_str is None:
            return False

        self._texts[value_id] = val_str
        txt_ctrl = self._text_ctrls[value_id]

        if txt_ctrl.get_text() != val_str:

            txt_ctrl.set_text(val_str)

            if self._is_text_shown and self._value_id == value_id:
                self.__update_card_image()

        if handle_value:
            self._value_handlers[value_id](value_id, value)

        if text_handler:
            text_handler(val_str)

        return True

    def get_value_id(self):

        return self._value_id

    def set_input_text(self, text):

        txt_ctrl = self._text_ctrls[self._value_id]
        txt_ctrl.set_text(text)

    def set_text(self, value_id, text, text_handler=None):

        if self._texts[value_id] == text:
            return False

        txt_ctrl = self._text_ctrls[value_id]
        txt_ctrl.set_text(text)
        self._texts[value_id] = text

        if self._is_text_shown and self._value_id == value_id:
            self.__update_card_image()

        if text_handler:
            text_handler(text)

        return True

    def get_text(self, value_id):

        return self._texts[value_id]

    def show_text(self, show=True):

        if self._is_text_shown == show:
            return False

        self._is_text_shown = show
        self.__update_card_image()

        return True

    def set_text_color(self, color=None):

        txt_ctrl = self._text_ctrls[self._value_id]

        if txt_ctrl.get_color() == color:
            return False

        for value_id, txt_ctrl in self._text_ctrls.items():
            txt_ctrl.set_color(color if color else self._text_color)
            txt_ctrl.set_text(self._texts[value_id])

        if self._is_text_shown:
            self.__update_card_image()

        return True

    def get_text_color(self):

        return self._text_ctrls[self._value_id].get_color()

    def clear(self, forget=True):

        txt_ctrl = self._text_ctrls[self._value_id]
        txt_ctrl.clear()

        if forget:
            self._texts[self._value_id] = ""

        if self._is_text_shown:
            self.__update_card_image()

    def show_value(self, value_id):

        if value_id in self._texts:

            self._value_id = value_id

            if self._is_text_shown:
                self.__update_card_image()

    def set_popup_menu(self, menu, manage=True):

        self._popup_menu = menu
        self._manage_popup_menu = manage
        self._popup_handler = menu.show_at_mouse_pos

    def get_popup_menu(self):

        if not self._popup_menu:
            self._popup_menu = Menu()
            self._popup_handler = self._popup_menu.show_at_mouse_pos

        return self._popup_menu

    def set_popup_handler(self, on_popup):

        if not self._popup_menu:
            self._popup_menu = Menu()

        def handle_popup():

            on_popup()
            self._popup_menu.show_at_mouse_pos()

        self._popup_handler = handle_popup

    def enable(self, enable=True, ignore_parent=False):

        if not Widget.enable(self, enable, ignore_parent):
            return False

        self.__update_card_image()

        return True
