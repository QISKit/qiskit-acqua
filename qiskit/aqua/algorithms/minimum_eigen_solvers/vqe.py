# -*- coding: utf-8 -*-

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

"""
The Variational Quantum Eigensolver algorithm.

See https://arxiv.org/abs/1304.3061
"""

from typing import Optional, List, Callable, Union
import logging
import warnings
from time import time

import numpy as np
from qiskit import ClassicalRegister
from qiskit.circuit import ParameterVector

from qiskit.providers import BaseBackend
from qiskit.aqua import QuantumInstance, AquaError
from qiskit.aqua.algorithms import QuantumAlgorithm
from qiskit.aqua.operators import (OperatorBase, ExpectationBase, CircuitStateFn,
                                   LegacyBaseOperator, ListOp, I)
from qiskit.aqua.components.optimizers import Optimizer, SLSQP
from qiskit.aqua.components.variational_forms import VariationalForm, RY
from qiskit.aqua.utils.validation import validate_min
from ..vq_algorithm import VQAlgorithm, VQResult
from .minimum_eigen_solver import MinimumEigensolver, MinimumEigensolverResult

logger = logging.getLogger(__name__)

# disable check for var_forms, optimizer setter because of pylint bug
# pylint: disable=no-member


class VQE(VQAlgorithm, MinimumEigensolver):
    r"""
    The Variational Quantum Eigensolver algorithm.

    `VQE <https://arxiv.org/abs/1304.3061>`__ is a hybrid algorithm that uses a
    variational technique and interleaves quantum and classical computations in order to find
    the minimum eigenvalue of the Hamiltonian :math:`H` of a given system.

    An instance of VQE requires defining two algorithmic sub-components:
    a trial state (ansatz) from Aqua's :mod:`~qiskit.aqua.components.variational_forms`, and one
    of the classical :mod:`~qiskit.aqua.components.optimizers`. The ansatz is varied, via its set
    of parameters, by the optimizer, such that it works towards a state, as determined by the
    parameters applied to the variational form, that will result in the minimum expectation value
    being measured of the input operator (Hamiltonian).

    An optional array of parameter values, via the *initial_point*, may be provided as the
    starting point for the search of the minimum eigenvalue. This feature is particularly useful
    such as when there are reasons to believe that the solution point is close to a particular
    point.  As an example, when building the dissociation profile of a molecule,
    it is likely that using the previous computed optimal solution as the starting
    initial point for the next interatomic distance is going to reduce the number of iterations
    necessary for the variational algorithm to converge.  Aqua provides an
    `initial point tutorial <https://github.com/Qiskit/qiskit-tutorials-community/blob/master
    /chemistry/h2_vqe_initial_point.ipynb>`__ detailing this use case.

    The length of the *initial_point* list value must match the number of the parameters
    expected by the variational form being used. If the *initial_point* is left at the default
    of ``None``, then VQE will look to the variational form for a preferred value, based on its
    given initial state. If the variational form returns ``None``,
    then a random point will be generated within the parameter bounds set, as per above.
    If the variational form provides ``None`` as the lower bound, then VQE
    will default it to :math:`-2\pi`; similarly, if the variational form returns ``None``
    as the upper bound, the default value will be :math:`2\pi`.
    """

    def __init__(self,
                 operator: Optional[Union[OperatorBase, LegacyBaseOperator]] = None,
                 var_form: Optional[VariationalForm] = None,
                 optimizer: Optional[Optimizer] = None,
                 initial_point: Optional[np.ndarray] = None,
                 expectation_value: Optional[ExpectationBase] = None,
                 max_evals_grouped: int = 1,
                 aux_operators: Optional[List[Optional[Union[OperatorBase, LegacyBaseOperator]]]] =
                 None,
                 callback: Optional[Callable[[int, np.ndarray, float, float], None]] = None,
                 quantum_instance: Optional[Union[QuantumInstance, BaseBackend]] = None) -> None:
        """

        Args:
            operator: Qubit operator of the Observable
            var_form: A parameterized variational form (ansatz).
            optimizer: A classical optimizer.
            initial_point: An optional initial point (i.e. initial parameter values)
                for the optimizer. If ``None`` then VQE will look to the variational form for a
                preferred point and if not will simply compute a random one.
            expectation_value: The Expectation Value algorithm for taking average value of the
                Observable over the var_form state function.
            max_evals_grouped: Max number of evaluations performed simultaneously. Signals the
                given optimizer that more than one set of parameters can be supplied so that
                potentially the expectation values can be computed in parallel. Typically this is
                possible when a finite difference gradient is used by the optimizer such that
                multiple points to compute the gradient can be passed and if computed in parallel
                improve overall execution time.
            aux_operators: Optional list of auxiliary operators to be evaluated with the
                eigenstate of the minimum eigenvalue main result and their expectation values
                returned. For instance in chemistry these can be dipole operators, total particle
                count operators so we can get values for these at the ground state.
            callback: a callback that can access the intermediate data during the optimization.
                Four parameter values are passed to the callback as follows during each evaluation
                by the optimizer for its current set of parameters as it works towards the minimum.
                These are: the evaluation count, the optimizer parameters for the
                variational form, the evaluated mean and the evaluated standard deviation.`
            quantum_instance: Quantum Instance or Backend
        """
        validate_min('max_evals_grouped', max_evals_grouped, 1)
        if var_form is None:
            # TODO after ansatz refactor num qubits can be set later so we do not have to have
            #      an operator to create a default
            if operator is not None:
                var_form = RY(operator.num_qubits)

        if optimizer is None:
            optimizer = SLSQP()

        # TODO after ansatz refactor we may still not be able to do this
        #      if num qubits is not set on var form
        if initial_point is None and var_form is not None:
            initial_point = var_form.preferred_init_points

        self._max_evals_grouped = max_evals_grouped

        super().__init__(var_form=var_form,
                         optimizer=optimizer,
                         cost_fn=self._energy_evaluation,
                         initial_point=initial_point,
                         quantum_instance=quantum_instance)
        self._ret = None
        self._eval_time = None
        self._optimizer.set_max_evals_grouped(max_evals_grouped)
        self._callback = callback

        self._expectation_value = expectation_value
        self.operator = operator
        self.aux_operators = aux_operators

        self._eval_count = 0
        logger.info(self.print_settings())

        self._var_form_params = None
        if self.var_form is not None:
            self._var_form_params = ParameterVector('θ', self.var_form.num_parameters)

    @property
    def operator(self) -> Optional[OperatorBase]:
        """ Returns operator """
        return self._operator

    @operator.setter
    def operator(self, operator: Union[OperatorBase, LegacyBaseOperator]) -> None:
        """ set operator """
        if isinstance(operator, LegacyBaseOperator):
            operator = operator.to_opflow()
        self._operator = operator
        self._check_operator_varform()
        if self._expectation_value is not None:
            self.expectation_value.operator = self._operator
        else:
            self._try_set_expectation_value_from_factory()

    def _try_set_expectation_value_from_factory(self):
        if self.operator and self.quantum_instance:
            self.expectation_value = ExpectationBase.factory(operator=self.operator,
                                                             backend=self.quantum_instance)

    @QuantumAlgorithm.quantum_instance.setter
    def quantum_instance(self, quantum_instance: Union[QuantumInstance, BaseBackend]) -> None:
        """ set quantum_instance """
        if isinstance(quantum_instance, BaseBackend):
            quantum_instance = QuantumInstance(quantum_instance)
        self._quantum_instance = quantum_instance
        if self._expectation_value is not None:
            self.expectation_value.backend = self.quantum_instance
        else:
            self._try_set_expectation_value_from_factory()

    @property
    def expectation_value(self) -> ExpectationBase:
        """ The Expectation Value algorithm used to compute the value of the observable at each
        update step. """
        return self._expectation_value

    @expectation_value.setter
    def expectation_value(self, exp: ExpectationBase) -> None:
        self._expectation_value = exp
        if self.operator:
            self._expectation_value.operator = self.operator

    @property
    def aux_operators(self) -> Optional[List[Optional[OperatorBase]]]:
        """ Returns aux operators """
        return self._aux_operators

    @aux_operators.setter
    def aux_operators(self,
                      aux_operators: Optional[List[Optional[Union[OperatorBase,
                                                                  LegacyBaseOperator]]]]) -> None:
        """ Set aux operators """
        # This is all terrible code to deal with weight 0-qubit None aux_ops.
        self._aux_op_nones = None
        if isinstance(aux_operators, list):
            self._aux_op_nones = [op is None for op in aux_operators]
            zero_op = I.tensorpower(self.operator.num_qubits) * 0.0
            converted = [op.to_opflow() if op else zero_op for op in aux_operators]
            # For some reason Chemistry passes aux_ops with 0 qubits and paulis sometimes.
            converted = [zero_op if op == 0 else op for op in converted]
            aux_operators = ListOp(converted)
        elif isinstance(aux_operators, LegacyBaseOperator):
            aux_operators = [aux_operators.to_opflow()]
        self._aux_operators = aux_operators
        if self.var_form is not None:
            self._var_form_params = ParameterVector('θ', self.var_form.num_parameters)
        self._parameterized_circuits = None

    @VQAlgorithm.var_form.setter
    def var_form(self, var_form: VariationalForm):
        """ Sets variational form """
        VQAlgorithm.var_form.fset(self, var_form)
        self._var_form_params = ParameterVector('θ', var_form.num_parameters)
        if self.initial_point is None:
            self.initial_point = var_form.preferred_init_points
        self._check_operator_varform()

    def _check_operator_varform(self):
        if self.operator is not None and self.var_form is not None:
            if self.operator.num_qubits != self.var_form.num_qubits:
                # TODO After Ansatz update we should be able to set in the
                #      number of qubits to var form. Important since use by
                #      application stack of VQE the user may be able to set
                #      a var form but not know num_qubits. Whether any smarter
                #      settings could be optionally done by VQE e.g adjust depth
                #      is TBD. Also this auto adjusting might not be reasonable for
                #      instance UCCSD where its parameterization is much closer to
                #      the specific problem and hence to the operator
                raise AquaError("Variational form num qubits does not match operator")

    @VQAlgorithm.optimizer.setter
    def optimizer(self, optimizer: Optimizer):
        """ Sets optimizer """
        super().optimizer = optimizer
        if optimizer is not None:
            optimizer.set_max_evals_grouped(self._max_evals_grouped)

    @property
    def setting(self):
        """Prepare the setting of VQE as a string."""
        ret = "Algorithm: {}\n".format(self.__class__.__name__)
        params = ""
        for key, value in self.__dict__.items():
            if key[0] == "_":
                if "initial_point" in key and value is None:
                    params += "-- {}: {}\n".format(key[1:], "Random seed")
                else:
                    params += "-- {}: {}\n".format(key[1:], value)
        ret += "{}".format(params)
        return ret

    def print_settings(self):
        """
        Preparing the setting of VQE into a string.

        Returns:
            str: the formatted setting of VQE
        """
        ret = "\n"
        ret += "==================== Setting of {} ============================\n".format(
            self.__class__.__name__)
        ret += "{}".format(self.setting)
        ret += "===============================================================\n"
        if self._var_form is not None:
            ret += "{}".format(self._var_form.setting)
        else:
            ret += 'var_form has not been set'
        ret += "===============================================================\n"
        ret += "{}".format(self._optimizer.setting)
        ret += "===============================================================\n"
        return ret

    def _run(self) -> 'VQEResult':
        """
        Run the algorithm to compute the minimum eigenvalue.

        Returns:
            dict: Dictionary of results

        Raises:
            AquaError: wrong setting of operator and backend.
        """
        if self.operator is None:
            raise AquaError("Operator was never provided")

        self._quantum_instance.circuit_summary = True

        self._eval_count = 0
        vqresult = self.find_minimum(initial_point=self.initial_point,
                                     var_form=self.var_form,
                                     cost_fn=self._energy_evaluation,
                                     optimizer=self.optimizer)

        # TODO remove all former dictionary logic
        self._ret = {}
        self._ret['num_optimizer_evals'] = vqresult.optimizer_evals
        self._ret['min_val'] = vqresult.optimal_value
        self._ret['opt_params'] = vqresult.optimal_point
        self._ret['eval_time'] = vqresult.optimizer_time

        if self._ret['num_optimizer_evals'] is not None and \
                self._eval_count >= self._ret['num_optimizer_evals']:
            self._eval_count = self._ret['num_optimizer_evals']
        self._eval_time = self._ret['eval_time']
        logger.info('Optimization complete in %s seconds.\nFound opt_params %s in %s evals',
                    self._eval_time, self._ret['opt_params'], self._eval_count)
        self._ret['eval_count'] = self._eval_count

        self._ret['energy'] = self.get_optimal_cost()
        self._ret['eigvals'] = np.asarray([self.get_optimal_cost()])
        self._ret['eigvecs'] = np.asarray([self.get_optimal_vector()])

        result = VQEResult()
        result.combine(vqresult)
        result.eigenvalue = vqresult.optimal_value + 0j
        result.eigenstate = self.get_optimal_vector()

        if self.aux_operators:
            self._eval_aux_ops()
            # TODO remove when ._ret is deprecated
            result.aux_operator_eigenvalues = self._ret['aux_ops'][0]

        result.cost_function_evals = self._eval_count

        return result

    def _eval_aux_ops(self, threshold=1e-12):
        # Create a new ExpectationBase object to evaluate the auxops.
        expect = self.expectation_value.__class__(operator=self.aux_operators,
                                                  backend=self._quantum_instance,
                                                  state=CircuitStateFn(self.get_optimal_circuit()))
        values = np.real(expect.compute_expectation())
        # Discard values below threshold
        # TODO remove reshape when ._ret is deprecated
        aux_op_results = (values * (np.abs(values) > threshold))
        # Deal with the aux_op behavior where there can be Nones or Zero qubit Paulis in the list
        self._ret['aux_ops'] = [None if is_none else [result]
                                for (is_none, result) in zip(self._aux_op_nones, aux_op_results)]
        self._ret['aux_ops'] = np.array([self._ret['aux_ops']])

    def compute_minimum_eigenvalue(
            self, operator: Optional[OperatorBase] = None,
            aux_operators: Optional[List[OperatorBase]] = None) -> MinimumEigensolverResult:
        super().compute_minimum_eigenvalue(operator, aux_operators)
        return self._run()

    # This is the objective function to be passed to the optimizer that is used for evaluation
    def _energy_evaluation(self, parameters):
        """
        Evaluate energy at given parameters for the variational form.

        Args:
            parameters (numpy.ndarray): parameters for variational form.

        Returns:
            Union(float, list[float]): energy of the hamiltonian of each parameter.
        """
        num_parameter_sets = len(parameters) // self._var_form.num_parameters
        parameter_sets = np.split(parameters, num_parameter_sets)

        # If ExpectationValue was never created, create one now.
        if not self.expectation_value:
            self._try_set_expectation_value_from_factory()

        if not self._expectation_value.state:
            ansatz_circuit_op = CircuitStateFn(
                self._var_form.construct_circuit(self._var_form_params))
            self._expectation_value.state = ansatz_circuit_op
        param_bindings = {self._var_form_params: parameter_sets}

        start_time = time()
        means = np.real(self._expectation_value.compute_expectation(params=param_bindings))

        if self._callback is not None:
            stds = np.real(
                self._expectation_value.compute_standard_deviation(params=param_bindings))
            for i, param_set in enumerate(parameter_sets):
                self._eval_count += 1
                self._callback(self._eval_count, param_set, means[i], stds[i])
        else:
            self._eval_count += len(means)

        end_time = time()
        logger.info('Energy evaluation returned %s - %.5f (ms), eval count: %s',
                    means, (end_time - start_time) * 1000, self._eval_count)

        return means if len(means) > 1 else means[0]

    def get_optimal_cost(self):
        if 'opt_params' not in self._ret:
            raise AquaError("Cannot return optimal cost before running the "
                            "algorithm to find optimal params.")
        return self._ret['min_val']

    def get_optimal_circuit(self):
        if 'opt_params' not in self._ret:
            raise AquaError("Cannot find optimal circuit before running the "
                            "algorithm to find optimal params.")
        return self._var_form.construct_circuit(self._ret['opt_params'])

    def get_optimal_vector(self):
        # pylint: disable=import-outside-toplevel
        from qiskit.aqua.utils.run_circuits import find_regs_by_name

        if 'opt_params' not in self._ret:
            raise AquaError("Cannot find optimal vector before running the "
                            "algorithm to find optimal params.")
        qc = self.get_optimal_circuit()
        if self._quantum_instance.is_statevector:
            ret = self._quantum_instance.execute(qc)
            self._ret['min_vector'] = ret.get_statevector(qc)
        else:
            c = ClassicalRegister(qc.width(), name='c')
            q = find_regs_by_name(qc, 'q')
            qc.add_register(c)
            qc.barrier(q)
            qc.measure(q, c)
            ret = self._quantum_instance.execute(qc)
            self._ret['min_vector'] = ret.get_counts(qc)
        return self._ret['min_vector']

    @property
    def optimal_params(self):
        if 'opt_params' not in self._ret:
            raise AquaError("Cannot find optimal params before running the algorithm.")
        return self._ret['opt_params']


class VQEResult(VQResult, MinimumEigensolverResult):
    """ VQE Result."""

    @property
    def cost_function_evals(self) -> int:
        """ Returns number of cost optimizer evaluations """
        return self.get('cost_function_evals')

    @cost_function_evals.setter
    def cost_function_evals(self, value: int) -> None:
        """ Sets number of cost function evaluations """
        self.data['cost_function_evals'] = value

    def __getitem__(self, key: object) -> object:
        if key == 'eval_count':
            warnings.warn('eval_count deprecated, use cost_function_evals property.',
                          DeprecationWarning)
            return super().__getitem__('cost_function_evals')

        try:
            return VQResult.__getitem__(self, key)
        except KeyError:
            return MinimumEigensolverResult.__getitem__(self, key)
