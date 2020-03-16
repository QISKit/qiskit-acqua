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

""" An Object to represent State Functions constructed from Operators """


import numpy as np

from qiskit.quantum_info import Statevector
from qiskit.aqua import AquaError

from ..operator_base import OperatorBase
from . import StateFn
from ..operator_combos import OpVec


class StateFnVector(StateFn):
    """ A class for representing state functions and measurements.

    State functions are defined to be complex functions over a single binary string
    (as compared to an operator,
    which is defined as a function over two binary strings, or a function taking a
    binary function to another
    binary function). This function may be called by the eval() method.

    Measurements are defined to be functionals over StateFns, taking them to real values.
    Generally, this real value
    is interpreted to represent the probability of some classical state (binary string)
    being observed from a
    probabilistic or quantum system represented by a StateFn. This leads to the equivalent
    definition, which is that
    a measurement m is a function over binary strings producing StateFns, such that the
    probability of measuring
    a given binary string b from a system with StateFn f is equal to the inner product
    between f and m(b).

    NOTE: State functions here are not restricted to wave functions,
    as there is no requirement of normalization.
    """

    # TODO maybe break up into different classes for different fn definition primitives
    # TODO allow normalization somehow?
    def __init__(self, primitive, coeff=1.0, is_measurement=False):
        """
        Args
            primitive(str, dict, OperatorBase, Result, np.ndarray, list)
            coeff(int, float, complex): A coefficient by which to multiply the state
        """
        # Lists and Numpy arrays representing statevectors are stored
        # in Statevector objects for easier handling.
        if isinstance(primitive, (np.ndarray, list)):
            primitive = Statevector(primitive)

        super().__init__(primitive, coeff=coeff, is_measurement=is_measurement)

    def get_primitives(self):
        """ Return a set of strings describing the primitives contained in the Operator """
        return {'Vector'}

    @property
    def num_qubits(self):
        return len(self.primitive.dims())

    def add(self, other):
        """ Addition. Overloaded by + in OperatorBase. """
        if not self.num_qubits == other.num_qubits:
            raise ValueError(
                'Sum over statefns with different numbers of qubits, {} and {}, is not well '
                'defined'.format(self.num_qubits, other.num_qubits))

        # Right now doesn't make sense to add a StateFn to a Measurement
        if isinstance(other, StateFnVector) and self.is_measurement == other.is_measurement:
            # Covers MatrixOperator, Statevector and custom.
            return StateFnVector((self.coeff * self.primitive).add(other.primitive * other.coeff),
                                 is_measurement=self._is_measurement)
        # pylint: disable=cyclic-import,import-outside-toplevel
        from .. import OpSum
        return OpSum([self, other])

    def adjoint(self):
        return StateFnVector(self.primitive.conjugate(),
                             coeff=np.conj(self.coeff),
                             is_measurement=(not self.is_measurement))

    def kron(self, other):
        """ Kron
        Note: You must be conscious of Qiskit's big-endian bit printing convention.
        Meaning, Plus.kron(Zero)
        produces a |+⟩ on qubit 0 and a |0⟩ on qubit 1, or |+⟩⨂|0⟩,
        but would produce a QuantumCircuit like
        |0⟩--
        |+⟩--
        Because Terra prints circuits and results with qubit 0 at the end of the string or circuit.
        """
        # TODO accept primitives directly in addition to OpPrimitive?

        if isinstance(other, StateFnVector):
            return StateFn(self.primitive.tensor(other.primitive),
                           coeff=self.coeff * other.coeff,
                           is_measurement=self.is_measurement)
        # pylint: disable=cyclic-import,import-outside-toplevel
        from .. import OpKron
        return OpKron([self, other])

    def to_density_matrix(self, massive=False):
        """ Return numpy matrix of density operator, warn if more than 16 qubits
        to force the user to set
        massive=True if they want such a large matrix. Generally big methods
        like this should require the use of a
        converter, but in this case a convenience method for quick hacking and
        access to classical tools is
        appropriate. """

        if self.num_qubits > 16 and not massive:
            # TODO figure out sparse matrices?
            raise ValueError(
                'to_matrix will return an exponentially large matrix,'
                ' in this case {0}x{0} elements.'
                ' Set massive=True if you want to proceed.'.format(2**self.num_qubits))

        return self.primitive.to_operator().data * self.coeff

    def to_matrix(self, massive=False):
        """
        NOTE: THIS DOES NOT RETURN A DENSITY MATRIX, IT RETURNS A CLASSICAL
        MATRIX CONTAINING THE QUANTUM OR CLASSICAL
        VECTOR REPRESENTING THE EVALUATION OF THE STATE FUNCTION ON EACH BINARY BASIS STATE.
        DO NOT ASSUME THIS IS
        IS A NORMALIZED QUANTUM OR CLASSICAL PROBABILITY VECTOR.
        If we allowed this to return a density matrix,
        then we would need to change the definition of composition to
        be ~Op @ StateFn @ Op for those cases,
        whereas by this methodology we can ensure that composition always means Op @ StateFn.

        Return numpy vector of state vector, warn if more than 16 qubits to force the user to set
        massive=True if they want such a large vector. Generally big methods
        like this should require the use of a
        converter, but in this case a convenience method for
        quick hacking and access to classical tools is
        appropriate.
        Returns:
            np.ndarray: vector of state vector
        Raises:
            ValueError: invalid parameters.
        """

        if self.num_qubits > 16 and not massive:
            # TODO figure out sparse matrices?
            raise ValueError(
                'to_vector will return an exponentially large vector, in this case {0} elements.'
                ' Set massive=True if you want to proceed.'.format(2**self.num_qubits))

        vec = self.primitive.data * self.coeff

        return vec if not self.is_measurement else vec.reshape(1, -1)

    def __str__(self):
        """Overload str() """
        prim_str = str(self.primitive)
        if self.coeff == 1.0:
            return "{}({})".format('StateFnVector' if not self.is_measurement
                                   else 'MeasurementVector', prim_str)
        else:
            return "{}({}) * {}".format('StateFnVector' if not self.is_measurement
                                        else 'MeasurementVector',
                                        prim_str,
                                        self.coeff)

    # pylint: disable=too-many-return-statements
    def eval(self, front=None, back=None):
        if back:
            raise AquaError('Eval with back is only defined for Operators, not StateFns.')

        if not self.is_measurement and isinstance(front, OperatorBase):
            raise ValueError(
                'Cannot compute overlap with StateFn or Operator if not Measurement. Try taking '
                'sf.adjoint() first to convert to measurement.')
        if isinstance(front, list):
            return [self.eval(front_elem) for front_elem in front]
        if isinstance(front, OpVec) and front.distributive:
            return front.combo_fn([self.eval(front.coeff * front_elem)
                                   for front_elem in front.oplist])
        if not isinstance(front, OperatorBase):
            front = StateFn(front)
        # pylint: disable=cyclic-import,import-outside-toplevel
        from . import StateFnDict, StateFnOperator
        if isinstance(front, StateFnDict):
            return sum([v * self.primitive.data[int(b, 2)] * front.coeff
                        for (b, v) in front.primitive.items()]) * self.coeff
        elif isinstance(front, StateFnVector):
            # Need to extract the element or np.array([1]) is returned.
            return np.dot(self.to_matrix(), front.to_matrix())[0]
        if isinstance(front, StateFnOperator):
            return front.adjoint().eval(self.primitive) * self.coeff
        if isinstance(front, OperatorBase):
            return front.adjoint().eval(self.adjoint().primitive).adjoint() * self.coeff

        # TODO figure out what to actually do here.
        return self.to_matrix()

    # TODO
    def sample(self, shots):
        """ Sample the state function as a normalized probability distribution."""
        raise NotImplementedError
