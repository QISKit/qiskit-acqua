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

""" CircuitSampler Class """

from typing import Optional, Dict, List
import logging
from functools import partial

from qiskit.providers import BaseBackend
from qiskit.circuit import ParameterExpression
from qiskit import QiskitError
from qiskit.aqua import QuantumInstance
from qiskit.aqua.utils.backend_utils import is_aer_provider, is_statevector_backend
from qiskit.aqua.operators.operator_base import OperatorBase
from qiskit.aqua.operators.operator_globals import Zero
from qiskit.aqua.operators.combo_operators.list_op import ListOp
from qiskit.aqua.operators.state_functions.state_fn import StateFn
from qiskit.aqua.operators.state_functions.circuit_state_fn import CircuitStateFn
from qiskit.aqua.operators.state_functions.dict_state_fn import DictStateFn
from qiskit.aqua.operators.converters.converter_base import ConverterBase

logger = logging.getLogger(__name__)


class CircuitSampler(ConverterBase):
    """ A sampler for local Quantum simulator backends
    """

    def __init__(self,
                 backend: Optional[BaseBackend] = None,
                 statevector: Optional[bool] = None,
                 param_qobj: bool = False,
                 attach_results: bool = False) -> None:
        """
        Args:
            backend:
            statevector:
            param_qobj:
        Raises:
            ValueError: Set statevector or param_qobj True when not supported by backend.
        """
        self._qi = backend if isinstance(backend, QuantumInstance) else\
            QuantumInstance(backend=backend)
        self._statevector = statevector if statevector is not None else self._qi.is_statevector
        if self._statevector and not is_statevector_backend(self.quantum_instance.backend):
            raise ValueError('Statevector mode for circuit sampling requires statevector '
                             'backend, not {}.'.format(backend))
        self._attach_results = attach_results

        # Object state variables
        self._last_op = None
        self._reduced_op_cache = None
        self._circuit_ops_cache = {}
        self._transpiled_circ_cache = None
        self._transpile_before_bind = True

        self._param_qobj = param_qobj
        if self._param_qobj and not is_aer_provider(self.quantum_instance.backend):
            raise ValueError('Parameterized Qobj mode requires Aer '
                             'backend, not {}.'.format(backend))
        self._binding_mappings = None

    @property
    def backend(self) -> BaseBackend:
        """ returns backend """
        return self.quantum_instance.backend

    @backend.setter
    def backend(self, backend: BaseBackend) -> None:
        self.quantum_instance = QuantumInstance(backend=backend)

    @property
    def quantum_instance(self) -> QuantumInstance:
        """ returns quantum instance """
        return self._qi

    @quantum_instance.setter
    def quantum_instance(self, quantum_instance: QuantumInstance) -> None:
        self._qi = quantum_instance

    # pylint: disable=arguments-differ
    def convert(self,
                operator: OperatorBase,
                params: dict = None):
        if self._last_op is None or not operator == self._last_op:
            # Clear caches
            self._last_op = operator
            self._reduced_op_cache = None
            self._circuit_ops_cache = None
            self._transpiled_circ_cache = None

        if not self._reduced_op_cache:
            operator_dicts_replaced = operator.to_circuit_op()
            self._reduced_op_cache = operator_dicts_replaced.reduce()

        if not self._circuit_ops_cache:
            self._circuit_ops_cache = {}
            self._extract_circuitstatefns(self._reduced_op_cache)

        if params:
            num_parameterizations = len(list(params.values())[0])
            param_bindings = [{param: value_list[i] for (param, value_list) in params.items()}
                              for i in range(num_parameterizations)]
        else:
            param_bindings = None
            num_parameterizations = 1

        # Don't pass circuits if we have in the cache, the sampling function knows to use the cache
        circs = list(self._circuit_ops_cache.values()) if not self._transpiled_circ_cache else None
        sampled_statefn_dicts = self.sample_circuits(circuit_sfns=circs,
                                                     param_bindings=param_bindings)

        def replace_circuits_with_dicts(operator, param_index=0):
            if isinstance(operator, CircuitStateFn):
                return sampled_statefn_dicts[id(operator)][param_index]
            elif isinstance(operator, ListOp):
                return operator.traverse(partial(replace_circuits_with_dicts,
                                                 param_index=param_index))
            else:
                return operator

        if params:
            return ListOp([replace_circuits_with_dicts(self._reduced_op_cache, param_index=i)
                           for i in range(num_parameterizations)])
        else:
            return replace_circuits_with_dicts(self._reduced_op_cache, param_index=0)

    # pylint: disable=inconsistent-return-statements
    def _extract_circuitstatefns(self, operator):
        if isinstance(operator, CircuitStateFn):
            self._circuit_ops_cache[id(operator)] = operator
        elif isinstance(operator, ListOp):
            for op in operator.oplist:
                self._extract_circuitstatefns(op)
        else:
            return operator

    def sample_circuits(self,
                        circuit_sfns: Optional[List[CircuitStateFn]] = None,
                        param_bindings: Optional[List[Dict[
                            ParameterExpression, List[float]]]] = None) -> Dict[int, DictStateFn]:
        """
        Args:
            circuit_sfns: The list of circuits or CircuitStateFns to sample
            param_bindings: bindings
        Returns:
            Dict: dictionary of sampled state functions
        """
        if circuit_sfns or not self._transpiled_circ_cache:
            if self._statevector:
                circuits = [op_c.to_circuit(meas=False) for op_c in circuit_sfns]
            else:
                circuits = [op_c.to_circuit(meas=True) for op_c in circuit_sfns]

            try:
                self._transpiled_circ_cache = self._qi.transpile(circuits)
            except QiskitError:
                # TODO does this fail too silently?
                self._transpile_before_bind = False
                self._transpiled_circ_cache = circuits
        else:
            circuit_sfns = list(self._circuit_ops_cache.values())

        if param_bindings is not None:
            if self._param_qobj:
                ready_circs = self._transpiled_circ_cache
                self._prepare_parameterized_run_config(param_bindings)
            else:
                ready_circs = [circ.bind_parameters(binding)
                               for circ in self._transpiled_circ_cache
                               for binding in param_bindings]
        else:
            ready_circs = self._transpiled_circ_cache

        results = self._qi.execute(ready_circs, had_transpiled=self._transpile_before_bind)

        # Wipe parameterizations, if any
        # self._qi._run_config.parameterizations = None

        sampled_statefn_dicts = {}
        for i, op_c in enumerate(circuit_sfns):
            # Taking square root because we're replacing a statevector
            # representation of probabilities.
            reps = len(param_bindings) if param_bindings is not None else 1
            c_statefns = []
            for j in range(reps):
                circ_index = (i * reps) + j
                circ_results = results.data(circ_index)

                if 'expval_measurement' in circ_results.get('snapshots', {}).get(
                        'expectation_value', {}):
                    # TODO Also, allow setting on CircuitSamplers whether to attach Results to
                    #  DictStateFns or not.
                    snapshot_data = results.data(circ_index)['snapshots']
                    avg = snapshot_data['expectation_value']['expval_measurement'][0]['value']
                    if isinstance(avg, (list, tuple)):
                        # Aer versions before 0.4 use a list snapshot format
                        # which must be converted to a complex value.
                        avg = avg[0] + 1j * avg[1]
                    # Will be replaced with just avg when eval is called later
                    num_qubits = circuit_sfns[0].num_qubits
                    result_sfn = (Zero ^ num_qubits).adjoint() * avg
                elif self._statevector:
                    result_sfn = StateFn(op_c.coeff * results.get_statevector(circ_index))
                else:
                    result_sfn = StateFn({b: (v * op_c.coeff / self._qi._run_config.shots) ** .5
                                          for (b, v) in results.get_counts(circ_index).items()})
                if self._attach_results:
                    result_sfn.execution_results = circ_results
                c_statefns.append(result_sfn)
            sampled_statefn_dicts[id(op_c)] = c_statefns
        return sampled_statefn_dicts

    def _prepare_parameterized_run_config(self, param_bindings: dict):
        pass
        # Wipe parameterizations, if any
        # self._qi._run_config.parameterizations = None

        # if not self._binding_mappings:
        #     phony_binding = {k: str(k) for k in param_bindings[0].keys()}
        #     phony_bound_circuits = [circ.bind_parameters(phony_binding)
        #                             for circ in self._transpiled_circ_cache]
        #     qobj = self._qi.assemble(phony_bound_circuits)
        #     # for circ in qobj:
        #     #     mapping = None
        #     #     for
        #
        # # self._qi._run_config.parameterizations = [params_circ]