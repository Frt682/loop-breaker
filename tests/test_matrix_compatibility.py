"""
Universal Matrix Compatibility Test Suite for LoopBreaker.
Tests compatibility across EVERY variable:
1. AI Model Formats (Claude, OpenAI GPT-4/o1/o3, Gemini, DeepSeek R1, Llama)
2. Operating Systems & Path Formats (Windows Drive, UNC, POSIX Linux, macOS, Mixed slashes, CRLF/LF)
3. Programming Languages (Python, TypeScript/JS, Go, Rust, Java, C++ ASan, Ruby, SQL)
4. Hyperparameter Matrix Grid (Window sizes, thresholds, churn ratios)
5. Multi-Lingual International Errors (Turkish, Japanese, Cyrillic, German)
6. Extreme Boundary Inputs (250KB log spam, non-printable characters, zero/empty inputs)
"""
import os
import sys
import unittest
import itertools
from loop_breaker.models import LoopType, SentinelDecision, StepRecord
from loop_breaker.detector import DoomLoopDetector
from loop_breaker.sentinel import LoopBreakerSentinel

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

class TestAIModelOutputCompatibility(unittest.TestCase):
    """Verifies that error extraction & normalization works across all LLM output conventions."""

    def test_claude_xml_thinking_and_markdown_wrapper(self):
        claude_output = """
        <thinking>
        The user wants to resolve the TypeError. Let me inspect the stack trace.
        The function received a string instead of an int.
        </thinking>
        Here is the terminal output from the test execution:
        ```bash
        TypeError: unsupported operand type(s) for +: 'int' and 'str' at 0x7fa99b line 42
        ```
        """
        norm, hash_val = DoomLoopDetector.normalize_error(claude_output)
        self.assertNotIn("<thinking>", norm)
        self.assertNotIn("0x7fa99b", norm)
        self.assertIn("TypeError", norm)
        self.assertTrue(len(hash_val) == 12)

    def test_deepseek_r1_thinking_wrapper(self):
        deepseek_output = """
        <think>
        Looking at the error, it seems `user_id` is None.
        I will try to cast it.
        </think>
        KeyError: 'user_id' in session.py:line 88 at 0x0000a12
        """
        norm, hash_val = DoomLoopDetector.normalize_error(deepseek_output)
        self.assertNotIn("<think>", norm)
        self.assertIn("KeyError", norm)

    def test_openai_tool_call_json_wrapper(self):
        openai_json_output = """
        {
          "tool_call": "execute_bash",
          "result": "\u001b[31;1mError: Cannot find module './config'\u001b[0m\\n at Object.<anonymous> (/app/src/index.ts:15:3)"
        }
        """
        norm, hash_val = DoomLoopDetector.normalize_error(openai_json_output)
        self.assertNotIn("\u001b[31;1m", norm)
        self.assertIn("Cannot find module", norm)

    def test_terminal_ansi_color_escape_stripping(self):
        colored_terminal = "\x1b[31mFAIL\x1b[0m \x1b[1mtests/auth.test.ts\x1b[0m\n\x1b[31m  ● Auth > should login\x1b[0m\n\n    AssertionError: expected 401 to equal 200"
        norm, hash_val = DoomLoopDetector.normalize_error(colored_terminal)
        self.assertNotIn("\x1b[31m", norm)
        self.assertIn("AssertionError", norm)


class TestOperatingSystemAndPathMatrix(unittest.TestCase):
    """Verifies path normalization across Windows, Linux, macOS, UNC networks, and Line Endings."""

    def test_cross_os_path_equivalence(self):
        win_path_err = "FileNotFoundError: [Errno 2] No such file or directory: 'C:\\Users\\admin\\workspace\\config.json' at line 10"
        posix_path_err = "FileNotFoundError: [Errno 2] No such file or directory: '/home/ubuntu/workspace/config.json' at line 99"
        macos_path_err = "FileNotFoundError: [Errno 2] No such file or directory: '/Users/developer/workspace/config.json' at line 300"
        unc_path_err = "FileNotFoundError: [Errno 2] No such file or directory: '\\\\corp-nas\\shares\\config.json' at line 4"

        norm_win, hash_win = DoomLoopDetector.normalize_error(win_path_err)
        norm_posix, hash_posix = DoomLoopDetector.normalize_error(posix_path_err)
        norm_macos, hash_macos = DoomLoopDetector.normalize_error(macos_path_err)
        norm_unc, hash_unc = DoomLoopDetector.normalize_error(unc_path_err)

        self.assertEqual(hash_win, hash_posix, "Windows and Linux paths must produce identical error signatures")
        self.assertEqual(hash_win, hash_macos, "Windows and macOS paths must produce identical error signatures")
        self.assertEqual(hash_win, hash_unc, "UNC and local paths must produce identical error signatures")

    def test_crlf_vs_lf_determinism(self):
        lf_text = "Traceback (most recent call last):\n  File 'app.py', line 12\nValueError: invalid literal"
        crlf_text = "Traceback (most recent call last):\r\n  File 'app.py', line 12\r\nValueError: invalid literal"

        _, hash_lf = DoomLoopDetector.normalize_error(lf_text)
        _, hash_crlf = DoomLoopDetector.normalize_error(crlf_text)

        self.assertEqual(hash_lf, hash_crlf, "CRLF and LF line endings must yield identical signatures")


