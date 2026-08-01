"""Единая цветовая палитра проекта FlowLink Proxy.

Все hex-коды синхронизированы с CSS-переменными в extension/popup/popup.css
и help.html. Используется как в Python (tkinter), так и как эталон для CSS.
"""

# pylint: disable=too-few-public-methods — класс хранит только статические
# константы (цвета темы), методов у него нет по назначению


class ThemeColors:
    """Единая цветовая палитра проекта FlowLink Proxy.

    Все hex-коды синхронизированы с CSS-переменными в extension/popup/popup.css
    и help.html. Используется как в Python (tkinter), так и как эталон для CSS.
    """

    # Основные цвета
    BG = '#0d0d1a'              # --bg-primary: основной фон
    SURFACE = '#1a1a2e'         # --bg-surface: поверхность карточек
    SURFACE_HOVER = '#222244'   # --bg-surface-hover: hover элементов
    INPUT_BG = '#16213e'        # --bg-input: поля ввода, code-блоки

    # Текст
    TEXT = '#e0e0e0'            # --text-primary: основной текст
    TEXT_SECONDARY = '#999999'  # --text-secondary: вторичный текст
    TEXT_MUTED = '#666666'      # --text-muted: приглушённый текст

    # Границы и разделители
    BORDER = '#2a2a4a'          # --border: все границы

    # Акценты
    ACCENT = '#e74c3c'          # --accent-red: красный акцент (основной)
    ACCENT_HOVER = '#c0392b'    # --accent-red-hover: hover красного
    GREEN = '#2ecc71'           # --accent-green: зелёный (успех, ping OK)
    GREEN_DIM = '#1a8c4a'       # --accent-green-dim: приглушённый зелёный
    ORANGE = '#e67e22'          # --accent-orange: оранжевый (предупреждение)
    BLUE = '#3498db'            # --accent-blue: синий (информация)

    # Опасность / удаление
    DANGER = '#ff4444'          # --danger: опасность
    DANGER_HOVER = '#ff6666'    # hover опасности

    # Полупрозрачные цвета (для оверлеев и фоновых эффектов)
    OVERLAY = 'rgba(0, 0, 0, 0.7)'          # overlay модальных окон
    ACCENT_TRANSPARENT = 'rgba(231, 76, 60, 0.15)'   # полупрозрачный красный
    ORANGE_TRANSPARENT = 'rgba(230, 126, 34, 0.2)'   # полупрозрачный оранжевый
    BLUE_TRANSPARENT = 'rgba(52, 152, 219, 0.15)'    # полупрозрачный синий
    DANGER_TRANSPARENT = 'rgba(255, 68, 68, 0.15)'   # полупрозрачный опасность

    # Шрифты (tkinter)
    FONT_FAMILY = ('Segoe UI', 'TkDefaultFont')
    FONT_SIZE_SMALL = 9
    FONT_SIZE_NORMAL = 10
    FONT_SIZE_LARGE = 11
    FONT_SIZE_TITLE = 13
