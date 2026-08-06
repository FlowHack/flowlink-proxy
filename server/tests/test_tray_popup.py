"""
Тесты модуля tray/popup.py.

Тестирует: PopupColors (константы), FlowLinkPopup._calc_height (чистая функция).
Не тестирует: tkinter-виджеты (требуют display server).

Пропускается если tkinter не установлен (серверные среды без GUI).
"""

import unittest
from pathlib import Path
from unittest.mock import MagicMock

try:
    import tkinter as tk
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

    def test_theme_colors_synced_with_css(self):
        """Hex-цвета ThemeColors присутствуют в CSS-файлах расширения.

        Проверяет заявленную синхронизацию палитры (server/ui/theme.py) с
        extension/popup/popup.css и extension/popup/help.css: каждый hex-цвет
        из ThemeColors должен встречаться хотя бы в одном CSS-файле.
        """
        repo_root = Path(__file__).resolve().parents[2]
        popup_css = (
            repo_root / 'extension' / 'popup' / 'popup.css'
        ).read_text(encoding='utf-8')
        help_css = (
            repo_root / 'extension' / 'popup' / 'help.css'
        ).read_text(encoding='utf-8')
        combined = popup_css + '\n' + help_css

        missing = []
        for name in dir(PopupColors):  # type: ignore[reportPossiblyUnbound]
            if name.startswith('_'):
                continue
            value = getattr(PopupColors, name)  # type: ignore[reportPossiblyUnbound]
            if not isinstance(value, str):
                continue
            if not (value.startswith('#') and len(value) == 7):
                continue  # rgba()-цвета и прочие форматы не сравниваются
            if value not in combined:
                missing.append(f'{name}={value}')
        self.assertEqual(
            missing, [],
            f'Цвета ThemeColors отсутствуют в CSS расширения: {missing}',
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
class TestFlowLinkPopupGeometry(unittest.TestCase):
    """Тесты чистой геометрии popup (без реального tkinter-окна).

    _calc_y_position и _is_click_outside_popup — приватные методы, но их
    логика (позиционирование относительно курсора/экрана и проверка
    попадания точки в прямоугольник окна) тестируема с мок-объектами
    без display-сервера.
    """

    # protected-access: белый ящик — тесты сознательно обращаются
    # к приватным методам геометрии через мок-попап
    # pylint: disable=protected-access

    def _make_popup(self) -> FlowLinkPopup:
        """Создаёт popup без реального окна."""
        return FlowLinkPopup()  # type: ignore[reportPossiblyUnbound]

    # ── _calc_y_position ──────────────────────────────────────────

    def test_calc_y_explicit_value_unchanged(self):
        """Явная y возвращается без изменений (не зависит от экрана)."""
        popup = self._make_popup()
        # popup без _root/_popup не мешает: ветка с явной y их не трогает
        self.assertEqual(
            popup._calc_y_position(100, 50), 100,  # pylint: disable=protected-access
        )
        self.assertEqual(
            popup._calc_y_position(0, 200), 0,  # pylint: disable=protected-access
        )

    def test_calc_y_places_above_cursor(self):
        """y=None: меню располагается над курсором, если влезает."""
        popup = self._make_popup()
        popup._popup = MagicMock()  # pylint: disable=protected-access
        popup._popup.winfo_screenheight.return_value = 1080
        popup._root = MagicMock()  # pylint: disable=protected-access
        popup._root.winfo_pointery.return_value = 200
        result = popup._calc_y_position(None, 50)  # pylint: disable=protected-access
        # above_y = 200 - 50 - 8 = 142 >= 0 → меню над курсором
        self.assertEqual(result, 142)

    def test_calc_y_places_below_cursor(self):
        """y=None: над курсором не влезает → меню под курсором."""
        popup = self._make_popup()
        popup._popup = MagicMock()  # pylint: disable=protected-access
        popup._popup.winfo_screenheight.return_value = 1080
        popup._root = MagicMock()  # pylint: disable=protected-access
        popup._root.winfo_pointery.return_value = 100
        result = popup._calc_y_position(None, 500)  # pylint: disable=protected-access
        # above_y = 100 - 500 - 8 = -408 < 0; below_y = 108; 108 + 500 <= 1080
        self.assertEqual(result, 108)

    def test_calc_y_clamps_to_bottom(self):
        """y=None: не влезает ни над, ни под курсором → к нижнему краю."""
        popup = self._make_popup()
        popup._popup = MagicMock()  # pylint: disable=protected-access
        popup._popup.winfo_screenheight.return_value = 1080
        popup._root = MagicMock()  # pylint: disable=protected-access
        popup._root.winfo_pointery.return_value = 100
        result = popup._calc_y_position(None, 1000)  # pylint: disable=protected-access
        # below_y + height = 108 + 1000 = 1108 > 1080 → sh - height - 4
        self.assertEqual(result, 1080 - 1000 - 4)

    def test_calc_y_fallback_screen_height_on_tcl_error(self):
        """TclError при получении высоты экрана → fallback 1080."""
        popup = self._make_popup()
        popup._popup = MagicMock()  # pylint: disable=protected-access
        popup._popup.winfo_screenheight.side_effect = tk.TclError('no display')
        popup._root = MagicMock()  # pylint: disable=protected-access
        popup._root.winfo_pointery.return_value = 500
        result = popup._calc_y_position(None, 100)  # pylint: disable=protected-access
        # fallback sh=1080; above_y = 500 - 100 - 8 = 392 >= 0
        self.assertEqual(result, 392)

    # ── _is_click_outside_popup ───────────────────────────────────

    def test_click_outside_without_popup(self):
        """Без popup клик не считается внешним (False)."""
        popup = self._make_popup()
        self.assertFalse(
            popup._is_click_outside_popup(100, 100),  # pylint: disable=protected-access
        )

    def test_click_outside_destroyed_popup(self):
        """Разрушенное окно (winfo_exists=False) → False."""
        popup = self._make_popup()
        popup._popup = MagicMock()  # pylint: disable=protected-access
        popup._popup.winfo_exists.return_value = False
        self.assertFalse(
            popup._is_click_outside_popup(100, 100),  # pylint: disable=protected-access
        )

    def test_click_outside_unknown_geometry(self):
        """Окно ещё не отрисовано (width<=1) → False (не закрывать меню)."""
        popup = self._make_popup()
        popup._popup = MagicMock()  # pylint: disable=protected-access
        popup._popup.winfo_exists.return_value = True
        popup._popup.winfo_width.return_value = 1
        popup._popup.winfo_height.return_value = 220
        self.assertFalse(
            popup._is_click_outside_popup(100, 100),  # pylint: disable=protected-access
        )

    def test_click_outside_geometry(self):
        """Клик вне прямоугольника окна → True, внутри → False."""
        popup = self._make_popup()
        popup._popup = MagicMock()  # pylint: disable=protected-access
        popup._popup.winfo_exists.return_value = True
        popup._popup.winfo_width.return_value = 220
        popup._popup.winfo_height.return_value = 100
        popup._popup.winfo_rootx.return_value = 100
        popup._popup.winfo_rooty.return_value = 200
        # Прямоугольник окна: x 100..320, y 200..300
        self.assertFalse(
            popup._is_click_outside_popup(150, 250),  # pylint: disable=protected-access  # внутри
        )
        self.assertTrue(
            popup._is_click_outside_popup(99, 250),  # pylint: disable=protected-access  # слева
        )
        self.assertTrue(
            popup._is_click_outside_popup(321, 250),  # pylint: disable=protected-access  # справа
        )
        self.assertTrue(
            popup._is_click_outside_popup(150, 199),  # pylint: disable=protected-access  # сверху
        )
        self.assertTrue(
            popup._is_click_outside_popup(150, 301),  # pylint: disable=protected-access  # снизу
        )

    def test_click_outside_tcl_error(self):
        """TclError при проверке геометрии → False (не падаем)."""
        popup = self._make_popup()
        popup._popup = MagicMock()  # pylint: disable=protected-access
        popup._popup.winfo_exists.side_effect = tk.TclError('bad window')
        self.assertFalse(
            popup._is_click_outside_popup(100, 100),  # pylint: disable=protected-access
        )


if __name__ == '__main__':
    unittest.main()
