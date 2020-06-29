# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2018, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

""" Test SLSQP Optimizer """

import logging
import unittest

from test.optimization.optimization_test_case import QiskitOptimizationTestCase

import numpy as np
from qiskit.optimization.algorithms import SlsqpOptimizer
from qiskit.optimization.problems import QuadraticProgram


logger = logging.getLogger(__name__)


class TestSlsqpOptimizer(QiskitOptimizationTestCase):
    """SLSQP Optimizer Tests. """

    def test_slsqp_optimizer(self):
        """ Generic SLSQP Optimizer Test. """

        problem = QuadraticProgram()
        problem.continuous_var(upperbound=4)
        problem.continuous_var(upperbound=4)
        problem.linear_constraint(linear=[1, 1], sense='=', rhs=2)
        problem.minimize(linear=[2, 2], quadratic=[[2, 0.25], [0.25, 0.5]])

        # solve problem with SLSQP
        slsqp = SlsqpOptimizer(shots=3)
        result = slsqp.solve(problem)

        self.assertAlmostEqual(result.fval, 5.8750)

    def test_slsqp_unbounded(self):
        """Unbounded test for optimization"""
        problem = QuadraticProgram()
        problem.continuous_var(name="x")
        problem.continuous_var(name="y")
        problem.maximize(linear=[2, 0], quadratic=[[-1, 2], [0, -2]])

        slsqp = SlsqpOptimizer()
        solution = slsqp.solve(problem)

        self.assertIsNotNone(solution)
        self.assertIsNotNone(solution.x)
        np.testing.assert_almost_equal([2., 1.], solution.x, 3)
        self.assertIsNotNone(solution.fval)
        np.testing.assert_almost_equal(2., solution.fval, 3)

    def test_slsqp_bounded(self):
        """Same as above, but a bounded test"""
        problem = QuadraticProgram()
        problem.continuous_var(name="x", lowerbound=2.5)
        problem.continuous_var(name="y", upperbound=0.5)
        problem.maximize(linear=[2, 0], quadratic=[[-1, 2], [0, -2]])

        slsqp = SlsqpOptimizer()
        solution = slsqp.solve(problem)

        self.assertIsNotNone(solution)
        self.assertIsNotNone(solution.x)
        np.testing.assert_almost_equal([2.5, 0.5], solution.x, 3)
        self.assertIsNotNone(solution.fval)
        np.testing.assert_almost_equal(0.75, solution.fval, 3)

    def test_slsqp_equality(self):
        """A test with equality constraint"""
        problem = QuadraticProgram()
        problem.continuous_var(name="x")
        problem.continuous_var(name="y")
        problem.linear_constraint(linear=[1, -1], sense='=', rhs=0)
        problem.maximize(linear=[2, 0], quadratic=[[-1, 2], [0, -2]])

        slsqp = SlsqpOptimizer()
        solution = slsqp.solve(problem)

        self.assertIsNotNone(solution)
        self.assertIsNotNone(solution.x)
        np.testing.assert_almost_equal([1., 1.], solution.x, 3)
        self.assertIsNotNone(solution.fval)
        np.testing.assert_almost_equal(1., solution.fval, 3)

    def test_slsqp_inequality(self):
        """A test with inequality constraint"""
        problem = QuadraticProgram()
        problem.continuous_var(name="x")
        problem.continuous_var(name="y")
        problem.linear_constraint(linear=[1, -1], sense='>=', rhs=1)
        problem.maximize(linear=[2, 0], quadratic=[[-1, 2], [0, -2]])

        slsqp = SlsqpOptimizer()
        solution = slsqp.solve(problem)

        self.assertIsNotNone(solution)
        self.assertIsNotNone(solution.x)
        np.testing.assert_almost_equal([2., 1.], solution.x, 3)
        self.assertIsNotNone(solution.fval)
        np.testing.assert_almost_equal(2., solution.fval, 3)

    def test_slsqp_optimizer_with_quadratic_constraint(self):
        """A test with equality constraint"""
        problem = QuadraticProgram()
        problem.continuous_var(upperbound=1)
        problem.continuous_var(upperbound=1)

        problem.minimize(linear=[1, 1])

        linear = [-1, -1]
        quadratic = [[1, 0], [0, 1]]
        problem.quadratic_constraint(linear=linear, quadratic=quadratic, rhs=-1/2)

        slsqp = SlsqpOptimizer()
        solution = slsqp.solve(problem)

        self.assertIsNotNone(solution)
        self.assertIsNotNone(solution.x)
        np.testing.assert_almost_equal([0.5, 0.5], solution.x, 3)
        self.assertIsNotNone(solution.fval)
        np.testing.assert_almost_equal(1., solution.fval, 3)


if __name__ == '__main__':
    unittest.main()
