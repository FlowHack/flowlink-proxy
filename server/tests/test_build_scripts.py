"""
Тесты build-скриптов CRX-сборки.

Проверяют наличие интеграции CRX во всех build-скриптах и workflow.
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
# build.sh — интеграция CRX
# ──────────────────────────────────────────────────────────────


class TestBuildShIntegration(unittest.TestCase):
    """Тесты интеграции CRX в build.sh."""

    def test_build_sh_has_crx_section(self):
        """build.sh содержит блок «Сборка CRX расширения»."""
        content = _read_file('scripts/build/build.sh')
        self.assertIn('Сборка CRX расширения', content)

    def test_build_sh_has_crx_data_variable(self):
        """build.sh объявляет переменную CRX_DATA."""
        content = _read_file('scripts/build/build.sh')
        self.assertIn('CRX_DATA=""', content)

    def test_build_sh_crx_conditional(self):
        """build.sh содержит условный --add-data через переменную CRX_DATA."""
        content = _read_file('scripts/build/build.sh')
        self.assertIn('CRX_DATA="--add-data releases/flowlink-proxy.crx', content)

    def test_build_sh_uses_crx_variable_in_pyinstaller(self):
        """build.sh использует $CRX_DATA в команде PyInstaller."""
        content = _read_file('scripts/build/build.sh')
        self.assertIn('$CRX_DATA', content)

    def test_build_sh_checks_key_file(self):
        """build.sh проверяет наличие crx-private-key.pem."""
        content = _read_file('scripts/build/build.sh')
        self.assertIn('crx-private-key.pem', content)

    def test_build_sh_calls_build_crx(self):
        """build.sh вызывает build-crx.sh."""
        content = _read_file('scripts/build/build.sh')
        self.assertIn('build-crx.sh', content)


# ──────────────────────────────────────────────────────────────
# build.ps1 — интеграция CRX
# ──────────────────────────────────────────────────────────────


class TestBuildPs1Integration(unittest.TestCase):
    """Тесты интеграции CRX в build.ps1."""

    def test_build_ps1_has_crx_section(self):
        """build.ps1 содержит блок «Сборка CRX расширения»."""
        content = _read_file('scripts/build/build.ps1')
        self.assertIn('Сборка CRX расширения', content)

    def test_build_ps1_has_crx_data_flag(self):
        """build.ps1 объявляет переменную $crxDataFlag."""
        content = _read_file('scripts/build/build.ps1')
        self.assertIn('$crxDataFlag', content)

    def test_build_ps1_crx_conditional(self):
        """build.ps1 содержит условный --add-data через $crxDataFlag."""
        content = _read_file('scripts/build/build.ps1')
        self.assertIn("'releases/flowlink-proxy.crx;.'", content)

    def test_build_ps1_uses_crx_flag_in_pyinstaller(self):
        """build.ps1 использует $crxDataFlag в команде PyInstaller."""
        content = _read_file('scripts/build/build.ps1')
        # В ps1 переменная используется как: $crxDataFlag `
        self.assertIn('$crxDataFlag', content)

    def test_build_ps1_checks_key(self):
        """build.ps1 проверяет наличие crx-private-key.pem."""
        content = _read_file('scripts/build/build.ps1')
        self.assertIn('crx-private-key.pem', content)


# ──────────────────────────────────────────────────────────────
# Пакетные скрипты — CRX включается в каждый формат
# ──────────────────────────────────────────────────────────────


class TestPackageScripts(unittest.TestCase):
    """Тесты включения CRX во все пакетные скрипты."""

    def test_create_release_has_crx(self):
        """create-release.sh копирует CRX в архив релиза."""
        content = _read_file('scripts/build/create-release.sh')
        self.assertIn('flowlink-proxy.crx', content)
        # Проверяем что CRX копируется через cp
        lines = [l for l in content.splitlines() if 'flowlink-proxy.crx' in l]
        has_cp = any('cp ' in l for l in lines)
        self.assertTrue(has_cp, 'create-release.sh не содержит cp для CRX')

    def test_deb_has_crx(self):
        """build-deb.sh устанавливает CRX в .deb пакет."""
        content = _read_file('scripts/build/build-deb.sh')
        self.assertIn('flowlink-proxy.crx', content)
        self.assertIn('install', content)

    def test_rpm_has_crx(self):
        """build-rpm.sh копирует CRX в RPM tarball."""
        content = _read_file('scripts/build/build-rpm.sh')
        self.assertIn('flowlink-proxy.crx', content)
        self.assertIn('install', content)

    def test_pkg_has_crx(self):
        """build-pkg.sh копирует CRX в .pkg структуру."""
        content = _read_file('scripts/build/build-pkg.sh')
        self.assertIn('flowlink-proxy.crx', content)
        self.assertIn('install', content)

    def test_iss_has_crx(self):
        """flowlink-installer.iss содержит Source для CRX."""
        content = _read_file('scripts/installer/flowlink-installer.iss')
        self.assertIn('flowlink-proxy.crx', content)
        self.assertIn('DestDir: "{app}"', content)

    def test_deb_crx_conditional(self):
        """build-deb.sh копирует CRX условно (if -f)."""
        content = _read_file('scripts/build/build-deb.sh')
        self.assertIn('if [ -f "$PROJECT_DIR/releases/flowlink-proxy.crx" ]', content)

    def test_rpm_crx_conditional(self):
        """build-rpm.sh копирует CRX условно (if -f)."""
        content = _read_file('scripts/build/build-rpm.sh')
        self.assertIn('if [ -f "$PROJECT_DIR/releases/flowlink-proxy.crx" ]', content)

    def test_pkg_crx_conditional(self):
        """build-pkg.sh копирует CRX условно (if -f)."""
        content = _read_file('scripts/build/build-pkg.sh')
        self.assertIn('if [ -f "$PROJECT_DIR/releases/flowlink-proxy.crx" ]', content)


# ──────────────────────────────────────────────────────────────
# GitHub Actions workflow
# ──────────────────────────────────────────────────────────────


class TestWorkflowYaml(unittest.TestCase):
    """Тесты GitHub Actions workflow для CRX."""

    def test_build_yml_has_crx_job(self):
        """build.yml содержит джобу build-crx."""
        content = _read_file('.github/workflows/build.yml')
        self.assertIn('build-crx:', content)

    def test_build_yml_crx_job_has_checkout(self):
        """Джоба build-crx содержит checkout."""
        content = _read_file('.github/workflows/build.yml')
        self.assertIn('actions/checkout@v4', content)

    def test_build_yml_crx_job_has_node(self):
        """Джоба build-crx настраивает Node.js."""
        content = _read_file('.github/workflows/build.yml')
        self.assertIn('setup-node@v4', content)

    def test_build_yml_crx_job_has_secret(self):
        """Джоба build-crx восстанавливает ключ из секрета."""
        content = _read_file('.github/workflows/build.yml')
        self.assertIn('CRX_PRIVATE_KEY', content)

    def test_build_yml_crx_job_builds_crx(self):
        """Джоба build-crx собирает CRX через crx3-utils."""
        content = _read_file('.github/workflows/build.yml')
        self.assertIn('crx3-utils', content)
        self.assertIn('crx3-new', content)

    def test_build_yml_crx_job_uploads_artifact(self):
        """Джоба build-crx загружает артефакт."""
        content = _read_file('.github/workflows/build.yml')
        self.assertIn('upload-artifact@v4', content)
        self.assertIn('crx-artifact', content)

    def test_release_yml_has_crx_extension(self):
        """release.yml включает *.crx в сборку артефактов."""
        content = _read_file('.github/workflows/release.yml')
        self.assertIn('*.crx', content)

    def test_release_yml_downloads_all_artifacts(self):
        """release.yml загружает все артефакты (включая CRX)."""
        content = _read_file('.github/workflows/release.yml')
        self.assertIn('download-artifact@v4', content)


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
            )
            if result.returncode != 0:
                errors.append(f'{script}: {result.stderr.strip()}')
        self.assertEqual(
            errors, [],
            'Ошибки синтаксиса:\n' + '\n'.join(errors),
        )


if __name__ == '__main__':
    unittest.main()
