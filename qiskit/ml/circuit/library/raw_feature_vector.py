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

"""The raw feature vector circuit."""

from typing import Set, List, Optional
import numpy as np
from qiskit.circuit import QuantumRegister, ParameterVector, ParameterExpression, Gate
from qiskit.circuit.library import BlueprintCircuit


class RawFeatureVector(BlueprintCircuit):
    """The raw feature vector circuit."""

    def __init__(self, feature_dimension: Optional[int]) -> None:
        """
        Args:
            feature_dimension: The feature dimension and number of qubits.

        """
        super().__init__()

        self._num_qubits = None
        self._parameters = None

        if feature_dimension:
            self.feature_dimension = feature_dimension

    def _build(self):
        super()._build()

        # if the parameters are fully specified, use the initialize instruction
        if len(self.parameters) == 0:
            self.initialize(self._parameters, self.qubits)  # pylint: disable=no-member

        # otherwise get a gate that acts as placeholder
        else:
            placeholder = Gate('Raw', self.num_qubits, self._parameters[:], label='Raw')
            self.append(placeholder, self.qubits)

    def _check_configuration(self, raise_on_failure=True):
        pass

    @property
    def num_qubits(self) -> int:
        """Returns the number of qubits in this circuit.

        Returns:
            The number of qubits.
        """
        return self._num_qubits if self._num_qubits is not None else 0

    @num_qubits.setter
    def num_qubits(self, num_qubits: int) -> None:
        """Set the number of qubits for the n-local circuit.

        Args:
            The new number of qubits.
        """
        if self._num_qubits != num_qubits:
            # invalidate the circuit
            self._invalidate()
            self._num_qubits = num_qubits
            self._parameters = list(ParameterVector('p', length=self.feature_dimension))
            self.add_register(QuantumRegister(self.num_qubits, 'q'))

    @property
    def feature_dimension(self) -> int:
        """Return the feature dimension.

        Returns:
            The feature dimension, which is ``2 ** num_qubits``.
        """
        return 2 ** self.num_qubits

    @feature_dimension.setter
    def feature_dimension(self, feature_dimension: int) -> None:
        """Set the feature dimension.

        Args:
            feature_dimension: The new feature dimension. Must be a power of 2.

        Raises:
            ValueError: If ``feature_dimension`` is not a power of 2.
        """
        num_qubits = np.log2(feature_dimension)
        if self._num_qubits is None or num_qubits != self._num_qubits:
            if int(num_qubits) != num_qubits:
                raise ValueError('feature_dimension must be a power of 2!')

            self._invalidate()
            self.num_qubits = int(num_qubits)

    def _invalidate(self):
        super()._invalidate()
        self._parameters = None
        self._num_qubits = None

    @property
    def parameters(self) -> Set[ParameterExpression]:
        """Return the free parameters in the RawFeatureVector.

        Returns:
            A set of the free parameters.
        """
        return set(self.ordered_parameters)

    @property
    def ordered_parameters(self) -> List[ParameterExpression]:
        """Return the free parameters in the RawFeatureVector.

        Returns:
            A list of the free parameters.
        """
        return list(param for param in self._parameters if isinstance(param, ParameterExpression))

    def bind_parameters(self, value_dict):
        """Bind parameters."""
        if not isinstance(value_dict, dict):
            value_dict = dict(zip(self.ordered_parameters, value_dict))
        return super().bind_parameters(value_dict)

    def assign_parameters(self, param_dict, inplace=False):
        """Call the initialize instruction."""
        if not isinstance(param_dict, dict):
            param_dict = dict(zip(self.ordered_parameters, param_dict))

        if inplace:
            dest = self
        else:
            dest = RawFeatureVector(2 ** self.num_qubits)
            dest._build()
            dest._parameters = self._parameters.copy()

        # update the parameter list
        for i, param in enumerate(dest._parameters):
            if param in param_dict.keys():
                dest._parameters[i] = param_dict[param]

        # if fully bound call the initialize instruction
        if len(dest.parameters) == 0:
            dest._data = []  # wipe the current data
            parameters = dest._parameters / np.linalg.norm(dest._parameters)
            dest.initialize(parameters, dest.qubits)  # pylint: disable=no-member

        # else update the placeholder
        else:
            dest.data[0][0].params = dest._parameters

        if not inplace:
            return dest