#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Генератор version_info для PyInstaller (Windows version resource).

Скрипт создаёт файл version_info.txt, который передаётся в PyInstaller
через флаг --version-file. Наличие version resource в exe снижает ложные
срабатывания антивирусных эвристик (в частности, Windows Defender), поскольку
exe перестаёт выглядеть как «неописанный» бинарник.

Использование:
    python make_version_info.py <VERSION> <OUTPUT_PATH>

VERSION — строка вида X.Y.Z; допускается суффикс (например, X.Y.Z.dev1).
Для version resource используются только числовые компоненты версии:
недостающие компоненты заменяются на 0.
"""

import re
import sys
from pathlib import Path


def parse_version(version: str) -> tuple:
    """Разбирает строку версии на 4 числовых компонента.

    Args:
        version: Строка версии, например "1.2.3" или "1.2.3.dev1".

    Returns:
        Кортеж (major, minor, build, patch) из целых чисел.
        Нечисловые суффиксы отбрасываются, недостающие компоненты равны 0.
    """
    match = re.match(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:\.(\d+))?", version or "")
    if not match:
        return (0, 0, 0, 0)
    parts = [int(group) if group else 0 for group in match.groups()]
    # Дополняем кортеж до 4 компонентов (patch по умолчанию = 0)
    while len(parts) < 4:
        parts.append(0)
    return tuple(parts[:4])


def build_version_info(version: str) -> str:
    """Формирует содержимое version_info-файла для PyInstaller.

    Args:
        version: Строка версии (например, "1.2.3").

    Returns:
        Текст файла в формате VSVersionInfo, готовый к записи.
    """
    filevers = prodvers = parse_version(version)
    return f"""# UTF-8
#
# Для получения информации о fixed file info 'ffi' смотрите:
# http://msdn.microsoft.com/en-us/library/ms646997.aspx

VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={filevers!r},
    prodvers={prodvers!r},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        u'040904B0',
        [StringStruct(u'CompanyName', u'FlowLink'),
        StringStruct(u'FileDescription', u'FlowLink Proxy'),
        StringStruct(u'FileVersion', u'{version}'),
        StringStruct(u'InternalName', u'FlowLink Proxy'),
        StringStruct(u'LegalCopyright', u'Copyright (c) FlowLink. Лицензия GNU AGPL v3.'),
        StringStruct(u'OriginalFilename', u'FlowLink Proxy.exe'),
        StringStruct(u'ProductName', u'FlowLink Proxy'),
        StringStruct(u'ProductVersion', u'{version}')])
      ])
    ,
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
"""


def main() -> None:
    """Точка входа: генерирует version_info-файл по аргументам CLI."""
    if len(sys.argv) != 3:
        print("Использование: python make_version_info.py <VERSION> <OUTPUT_PATH>")
        sys.exit(2)

    version = sys.argv[1]
    output_path = Path(sys.argv[2])

    content = build_version_info(version)
    try:
        output_path.write_text(content, encoding="utf-8")
    except OSError as exc:
        print(f"Ошибка записи version_info в {output_path}: {exc}")
        sys.exit(1)

    print(f"version_info записан в {output_path} (версия: {version})")


if __name__ == "__main__":
    main()
