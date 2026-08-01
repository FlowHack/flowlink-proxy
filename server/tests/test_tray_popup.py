"""
Тесты модуля tray/popup.py.

Тестирует: PopupColors (константы), FlowLinkPopup._calc_height (чистая функция).
Не тестирует: tkinter-виджеты (требуют display server).

Пропускается если tkinter не установлен (серверные среды без GUI).
"""

import unittest
from unittest.mock import patch

try:
    from server.tray.popup import FlowLinkPopup, PopupColors
    _HAS_TKINTER = True
except ImportError:
    _HAS_TKINTER = False

# type: ignore[reportPossiblyUnbound] / [reportArgumentType] в тестах ниже:
# pyright не знает runtime-типы tkinter (PopupColors — константы, объявленные
# как ClassVar, FlowLinkPopup.calc_height — статик-метод с runtime-аргументами).


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
        """Пустой список — только статусбар: 6 (padding) + 6 (padding) + 56 = 68."""
        result = FlowLinkPopup.calc_height([])  # type: ignore[reportPossiblyUnbound]
        self.assertEqual(result, 68)

    def test_single_item(self):
        """Один пункт: 6 (padding) + 28 (item) + 6 (padding) + 56 (статусбар) = 96."""
        items = [{'type': 'item', 'text': 'Test'}]
        result = FlowLinkPopup.calc_height(items)  # type: ignore[reportPossiblyUnbound]
        self.assertEqual(result, 96)

    def test_two_items(self):
        """Два пункта: 6 + 28 + 28 + 6 + 56 = 124."""
        items = [
            {'type': 'item', 'text': 'First'},
            {'type': 'item', 'text': 'Second'},
        ]
        result = FlowLinkPopup.calc_height(items)  # type: ignore[reportPossiblyUnbound]
        self.assertEqual(result, 124)

    def test_separator_height(self):
        """Разделитель: 6 + 8 + 28 + 6 + 56 = 104."""
        items = [
            {'type': 'separator'},
            {'type': 'item', 'text': 'Test'},
        ]
        result = FlowLinkPopup.calc_height(items)  # type: ignore[reportPossiblyUnbound]
        self.assertEqual(result, 104)

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
        # 6 + 28*6 + 8*2 + 6 + 56 (статусбар) = 252
        result = FlowLinkPopup.calc_height(items)  # type: ignore[reportPossiblyUnbound]
        self.assertEqual(result, 252)

    def test_unknown_type_treated_as_item(self):
        """Неизвестный тип обрабатывается как пункт."""
        items = [{'type': 'unknown', 'text': 'Test'}]
        result = FlowLinkPopup.calc_height(items)  # type: ignore[reportPossiblyUnbound]
        # Высота как для обычного item: 6 + 28 + 6 + 56 (статусбар) = 96
        self.assertEqual(result, 96)

    def test_statusbar_reserves_multiline_space(self):
        """Статусбар резервирует место под многострочный тултип (до 3 строк).

        Проверяем, что увеличение статусбара не зависит от количества
        пунктов: разница между 3 и 1 пунктом остаётся ровно 2 * item_height.
        """
        result_single = FlowLinkPopup.calc_height(
            [{'type': 'item', 'text': 'X'}],  # type: ignore[reportPossiblyUnbound]
        )
        result_multi = FlowLinkPopup.calc_height([
            {'type': 'item', 'text': 'X'},
            {'type': 'item', 'text': 'Y'},
            {'type': 'item', 'text': 'Z'},
        ])  # type: ignore[reportPossiblyUnbound]
        self.assertEqual(result_multi - result_single, 2 * 28)

@unittest.skipUnless(_HAS_TKINTER, 'tkinter не установлен')
class TestFlowLinkPopupInit(unittest.TestCase):
    """Тесты поведения FlowLinkPopup без реального tkinter-окна."""

    def test_set_tk_root(self):
        """set_tk_root устанавливает корневой объект."""
        popup = FlowLinkPopup()  # type: ignore[reportPossiblyUnbound]
        sentinel = object()
        # тест проверяет что set_tk_root принимает любой объект
        popup.set_tk_root(sentinel)  # type: ignore[reportArgumentType]
        # _root — internal tkinter: проверка что set_tk_root работает
        self.assertIs(popup._root, sentinel)  # pylint: disable=protected-access

    def test_dismiss_when_no_popup(self):
        """dismiss() на пустом popup не бросает исключение."""
        popup = FlowLinkPopup()  # type: ignore[reportPossiblyUnbound]
        # Не должен бросить исключение
        popup.dismiss()


@unittest.skipUnless(_HAS_TKINTER, 'tkinter не установлен')
class TestFlowLinkPopupTooltip(unittest.TestCase):
    """Тесты логики тултипов (без реального tkinter-окна)."""

    def test_initial_tooltip_state(self):
        """При создании статусбар и текст тултипа пусты."""
        popup = FlowLinkPopup()  # type: ignore[reportPossiblyUnbound]
        # internal: проверка приватного состояния тултипа
        self.assertIsNone(popup._tooltip_label)  # pylint: disable=protected-access
        self.assertEqual(popup._tooltip_text, '')  # pylint: disable=protected-access  # internal: проверка тултипов

    def test_show_tooltip_without_popup_sets_text(self):
        """_show_tooltip без popup сохраняет текст."""
        popup = FlowLinkPopup()  # type: ignore[reportPossiblyUnbound]
        # internal: вызов приватного метода тултипа для проверки логики
        popup._show_tooltip('Подсказка')  # pylint: disable=protected-access
        self.assertEqual(popup._tooltip_text, 'Подсказка')  # pylint: disable=protected-access

    def test_show_tooltip_displayed_immediately(self):
        """_show_tooltip сразу вызывает _display_tooltip (без after-задержки)."""
        popup = FlowLinkPopup()  # type: ignore[reportPossiblyUnbound]
        with patch.object(popup, '_display_tooltip') as display:
            # internal: вызов приватного метода тултипа для проверки логики
            popup._show_tooltip('Подсказка')  # pylint: disable=protected-access
            display.assert_called_once_with()

    def test_hide_tooltip_clears_text(self):
        """_hide_tooltip очищает текст подсказки."""
        popup = FlowLinkPopup()  # type: ignore[reportPossiblyUnbound]
        # internal: проверка приватных методов тултипа
        popup._show_tooltip('Подсказка')  # pylint: disable=protected-access
        popup._hide_tooltip()  # pylint: disable=protected-access
        self.assertEqual(popup._tooltip_text, '')  # pylint: disable=protected-access

    def test_hide_tooltip_on_empty_no_crash(self):
        """_hide_tooltip на пустом popup не бросает исключение."""
        popup = FlowLinkPopup()  # type: ignore[reportPossiblyUnbound]
        # internal: вызов приватного метода тултипа для проверки логики
        popup._hide_tooltip()  # pylint: disable=protected-access


if __name__ == '__main__':
    unittest.main()
