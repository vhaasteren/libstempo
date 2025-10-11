import unittest
import libstempo as t2
from libstempo.sandbox import tempopulsar, Policy, configure_logging
from libstempo.tim_file_analyzer import TimFileAnalyzer
import tempfile
import numpy as np
from numpy.testing import assert_allclose


class TestSandbox(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_path = t2.__path__[0] + "/data/"
        cls.parfile = cls.data_path + "J1909-3744_NANOGrav_dfg+12.par"
        cls.timfile = cls.data_path + "J1909-3744_NANOGrav_dfg+12.tim"

    def test_basic_sandbox_usage(self):
        """Test basic sandbox functionality"""
        psr = tempopulsar(parfile=self.parfile, timfile=self.timfile)
        self.assertEqual(psr.name, "1909-3744")
        self.assertEqual(psr.nobs, 1001)

    def test_policy_configuration(self):
        """Test Policy configuration"""
        policy = Policy(ctor_retry=2, call_timeout_s=30.0)
        psr = tempopulsar(parfile=self.parfile, timfile=self.timfile, policy=policy)
        self.assertEqual(psr.name, "1909-3744")

    def test_designmatrix_call(self):
        """Test calling designmatrix through sandbox"""
        psr = tempopulsar(parfile=self.parfile, timfile=self.timfile)
        dmat = psr.designmatrix()
        self.assertEqual(dmat.shape, (1001, 83))

    def test_attribute_access(self):
        """Test accessing attributes through sandbox"""
        psr = tempopulsar(parfile=self.parfile, timfile=self.timfile)
        self.assertEqual(psr.name, "1909-3744")
        self.assertEqual(psr.nobs, 1001)
        self.assertEqual(len(psr.stoas), 1001)

    def test_logging_configuration(self):
        """Test logging configuration"""
        # This should not raise an exception
        configure_logging(level="DEBUG", enable_console=False)
        configure_logging(level="INFO", enable_console=True)

    def test_logs_readout(self):
        """Test that logs() captures tempo2 output via savepar()."""
        psr = tempopulsar(parfile=self.parfile, timfile=self.timfile, dofit=False)
        # Baseline logs
        logs_before = psr.logs(2000)
        self.assertIsInstance(logs_before, str)
        # Invoke an operation that emits tempo2 text output
        tmp_par = tempfile.NamedTemporaryFile(delete=True)
        tmp_par.close()
        _ = psr.savepar(tmp_par.name)
        # Give background drain thread a moment to process
        import time as _t

        _t.sleep(0.1)
        logs_after = psr.logs(8000)
        self.assertIsInstance(logs_after, str)
        # Expect noticeable output; check growth and presence of a known token
        self.assertGreater(len(logs_after), len(logs_before))
        self.assertIn("Results for PSR", logs_after)

    def test_sandbox_native_parity(self):
        """Compare key attributes and outputs between sandbox and native tempopulsar."""
        psr_s = tempopulsar(parfile=self.parfile, timfile=self.timfile)
        psr_n = t2.tempopulsar(parfile=self.parfile, timfile=self.timfile)

        # Scalar/string attributes
        self.assertEqual(psr_s.name, psr_n.name)
        self.assertEqual(psr_s.nobs, psr_n.nobs)

        # Arrays: use a tight tolerance
        assert_allclose(psr_s.stoas, psr_n.stoas, rtol=0, atol=0)

        # Residuals
        res_s = psr_s.residuals()
        res_n = psr_n.residuals()
        self.assertEqual(res_s.shape, res_n.shape)
        assert_allclose(res_s, res_n, rtol=0, atol=0)

        # Design matrix
        dm_s = psr_s.designmatrix()
        dm_n = psr_n.designmatrix()
        self.assertEqual(dm_s.shape, dm_n.shape)
        assert_allclose(dm_s, dm_n, rtol=0, atol=0)

        # TOAs
        toas_s = psr_s.toas()
        toas_n = psr_n.toas()
        self.assertEqual(len(toas_s), len(toas_n))
        assert_allclose(np.asarray(toas_s), np.asarray(toas_n), rtol=0, atol=0)

        # Timing model parameters (subset): ensure values and metadata match
        s_all = set(psr_s.pars(which="all"))
        n_all = set(psr_n.pars(which="all"))
        s_fit = set(psr_s.pars())  # defaults to fitted
        n_fit = set(psr_n.pars())
        s_set = set(psr_s.pars(which="set"))
        n_set = set(psr_n.pars(which="set"))

        for par_name in ["RAJ", "DECJ"]:
            if par_name in s_all and par_name in n_all:
                # numeric values and errors via bulk accessors
                s_val = np.asarray(psr_s.vals(which=[par_name]))[0]
                n_val = np.asarray(psr_n.vals(which=[par_name]))[0]
                s_err = np.asarray(psr_s.errs(which=[par_name]))[0]
                n_err = np.asarray(psr_n.errs(which=[par_name]))[0]
                assert_allclose(s_val, n_val, rtol=0, atol=0)
                assert_allclose(s_err, n_err, rtol=0, atol=0)
                # fit/set flags via pars() groups
                self.assertEqual(par_name in s_fit, par_name in n_fit)
                self.assertEqual(par_name in s_set, par_name in n_set)


class TestTimFileAnalyzer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data_path = t2.__path__[0] + "/data/"
        cls.timfile = cls.data_path + "J1909-3744_NANOGrav_dfg+12.tim"

    def test_toa_count(self):
        """Test TOA counting functionality"""
        analyzer = TimFileAnalyzer()
        count = analyzer.count_toas(self.timfile)
        self.assertEqual(count, 1001)

    def test_timespan_calculation(self):
        """Test timespan calculation"""
        analyzer = TimFileAnalyzer()
        timespan = analyzer.calculate_timespan(self.timfile)
        self.assertGreater(timespan, 0)
        self.assertIsInstance(timespan, float)

    def test_combined_analysis(self):
        """Test getting both timespan and count"""
        analyzer = TimFileAnalyzer()
        timespan, count = analyzer.get_timespan_and_count(self.timfile)
        self.assertEqual(count, 1001)
        self.assertGreater(timespan, 0)
        self.assertIsInstance(timespan, float)

    def test_cache_functionality(self):
        """Test that caching works correctly"""
        analyzer = TimFileAnalyzer()

        # First call
        timespan1, count1 = analyzer.get_timespan_and_count(self.timfile)

        # Second call should use cache
        timespan2, count2 = analyzer.get_timespan_and_count(self.timfile)

        self.assertEqual(timespan1, timespan2)
        self.assertEqual(count1, count2)

        # Clear cache and test again
        analyzer.clear_cache()
        timespan3, count3 = analyzer.get_timespan_and_count(self.timfile)
        self.assertEqual(timespan1, timespan3)
        self.assertEqual(count1, count3)


if __name__ == "__main__":
    unittest.main()
