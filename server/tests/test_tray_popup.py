"""
Тесты модуля tray/popup.py.

Тестирует: PopupColors (константы), FlowLinkPopup._calc_height (чистая функция).
Не тестирует: tkinter-виджеты (требуют display server).

Пропускается если tkinter не установлен (серверные среды без GUI).
"""

import unittest

try:
    from server.tray.popup import FlowLinkPopup, PopupColors
    _HAS_TKINTER = True
except ImportError:
    _HAS_TKINTER = False


@unittest.skipUnless(_HAS_TKINTER, 'tkinter не установлен')
class TestPopupColors(unittest.TestCase):
    """Тесты цветовых констант меню."""

    def test_bg_is_dark(self):
        """Фон — тёмный цвет."""
        self.assertTrue(PopupColors.BG.startswith('#'))  # type: ignore[reportPossiblyUnbound]
        # Тёмный фон: каналы < 0x20
        r = int(PopupColors.BG[1:3], 16)  # type: ignore[reportPossiblyUnbound]
        g = int(PopupColors.BG[3:5], 16)  # type: ignore[reportPossiblyUnbound]
        b = int(PopupColors.BG[5:7], 16)  # type: ignore[reportPossiblyUnbound]
        self.assertLess(r, 0x20)
        self.assertLess(g, 0x20)
        self.assertLess(b, 0x20)

    def test_text_is_light(self):
        """Текст — светлый цвет на тёмном фоне."""
        r = int(PopupColors.TEXT[1:3], 16)  # type: ignore[reportPossiblyUnbound]
        self.assertGreater(r, 0xC0)

    def test_green_for_checkmark(self):
        """Зелёный для галочки чекбокса."""
        self.assertEqual(PopupColors.GREEN, '#2ecc71')  # type: ignore[reportPossiblyUnbound]

    def test_accent_is_red(self):
        """Accent — красный (как в расширении)."""
        self.assertEqual(PopupColors.ACCENT, '#e74c3c')  # type: ignore[reportPossiblyUnbound]

    def test_all_colors_are_hex(self):
        """Все цвета — валидные hex-строки или rgba()."""
        for attr in dir(PopupColors):  # type: ignore[reportPossiblyUnbound]
            if attr.startswith('_'):
                continue
            val = getattr(PopupColors, attr)  # type: ignore[reportPossiblyUnbound]
            if isinstance(val, str):
                is_hex = val.startswith('#') and len(val) == 7
                is_rgba = val.startswith('rgba(') and val.endswith(')')
                is_font = attr.startswith('FONT')
                self.assertTrue(
                    is_hex or is_rgba or is_font,
                    f'{attr} = {val!r} не hex-цвет и не rgba()',
                )


@unittest.skipUnless(_HAS_TKINTER, 'tkinter не установлен')
class TestFlowLinkPopupCalcHeight(unittest.TestCase):
    """Тесты calc_height (статический метод, чистая функция)."""

    def test_empty_list(self):
        """Пустой список — минимальная высота 40."""
        result = FlowLinkPopup.calc_height([])  # type: ignore[reportPossiblyUnbound]
        self.assertEqual(result, 40)

    def test_single_item(self):
        """Один пункт: 6 (padding) + 28 (item) + 6 (padding) + 20 (статусбар) = 60."""
        items = [{'type': 'item', 'text': 'Test'}]
        result = FlowLinkPopup.calc_height(items)  # type: ignore[reportPossiblyUnbound]
        self.assertEqual(result, 60)

    def test_two_items(self):
        """Два пункта: 6 + 28 + 28 + 6 + 20 = 88."""
        items = [
            {'type': 'item', 'text': 'First'},
            {'type': 'item', 'text': 'Second'},
        ]
        result = FlowLinkPopup.calc_height(items)  # type: ignore[reportPossiblyUnbound]
        self.assertEqual(result, 88)

    def test_separator_height(self):
        """Разделитель: 6 + 8 + 28 + 6 + 20 = 68."""
        items = [
            {'type': 'separator'},
            {'type': 'item', 'text': 'Test'},
        ]
        result = FlowLinkPopup.calc_height(items)  # type: ignore[reportPossiblyUnbound]
        self.assertEqual(result, 68)

    def test_menu_7_items_2_separators(self):
        """Полное меню (6 пунктов + 2 разделителя)."""
        items = [
            {'type': 'item', 'text': '1'},
            {'type': 'item', 'text': '2'},
            {'type': 'item', 'text': '3'},
            {'type': 'item', 'text': '4'},
            {'type': 'separator'},
            {'type': 'check', 'text': '5'},
            {'type': 'separator'},
            {'type': 'item', 'text': '6'},
        ]
        # 6 + 28*6 + 8*2 + 6 + 20 (статусбар) = 216
        result = FlowLinkPopup.calc_height(items)  # type: ignore[reportPossiblyUnbound]
        self.assertEqual(result, 216)

    def test_unknown_type_treated_as_item(self):
        """Неизвестный тип обрабатывается как пункт."""
        items = [{'type': 'unknown', 'text': 'Test'}]
        result = FlowLinkPopup.calc_height(items)  # type: ignore[reportPossiblyUnbound]
        # Высота как для обычного item: 6 + 28 + 6 + 20 (статусбар) = 60
        self.assertEqual(result, 60)

    def test_min_height_floor(self):
        """Минимальная высота — 40, даже если calculation меньше."""
        # Теоретически не может быть < 40 при реальных данных,
        # но проверяем guard в коде
        result = FlowLinkPopup.calc_height([])  # type: ignore[reportPossiblyUnbound]
        self.assertGreaterEqual(result, 40)


