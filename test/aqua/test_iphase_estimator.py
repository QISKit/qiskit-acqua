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

"""Test iterative phase estimation"""

import unittest
from test.aqua import QiskitAquaTestCase
from qiskit.aqua.algorithms.phase_estimators import IPhaseEstimation
import qiskit
from qiskit.aqua.operators import (H, X, Z)


class TestIPhaseEstimation(QiskitAquaTestCase):
    """Evolution tests."""

    # pylint: disable=invalid-name
    def one_phase(self, unitary_circuit, state_preparation=None, n_eval_qubits=6,
                  backend=qiskit.BasicAer.get_backend('qasm_simulator')):
        """Run phase estimation with operator, eigenvalue pair `unitary_circuit`,
        `state_preparation`. Return the estimated phase as a value in :math:`[0,1)`.
        """
        qi = qiskit.aqua.QuantumInstance(backend=backend, shots=10000)
        p_est = IPhaseEstimation(num_iterations=n_eval_qubits,
                                 unitary=unitary_circuit,
                                 quantum_instance=qi,
                                 state_preparation=state_preparation)
        result = p_est.estimate()
        phase = result.phase
        return phase

    def test_qpe_Z0(self):
        """eigenproblem Z, |0>"""

        unitary_circuit = Z.to_circuit()
        state_preparation = None  # prepare |0>
        phase = self.one_phase(unitary_circuit, state_preparation)
        self.assertEqual(phase, 0.0)

    def test_qpe_Z0_statevector(self):
        """eigenproblem Z, |0>, statevector simulator"""

        unitary_circuit = Z.to_circuit()
        state_preparation = None  # prepare |0>
        phase = self.one_phase(unitary_circuit, state_preparation,
                               backend=qiskit.BasicAer.get_backend('statevector_simulator'))
        self.assertEqual(phase, 0.0)

    def test_qpe_Z1(self):
        """eigenproblem Z, |1>"""
        unitary_circuit = Z.to_circuit()
        state_preparation = X.to_circuit()  # prepare |1>
        phase = self.one_phase(unitary_circuit, state_preparation)
        self.assertEqual(phase, 0.5)

    def test_qpe_Z1_estimate(self):
        """eigenproblem Z, |1>, estimate interface"""
        unitary_circuit = Z.to_circuit()
        state_preparation = X.to_circuit()  # prepare |1>
        backend = qiskit.BasicAer.get_backend('statevector_simulator')
        num_iterations = 6
        pe = IPhaseEstimation(num_iterations, quantum_instance=backend)
        result = pe.estimate(unitary=unitary_circuit, state_preparation=state_preparation)
        phase = result.phase
        self.assertEqual(phase, 0.5)

    def test_qpe_Xplus(self):
        """eigenproblem X, |+>"""
        unitary_circuit = X.to_circuit()
        state_preparation = H.to_circuit()  # prepare |+>
        phase = self.one_phase(unitary_circuit, state_preparation)
        self.assertEqual(phase, 0.0)

    def test_qpe_Xminus(self):
        """eigenproblem X, |->"""
        unitary_circuit = X.to_circuit()
        state_preparation = X.to_circuit()
        state_preparation.append(H.to_circuit(), [0])  # prepare |->
        phase = self.one_phase(unitary_circuit, state_preparation)
        self.assertEqual(phase, 0.5)


if __name__ == '__main__':
    unittest.main()
