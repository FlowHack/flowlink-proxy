"""
Тесты модуля ui/dialogs.py.

Тестирует: _make_compact_item_row (формирование строки списка).
tkinter-виджеты мокаются — реальный display server не требуется.
"""

import unittest
from unittest.mock import MagicMock, patch

from server.ui.dialogs import _make_compact_item_row
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

        def _frame_factory(*args, **kwargs):  # pylint: disable=unused-argument
            frame_kwargs.update(kwargs)
            return frame

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


if __name__ == '__main__':
    unittest.main()
