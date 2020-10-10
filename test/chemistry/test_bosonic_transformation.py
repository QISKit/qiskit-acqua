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

""" Test Fermionic Transformation """

import unittest

from test.chemistry import QiskitChemistryTestCase
from qiskit.aqua.operators import WeightedPauliOperator
from qiskit.chemistry.qubit_transformations import BosonicTransformation
from qiskit.chemistry.qubit_transformations import BosonicTransformationType, BosonicQubitMappingType
from qiskit.chemistry.drivers. gaussiand import GaussianLogResult


class TestBosonicTransformation(QiskitChemistryTestCase):
    """Bosonic Transformation tests."""

    def setUp(self):
        super().setUp()
        self.driver = GaussianLogResult(self.get_resource_path('CO2_freq_B3LYP_ccpVDZ.log'))

    def _validate_input_object(self, qubit_op, num_qubits, num_paulis):
        self.assertTrue(isinstance(qubit_op, WeightedPauliOperator))
        self.assertIsNotNone(qubit_op)
        self.assertEqual(qubit_op.num_qubits, num_qubits)
        self.assertEqual(len(qubit_op.to_dict()['paulis']), num_paulis)

    def test_output(self):
        bosonic_transformation = BosonicTransformation(qubit_mapping=BosonicQubitMappingType.DIRECT,
                                                       transformation_type=BosonicTransformationType.HARMONIC,
                                                       basis_size=2, truncation=2)

        qubit_op, aux_ops = bosonic_transformation.transform(self.driver)
        self.assertEqual(bosonic_transformation.num_modes, 4)
        self._validate_input_object(qubit_op, num_qubits=8, num_paulis=59)
        self.assertEqual(len(aux_ops), 4)



if __name__ == '__main__':
    unittest.main()