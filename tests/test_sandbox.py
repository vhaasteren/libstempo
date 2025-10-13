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

    def test_param_proxy_accessors(self):
        """Test psr['parname'].val/err/fit/set mapping accessors and roundtrips."""
        psr = tempopulsar(parfile=self.parfile, timfile=self.timfile)

        # Choose parameters that are present and safe to touch
        par_val = "RAJ"
        par_fit = "DM"  # commonly present and safe to toggle fit flag

        # Read val/err via mapping
        v0 = psr[par_val].val
        e0 = psr[par_val].err
        self.assertIsInstance(float(v0), float)
        self.assertIsInstance(float(e0), float)

        # Roundtrip val by setting the same value (as Python float)
        psr[par_val].val = float(v0)
        self.assertAlmostEqual(float(psr[par_val].val), float(v0), places=12)

        # Roundtrip err by setting the same value (as Python float)
        psr[par_val].err = float(e0)
        self.assertAlmostEqual(float(psr[par_val].err), float(e0), places=12)

        # Toggle fit flag and revert
        fit0 = bool(psr[par_fit].fit)
        psr[par_fit].fit = not fit0
        self.assertEqual(bool(psr[par_fit].fit), (not fit0))
        # revert
        psr[par_fit].fit = fit0
        self.assertEqual(bool(psr[par_fit].fit), fit0)

        # 'set' flag should be boolean and readable; do not change it here
        self.assertIsInstance(bool(psr[par_val].set), bool)

    def test_stoas_edit_and_fit_matches_native(self):
        """Edit stoas and toaerrs, run fit, and compare residuals to native."""
        rng = np.random.default_rng(12345)

        # Sandbox and native
        psr_s = tempopulsar(parfile=self.parfile, timfile=self.timfile)
        psr_n = t2.tempopulsar(parfile=self.parfile, timfile=self.timfile)

        # Create identical noise realization
        noise = 0.1e-6 * rng.standard_normal(psr_s.nobs) / 86400.0

        # Apply to stoas and toaerrs in both
        # Sandbox: use write-through proxies (backward compatible API)
        psr_s.stoas[:] = psr_s.stoas[:] + noise
        psr_s.toaerrs[:] = 0.1

        # Native
        psr_n.stoas[:] = psr_n.stoas + noise
        psr_n.toaerrs[:] = 0.1

        # Fit both
        _ = psr_s.fit()
        _ = psr_n.fit()

        # Compare residuals tightly
        res_s = psr_s.residuals()
        res_n = psr_n.residuals()
        self.assertEqual(res_s.shape, res_n.shape)
        assert_allclose(res_s, res_n, rtol=0, atol=0)

    def test_param_attribute_proxy_no_pickling_and_roundtrip(self):
        """Access psr.RAJ attribute (check pickling error) and roundtrip fields."""
        psr = tempopulsar(parfile=self.parfile, timfile=self.timfile, dofit=False)

        # This attribute access used to force pickling of a non-picklable param object.
        p = psr.RAJ

        # Read primitives
        v0 = float(p.val)
        e0 = float(p.err)
        f0 = bool(p.fit)

        # Sanity on types
        self.assertIsInstance(v0, float)
        self.assertIsInstance(e0, float)
        self.assertIsInstance(f0, bool)

        # Roundtrip same values (ensures proxy->worker set path works)
        p.val = v0
        self.assertAlmostEqual(float(psr.RAJ.val), v0, places=12)

        p.err = e0
        self.assertAlmostEqual(float(psr.RAJ.err), e0, places=12)

        # Toggle fit and revert
        p.fit = not f0
        self.assertEqual(bool(psr.RAJ.fit), (not f0))
        p.fit = f0
        self.assertEqual(bool(psr.RAJ.fit), f0)

        # Proxy should be printable
        _ = repr(p)
        _ = str(p)

    def test_param_attribute_vs_mapping_consistency(self):
        """Ensure attribute-style psr.RAJ and mapping psr['RAJ'] remain consistent."""
        psr = tempopulsar(parfile=self.parfile, timfile=self.timfile, dofit=False)

        # Values and errors agree between attribute and mapping APIs
        self.assertAlmostEqual(float(psr.RAJ.val), float(psr["RAJ"].val), places=12)
        self.assertAlmostEqual(float(psr.RAJ.err), float(psr["RAJ"].err), places=12)

        # Setting via attribute reflects in mapping
        new_val = float(psr.RAJ.val)
        psr.RAJ.val = new_val
        self.assertAlmostEqual(float(psr["RAJ"].val), new_val, places=12)

        # Setting via mapping reflects in attribute
        new_err = float(psr["RAJ"].err)
        psr["RAJ"].err = new_err
        self.assertAlmostEqual(float(psr.RAJ.err), new_err, places=12)


