"""
Тесты build-скриптов.

Проверяют скрипт сборки CRX (build-crx.sh) и синтаксис всех shell-скриптов.
Тесты быстрые — не запускают реальную сборку, только проверяют содержимое файлов.
"""

import os
import subprocess
import unittest

# Путь к корню проекта (от server/tests/ поднимаемся на 2 уровня)
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..')
)


def _read_file(rel_path: str) -> str:
    """Читает файл относительно корня проекта."""
    full = os.path.join(PROJECT_ROOT, rel_path)
    with open(full, 'r', encoding='utf-8') as f:
        return f.read()


def _file_exists(rel_path: str) -> bool:
    """Проверяет существование файла относительно корня проекта."""
    return os.path.isfile(os.path.join(PROJECT_ROOT, rel_path))


# ──────────────────────────────────────────────────────────────
# build-crx.sh
# ──────────────────────────────────────────────────────────────


class TestBuildCrxScript(unittest.TestCase):
    """Тесты скрипта scripts/build/build-crx.sh."""

    def test_build_crx_script_exists(self):
        """Скрипт build-crx.sh существует."""
        self.assertTrue(
            _file_exists('scripts/build/build-crx.sh'),
            'scripts/build/build-crx.sh не найден',
        )

    def test_build_crx_script_syntax(self):
        """Скрипт build-crx.sh проходит проверку bash -n."""
        result = subprocess.run(
            ['bash', '-n', 'scripts/build/build-crx.sh'],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(
            result.returncode, 0,
            f'bash -n завершился с ошибкой:\n{result.stderr}',
        )

    def test_build_crx_requires_key(self):
        """При отсутствии ключа скрипт завершается с ошибкой."""
        result = subprocess.run(
            ['bash', 'scripts/build/build-crx.sh', '--key', '/tmp/nonexistent_key.pem'],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Приватный ключ не найден', result.stdout + result.stderr)

    def test_build_crx_output_name(self):
        """Скрипт формирует выходной файл releases/flowlink-proxy.crx."""
        content = _read_file('scripts/build/build-crx.sh')
        self.assertIn('flowlink-proxy.crx', content)

    def test_build_crx_uses_openssl(self):
        """Скрипт использует openssl для извлечения публичного ключа."""
        content = _read_file('scripts/build/build-crx.sh')
        self.assertIn('openssl', content)
        self.assertIn('rsa', content)
        self.assertIn('pubout', content)

    def test_build_crx_uses_crx3(self):
        """Скрипт использует crx3-utils для сборки CRX."""
        content = _read_file('scripts/build/build-crx.sh')
        self.assertIn('crx3-utils', content)
        self.assertIn('crx3-new', content)


# ──────────────────────────────────────────────────────────────
# Проверка синтаксиса всех shell-скриптов
# ──────────────────────────────────────────────────────────────


class TestShellSyntax(unittest.TestCase):
    """Проверка синтаксиса всех build shell-скриптов."""

    SHELL_SCRIPTS = [
        'scripts/build/build-crx.sh',
        'scripts/build/build.sh',
        'scripts/build/create-release.sh',
        'scripts/build/build-deb.sh',
        'scripts/build/build-rpm.sh',
        'scripts/build/build-pkg.sh',
    ]

    def test_shell_syntax_all_scripts(self):
        """Все shell-скрипты проходят проверку bash -n."""
        errors = []
        for script in self.SHELL_SCRIPTS:
            result = subprocess.run(
                ['bash', '-n', script],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                errors.append(f'{script}: {result.stderr.strip()}')
        self.assertEqual(
            errors, [],
            'Ошибки синтаксиса:\n' + '\n'.join(errors),
        )


if __name__ == '__main__':
    unittest.main()
