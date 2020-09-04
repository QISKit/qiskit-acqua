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

"""The Grover operator."""

from typing import List, Optional
import numpy
from qiskit.circuit import QuantumCircuit, QuantumRegister, AncillaRegister
from .bit_oracle import BitOracle


class GroverOperator(QuantumCircuit):
    """The Grover operator."""

    def __init__(self, oracle: QuantumCircuit,
                 state_in: Optional[QuantumCircuit] = None,
                 zero_reflection: Optional[QuantumCircuit] = None,
                 idle_qubits: Optional[List[int]] = None,
                 insert_barriers: bool = False,
                 mcx: str = 'noancilla',
                 name: str = 'Q') -> None:
        """
        Args:
            oracle: The oracle implementing a reflection about the bad state.
            state_in: The operator preparing the good and bad state. For Grover's algorithm,
                this is a n-qubit Hadamard gate and for Amplitude Amplification or Estimation
                the operator A.
            zero_reflection: The reflection about the zero state.
            idle_qubits: Qubits that are ignored in the reflection about zero.
            insert_barriers: Whether barriers should be inserted between the reflections and A.
            mcx: The mode to use for building the default zero reflection.
            name: The name of the circuit.
        """
        super().__init__(name=name)

        # store inputs
        self._oracle = oracle
        self._state_in = state_in
        self._zero_reflection = zero_reflection
        self._idle_qubits = idle_qubits
        self._insert_barriers = insert_barriers
        self._mcx = mcx

        # build circuit
        self._build()

    @property
    def num_state_qubits(self):
        """The number of state qubits."""
        if hasattr(self._oracle, 'num_state_qubits'):
            return self._oracle.num_state_qubits
        return self._oracle.num_qubits

    @property
    def idle_qubits(self):
        """Idle qubits, on which S0 is not applied."""
        if self._idle_qubits is None:
            return []
        return self._idle_qubits

    @property
    def zero_reflection(self) -> QuantumCircuit:
        """The subcircuit implementing the reflection about 0."""
        if self._zero_reflection is not None:
            return self._zero_reflection

        num_state_qubits = self.oracle.num_qubits - self.oracle.num_ancillas
        qubits = [i for i in range(num_state_qubits) if i not in self.idle_qubits]
        zero_reflection = BitOracle(num_state_qubits, qubits, mcx=self._mcx)
        return zero_reflection

    @property
    def state_in(self) -> QuantumCircuit:
        """The subcircuit implementing the A operator or Hadamards."""
        if self._state_in:
            return self._state_in

        num_state_qubits = self.oracle.num_qubits - self.oracle.num_ancillas
        qubits = [i for i in range(num_state_qubits) if i not in self.idle_qubits]
        hadamards = QuantumCircuit(num_state_qubits, name='H')
        hadamards.h(qubits)
        return hadamards

    @property
    def oracle(self):
        """The oracle implementing a reflection about the bad state."""
        return self._oracle

    def _build(self):
        num_state_qubits = self.oracle.num_qubits - self.oracle.num_ancillas
        self.qregs = [QuantumRegister(num_state_qubits, name='state')]
        num_ancillas = numpy.max([self.oracle.num_ancillas,
                                  self.zero_reflection.num_ancillas,
                                  self.state_in.num_ancillas])
        if num_ancillas > 0:
            self.qregs += [AncillaRegister(num_ancillas, name='ancilla')]

        self.compose(self.oracle, list(range(self.oracle.num_qubits)), inplace=True)
        if self._insert_barriers:
            self.barrier()
        self.compose(self.state_in.inverse(), list(range(self.state_in.num_qubits)), inplace=True)
        if self._insert_barriers:
            self.barrier()
        self.compose(self.zero_reflection, list(range(self.zero_reflection.num_qubits)),
                     inplace=True)
        if self._insert_barriers:
            self.barrier()
        self.compose(self.state_in, list(range(self.state_in.num_qubits)), inplace=True)


def _append(target, other, qubits=None, ancillas=None):
    if hasattr(other, 'num_state_qubits') and hasattr(other, 'num_ancilla_qubits'):
        num_state_qubits = other.num_state_qubits
        num_ancilla_qubits = other.num_ancilla_qubits
    else:
        num_state_qubits = other.num_qubits
        num_ancilla_qubits = 0

    if qubits is None:
        qubits = list(range(num_state_qubits))
    elif isinstance(qubits, QuantumRegister):
        qubits = qubits[:]

    if num_ancilla_qubits > 0:
        if ancillas is None:
            qubits += list(range(num_state_qubits, num_state_qubits + num_ancilla_qubits))
        else:
            qubits += ancillas[:num_ancilla_qubits]

    target.append(other.to_gate(), qubits)
