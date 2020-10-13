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

"""Ground state computation using a minimum eigensolver."""

from typing import Union, List, Any, Optional, Dict

import numpy as np

from qiskit import QuantumCircuit
from qiskit.circuit import Instruction
from qiskit.quantum_info import Statevector
from qiskit.result import Result
from qiskit.aqua.algorithms import MinimumEigensolver
from qiskit.aqua.operators import OperatorBase, WeightedPauliOperator, StateFn, CircuitSampler
from qiskit.chemistry import FermionicOperator
from qiskit.chemistry.drivers import BaseDriver
from qiskit.chemistry.ground_state_calculation import GroundStateCalculation
from qiskit.chemistry.qubit_transformations import QubitOperatorTransformation
from qiskit.chemistry.results import EigenstateResult

from .mes_factories import MESFactory


class MinimumEigensolverGroundStateCalculation(GroundStateCalculation):
    """Ground state computation using a minimum eigensolver."""

    def __init__(self, transformation: QubitOperatorTransformation,
                 solver: Union[MinimumEigensolver, MESFactory]) -> None:
        """

        Args:
            transformation: Qubit Operator Transformation
            solver: Minimum Eigensolver or MESFactory object, e.g. the VQEUCCSDFactory.
        """
        super().__init__(transformation)
        self._solver = solver

    @property
    def solver(self) -> Union[MinimumEigensolver, MESFactory]:
        """Returns the minimum eigensolver or factory."""
        return self._solver

    @solver.setter
    def solver(self, solver: Union[MinimumEigensolver, MESFactory]) -> None:
        """Sets the minimum eigensolver or factory."""
        self._solver = solver

    def returns_groundstate(self) -> bool:
        """TODO
        whether the eigensolver returns the ground state or only ground state energy."""

        return False

    def compute_groundstate(self, driver: BaseDriver,
                            aux_operators: Optional[List[Any]] = None
                            ) -> EigenstateResult:
        """Compute Ground State properties.

        Args:
            driver: a chemistry driver object which defines the chemical problem that is to be
                    solved by this calculation.
            aux_operators: Additional auxiliary operators to evaluate at the ground state.
                Depending on whether a fermionic or bosonic system is solved, the type of the
                operators must be ``FermionicOperator`` or ``BosonicOperator``, respectively.

        Raises:
            NotImplementedError: If an operator in ``aux_operators`` is not of type
                ``FermionicOperator``.

        Returns:
            An eigenstate result. Depending on the transformation this can be an electronic
            structure or bosonic result.
        """
        if aux_operators is not None:
            if any(not isinstance(op, (WeightedPauliOperator, FermionicOperator))
                   for op in aux_operators):
                raise NotImplementedError('Currently only fermionic problems are supported.')

        # get the operator and auxiliary operators, and transform the provided auxiliary operators
        # note that ``aux_operators`` contains not only the transformed ``aux_operators`` passed
        # by the user but also additional ones from the transformation
        operator, aux_operators = self.transformation.transform(driver, aux_operators)

        if isinstance(self._solver, MESFactory):
            # this must be called after transformation.transform
            solver = self._solver.get_solver(self.transformation)
        else:
            solver = self._solver

        # if the eigensolver does not support auxiliary operators, reset them
        if not solver.supports_aux_operators():
            aux_operators = None

        raw_mes_result = solver.compute_minimum_eigenvalue(operator, aux_operators)

        eigenstate_result = EigenstateResult()
        eigenstate_result.raw_result = raw_mes_result
        eigenstate_result.eigenenergies = np.asarray([raw_mes_result.eigenvalue])
        eigenstate_result.eigenstates = [raw_mes_result.eigenstate]
        eigenstate_result.aux_operator_eigenvalues = raw_mes_result.aux_operator_eigenvalues
        result = self.transformation.interpret(eigenstate_result)
        return result

    def evaluate_operators(self,
                           state: Union[str, dict, Result,
                                        list, np.ndarray, Statevector,
                                        QuantumCircuit, Instruction,
                                        OperatorBase],
                           operators: Union[WeightedPauliOperator, OperatorBase, list, dict]
                           ) -> Union[float, List[float], Dict[str, float]]:
        """Evaluates additional operators at the given state.

        Args:
            state: any kind of input that can be used to specify a state. See also ``StateFn`` for
                   more details.
            operators: either a single, list or dictionary of ``WeightedPauliOperator``s or any kind
                       of operator implementing the ``OperatorBase``.

        Returns:
            The expectation value of the given operator(s). The return type will be identical to the
            format of the provided operators.
        """
        # try to get a QuantumInstance from the solver
        quantum_instance = getattr(self._solver, 'quantum_instance', None)

        if not isinstance(state, StateFn):
            state = StateFn(state)

        # handle all possible formats of operators
        # i.e. if a user gives us a dict of operators, we return the results equivalently, etc.
        if isinstance(operators, list):
            results = []
            for op in operators:
                results.append(self._eval_op(state, op, quantum_instance))
        elif isinstance(operators, dict):
            results = {}  # type: ignore
            for name, op in operators.items():
                results[name] = self._eval_op(state, op, quantum_instance)
        else:
            results = self._eval_op(state, operators, quantum_instance)

        return results

    def _eval_op(self, state, op, quantum_instance):
        if not isinstance(op, OperatorBase):
            op = op.to_opflow()

        # if the operator is empty we simply return 0
        if op == 0:
            # Note, that for some reason the individual results need to be wrapped in lists.
            # See also: VQE._eval_aux_ops()
            return [0.j]

        exp = ~StateFn(op) @ state  # <state|op|state>

        if quantum_instance is not None:
            try:
                sampler = CircuitSampler(quantum_instance)
                result = sampler.convert(exp).eval()
            except ValueError:
                # TODO make this cleaner. The reason for it being here is that some quantum
                # instances can lead to non-positive statevectors which the Qiskit circuit
                # Initializer is unable to handle.
                result = exp.eval()
        else:
            result = exp.eval()

        # Note, that for some reason the individual results need to be wrapped in lists.
        # See also: VQE._eval_aux_ops()
        return [result]
