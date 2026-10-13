"""Unit tests for preprocessing and cyclical feature engineering using standard library unittest."""

import unittest
import numpy as np
import pandas as pd

from src.data.preprocessing import add_cyclical_features


class TestCyclicalFeatures(unittest.TestCase):
    def test_cyclical_features_values(self):
        """Verify standard sine and cosine values at key hours of the day."""
        df = pd.DataFrame({
            "hour": [0, 6, 12, 18],
            "day_of_week": [0, 1, 2, 3],
        })
        result = add_cyclical_features(df)

        self.assertIn("hour_sin", result.columns)
        self.assertIn("hour_cos", result.columns)
        self.assertIn("dow_sin", result.columns)
        self.assertIn("dow_cos", result.columns)

        # Hour 0: sin(0) = 0, cos(0) = 1
        self.assertTrue(np.isclose(result.loc[0, "hour_sin"], 0.0, atol=1e-6))
        self.assertTrue(np.isclose(result.loc[0, "hour_cos"], 1.0, atol=1e-6))

        # Hour 6: sin(pi/2) = 1, cos(pi/2) = 0
        self.assertTrue(np.isclose(result.loc[1, "hour_sin"], 1.0, atol=1e-6))
        self.assertTrue(np.isclose(result.loc[1, "hour_cos"], 0.0, atol=1e-6))

        # Hour 12: sin(pi) = 0, cos(pi) = -1
        self.assertTrue(np.isclose(result.loc[2, "hour_sin"], 0.0, atol=1e-6))
        self.assertTrue(np.isclose(result.loc[2, "hour_cos"], -1.0, atol=1e-6))

        # Hour 18: sin(3pi/2) = -1, cos(3pi/2) = 0
        self.assertTrue(np.isclose(result.loc[3, "hour_sin"], -1.0, atol=1e-6))
        self.assertTrue(np.isclose(result.loc[3, "hour_cos"], 0.0, atol=1e-6))

    def test_cyclical_features_pythagorean_identity(self):
        """Verify that sin^2 + cos^2 == 1 for all hours and days of the week."""
        all_hours = list(range(24))
        all_dows = [h % 7 for h in all_hours]
        df = pd.DataFrame({"hour": all_hours, "day_of_week": all_dows})
        result = add_cyclical_features(df)

        hour_norm = result["hour_sin"] ** 2 + result["hour_cos"] ** 2
        self.assertTrue(np.allclose(hour_norm, 1.0, atol=1e-6))

        dow_norm = result["dow_sin"] ** 2 + result["dow_cos"] ** 2
        self.assertTrue(np.allclose(dow_norm, 1.0, atol=1e-6))

    def test_cyclical_features_smooth_periodicity(self):
        """Verify that hour 23 and hour 0 are close in Euclidean cyclical space."""
        df = pd.DataFrame({"hour": [0, 23], "day_of_week": [0, 0]})
        result = add_cyclical_features(df)

        p0 = np.array([result.loc[0, "hour_sin"], result.loc[0, "hour_cos"]])
        p23 = np.array([result.loc[1, "hour_sin"], result.loc[1, "hour_cos"]])
        p12 = np.array([np.sin(np.pi), np.cos(np.pi)])  # 12 hours away

        dist_adjacent = np.linalg.norm(p0 - p23)
        dist_opposite = np.linalg.norm(p0 - p12)

        self.assertLess(dist_adjacent, 0.3)
        self.assertGreater(dist_opposite, 1.9)


if __name__ == "__main__":
    unittest.main()