class TestStateManagement(unittest.TestCase):
    """Tests for state management and crash recovery."""

    @classmethod
    def setUpClass(cls):
        cls.data_path = t2.__path__[0] + "/data/"
        cls.parfile = cls.data_path + "J1909-3744_NANOGrav_dfg+12.par"
        cls.timfile = cls.data_path + "J1909-3744_NANOGrav_dfg+12.tim"

    def test_param_state_capture(self):
        """Test that parameter modifications are captured in state cache."""
        psr = tempopulsar(parfile=self.parfile, timfile=self.timfile)

        # Modify parameters
        original_raj = psr["RAJ"].val
        psr["RAJ"].val = original_raj + 0.001
        psr["DM"].fit = False

        # Check state cache
        self.assertIn("RAJ", psr._state.param_cache)
        self.assertIn("val", psr._state.param_cache["RAJ"])
        self.assertEqual(psr._state.param_cache["RAJ"]["val"], original_raj + 0.001)
        self.assertEqual(psr._state.param_cache["DM"]["fit"], False)

    def test_array_state_capture(self):
        """Test that array modifications are captured in state cache."""
        psr = tempopulsar(parfile=self.parfile, timfile=self.timfile)

        # Modify arrays
        original_stoas = psr.stoas.copy()
        psr.stoas[:] = original_stoas + 1e-6

        # Check state cache
        self.assertIn("stoas", psr._state.array_cache)
        expected_stoas = original_stoas + 1e-6
        np.testing.assert_allclose(psr._state.array_cache["stoas"], expected_stoas)

    def test_state_restoration_after_recycle(self):
        """Test that state is restored after worker recycle."""
        psr = tempopulsar(parfile=self.parfile, timfile=self.timfile)

        # Modify state
        psr["RAJ"].val = 5.020
        psr["DM"].fit = True
        original_stoas = psr.stoas.copy()
        psr.stoas[:] = original_stoas + 2e-6

        # Force recycle
        psr._recycle()

        # Verify restoration
        self.assertAlmostEqual(psr["RAJ"].val, 5.020, places=6)
        self.assertTrue(psr["DM"].fit)
        np.testing.assert_allclose(psr.stoas, original_stoas + 2e-6, rtol=1e-10)

    def test_crash_statistics_tracking(self):
        """Test crash statistics tracking."""
        psr = tempopulsar(parfile=self.parfile, timfile=self.timfile)

        # Initial stats
        stats = psr.get_crash_stats()
        self.assertEqual(stats["crash_count"], 0)
        self.assertIsNone(stats["last_crash_at"])

        # Record crash manually
        psr._record_crash()

        # Check stats
        stats = psr.get_crash_stats()
        self.assertEqual(stats["crash_count"], 1)
        self.assertIsNotNone(stats["last_crash_at"])

        # Record another crash
        psr._record_crash()
        stats = psr.get_crash_stats()
        self.assertEqual(stats["crash_count"], 2)

    def test_crash_stats_after_recycle(self):
        """Test crash statistics after recycle."""
        psr = tempopulsar(parfile=self.parfile, timfile=self.timfile)

        # Record crash and recycle
        psr._record_crash()
        psr._recycle()

        # Check stats
        stats = psr.get_crash_stats()
        self.assertEqual(stats["crash_count"], 1)
        self.assertIsNotNone(stats["last_crash_at"])
        self.assertGreater(stats["worker_age_s"], 0)

    def test_complete_crash_recovery_workflow(self):
        """Test complete workflow: modify -> crash -> recover -> verify."""
        psr = tempopulsar(parfile=self.parfile, timfile=self.timfile)

        # Step 1: Modify state
        original_raj = psr["RAJ"].val
        original_dm_fit = psr["DM"].fit
        original_stoas = psr.stoas.copy()

        psr["RAJ"].val = original_raj + 0.005
        psr["DM"].fit = not original_dm_fit
        psr.stoas[:] = original_stoas + 5e-6

        # Step 2: Simulate crash and recovery
        psr._record_crash()
        psr._recycle()

        # Step 3: Verify state restoration
        self.assertAlmostEqual(psr["RAJ"].val, original_raj + 0.005, places=6)
        self.assertEqual(psr["DM"].fit, not original_dm_fit)
        np.testing.assert_allclose(psr.stoas, original_stoas + 5e-6, rtol=1e-10)

        # Step 4: Verify crash stats
        stats = psr.get_crash_stats()
        self.assertEqual(stats["crash_count"], 1)
        self.assertIsNotNone(stats["last_crash_at"])

    def test_state_preservation_across_multiple_crashes(self):
        """Test state preservation across multiple crashes."""
        psr = tempopulsar(parfile=self.parfile, timfile=self.timfile)

        # Initial modifications
        psr["RAJ"].val = 5.025
        psr["DM"].fit = False

        # Multiple crashes and recoveries
        for i in range(3):
            psr._record_crash()
            psr._recycle()

            # Verify state preserved
            self.assertAlmostEqual(psr["RAJ"].val, 5.025, places=6)
            self.assertFalse(psr["DM"].fit)

        # Check final crash count
        stats = psr.get_crash_stats()
        self.assertEqual(stats["crash_count"], 3)

    def test_state_restoration_with_invalid_parameters(self):
        """Test state restoration when some parameters are invalid."""
        psr = tempopulsar(parfile=self.parfile, timfile=self.timfile)

        # Modify valid parameter
        psr["RAJ"].val = 5.030

        # Add invalid parameter to cache (simulate edge case)
        psr._state.param_cache["INVALID_PARAM"] = {"val": 999.0}

        # Recycle and verify valid parameter restored
        psr._recycle()
        self.assertAlmostEqual(psr["RAJ"].val, 5.030, places=6)

    def test_empty_state_cache_restoration(self):
        """Test restoration when state cache is empty."""
        psr = tempopulsar(parfile=self.parfile, timfile=self.timfile)

        # Ensure empty cache
        psr._state.param_cache.clear()
        psr._state.array_cache.clear()

        # Recycle should not fail
        psr._recycle()

        # Basic functionality should still work
        self.assertEqual(psr.name, "1909-3744")

    def test_state_capture_performance(self):
        """Test that state capture doesn't significantly impact performance."""
        import time

        psr = tempopulsar(parfile=self.parfile, timfile=self.timfile)

        # Time parameter modifications
        start = time.time()
        for i in range(100):
            psr["RAJ"].val = 5.0 + i * 0.001
        param_time = time.time() - start

        # Time array modifications
        start = time.time()
        for i in range(10):
            # Get the array, modify it, and set it back
            current_stoas = psr.stoas.copy()
            psr.stoas[:] = current_stoas + i * 1e-6
        array_time = time.time() - start

        # Should be reasonable (adjust thresholds as needed)
        self.assertLess(param_time, 5.0)  # 100 param changes in < 5 seconds
        self.assertLess(array_time, 10.0)  # 10 array changes in < 10 seconds


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
