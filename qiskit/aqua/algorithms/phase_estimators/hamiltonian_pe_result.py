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

"""Result from running HamiltonianPE"""


from typing import Dict, Union, cast
import numpy
from qiskit.result import Result
from .phase_estimator_result import PhaseEstimatorResult
from .phase_estimation_scale import PhaseEstimationScale


class HamiltonianPEResult(PhaseEstimatorResult):
    """Store and manipulate results from running `HamiltonianPE`.

    This API of this class is nearly the same as `PhaseEstimatorResult`, differing only in
    the presence of an additional keyword argument in the methods. If `scaled`
    is `False`, then the phases are not translated and scaled to recover the
    eigenvalues of the Hamiltonian. Instead `phi` in :math:`[0, 1)` is returned,
    as is the case when then unitary is not derived from a Hamiltonian.
    """
    def __init__(self, num_evaluation_qubits: int, circuit_result: Result,
                 phase_estimation_scale: PhaseEstimationScale,
                 phases: Union[numpy.ndarray, Dict[str, float]]) -> None:
        """
        Args:
            num_evaluation_qubits: number of qubits in phase-readout register.
            circuit_result: result object returned by method running circuit.
            phase_estimation_scale: object used to scale phases to obtain eigenvalues.
            phases: ndarray or dict of phases and frequencies determined by QPE.
        """
        self._phase_estimation_scale = phase_estimation_scale

        super().__init__(num_evaluation_qubits, circuit_result, phases)

    # pylint: disable=arguments-differ
    def filter_phases(self, cutoff: float = 0.0, scaled: bool = True,  # type: ignore
                      as_float: bool = True) -> Dict[Union[str, float], float]:
        """Filter phases as does `PhaseEstimatorResult.filter_phases`, with
        the addition that `phi` is shifted and translated to return eigenvalues
        of the Hamiltonian.

        Args:
            cutoff: Minimum weight of number of counts required to keep a bit string.
                          The default value is `0.0`.
            scaled: If False, return `phi` in :math:`[0, 1)` rather than the eigenvalues of
                         the Hamiltonian.
            as_float: If `True`, returned keys are floats in :math:`[0.0, 1.0)`. If `False`
                      returned keys are bit strings.

        Raises:
            ValueError: if as_float` is `False` and `scaled` is `True`.

        Returns:
              A dict of filtered phases.
        """
        if scaled and not as_float:
            raise ValueError('`as_float` must be `True` if `scaled` is `True`.')

        phases = super().filter_phases(cutoff, as_float=as_float)
        if scaled:
            return cast(Dict, self._phase_estimation_scale.scale_phases(phases))
        else:
            return cast(Dict, phases)

    @property
    def most_likely_eigenvalue(self) -> float:
        """The most likely eigenvalue of the Hamiltonian.

        This method calls `most_likely_phase` and scales the result to
        obtain an eigenvalue.

        Returns:
            The most likely eigenvalue of the Hamiltonian.
        """
        phase = super().most_likely_phase
        return self._phase_estimation_scale.scale_phase(phase)