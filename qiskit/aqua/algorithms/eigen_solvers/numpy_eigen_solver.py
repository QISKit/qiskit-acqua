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

"""The Eigensolver algorithm."""

from typing import List, Optional
import logging
import pprint
import warnings
import numpy as np
from scipy import sparse as scisparse

from qiskit.aqua import AquaError
from qiskit.aqua.algorithms import ClassicalAlgorithm
from qiskit.aqua.operators import LegacyBaseOperator, I, StateFn
from qiskit.aqua.utils.validation import validate_min
from .eigen_solver_result import EigensolverResult

logger = logging.getLogger(__name__)


# pylint: disable=invalid-name


class NumPyEigensolver(ClassicalAlgorithm):
    r"""
    The NumPy Eigensolver algorithm.

    NumPy Eigensolver computes up to the first :math:`k` eigenvalues of a complex-valued square
    matrix of dimension :math:`n \times n`, with :math:`k \leq n`.

    Note:
        Operators are automatically converted to :class:`~qiskit.aqua.operators.MatrixOperator`
        as needed and this conversion can be costly in terms of memory and performance as the
        operator size, mostly in terms of number of qubits it represents, gets larger.
    """

    def __init__(self, operator: Optional[LegacyBaseOperator] = None, k: int = 1,
                 aux_operators: Optional[List[LegacyBaseOperator]] = None) -> None:
        """
        Args:
            operator: Operator instance. If None is supplied it must be provided later before
                run() is called. Allowing None here permits the algorithm to be configured
                and used later when operator is available, say creating an instance an letting
                application stack use this algorithm with an operator it creates.
            k: How many eigenvalues are to be computed, has a min. value of 1.
            aux_operators: Auxiliary operators to be evaluated at each eigenvalue
        """
        validate_min('k', k, 1)
        super().__init__()

        self._operator = None
        self._aux_operators = None
        self._in_k = k
        self._k = k

        self.operator = operator
        self.aux_operators = aux_operators

        self._ret = {}

    @property
    def operator(self) -> LegacyBaseOperator:
        """ returns operator """
        return self._operator

    @operator.setter
    def operator(self, operator: LegacyBaseOperator) -> None:
        """ set operator """
        if isinstance(operator, LegacyBaseOperator):
            operator = operator.to_opflow()
        if operator is None:
            self._operator = None
        else:
            self._operator = operator
            self._check_set_k()

    @property
    def aux_operators(self) -> List[LegacyBaseOperator]:
        """ returns aux operators """
        return self._aux_operators

    @aux_operators.setter
    def aux_operators(self, aux_operators: List[LegacyBaseOperator]) -> None:
        """ set aux operators """
        if aux_operators is None:
            self._aux_operators = []
        else:
            aux_operators = \
                [aux_operators] if not isinstance(aux_operators, list) else aux_operators
            converted = [op.to_opflow() for op in aux_operators]
            # For some reason Chemistry passes aux_ops with 0 qubits and paulis sometimes. TODO fix
            zero_op = I.kronpower(self.operator.num_qubits) * 0.0
            converted = [zero_op if op == 0 else op for op in converted]
            self._aux_operators = converted

    @property
    def k(self) -> int:
        """ returns k (number of eigenvalues requested) """
        return self._in_k

    @k.setter
    def k(self, k: int) -> int:
        """ set k (number of eigenvalues requested) """
        validate_min('k', k, 1)
        self._in_k = k
        self._check_set_k()

    def supports_aux_operators(self) -> bool:
        """ If will process auxiliary operators or not """
        return True

    def _check_set_k(self):
        if self._operator is not None:
            if self._in_k > 2**(self._operator.num_qubits):
                self._k = 2**(self._operator.num_qubits)
                logger.debug("WARNING: Asked for %s eigenvalues but max possible is %s.",
                             self._in_k, self._k)
            else:
                self._k = self._in_k

    def _solve(self):
        if self._k >= 2**(self._operator.num_qubits) - 1:
            logger.debug("SciPy doesn't support to get all eigenvalues, using NumPy instead.")
            eigval, eigvec = np.linalg.eig(self._operator.to_matrix())
        else:
            eigval, eigvec = scisparse.linalg.eigs(self._operator.to_matrix(),
                                                   k=self._k, which='SR')
        if self._k > 1:
            idx = eigval.argsort()
            eigval = eigval[idx]
            eigvec = eigvec[:, idx]
        self._ret['eigvals'] = eigval
        self._ret['eigvecs'] = eigvec.T

    def _get_ground_state_energy(self):
        if 'eigvals' not in self._ret or 'eigvecs' not in self._ret:
            self._solve()
        self._ret['energy'] = self._ret['eigvals'][0].real
        self._ret['wavefunction'] = self._ret['eigvecs']

    def _get_energies(self):
        if 'eigvals' not in self._ret or 'eigvecs' not in self._ret:
            self._solve()
        energies = np.empty(self._k)
        for i in range(self._k):
            energies[i] = self._ret['eigvals'][i].real
        self._ret['energies'] = energies
        if self._aux_operators:
            aux_op_vals = np.empty([self._k, len(self._aux_operators), 2])
            for i in range(self._k):
                aux_op_vals[i, :] = self._eval_aux_operators(self._ret['eigvecs'][i])
            self._ret['aux_ops'] = aux_op_vals

    def _eval_aux_operators(self, wavefn, threshold=1e-12):
        values = []
        for operator in self._aux_operators:
            value = 0.0
            if not operator.coeff == 0:
                value = StateFn(operator, is_measurement=True).to_matrix_op().eval(wavefn)
                value = value.real if abs(value.real) > threshold else 0.0
            values.append((value, 0))
        return np.asarray(values)

    def _run(self):
        """
        Run the algorithm to compute up to the requested k number of eigenvalues.
        Returns:
            dict: Dictionary of results
        Raises:
             AquaError: if no operator has been provided
        """
        if self._operator is None:
            raise AquaError("Operator was never provided")

        self._ret = {}
        self._solve()
        self._get_ground_state_energy()
        self._get_energies()

        logger.debug('NumPyEigensolver _run result:\n%s',
                     pprint.pformat(self._ret, indent=4))
        result = EigensolverResult()
        if 'eigvals' in self._ret:
            result.eigenvalues = self._ret['eigvals']
        if 'eigvecs' in self._ret:
            result.eigenstates = self._ret['eigvecs']
        if 'aux_ops' in self._ret:
            result.aux_operator_eigenvalues = self._ret['aux_ops']

        logger.debug('EigensolverResult dict:\n%s',
                     pprint.pformat(result.data, indent=4))
        return result


class ExactEigensolver(NumPyEigensolver):
    """
    The deprecated Eigensolver algorithm.
    """

    def __init__(self, operator: LegacyBaseOperator, k: int = 1,
                 aux_operators: Optional[List[LegacyBaseOperator]] = None) -> None:
        warnings.warn('Deprecated class {}, use {}.'.format('ExactEigensolver',
                                                            'NumPyEigensolver'),
                      DeprecationWarning)
        super().__init__(operator, k, aux_operators)
