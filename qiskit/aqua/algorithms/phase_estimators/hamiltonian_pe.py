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

"""Phase estimation for the spectrum of a Hamiltonian"""

from typing import Optional, Union
from qiskit import QuantumCircuit
from qiskit.aqua import QuantumInstance
from qiskit.aqua.operators import EvolutionBase, OperatorBase
from qiskit.providers import BaseBackend, Backend
from .phase_estimator import PhaseEstimator
from . import phase_estimation_scale
from .hamiltonian_pe_result import HamiltonianPEResult
from .phase_estimation_scale import PhaseEstimationScale


class HamiltonianPE(PhaseEstimator):
    r"""Run the Quantum Phase Estimation algorithm to find the eigenvalues of a Hermitian operator.

    This class is nearly the same as :class:`~qiskit.aqua.algorithms.PhaseEstimator`, differing only
    in that the input in that class is a unitary operator, whereas here the input is a Hermitian
    operator from which a unitary will be obtained by scaling and exponentiating. The scaling is
    performed in order to prevent the phases from wrapping around :math:`2\pi`. This class uses and
    works together with :class:`~qiskit.aqua.algorithms.PhaseEstimationScale` to manage scaling the
    Hamiltonian and the phases that are obtained by the QPE algorithm. This includes setting, or
    computing, a bound on the eigenvalues of the operator, using this bound to obtain a scale
    factor, scaling the operator, and shifting and scaling the measured phases to recover the
    eigenvalues.

    Note that, although we speak of "evolving" the state according the the Hamiltonian, in the
    present algorithm, we are not actually considering time evolution. Rather, the role of time is
    played by the scaling factor, which is chosen to best extract the eigenvalues of the
    Hamiltonian.

    A few of the ideas in the algorithm may be found in Ref. [1].

    **Reference:**

    [1]: Quantum phase estimation of multiple eigenvalues for small-scale (noisy) experiments
         T.E. O'Brien, B. Tarasinski, B.M. Terhal
         https://arxiv.org/abs/1809.09697
    """
    def __init__(self,
                 num_evaluation_qubits: int,
                 hamiltonian: OperatorBase,
                 evolution: EvolutionBase,
                 state_preparation: Optional[QuantumCircuit] = None,
                 bound: Optional[float] = None,
                 quantum_instance: Optional[Union[QuantumInstance, BaseBackend, Backend]] = None) -> None:
        """
        Args:
            num_evaluation_qubits: The number of qubits used in estimating the phase. The
                                   phase will be estimated as a binary string with this many
                                   bits.
            hamiltonian: a Hamiltonian or Hermitian operator
            evolution: An evolution object that generates a unitary from `hamiltonian`.
            state_preparation: The circuit that prepares the state whose eigenphase will be
                                 measured.  If this parameter is omitted, no preparation circuit
                                 will be run and input state will be the all-zero state in the
                                 computational basis.
            bound: An upper bound on the absolute value of the eigenvalues of
                `hamiltonian`. If omitted, then `hamiltonian` must be a Pauli sum, in which case
                then a bound will be computed.
            quantum_instance: The quantum instance on which the circuit will be run.

        Raises:
            ValueError: if `bound` is `None` and `hamiltonian` is not a Pauli sum (i.e. a
            `SummedOp` whose terms are `PauliOp`s.)
        """

        self._hamiltonian = hamiltonian
        self._evolution = evolution
        self._bound = bound

        self._set_scale()
        unitary = self._get_unitary()

        super().__init__(num_evaluation_qubits,
                         unitary=unitary,
                         pe_circuit=None,
                         num_unitary_qubits=None,
                         state_preparation=state_preparation,
                         quantum_instance=quantum_instance)

    def _set_scale(self) -> None:
        if self._bound is None:
            pe_scale = phase_estimation_scale.from_pauli_sum(self._hamiltonian)
            self._pe_scale = pe_scale
        else:
            self._pe_scale = PhaseEstimationScale(self._bound)

    def _get_unitary(self) -> QuantumCircuit:
        """Evolve the Hamiltonian to obtain a unitary.

        Apply the scaling to the Hamiltonian that has been computed from an eigenvalue bound
        and compute the unitary by applying the evolution object.
        """
        # scale so that phase does not wrap.
        scaled_hamiltonian = self._pe_scale.scale * self._hamiltonian
        unitary = self._evolution.convert(scaled_hamiltonian.exp_i())
        if not isinstance(unitary, QuantumCircuit):
            unitary_circuit = unitary.to_circuit()
        else:
            unitary_circuit = unitary

        # Decomposing twice allows some 1Q Hamiltonians to give correct results
        # when using MatrixEvolution(), that otherwise would give incorrect results.
        # It does not break any others that we tested.
        return unitary_circuit.decompose().decompose()

    def _run(self) -> HamiltonianPEResult:
        """Run the circuit and return and return `HamiltonianPEResult`.
        """

        circuit_result = self._quantum_instance.execute(self.construct_circuit())
        phases = self._compute_phases(circuit_result)
        return HamiltonianPEResult(
            self._num_evaluation_qubits, phases=phases,
            circuit_result=circuit_result, phase_estimation_scale=self._pe_scale)
