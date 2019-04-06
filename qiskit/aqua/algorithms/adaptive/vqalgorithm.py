# -*- coding: utf-8 -*-

# Copyright 2018 IBM.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =============================================================================
"""
The Variational Quantum Algorithm Base Class. This class can be used an interface for working with Variation Quantum
Algorithms, such as VQE, QAOA, or VSVM, and also provides helper utilities for implementing new variational algorithms.
Writing a new variational algorithm is a simple as extending this class, implementing a cost function for the new
algorithm to pass to the optimizer, and running the find_minimum() function below to begin the optimization.
Alternatively, all of the functions below can be overridden to opt-out of this infrastructure but still meet the
interface requirements.

"""

import time
import logging
import numpy as np
from abc import abstractmethod

from qiskit.aqua.algorithms import QuantumAlgorithm

logger = logging.getLogger(__name__)


class VQAlgorithm(QuantumAlgorithm):
    """
    The Variational Quantum Algorithm Base Class.
    """

    def __init__(self,
                 var_form=None,
                 optimizer=None,
                 cost_fn=None,
                 initial_point=None):
        super().__init__()
        self._var_form = var_form
        self._optimizer = optimizer
        self._cost_fn = cost_fn
        self._initial_point = initial_point

    @abstractmethod
    def get_optimal_cost(self):
        raise NotImplementedError()

    @abstractmethod
    def get_optimal_circuit(self):
        raise NotImplementedError()

    @abstractmethod
    def get_optimal_vector(self):
        raise NotImplementedError()

    def find_minimum(self, initial_point=None, var_form=None, cost_fn=None, optimizer=None, gradient_fn=None):
        """Optimize to find the minimum cost value.

        Returns:
            Optimized variational parameters, and corresponding minimum cost value.

        Raises:
            ValueError:

        """
        initial_point = initial_point if initial_point is not None else self._initial_point
        var_form = var_form if var_form is not None else self._var_form
        cost_fn = cost_fn if cost_fn is not None else self._cost_fn
        optimizer = optimizer if optimizer is not None else self._optimizer

        nparms = var_form.num_parameters
        bounds = var_form.parameter_bounds

        if initial_point is not None and len(initial_point) != nparms:
            raise ValueError('Initial point size {} and parameter size {} mismatch'.format(len(initial_point), nparms))
        if len(bounds) != nparms:
            raise ValueError('Variational form bounds size does not match parameter size')
        # If *any* value is *equal* in bounds array to None then the problem does *not* have bounds
        problem_has_bounds = not np.any(np.equal(bounds, None))
        # Check capabilities of the optimizer
        if problem_has_bounds:
            if not optimizer.is_bounds_supported:
                raise ValueError('Problem has bounds but optimizer does not support bounds')
        else:
            if optimizer.is_bounds_required:
                raise ValueError('Problem does not have bounds but optimizer requires bounds')
        if initial_point is not None:
            if not optimizer.is_initial_point_supported:
                raise ValueError('Optimizer does not support initial point')
        else:
            if optimizer.is_initial_point_required:
                low = [(l if l is not None else -2 * np.pi) for (l, u) in bounds]
                high = [(u if u is not None else 2 * np.pi) for (l, u) in bounds]
                initial_point = self.random.uniform(low, high)
        if not optimizer.is_gradient_supported: # ignore the passed gradient function
            gradient_fn = None


        start = time.time()
        logger.info('Starting optimizer.\nbounds={}\ninitial point={}'.format(bounds, initial_point))
        opt_params, opt_val, num_optimizer_evals = optimizer.optimize(var_form.num_parameters,
                                                                      cost_fn,
                                                                      variable_bounds=bounds,
                                                                      initial_point=initial_point,
                                                                      gradient_function=gradient_fn # customized gradient func
                                                                      )
        eval_time = time.time() - start
        ret = {}
        ret['num_optimizer_evals'] = num_optimizer_evals
        ret['min_val'] = opt_val
        ret['opt_params'] = opt_params
        ret['eval_time'] = eval_time

        return ret

    # Helper function to get probability vectors for a set of params
    def get_prob_vector_for_params(self, construct_circuit_fn, params_s,
                                   quantum_instance, construct_circuit_args=None):
        circuits = []
        for params in params_s:
            circuit = construct_circuit_fn(params, **construct_circuit_args)
            circuits.append(circuit)
        results = quantum_instance.execute(circuits)

        probs_s = []
        for circuit in circuits:
            if quantum_instance.is_statevector:
                sv = results.get_statevector(circuit)
                probs = np.real(sv * np.conj(sv))
                probs_s.append(probs)
            else:
                counts = results.get_counts(circuit)
                probs_s.append(self.get_probabilities_for_counts(counts))
        return np.array(probs_s)

    def get_probabilities_for_counts(self, counts):
        shots = sum(counts.values())
        states = int(2 ** len(list(counts.keys())[0]))
        probs = np.zeros(states)
        for k, v in counts.items():
            probs[int(k, 2)] = v / shots
        return probs

    @property
    def initial_point(self):
        return self._initial_point

    @initial_point.setter
    def initial_point(self, new_value):
        self._initial_point = new_value

    @property
    @abstractmethod
    def optimal_params(self):
        raise NotImplementedError()

    @property
    def var_form(self):
        return self._var_form

    @var_form.setter
    def var_form(self, new_value):
        self._var_form = new_value

    @property
    def optimizer(self):
        return self._optimizer
