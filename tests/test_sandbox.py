import unittest
import libstempo as t2
from libstempo.sandbox import tempopulsar, Policy, configure_logging
from libstempo.tim_file_analyzer import TimFileAnalyzer


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
        psr = tempopulsar(
            parfile=self.parfile, timfile=self.timfile, policy=policy
        )
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