@unittest.skipUnless(_HAS_TKINTER, 'tkinter не установлен')
class TestFlowLinkPopupInit(unittest.TestCase):
    """Тесты начального состояния FlowLinkPopup."""

    def test_initial_root_none(self):
        """При создании _root = None."""
        popup = FlowLinkPopup()  # type: ignore[reportPossiblyUnbound]
        # _root — internal tkinter: проверка начального состояния
        self.assertIsNone(popup._root)  # pylint: disable=protected-access

    def test_initial_popup_none(self):
        """При создании _popup = None."""
        popup = FlowLinkPopup()  # type: ignore[reportPossiblyUnbound]
        # _popup — internal tkinter: проверка начального состояния
        self.assertIsNone(popup._popup)  # pylint: disable=protected-access

    def test_set_tk_root(self):
        """set_tk_root устанавливает _root."""
        popup = FlowLinkPopup()  # type: ignore[reportPossiblyUnbound]
        sentinel = object()
        # тест проверяет что set_tk_root принимает любой объект
        popup.set_tk_root(sentinel)  # type: ignore[reportArgumentType]
        # _root — internal tkinter: проверка что set_tk_root работает
        self.assertIs(popup._root, sentinel)  # pylint: disable=protected-access

    def test_queue_created(self):
        """При создании создаётся очередь."""
        popup = FlowLinkPopup()  # type: ignore[reportPossiblyUnbound]
        # _queue — internal tkinter: проверка что очередь создана
        self.assertIsNotNone(popup._queue)  # pylint: disable=protected-access

    def test_dismiss_when_no_popup(self):
        """dismiss() на пустом popup не бросает исключение."""
        popup = FlowLinkPopup()  # type: ignore[reportPossiblyUnbound]
        # Не должен бросить исключение
        popup.dismiss()

    def test_polling_active_initially_false(self):
        """_polling_active = False при создании."""
        popup = FlowLinkPopup()  # type: ignore[reportPossiblyUnbound]
        # _polling_active — internal tkinter: проверка начального состояния
        self.assertFalse(popup._polling_active)  # pylint: disable=protected-access


@unittest.skipUnless(_HAS_TKINTER, 'tkinter не установлен')
class TestFlowLinkPopupTooltip(unittest.TestCase):
    """Тесты логики тултипов (без реального tkinter-окна)."""

    def test_initial_tooltip_state(self):
        """При создании статусбар и таймер тултипа пусты."""
        popup = FlowLinkPopup()  # type: ignore[reportPossiblyUnbound]
        self.assertIsNone(popup._tooltip_label)  # pylint: disable=protected-access
        self.assertIsNone(popup._tooltip_after_id)  # pylint: disable=protected-access
        self.assertEqual(popup._tooltip_text, '')  # pylint: disable=protected-access

    def test_show_tooltip_without_popup_sets_text(self):
        """_show_tooltip без popup сохраняет текст, но не планирует таймер."""
        popup = FlowLinkPopup()  # type: ignore[reportPossiblyUnbound]
        popup._show_tooltip('Подсказка')  # pylint: disable=protected-access
        self.assertEqual(popup._tooltip_text, 'Подсказка')  # pylint: disable=protected-access
        self.assertIsNone(popup._tooltip_after_id)  # pylint: disable=protected-access

    def test_hide_tooltip_clears_text(self):
        """_hide_tooltip очищает текст подсказки."""
        popup = FlowLinkPopup()  # type: ignore[reportPossiblyUnbound]
        popup._show_tooltip('Подсказка')  # pylint: disable=protected-access
        popup._hide_tooltip()  # pylint: disable=protected-access
        self.assertEqual(popup._tooltip_text, '')  # pylint: disable=protected-access

    def test_hide_tooltip_on_empty_no_crash(self):
        """_hide_tooltip на пустом popup не бросает исключение."""
        popup = FlowLinkPopup()  # type: ignore[reportPossiblyUnbound]
        popup._hide_tooltip()  # pylint: disable=protected-access


if __name__ == '__main__':
    unittest.main()
