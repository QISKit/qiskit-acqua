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

""" Test QuadraticExpression """

import unittest
from test.optimization.optimization_test_case import QiskitOptimizationTestCase
import logging
import numpy as np
from scipy.sparse import dok_matrix

from qiskit.optimization import QuadraticProgram
from qiskit.optimization.problems import QuadraticExpression

logger = logging.getLogger(__name__)


class TestQuadraticExpression(QiskitOptimizationTestCase):
    """Test QuadraticExpression."""

    def test_init(self):
        """ test init. """

        quadratic_program = QuadraticProgram()
        for _ in range(5):
            quadratic_program.continuous_var()

        coefficients_list = [[i*j for i in range(5)] for j in range(5)]
        coefficients_array = np.array(coefficients_list)
        coefficients_dok = dok_matrix(coefficients_list)
        coefficients_dict_int = {(i, j): v for (i, j), v in coefficients_dok.items()}
        coefficients_dict_str = {('x{}'.format(i), 'x{}'.format(j)): v for (i, j), v in
                                 coefficients_dok.items()}

        for coeffs in [coefficients_list,
                       coefficients_array,
                       coefficients_dok,
                       coefficients_dict_int,
                       coefficients_dict_str]:

            quadratic = QuadraticExpression(quadratic_program, coeffs)
            self.assertEqual((quadratic.coefficients != coefficients_dok).nnz, 0)
            self.assertTrue((quadratic.coefficients_as_array() == coefficients_list).all())
            self.assertDictEqual(quadratic.coefficients_as_dict(
                use_index=True), coefficients_dict_int)
            self.assertDictEqual(quadratic.coefficients_as_dict(use_index=False),
                                 coefficients_dict_str)

    def test_get_item(self):
        """ test get_item. """

        quadratic_program = QuadraticProgram()
        for _ in range(5):
            quadratic_program.continuous_var()

        coefficients = [[i*j for i in range(5)] for j in range(5)]
        quadratic = QuadraticExpression(quadratic_program, coefficients)
        for i, jv in enumerate(coefficients):
            for j, v in enumerate(jv):
                self.assertEqual(quadratic[i, j], v)

    def test_setters(self):
        """ test setters. """

        quadratic_program = QuadraticProgram()
        for _ in range(5):
            quadratic_program.continuous_var()

        n = quadratic_program.get_num_vars()
        zeros = np.zeros((n, n))
        quadratic = QuadraticExpression(quadratic_program, zeros)

        coefficients_list = [[i*j for i in range(5)] for j in range(5)]
        coefficients_array = np.array(coefficients_list)
        coefficients_dok = dok_matrix(coefficients_list)
        coefficients_dict_int = {(i, j): v for (i, j), v in coefficients_dok.items()}
        coefficients_dict_str = {('x{}'.format(i), 'x{}'.format(j)): v for (i, j), v in
                                 coefficients_dok.items()}

        for coeffs in [coefficients_list,
                       coefficients_array,
                       coefficients_dok,
                       coefficients_dict_int,
                       coefficients_dict_str]:

            quadratic.coefficients = coeffs
            self.assertEqual((quadratic.coefficients != coefficients_dok).nnz, 0)
            self.assertTrue((quadratic.coefficients_as_array() == coefficients_list).all())
            self.assertDictEqual(quadratic.coefficients_as_dict(
                use_index=True), coefficients_dict_int)
            self.assertDictEqual(quadratic.coefficients_as_dict(use_index=False),
                                 coefficients_dict_str)

    def test_evaluate(self):
        """ test evaluate. """

        quadratic_program = QuadraticProgram()
        x = [quadratic_program.continuous_var() for _ in range(5)]

        coefficients_list = [[i*j for i in range(5)] for j in range(5)]
        quadratic = QuadraticExpression(quadratic_program, coefficients_list)

        values_list = [i for i in range(len(x))]
        values_array = np.array(values_list)
        values_dict_int = {i: i for i in range(len(x))}
        values_dict_str = {'x{}'.format(i): i for i in range(len(x))}

        for values in [values_list, values_array, values_dict_int, values_dict_str]:
            self.assertEqual(quadratic.evaluate(values), 900)


if __name__ == '__main__':
    unittest.main()
