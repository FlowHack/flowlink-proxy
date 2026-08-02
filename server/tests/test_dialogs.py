"""
Тесты модуля ui/dialogs.py.

Тестирует: _make_compact_item_row (формирование строки списка).
tkinter-виджеты мокаются — реальный display server не требуется.
"""

import unittest
from unittest.mock import MagicMock, patch

from server.ui.dialogs import (_make_compact_item_row, show_info,
                               show_item_picker)
from server.ui.theme import ThemeColors


class TestMakeCompactItemRow(unittest.TestCase):
    """Тесты _make_compact_item_row."""

    def _build_row(self, selected=False):
        """
        Создаёт строку с моками tkinter-виджетов.

        Args:
            selected: Значение параметра selected для функции.

        Returns:
            Кортеж (row, frame_kwargs, labels), где labels — список
            словарей с kwargs каждого вызова tk.Label.
        """
        parent = MagicMock()
        frame = MagicMock()
        frame_kwargs = {}
        labels = []

        # Параметры *args/**kwargs нужны для подмены tk.Frame (unused-argument)
        def _frame_factory(*args, **kwargs):  # pylint: disable=unused-argument
            frame_kwargs.update(kwargs)
            return frame

        # Параметры *args/**kwargs нужны для подмены tk.Label (unused-argument)
        def _label_factory(*args, **kwargs):  # pylint: disable=unused-argument
            lbl = MagicMock()
            lbl.cget = MagicMock(return_value='')
            labels.append(kwargs)
            return lbl

        with (
            patch(
                'server.ui.dialogs.tk.Frame',
                side_effect=_frame_factory,
            ),
            patch(
                'server.ui.dialogs.tk.Label',
                side_effect=_label_factory,
            ),
        ):
            row = _make_compact_item_row(
                parent, 'Браузер', '/usr/bin/browser', selected=selected,
            )
        return row, frame_kwargs, labels

    def test_selected_adds_green_checkmark(self):
        """При selected=True создаётся зелёная галочка ✓."""
        _, _, labels = self._build_row(selected=True)
        check_labels = [
            lbl for lbl in labels if lbl.get('text') == '\u2713'
        ]
        self.assertEqual(len(check_labels), 1)
        self.assertEqual(check_labels[0].get('fg'), ThemeColors.GREEN)

    def test_not_selected_has_no_checkmark(self):
        """При selected=False галочка не создаётся."""
        _, _, labels = self._build_row(selected=False)
        check_labels = [
            lbl for lbl in labels if lbl.get('text') == '\u2713'
        ]
        self.assertEqual(len(check_labels), 0)

    def test_selected_uses_green_dim_background(self):
        """При selected=True фон строки — приглушённый зелёный."""
        _, frame_kwargs, _ = self._build_row(selected=True)
        self.assertEqual(frame_kwargs.get('bg'), ThemeColors.GREEN_DIM)

    def test_not_selected_uses_surface_background(self):
        """При selected=False фон строки — стандартный SURFACE."""
        _, frame_kwargs, _ = self._build_row(selected=False)
        self.assertEqual(frame_kwargs.get('bg'), ThemeColors.SURFACE)


class TestShowInfo(unittest.TestCase):
    """Тесты show_info (мок tkinter-виджетов)."""

    def _make_tk_mocks(self):
        """
        Создаёт моки tkinter-виджетов для show_info.

        Returns:
            Словарь с моками: root, dialog, button, label.
        """
        root = MagicMock()
        dialog = MagicMock()
        # winfo_* возвращают числа (для расчёта размеров окна)
        dialog.winfo_screenwidth.return_value = 1920
        dialog.winfo_screenheight.return_value = 1080
        dialog.winfo_reqwidth.return_value = 480
        dialog.winfo_reqheight.return_value = 200
        button = MagicMock()
        label = MagicMock()
        return root, dialog, button, label

    def test_buttons_none_creates_ok_button(self):
        """При buttons=None создаётся одна кнопка 'OK'."""
        root, dialog, _button, label = self._make_tk_mocks()
        label_texts = []

        # Параметры *args/**kwargs нужны для подмены tk.Label (unused-argument)
        def _label_factory(*args, **kwargs):  # pylint: disable=unused-argument
            label_texts.append(kwargs.get('text', ''))
            return label

        with (
            patch('server.ui.dialogs._get_or_create_root', return_value=root),
            patch('server.ui.dialogs._set_window_icon'),
            patch('server.ui.dialogs.tk.Toplevel', return_value=dialog),
            patch('server.ui.dialogs.tk.Label', side_effect=_label_factory),
            patch('server.ui.dialogs.tk.Frame', return_value=MagicMock()),
        ):
            show_info('Заголовок', 'Сообщение')

        self.assertIn('OK', label_texts)

    def test_button_action_called(self):
        """Кнопка с action вызывает action при клике."""
        root, dialog, _button, label = self._make_tk_mocks()
        action_called = []

        def _action():
            action_called.append(True)

        # Параметры *args/**kwargs нужны для подмены tk.Label (unused-argument)
        def _label_factory(*args, **kwargs):  # pylint: disable=unused-argument
            return label

        with (
            patch('server.ui.dialogs._get_or_create_root', return_value=root),
            patch('server.ui.dialogs._set_window_icon'),
            patch('server.ui.dialogs.tk.Toplevel', return_value=dialog),
            patch('server.ui.dialogs.tk.Label', side_effect=_label_factory),
            patch('server.ui.dialogs.tk.Frame', return_value=MagicMock()),
        ):
            show_info(
                'Заголовок', 'Сообщение',
                buttons=[{'text': 'Действие', 'action': _action}],
            )

        # Кнопки создаются через tk.Label (см. _make_button).
        # Извлекаем bind-обработчик клика и вызываем его.
        for call in label.bind.call_args_list:
            args = call.args
            if args and args[0] == '<Button-1>':
                handler = args[1]
                handler()
                break

        self.assertEqual(action_called, [True])


