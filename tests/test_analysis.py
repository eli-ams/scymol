from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

import numpy as np

from scymol.analysis import (
    column_statistics,
    downsample_xy,
    parse_numeric_file,
)


class NumericAnalysisTests(unittest.TestCase):
    def test_parses_comment_headed_lammps_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "density.out"
            path.write_text(
                "# Time-averaged data\n# TimeStep Temp Density\n"
                "0 300 0.80\n100 302 0.82\n200 301 0.84\n",
                encoding="utf-8",
            )
            dataset = parse_numeric_file(path)
            self.assertEqual(dataset.columns, ("TimeStep", "Temp", "Density"))
            np.testing.assert_allclose(dataset.column("Density"), [0.80, 0.82, 0.84])

    def test_combines_repeated_lammps_thermo_blocks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "log.lammps"
            path.write_text(
                "LAMMPS (test)\nStep Temp Press\n0 300 1.0\n10 301 1.2\n"
                "Loop time of 1 on 1 procs\n"
                "Step Temp Press\n20 302 1.1\n30 303 1.3\n"
                "Loop time of 1 on 1 procs\n",
                encoding="utf-8",
            )
            dataset = parse_numeric_file(path)
            self.assertEqual(dataset.columns, ("Step", "Temp", "Press"))
            self.assertEqual(dataset.values.shape, (4, 3))
            np.testing.assert_allclose(dataset.column("Step"), [0, 10, 20, 30])

    def test_statistics_and_plot_downsampling_keep_full_statistics(self):
        values = np.arange(50_000, dtype=float)
        x, y = downsample_xy(values, values * 2, maximum_points=1000)
        stats = column_statistics(values)
        self.assertEqual(len(x), 1000)
        self.assertEqual(len(y), 1000)
        self.assertEqual(stats["count"], 50_000)
        self.assertAlmostEqual(stats["mean"], 24_999.5)

if __name__ == "__main__":
    unittest.main()
