import logging
from pathlib import Path
import pdb
import pytest
from pathlib import Path
import importlib
import tempfile
from importlib.metadata import version

from tts_tower.inputs.input_client import InputClient
from tts_tower.rule_results import RuleResults

log = logging.getLogger(__name__)

class TestResultCollector:
    """A simple pytest plugin to collect test results in memory."""
    def __init__(self):
        self.passed = []
        self.failed = []
        self.skipped = []
        self.errors = []

    def pytest_runtest_logreport(self, report):
        """This hook is called by pytest after each test phase (setup, call, teardown)."""
        # We usually care about the 'call' phase (when the actual test code runs)
        if report.when == "call":
            if report.passed:
                self.passed.append(report.nodeid)
            elif report.failed:
                # You can also grab the error message/traceback here via report.longrepr
                self.failed.append({
                    "test": report.nodeid,
                    "error": str(report.longrepr)
                })
            elif report.skipped:
                self.skipped.append(report.nodeid)
                
        # We also need to check the 'setup' phase. If a test fails in setup 
        # (e.g., a broken fixture), the 'call' phase never happens.
        elif report.when == "setup" and report.failed:
            self.errors.append({
                "test": report.nodeid,
                "error": str(report.longrepr)
            })

class UnitTestRegistryClient(InputClient):
    def _impl_init(self, pip_install_name):
        self.pip_install_name = pip_install_name
        self.module_name = pip_install_name.replace('-', '_')
        self.collector = TestResultCollector()
        self.html_report = None

    def _impl_populate(self):
        spec = importlib.util.find_spec(self.module_name)
        installed_dir = Path(spec.submodule_search_locations[0])
        test_dir = installed_dir / "test"

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            report_path = tmp_path / "temp_report.html"

            args = [
                str(test_dir), 
                "-q",
                f"--html={report_path}",
                "--self-contained-html"
                ]
            self.exit_code = pytest.main(args, plugins=[self.collector])

            with open(report_path, "rb") as f:
                self.html_report = f.read()

    def _get_run_info(self):
        return {
            'Library Tested': self.pip_install_name,
            'Version Tested': version(self.module_name)
        }        