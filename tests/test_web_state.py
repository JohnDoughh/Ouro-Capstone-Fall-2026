import shutil
import subprocess
import unittest
from pathlib import Path


class WebStateTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is required for the browser-state regression")
    def test_failed_next_load_does_not_reactivate_a_saved_assignment(self):
        script = Path(__file__).with_name("web_lab_state.test.cjs")
        result = subprocess.run(
            ["node", "--test", str(script)], capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
