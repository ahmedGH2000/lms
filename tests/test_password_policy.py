import unittest

from nightjar_learning.password_policy import password_error


class PasswordPolicyTests(unittest.TestCase):
    def test_eight_characters_and_both_required_classes_are_accepted(self):
        for value in ("qR7!v9m2", "Sun!rise", "Aمرحبا!س", "Abcdefg؟"):
            with self.subTest(value=value):
                self.assertIsNone(password_error(value, value))

    def test_missing_requirements_are_rejected(self):
        cases = (
            ("Ab!1234", "between 8 and 128"),
            ("abc!1234", "uppercase"),
            ("Abcd1234", "special character"),
            ("Abcdefg ", "special character"),
            ("Abcdefgع", "special character"),
            ("A!" + "x" * 127, "between 8 and 128"),
            (None, "between 8 and 128"),
        )
        for value, message in cases:
            with self.subTest(value=value):
                self.assertIn(message, password_error(value, value))

    def test_confirmation_and_upper_boundary(self):
        value = "A!" + "x" * 126
        self.assertIsNone(password_error(value, value))
        self.assertEqual(password_error("qR7!v9m2", "qR7!v9m3"), "The passwords do not match.")


if __name__ == "__main__":
    unittest.main()