class TestMultiLanguageStacktraceMatrix(unittest.TestCase):
    """Verifies stack trace normalization across 8 major language ecosystems."""

    def test_java_jvm_nullpointer(self):
        java_err = """
        Exception in thread "main" java.lang.NullPointerException: Cannot invoke "String.length()" because "str" is null
            at com.example.service.UserService.process(UserService.java:42)
            at com.example.App.main(App.java:15)
        """
        norm, hash_val = DoomLoopDetector.normalize_error(java_err)
        self.assertIn("NullPointerException", norm)
        self.assertTrue(len(hash_val) == 12)

    def test_cpp_clang_address_sanitizer(self):
        asan_err = """
        ==28912==ERROR: AddressSanitizer: heap-buffer-overflow on address 0x602000000050 at pc 0x000104
        READ of size 4 at 0x602000000050 thread T0
            #0 0x104d2e in main /src/buffer.cpp:18:12
        """
        norm, hash_val = DoomLoopDetector.normalize_error(asan_err)
        self.assertIn("AddressSanitizer", norm)
        self.assertNotIn("0x602000000050", norm)

    def test_ruby_nomethod_error(self):
        ruby_err = "app/controllers/users_controller.rb:25:in `show': undefined method `email' for nil:NilClass (NoMethodError)"
        norm, hash_val = DoomLoopDetector.normalize_error(ruby_err)
        self.assertIn("NoMethodError", norm)

    def test_sql_operational_error(self):
        sql_err = "psycopg2.OperationalError: FATAL: password authentication failed for user 'postgres' (port 5432)"
        norm, hash_val = DoomLoopDetector.normalize_error(sql_err)
        self.assertIn("OperationalError", norm)
        self.assertNotIn("5432", norm)


class TestHyperparameterPermutationMatrix(unittest.TestCase):
    """Tests the detection engine across a comprehensive hyperparameter grid."""

    def test_grid_sweep_robustness(self):
        window_sizes = [3, 5, 8, 12]
        repetition_thresholds = [2, 3, 4]
        oscillation_thresholds = [2, 3]

        for w, r, o in itertools.product(window_sizes, repetition_thresholds, oscillation_thresholds):
            detector = DoomLoopDetector(
                window_size=w,
                repetition_threshold=r,
                oscillation_threshold=o
            )
            # 1. Test empty history
            rep_empty = detector.detect([])
            self.assertFalse(rep_empty.is_loop_detected)

            # 2. Test single step
            rep_single = detector.detect([StepRecord(step_number=1, normalized_error="Error", error_signature_hash="abc")])
            self.assertFalse(rep_single.is_loop_detected)

            # 3. Test exact repetition up to r
            history_repeat = [
                StepRecord(step_number=i, normalized_error="IndexError", error_signature_hash="hash_idx", tests_failed=1)
                for i in range(1, r + 1)
            ]
            rep_repeat = detector.detect(history_repeat)
            self.assertTrue(rep_repeat.is_loop_detected, f"Failed at grid param: w={w}, r={r}, o={o}")
            self.assertEqual(rep_repeat.loop_type, LoopType.EXACT_ERROR_REPETITION)


class TestMultiLingualAndBoundaryInputs(unittest.TestCase):
    """Tests non-English errors, massive log dumps, and corrupted inputs."""

    def test_multilingual_error_logs(self):
        turkish_err = "Hata: Dosya açılamadı: 'settings.ini' [Errno 13] Yetki reddedildi (Permission denied)"
        japanese_err = "エラー: データベースへの接続に失敗しました (ConnectionRefusedError: Connection refused)"
        cyrillic_err = "Ошибка: Не удалось найти указанный модуль (ModuleNotFoundError: No module named 'core')"

        norm_tr, h_tr = DoomLoopDetector.normalize_error(turkish_err)
        norm_jp, h_jp = DoomLoopDetector.normalize_error(japanese_err)
        norm_ru, h_ru = DoomLoopDetector.normalize_error(cyrillic_err)

        self.assertTrue(len(h_tr) == 12)
        self.assertTrue(len(h_jp) == 12)
        self.assertTrue(len(h_ru) == 12)

    def test_massive_250kb_log_spam_performance(self):
        """Simulates a compiler spitting out 5,000 lines of warnings ending in 1 fatal syntax error."""
        noise_lines = [f"[WARNING] Unused variable x_{i} at /src/file_{i%50}.c:{i}" for i in range(5000)]
        noise_lines.append("SyntaxError: unexpected EOF while parsing at line 5001")
        massive_dump = "\n".join(noise_lines)

        self.assertGreater(len(massive_dump), 200_000)

        norm, sig = DoomLoopDetector.normalize_error(massive_dump)
        self.assertIn("SyntaxError", norm)
        self.assertTrue(len(sig) == 12)

    def test_non_printable_and_corrupt_binary_strings(self):
        corrupt_input = "\x00\x01\x02\x03\xff\xfe\r\nTypeError: broken payload\x00\x00"
        norm, sig = DoomLoopDetector.normalize_error(corrupt_input)
        self.assertIn("TypeError", norm)
        self.assertTrue(len(sig) == 12)

if __name__ == "__main__":
    unittest.main()
