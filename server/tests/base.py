"""
Базовые классы и миксины для тестов FlowLink Proxy.

Предоставляет переиспользуемые setUp/tearDown для типичных паттернов.
"""

import os
import tempfile

from server.config import config as cfg
from server.config import repo as config_repo


class TempConfigMixin:
    """
    Миксин: создаёт временную директорию и перенаправляет config.json.

    Использование:
        class MyTest(TempConfigMixin, unittest.TestCase):
            def test_something(self):
                # self.tmpdir — временная папка
                # config_repo.CONFIG_FILE указывает на self.tmpdir/config.json
                ...
    """

    def setUp(self):
        """Создаёт временную директорию и перенаправляет CONFIG_FILE."""
        self.tmpdir = tempfile.mkdtemp()
        self.orig_config_file = config_repo.CONFIG_FILE
        config_repo.CONFIG_FILE = os.path.join(self.tmpdir, 'config.json')

    def tearDown(self):
        """Восстанавливает оригинальный CONFIG_FILE и удаляет временную папку."""
        config_repo.CONFIG_FILE = self.orig_config_file
        for f in os.listdir(self.tmpdir):
            os.remove(os.path.join(self.tmpdir, f))
        os.rmdir(self.tmpdir)


class TempConfigEnabledMixin(TempConfigMixin):
    """
    Миксин: TempConfigMixin + сохранение/восстановление is_enabled.
    """

    def setUp(self):
        """Сохраняет текущее значение is_enabled."""
        super().setUp()
        self.orig_enabled = cfg.is_enabled()

    def tearDown(self):
        """Восстанавливает is_enabled и удаляет временную папку."""
        cfg.set_enabled(self.orig_enabled)
        super().tearDown()
