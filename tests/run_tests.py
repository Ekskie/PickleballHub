#!/usr/bin/env python3
"""
PickleballHub Master Test Suite Runner.
Discovers and executes all tests across the tests/ package, reporting detailed
timings, pass/fail status, and an executive QA quality score.
"""

import os
import sys
import time
import unittest

def run_all_tests():
    start_time = time.time()
    print("=" * 70)
    print("       PICKLEBALLHUB ENTERPRISE QA & TEST SUITE RUNNER")
    print("=" * 70)

    test_loader = unittest.TestLoader()
    test_dir = os.path.dirname(os.path.abspath(__file__))
    suite = test_loader.discover(test_dir, pattern="test_*.py")

    stream = unittest.runner._WritelnDecorator(sys.stdout)
    runner = unittest.TextTestRunner(verbosity=2, stream=stream)
    result = runner.run(suite)

    elapsed = time.time() - start_time
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    skipped = len(result.skipped)
    passed = total_tests - failures - errors - skipped
    pass_rate = (passed / total_tests * 100.0) if total_tests > 0 else 0.0

    print("\n" + "=" * 70)
    print("                       QA AUDIT & TEST RESULTS")
    print("=" * 70)
    print(f" Total Tests Executed : {total_tests}")
    print(f" Passed               : {passed} [OK]")
    print(f" Failures             : {failures}")
    print(f" Errors               : {errors}")
    print(f" Skipped              : {skipped}")
    print(f" Pass Rate            : {pass_rate:.1f}%")
    print(f" Execution Duration   : {elapsed:.2f} seconds")
    print("=" * 70)

    if failures == 0 and errors == 0:
        print(" [SUCCESS] ALL CRITICAL PATHS, SECURITY GUARDS & RULES VALIDATED!")
        return 0
    else:
        print(" [FAILURE] TEST FAILURES DETECTED. PLEASE REVIEW LOGS ABOVE.")
        return 1

if __name__ == '__main__':
    sys.exit(run_all_tests())
