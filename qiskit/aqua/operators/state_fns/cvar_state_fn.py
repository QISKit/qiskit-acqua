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

""" CVarStateFn Class """


from typing import Union, Set, Dict, Optional, Callable, Tuple
import numpy as np

from qiskit.aqua.aqua_error import AquaError
from qiskit.circuit import ParameterExpression, QuantumCircuit, Instruction
from qiskit.result import Result
from qiskit.quantum_info import Statevector

from ..operator_base import OperatorBase
from .state_fn import StateFn
from .operator_state_fn import OperatorStateFn


# pylint: disable=invalid-name

class CVarStateFn(OperatorStateFn):
    r"""
    A class for state functions and measurements which are defined by a density Operator,
    stored using an ``OperatorBase``.
    """

    @staticmethod
    # pylint: disable=unused-argument
    def __new__(cls,
                primitive: Union[str, dict, Result,
                                 list, np.ndarray, Statevector,
                                 QuantumCircuit, Instruction,
                                 OperatorBase] = None,
                coeff: Union[int, float, complex, ParameterExpression] = 1.0,
                alpha=1.0,
                is_measurement: bool = False) -> 'StateFn':
        return super().__new__(cls, primitive, coeff, is_measurement)

    # TODO allow normalization somehow?
    def __init__(self,
                 primitive: Union[OperatorBase] = None,
                 coeff: Union[int, float, complex, ParameterExpression] = 1.0,
                 alpha: float = 1,
                 is_measurement: bool = True) -> None:
        """
        Args:
            primitive: The ``OperatorBase`` which defines the behavior of the underlying State
                function.
            coeff: A coefficient by which to multiply the state function
            alpha: TODO
            is_measurement: Whether the StateFn is a measurement operator

        Raises:
            ValueError: TODO remove that this raises an error
        """
        if primitive is None:
            raise ValueError
        if not is_measurement:
            raise ValueError("CostFnMeasurement is only defined as a measurement")

        self._alpha = alpha

        super().__init__(primitive, coeff=coeff, is_measurement=True)

    @property
    def alpha(self) -> float:
        """TODO

        Returns:
            TODO
        """
        return self._alpha

    def primitive_strings(self) -> Set[str]:
        return self.primitive.primitive_strings()

    @property
    def num_qubits(self) -> int:
        if hasattr(self.primitive, 'num_qubits'):
            return self.primitive.num_qubits
        else:
            return None

    def add(self, other: OperatorBase) -> OperatorBase:
        raise NotImplementedError

    def adjoint(self) -> OperatorBase:
        """The adjoint of a CVaRMeasurement is not defined.

        Returns:
            Does not return anything, raises an error.

        Raises:
            AquaError: The adjoint of a CVaRMeasurement is not defined.
        """
        return AquaError("Adjoint of a cost function not defined")

    def mul(self, scalar: Union[int, float, complex, ParameterExpression]) -> OperatorBase:
        if not isinstance(scalar, (int, float, complex, ParameterExpression)):
            raise ValueError('Operators can only be scalar multiplied by float or complex, not '
                             '{} of type {}.'.format(scalar, type(scalar)))

        return self.__class__(self.primitive,
                              coeff=self.coeff * scalar,
                              is_measurement=self.is_measurement,
                              alpha=self._alpha)

    def tensor(self, other: OperatorBase) -> OperatorBase:
        if isinstance(other, OperatorStateFn):
            return StateFn(self.primitive.tensor(other.primitive),
                           coeff=self.coeff * other.coeff,
                           is_measurement=self.is_measurement)
        # pylint: disable=cyclic-import,import-outside-toplevel
        from .. import TensoredOp
        return TensoredOp([self, other])

    def to_density_matrix(self, massive: bool = False) -> np.ndarray:
        """ Return numpy matrix of density operator, warn if more than 16 qubits
        to force the user to set
        massive=True if they want such a large matrix. Generally big methods like
        this should require the use of a
        converter, but in this case a convenience method for quick hacking and
        access to classical tools is
        appropriate. """

        if self.num_qubits > 16 and not massive:
            raise ValueError(
                'to_matrix will return an exponentially large matrix,'
                ' in this case {0}x{0} elements.'
                ' Set massive=True if you want to proceed.'.format(2 ** self.num_qubits))

        return self.primitive.to_matrix() * self.coeff

    def to_matrix_op(self, massive: bool = False) -> OperatorBase:
        """ Return a MatrixOp for this operator. """
        return OperatorStateFn(self.primitive.to_matrix_op(massive=massive) * self.coeff,
                               is_measurement=self.is_measurement)

    def to_matrix(self, massive: bool = False) -> np.ndarray:
        r"""
        Not Implemented
        """
        raise NotImplementedError

    def to_circuit_op(self) -> OperatorBase:
        r""" Return ``StateFnCircuit`` corresponding to this StateFn. Ignore for now because this is
        undefined. TODO maybe call to_pauli_op and diagonalize here, but that could be very
        inefficient, e.g. splitting one Stabilizer measurement into hundreds of 1 qubit Paulis."""
        raise NotImplementedError

    def __str__(self) -> str:
        prim_str = str(self.primitive)
        if self.coeff == 1.0:
            return "{}({})".format('CVarMeasurement', prim_str)
        else:
            return "{}({}) * {}".format(
                'CVarMeasurement',
                prim_str,
                self.coeff)

    def eval(self,
             front: Union[str, dict, np.ndarray,
                          OperatorBase] = None) -> Union[OperatorBase, float, complex]:

        from .dict_state_fn import DictStateFn
        from .vector_state_fn import VectorStateFn
        from .circuit_state_fn import CircuitStateFn

        if isinstance(front, CircuitStateFn):
            front = front.eval()

        # Standardize the inputs to a dict
        if isinstance(front, DictStateFn):
            data = front.primitive
        elif isinstance(front, VectorStateFn):
            vec = front.primitive.data
            # Determine how many bits are needed
            key_len = int(np.ceil(np.log2(len(vec))))
            data = {format(index, '0'+str(key_len)+'b'): val for index, val in enumerate(vec)}
        else:
            raise ValueError("Unexpected Input to CVarStateFn: ", type(front))

        obs = self.primitive
        alpha = self._alpha

        assert isinstance(data, Dict)
        # TODO Handle probability gradients

        outcomes = list(data.items())
        # Sort based on energy evaluation
        for i, outcome in enumerate(outcomes):
            key = outcome[0]
            outcomes[i] += (obs.eval(key).adjoint().eval(key),)

        # Sort each observation based on it's energy
        outcomes = sorted(outcomes, key=lambda x: x[2])

        # Here P are the probabilities of observing each state.
        # H are the expectation values of each state with the
        # provided Hamiltonian
        _, P, H = zip(*outcomes)

        # Square the dict values
        # (since CircuitSampler takes the root...)
        P = [p*np.conj(p) for p in P]

        # Determine j, the index of the measurement outcome
        # which will be only partially included in the CVar sum
        j = 0
        running_total = 0
        for i, p_i in enumerate(P):
            # This is here for later on when
            # Gradients are supported
            if isinstance(p_i, Tuple):
                p = p_i[0]
            else:
                p = p_i

            running_total += p

            j = i
            if running_total > alpha:
                break

        h_j = H[j]
        cvar = alpha * h_j

        if alpha == 0:
            return h_j

        if j > 0:
            H = H[:j]
            P = P[:j]

            # CVar = alpha*Hj + \sum_i P[i]*(H[i] - Hj)
            for h_i, p_i in zip(H, P):
                if isinstance(p_i, Tuple):
                    cvar += p_i[0] * (h_i - h_j)
                else:
                    cvar += p_i * (h_i - h_j)

        return cvar/alpha

    def traverse(self,
                 convert_fn: Callable,
                 coeff: Optional[Union[int, float, complex, ParameterExpression]] = None
                 ) -> OperatorBase:
        r"""
        Apply the convert_fn to the internal primitive if the primitive is an Operator (as in
        the case of ``OperatorStateFn``). Otherwise do nothing. Used by converters.

        Args:
            convert_fn: The function to apply to the internal OperatorBase.
            coeff: A coefficient to multiply by after applying convert_fn.
                If it is None, self.coeff is used instead.

        Returns:
            The converted StateFn.
        """
        if coeff is None:
            coeff = self.coeff

        if isinstance(self.primitive, OperatorBase):
            return CVarStateFn(convert_fn(self.primitive),
                               coeff=coeff,
                               is_measurement=self.is_measurement,
                               alpha=self._alpha)
        return self

    def sample(self,
               shots: int = 1024,
               massive: bool = False,
               reverse_endianness: bool = False) -> dict:
        raise NotImplementedError
