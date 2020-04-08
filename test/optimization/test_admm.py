# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Tests of the ADMM algorithm."""

import unittest
from test.optimization import QiskitOptimizationTestCase

from docplex.mp.model import Model

import numpy as np
from qiskit.aqua.algorithms import NumPyMinimumEigensolver
from qiskit.optimization.algorithms import CplexOptimizer, MinimumEigenOptimizer
from qiskit.optimization.algorithms.admm_optimizer import ADMMOptimizer, ADMMParameters, \
    ADMMOptimizerResult, ADMMState
from qiskit.optimization.problems import QuadraticProgram


class TestADMMOptimizer(QiskitOptimizationTestCase):
    """ADMM Optimizer Tests"""

    def test_admm_maximization(self):
        """Tests a simple maximization problem using ADMM optimizer"""
        mdl = Model('test')
        c = mdl.continuous_var(lb=0, ub=10, name='c')
        x = mdl.binary_var(name='x')
        mdl.maximize(c + x * x)
        op = QuadraticProgram()
        op.from_docplex(mdl)
        self.assertIsNotNone(op)

        admm_params = ADMMParameters()

        qubo_optimizer = MinimumEigenOptimizer(NumPyMinimumEigensolver())
        continuous_optimizer = CplexOptimizer()

        solver = ADMMOptimizer(qubo_optimizer=qubo_optimizer,
                               continuous_optimizer=continuous_optimizer,
                               params=admm_params)
        solution: ADMMOptimizerResult = solver.solve(op)
        self.assertIsNotNone(solution)
        self.assertIsInstance(solution, ADMMOptimizerResult)

        self.assertIsNotNone(solution.x)
        np.testing.assert_almost_equal([10, 0], solution.x, 3)
        self.assertIsNotNone(solution.fval)
        np.testing.assert_almost_equal(10, solution.fval, 3)
        self.assertIsNotNone(solution.state)
        self.assertIsInstance(solution.state, ADMMState)

    def test_admm_ex6(self):
        """Example 6 as a unit test. Example 6 is reported in:
        Gambella, C., & Simonetto, A. (2020).
        Multi-block ADMM Heuristics for Mixed-Binary Optimization on Classical
        and Quantum Computers.
        arXiv preprint arXiv:2001.02069."""
        mdl = Model('ex6')

        # pylint:disable=invalid-name
        v = mdl.binary_var(name='v')
        w = mdl.binary_var(name='w')
        t = mdl.binary_var(name='t')
        u = mdl.continuous_var(name='u')

        mdl.minimize(v + w + t + 5 * (u - 2) ** 2)
        mdl.add_constraint(v + 2 * w + t + u <= 3, "cons1")
        mdl.add_constraint(v + w + t >= 1, "cons2")
        mdl.add_constraint(v + w == 1, "cons3")

        op = QuadraticProgram()
        op.from_docplex(mdl)

        qubo_optimizer = CplexOptimizer()
        continuous_optimizer = CplexOptimizer()

        admm_params = ADMMParameters(
            rho_initial=1001, beta=1000, factor_c=900,
            max_iter=100, three_block=True, tol=1.e-6
        )

        solver = ADMMOptimizer(params=admm_params, qubo_optimizer=qubo_optimizer,
                               continuous_optimizer=continuous_optimizer)
        solution = solver.solve(op)
        self.assertIsNotNone(solution)
        self.assertIsInstance(solution, ADMMOptimizerResult)

        self.assertIsNotNone(solution.x)
        np.testing.assert_almost_equal([1., 0., 0., 2.], solution.x, 3)
        self.assertIsNotNone(solution.fval)
        np.testing.assert_almost_equal(1., solution.fval, 3)
        self.assertIsNotNone(solution.state)
        self.assertIsInstance(solution.state, ADMMState)

    def test_admm_ex5(self):
        """Example 5 as a unit test. Example 5 is reported in:
        Gambella, C., & Simonetto, A. (2020).
        Multi-block ADMM Heuristics for Mixed-Binary Optimization on Classical
        and Quantum Computers.
        arXiv preprint arXiv:2001.02069."""
        mdl = Model('ex5')

        # pylint:disable=invalid-name
        v = mdl.binary_var(name='v')
        w = mdl.binary_var(name='w')
        t = mdl.binary_var(name='t')

        mdl.minimize(v + w + t)
        mdl.add_constraint(2 * v + 2 * w + t <= 3, "cons1")
        mdl.add_constraint(v + w + t >= 1, "cons2")
        mdl.add_constraint(v + w == 1, "cons3")

        op = QuadraticProgram()
        op.from_docplex(mdl)

        qubo_optimizer = CplexOptimizer()

        continuous_optimizer = CplexOptimizer()

        admm_params = ADMMParameters(
            rho_initial=1001, beta=1000, factor_c=900,
            max_iter=100, three_block=False
        )

        solver = ADMMOptimizer(params=admm_params, qubo_optimizer=qubo_optimizer,
                               continuous_optimizer=continuous_optimizer, )
        solution = solver.solve(op)

        self.assertIsNotNone(solution)
        self.assertIsInstance(solution, ADMMOptimizerResult)

        self.assertIsNotNone(solution.x)
        np.testing.assert_almost_equal([1., 0., 1.], solution.x, 3)
        self.assertIsNotNone(solution.fval)
        np.testing.assert_almost_equal(2., solution.fval, 3)
        self.assertIsNotNone(solution.state)
        self.assertIsInstance(solution.state, ADMMState)


if __name__ == '__main__':
    unittest.main()
