"""Réglages globaux de la suite de tests."""
import pytest


@pytest.fixture(autouse=True)
def _no_tasker_autorun(settings):
    """La boucle d'orchestration ne tourne pas pendant les tests.

    Elle enverrait de vrais ordres à des agents au milieu des assertions, et
    rendrait les tests non déterministes. Les tests qui la visent appellent
    ``runner.run_once()`` explicitement.
    """
    settings.COCKPIT_TASKER_AUTORUN = False
    from apps.tasker import runner

    runner.reset_for_tests()
    yield
    runner.reset_for_tests()
