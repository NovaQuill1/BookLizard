import unittest

import config


class DefaultResolutionTests(unittest.TestCase):
    def test_default_window_matches_first_preset(self):
        self.assertEqual(config.WIDTH, config.SCREEN_PRESETS[0]["width"])
        self.assertEqual(config.HEIGHT, config.SCREEN_PRESETS[0]["height"])
        self.assertEqual(config.SCREEN_PRESETS[0]["name"], "1280 x 720")


if __name__ == "__main__":
    unittest.main()
