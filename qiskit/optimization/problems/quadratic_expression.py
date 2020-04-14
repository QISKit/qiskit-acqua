# -*- coding: utf-8 -*-

# This code is part of Qiskit.
#
# (C) Copyright IBM 2019, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.

"""Quadratic expression interface."""


from typing import List, Union, Dict, Tuple
import numpy as np
from numpy import ndarray
from scipy.sparse import spmatrix, dok_matrix

from qiskit.optimization import QiskitOptimizationError
from qiskit.optimization.problems.has_quadratic_program import HasQuadraticProgram


class QuadraticExpression(HasQuadraticProgram):
    """ Representation of a quadratic expression by its coefficients."""

    def __init__(self, quadratic_program: "QuadraticProgram",
                 coefficients: Union[ndarray, spmatrix, List[List[float]],
                                     Dict[Tuple[Union[int, str], Union[int, str]], float]]) -> None:
        """Creates a new quadratic expression.

        The quadratic expression can be defined via an array, a list, a sparse matrix, or a
        dictionary that uses variable names or indices as keys and stores the values internally as a
        dok_matrix.

        Args:
            quadratic_program: The parent QuadraticProgram.
            coefficients: The (sparse) representation of the coefficients.

        """
        super().__init__(quadratic_program)
        self.coefficients = coefficients

    def _coeffs_to_dok_matrix(self,
                              coefficients: Union[ndarray, spmatrix, List[List[float]],
                                                  Dict[
                                                      Tuple[Union[int, str], Union[int, str]],
                                                      float]]) -> None:
        """Maps given coefficients to a dok_matrix.

        Args:
            coefficients: The coefficients to be mapped.

        Returns:
            The given coefficients as a dok_matrix

        Raises:
            QiskitOptimizationError: if coefficients are given in unsupported format.
        """
        if isinstance(coefficients, list)\
            or isinstance(coefficients, ndarray)\
                or isinstance(coefficients, spmatrix):
            coefficients = dok_matrix(coefficients)
        elif isinstance(coefficients, dict):
            n = self.quadratic_program.get_num_vars()
            coeffs = dok_matrix((n, n))
            for (i, j), value in coefficients.items():
                if isinstance(i, str):
                    i = self.quadratic_program.variables_index[i]
                if isinstance(j, str):
                    j = self.quadratic_program.variables_index[j]
                coeffs[i, j] = value
            coefficients = coeffs
        else:
            raise QiskitOptimizationError("Unsupported format for coefficients.")
        return coefficients

    @property
    def coefficients(self) -> dok_matrix:
        """ Returns the coefficients of the quadratic expression.

        Returns:
            The coefficients of the quadratic expression.
        """
        return self._coefficients

    @coefficients.setter
    def coefficients(self,
                     coefficients: Union[ndarray, spmatrix, List[List[float]],
                                         Dict[Tuple[Union[int, str], Union[int, str]], float]]
                     ) -> None:
        """Sets the coefficients of the quadratic expression.

        Args:
            coefficients: The coefficients of the quadratic expression.
        """
        self._coefficients = self._coeffs_to_dok_matrix(coefficients)

    def coefficients_as_array(self) -> ndarray:
        """Returns the coefficients of the quadratic expression as array.

        Returns:
            An array with the coefficients corresponding to the quadratic expression.
        """
        return self._coefficients.toarray()

    def coefficients_as_dict(self, use_index: bool = True
                             ) -> Dict[Union[Tuple[int, int], Tuple[str, str]], float]:
        """Returns the coefficients of the quadratic expression as dictionary, either using tuples
        of variable names or indices as keys.

        Args:
            use_index: Determines whether to use index or names to refer to variables.

        Returns:
            An dictionary with the coefficients corresponding to the quadratic expression.
        """
        if use_index:
            return {(i, j): v for (i, j), v in self._coefficients.items()}
        else:
            return {(self.quadratic_program.variables[i].name,
                     self.quadratic_program.variables[j].name): v
                    for (i, j), v in self._coefficients.items()}

    def evaluate(self, x: Union[ndarray, List, Dict[Union[int, str], float]]) -> float:
        """Evaluate the quadratic expression for given variables: x * Q * x.

        Args:
            x: The values of the variables to be evaluated.

        Returns:
            The value of the quadratic expression given the variable values.
        """
        # cast input to dok_matrix if it is a dictionary
        if isinstance(x, dict):
            x_aux = np.zeros(self.quadratic_program.get_num_vars())
            for i, v in x.items():
                if isinstance(i, str):
                    i = self.quadratic_program.variables_index[i]
                x_aux[i] = v
            x = x_aux
        if isinstance(x, List):
            x = np.array(x)

        # compute x * Q * x for the quadratic expression
        val = x @ self.coefficients @ x

        # return the result
        return val