class TestShowItemPicker(unittest.TestCase):
    """Тесты show_item_picker (мок tkinter-виджетов)."""

    def _make_tk_mocks(self):
        """
        Создаёт моки tkinter-виджетов для show_item_picker.

        Returns:
            Словарь с моками: root, dialog, button, label.
        """
        root = MagicMock()
        dialog = MagicMock()
        # winfo_* возвращают числа (для расчёта размеров окна)
        dialog.winfo_screenwidth.return_value = 1920
        dialog.winfo_screenheight.return_value = 1080
        dialog.winfo_reqwidth.return_value = 480
        dialog.winfo_reqheight.return_value = 200
        button = MagicMock()
        label = MagicMock()
        return root, dialog, button, label

    def test_manual_button_shown_when_allowed(self):
        """Кнопка 'Указать вручную' появляется при allow_manual=True."""
        root, dialog, _button, label = self._make_tk_mocks()
        label_texts = []

        # Параметры *args/**kwargs нужны для подмены tk.Label (unused-argument)
        def _label_factory(*args, **kwargs):  # pylint: disable=unused-argument
            label_texts.append(kwargs.get('text', ''))
            return label

        with (
            patch('server.ui.dialogs._get_or_create_root', return_value=root),
            patch('server.ui.dialogs._set_window_icon'),
            patch('server.ui.dialogs.tk.Toplevel', return_value=dialog),
            patch('server.ui.dialogs.tk.Label', side_effect=_label_factory),
            patch('server.ui.dialogs.tk.Frame', return_value=MagicMock()),
        ):
            show_item_picker(
                'Заголовок', 'Сообщение',
                items=[{'label': 'Элемент', 'subtitle': 'Описание'}],
                on_select=lambda item: None,
                allow_manual=True,
            )

        self.assertIn('Указать вручную', label_texts)

    def test_manual_button_hidden_when_not_allowed(self):
        """Кнопка 'Указать вручную' НЕ появляется при allow_manual=False."""
        root, dialog, _button, label = self._make_tk_mocks()
        label_texts = []

        # Параметры *args/**kwargs нужны для подмены tk.Label (unused-argument)
        def _label_factory(*args, **kwargs):  # pylint: disable=unused-argument
            label_texts.append(kwargs.get('text', ''))
            return label

        with (
            patch('server.ui.dialogs._get_or_create_root', return_value=root),
            patch('server.ui.dialogs._set_window_icon'),
            patch('server.ui.dialogs.tk.Toplevel', return_value=dialog),
            patch('server.ui.dialogs.tk.Label', side_effect=_label_factory),
            patch('server.ui.dialogs.tk.Frame', return_value=MagicMock()),
        ):
            show_item_picker(
                'Заголовок', 'Сообщение',
                items=[{'label': 'Элемент', 'subtitle': 'Описание'}],
                on_select=lambda item: None,
                allow_manual=False,
            )

        self.assertNotIn('Указать вручную', label_texts)

    def test_item_selection_calls_on_select(self):
        """Выбор элемента вызывает on_select с данными элемента."""
        root, dialog, _button, label = self._make_tk_mocks()
        selected_items = []

        def _on_select(item):
            selected_items.append(item)

        # Параметры *args/**kwargs нужны для подмены tk.Label (unused-argument)
        def _label_factory(*args, **kwargs):  # pylint: disable=unused-argument
            return label

        with (
            patch('server.ui.dialogs._get_or_create_root', return_value=root),
            patch('server.ui.dialogs._set_window_icon'),
            patch('server.ui.dialogs.tk.Toplevel', return_value=dialog),
            patch('server.ui.dialogs.tk.Label', side_effect=_label_factory),
            patch('server.ui.dialogs.tk.Frame', return_value=MagicMock()),
        ):
            show_item_picker(
                'Заголовок', 'Сообщение',
                items=[{'label': 'Элемент', 'subtitle': 'Описание'}],
                on_select=_on_select,
                allow_manual=False,
            )

        # Элементы списка создаются через tk.Label (см. _make_compact_item_row).
        # Извлекаем bind-обработчик клика и вызываем его.
        for call in label.bind.call_args_list:
            args = call.args
            if args and args[0] == '<Button-1>':
                handler = args[1]
                handler()
                break

        self.assertEqual(len(selected_items), 1)
        self.assertEqual(selected_items[0]['label'], 'Элемент')


if __name__ == '__main__':
    unittest.main()
