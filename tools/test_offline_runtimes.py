"""Pinned offline dependency provenance and package shape checks."""

import unittest

from fetch_offline_runtimes import (
    DESTINATION, RUNTIMES, LIBRARIES, library_payload, validate, deb_data,
)


class OfflineRuntimeTests(unittest.TestCase):
    def test_pinned_squashfs_payloads(self):
        for name, (_, blob, size) in RUNTIMES.items():
            with self.subTest(name=name):
                path = DESTINATION / name
                if not path.exists():
                    self.skipTest("Run fetch_offline_runtimes.py first")
                validate(path.read_bytes(), blob, size)

    def test_bad_squashfs_is_rejected(self):
        with self.assertRaises(ValueError):
            validate(b"wrong file", "0" * 40, 10)

    def test_arm64_libraries_retain_their_notices(self):
        for name in LIBRARIES:
            with self.subTest(name=name):
                binary, notice = library_payload(name)
                self.assertEqual(binary[:4], b"\x7fELF")
                self.assertEqual(binary[18:20], b"\xb7\0")
                self.assertIn(b"Copyright", notice)

    def test_debian_parser_rejects_non_archive(self):
        with self.assertRaises(ValueError):
            deb_data(b"not a Debian package")


if __name__ == "__main__":
    unittest.main()
