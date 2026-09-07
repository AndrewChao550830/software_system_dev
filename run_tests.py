import sys
import os
import unittest

# Add current directory to path
sys.path.insert(0, os.getcwd())

# Import and run tests
import test_product_review_dashboard

if __name__ == '__main__':
    # Create a test suite
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(test_product_review_dashboard)

    # Run the tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Exit with error code if tests failed
    sys.exit(0 if result.wasSuccessful() else 1)