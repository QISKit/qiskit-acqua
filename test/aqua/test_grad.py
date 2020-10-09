# This code is part of Qiskit.
#
# (C) Copyright IBM 2019, 2020.
#
# This code is licensed under the Apache License, Version 2.0. You may
# obtain a copy of this license in the LICENSE.txt file in the root directory
# of this source tree or at http://www.apache.org/licenses/LICENSE-2.0.
#
# Any modifications or derivative works of this code must retain this
# copyright notice, and modified files need to carry a notice indicating
# that they have been altered from the originals.
# =============================================================================

""" Test Quantum Gradient Framework """

import unittest
from test.aqua import QiskitAquaTestCase
from itertools import product

import numpy as np
from ddt import ddt, data, idata, unpack
from sympy import Symbol, cos

try:
    import jax.numpy as jnp
    _HAS_JAX = True
except ImportError:
    _HAS_JAX = False

from qiskit import Aer
from qiskit import QuantumCircuit, QuantumRegister, BasicAer
from qiskit.aqua import QuantumInstance
from qiskit.aqua import aqua_globals
from qiskit.aqua.algorithms import VQE
from qiskit.aqua.components.optimizers import CG
from qiskit.aqua.operators import I, X, Z, StateFn, CircuitStateFn, ListOp, CircuitSampler
from qiskit.aqua.operators.gradients import Gradient, NaturalGradient, Hessian
from qiskit.aqua.operators.gradients.qfi import QFI
from qiskit.circuit import Parameter, ParameterExpression
from qiskit.circuit import ParameterVector


@ddt
class TestGradients(QiskitAquaTestCase):
    """ Test Qiskit Gradient Framework """

    def setUp(self):
        super().setUp()
        aqua_globals.random_seed = 50

    @data('lin_comb', 'param_shift', 'fin_diff')
    def test_gradient_p(self, method):
        """Test the state gradient for p
        |psi> = 1/sqrt(2)[[1, exp(ia)]]
        Tr(|psi><psi|Z) = 0
        Tr(|psi><psi|X) = cos(a)
        d<H>/da = - 0.5 sin(a)
        """
        ham = 0.5 * X - 1 * Z
        a = Parameter('a')
        params = [a]

        q = QuantumRegister(1)
        qc = QuantumCircuit(q)
        qc.h(q)
        qc.p(params[0], q[0])
        op = ~StateFn(ham) @ CircuitStateFn(primitive=qc, coeff=1.)

        state_grad = Gradient(grad_method=method).convert(operator=op, params=params)
        values_dict = [{a: np.pi / 4}, {a: 0}, {a: np.pi / 2}]
        correct_values = [-0.5 / np.sqrt(2), 0, -0.5]

        for i, value_dict in enumerate(values_dict):
            np.testing.assert_array_almost_equal(state_grad.assign_parameters(value_dict).eval(),
                                                 correct_values[i], decimal=1)

    @data('lin_comb', 'param_shift', 'fin_diff')
    def test_gradient_u(self, method):
        """Test the state gradient for U
        Tr(|psi><psi|Z) = - 0.5 sin(a)cos(c)
        Tr(|psi><psi|X) = cos^2(a/2) cos(b+c) - sin^2(a/2) cos(b-c)
        """

        ham = 0.5 * X - 1 * Z
        a = Parameter('a')
        b = Parameter('b')
        c = Parameter('c')

        q = QuantumRegister(1)
        qc = QuantumCircuit(q)
        qc.h(q)
        qc.u(a, b, c, q[0])

        op = ~StateFn(ham) @ CircuitStateFn(primitive=qc, coeff=1.)
        params = [a, b, c]
        state_grad = Gradient(grad_method=method).convert(operator=op, params=params)
        values_dict = [{a: np.pi / 4, b: 0, c: 0}, {a: np.pi / 4, b: np.pi / 4, c: np.pi / 4}]
        correct_values = [[0.3536, 0, 0], [0.3232, -0.42678, -0.92678]]
        for i, value_dict in enumerate(values_dict):
            np.testing.assert_array_almost_equal(state_grad.assign_parameters(value_dict).eval(),
                                                 correct_values[i],
                                                 decimal=1)

        # Tr(|psi><psi|Z) = - 0.5 sin(a)cos(c)
        # Tr(|psi><psi|X) = cos^2(a/2) cos(b+c) - sin^2(a/2) cos(b-c)
        # dTr(|psi><psi|H)/da = 0.5(cos(2a)) + 0.5()

        q = QuantumRegister(1)
        qc = QuantumCircuit(q)
        qc.h(q)
        qc.u(a, a, a, q[0])

        op = ~StateFn(ham) @ CircuitStateFn(primitive=qc, coeff=1.)
        params = [a]
        state_grad = Gradient(grad_method=method).convert(operator=op, params=params)
        values_dict = [{a: np.pi / 4}, {a: np.pi / 2}]
        correct_values = [[-1.03033], [-1]]
        for i, value_dict in enumerate(values_dict):
            np.testing.assert_array_almost_equal(state_grad.assign_parameters(value_dict).eval(),
                                                 correct_values[i],
                                                 decimal=1)

    @data('lin_comb', 'param_shift', 'fin_diff')
    def test_state_gradient1(self, method):
        """Test the state gradient

        Tr(|psi><psi|Z) = sin(a)sin(b)
        Tr(|psi><psi|X) = cos(a)
        d<H>/da = - 0.5 sin(a) - 1 cos(a)sin(b)
        d<H>/db = - 1 sin(a)cos(b)
        """

        ham = 0.5 * X - 1 * Z
        a = Parameter('a')
        b = Parameter('b')
        params = [a, b]

        q = QuantumRegister(1)
        qc = QuantumCircuit(q)
        qc.h(q)
        qc.rz(params[0], q[0])
        qc.rx(params[1], q[0])
        op = ~StateFn(ham) @ CircuitStateFn(primitive=qc, coeff=1.)

        state_grad = Gradient(grad_method=method).convert(operator=op, params=params)
        values_dict = [{a: np.pi / 4, b: np.pi}, {params[0]: np.pi / 4, params[1]: np.pi / 4},
                       {params[0]: np.pi / 2, params[1]: np.pi / 4}]
        correct_values = [[-0.5 / np.sqrt(2), 1 / np.sqrt(2)], [-0.5 / np.sqrt(2) - 0.5, -1 / 2.],
                          [-0.5, -1 / np.sqrt(2)]]

        for i, value_dict in enumerate(values_dict):
            np.testing.assert_array_almost_equal(state_grad.assign_parameters(value_dict).eval(),
                                                 correct_values[i], decimal=1)

    @data('lin_comb', 'param_shift', 'fin_diff')
    def test_state_gradient2(self, method):
        """Test the state gradient 2

        Tr(|psi><psi|Z) = sin(a)sin(a)
        Tr(|psi><psi|X) = cos(a)
        d<H>/da = - 0.5 sin(a) - 2 cos(a)sin(a)
        """
        ham = 0.5 * X - 1 * Z
        a = Parameter('a')
        # b = Parameter('b')
        params = [a]

        q = QuantumRegister(1)
        qc = QuantumCircuit(q)
        qc.h(q)
        qc.rz(a, q[0])
        qc.rx(a, q[0])
        op = ~StateFn(ham) @ CircuitStateFn(primitive=qc, coeff=1.)

        state_grad = Gradient(grad_method=method).convert(operator=op, params=params)
        values_dict = [{a: np.pi / 4}, {a: 0},
                       {a: np.pi / 2}]
        correct_values = [-1.353553, -0, -0.5]

        for i, value_dict in enumerate(values_dict):
            np.testing.assert_array_almost_equal(state_grad.assign_parameters(value_dict).eval(),
                                                 correct_values[i],
                                                 decimal=1)

    @data('lin_comb', 'param_shift', 'fin_diff')
    def test_state_gradient3(self, method):
        """Test the state gradient 3

        Tr(|psi><psi|Z) = sin(a)sin(c(a)) = sin(a)sin(cos(a)+1)
        Tr(|psi><psi|X) = cos(a)
        d<H>/da = - 0.5 sin(a) - 1 cos(a)sin(cos(a)+1) + 1 sin^2(a)cos(cos(a)+1)
        """
        ham = 0.5 * X - 1 * Z
        a = Parameter('a')
        # b = Parameter('b')
        params = [a]
        x = Symbol('x')
        expr = cos(x) + 1
        c = ParameterExpression({a: x}, expr)

        q = QuantumRegister(1)
        qc = QuantumCircuit(q)
        qc.h(q)
        qc.rz(a, q[0])
        qc.rx(c, q[0])
        op = ~StateFn(ham) @ CircuitStateFn(primitive=qc, coeff=1.)

        state_grad = Gradient(grad_method=method).convert(operator=op, params=params)
        values_dict = [{a: np.pi / 4}, {a: 0}, {a: np.pi / 2}]
        correct_values = [-1.1220, -0.9093, 0.0403]
        for i, value_dict in enumerate(values_dict):
            np.testing.assert_array_almost_equal(state_grad.assign_parameters(value_dict).eval(),
                                                 correct_values[i],
                                                 decimal=1)

    @data('lin_comb', 'param_shift', 'fin_diff')
    def test_state_gradient4(self, method):
        """Test the state gradient 4
         Tr(|psi><psi|ZX) = -cos(a)
         daTr(|psi><psi|ZX) = sin(a)
        """

        ham = X ^ Z
        a = Parameter('a')
        params = [a]

        q = QuantumRegister(2)
        qc = QuantumCircuit(q)
        qc.x(q[0])
        qc.h(q[1])
        qc.crz(a, q[0], q[1])
        op = ~StateFn(ham) @ CircuitStateFn(primitive=qc, coeff=1.)

        state_grad = Gradient(grad_method=method).convert(operator=op, params=params)
        values_dict = [{a: np.pi / 4}, {a: 0},
                       {a: np.pi / 2}]
        correct_values = [1 / np.sqrt(2), 0, 1]

        for i, value_dict in enumerate(values_dict):
            np.testing.assert_array_almost_equal(state_grad.assign_parameters(value_dict).eval(),
                                                 correct_values[i],
                                                 decimal=1)

    @data('lin_comb', 'param_shift', 'fin_diff')
    def test_state_gradient5(self, method):
        """Test the state gradient

        Tr(|psi><psi|Z) = sin(a0)sin(a1)
        Tr(|psi><psi|X) = cos(a0)
        d<H>/da0 = - 0.5 sin(a0) - 1 cos(a0)sin(a1)
        d<H>/da1 = - 1 sin(a0)cos(a1)
        """

        ham = 0.5 * X - 1 * Z
        a = ParameterVector('a', 2)
        params = a

        q = QuantumRegister(1)
        qc = QuantumCircuit(q)
        qc.h(q)
        qc.rz(params[0], q[0])
        qc.rx(params[1], q[0])
        op = ~StateFn(ham) @ CircuitStateFn(primitive=qc, coeff=1.)

        state_grad = Gradient(grad_method=method).convert(operator=op, params=params)
        values_dict = [{a: [np.pi / 4, np.pi]}, {a: [np.pi / 4, np.pi / 4]},
                       {a: [np.pi / 2, np.pi / 4]}]
        correct_values = [[-0.5 / np.sqrt(2), 1 / np.sqrt(2)], [-0.5 / np.sqrt(2) - 0.5, -1 / 2.],
                          [-0.5, -1 / np.sqrt(2)]]

        for i, value_dict in enumerate(values_dict):
            np.testing.assert_array_almost_equal(state_grad.assign_parameters(value_dict).eval(),
                                                 correct_values[i], decimal=1)

    @data('lin_comb', 'param_shift', 'fin_diff')
    def test_state_hessian(self, method):
        """Test the state Hessian

        Tr(|psi><psi|Z) = sin(a)sin(b)
        Tr(|psi><psi|X) = cos(a)
        d^2<H>/da^2 = - 0.5 cos(a) + 1 sin(a)sin(b)
        d^2<H>/dbda = - 1 cos(a)cos(b)
        d^2<H>/dbda = - 1 cos(a)cos(b)
        d^2<H>/db^2 = + 1 sin(a)sin(b)
        """

        ham = 0.5 * X - 1 * Z
        a = Parameter('a')
        b = Parameter('b')
        params = [(a, a), (a, b), (b, b)]

        q = QuantumRegister(1)
        qc = QuantumCircuit(q)
        qc.h(q)
        qc.rz(a, q[0])
        qc.rx(b, q[0])

        op = ~StateFn(ham) @ CircuitStateFn(primitive=qc, coeff=1.)
        state_hess = Hessian(hess_method=method).convert(operator=op, params=params)

        values_dict = [{a: np.pi / 4, b: np.pi}, {a: np.pi / 4, b: np.pi / 4},
                       {a: np.pi / 2, b: np.pi / 4}]
        correct_values = [[-0.5 / np.sqrt(2), 1 / np.sqrt(2), 0],
                          [-0.5 / np.sqrt(2) + 0.5, -1 / 2., 0.5],
                          [1 / np.sqrt(2), 0, 1 / np.sqrt(2)]]

        for i, value_dict in enumerate(values_dict):
            np.testing.assert_array_almost_equal(state_hess.assign_parameters(value_dict).eval(),
                                                 correct_values[i], decimal=1)

    @data('lin_comb', 'param_shift', 'fin_diff')
    def test_prob_grad(self, method):
        """Test the probability gradient

        dp0/da = cos(a)sin(b) / 2
        dp1/da = - cos(a)sin(b) / 2
        dp0/db = sin(a)cos(b) / 2
        dp1/db = - sin(a)cos(b) / 2
        """

        a = Parameter('a')
        b = Parameter('b')
        params = [a, b]

        q = QuantumRegister(1)
        qc = QuantumCircuit(q)
        qc.h(q)
        qc.rz(params[0], q[0])
        qc.rx(params[1], q[0])

        op = CircuitStateFn(primitive=qc, coeff=1.)

        prob_grad = Gradient(grad_method=method).convert(operator=op, params=params)
        values_dict = [{a: np.pi / 4, b: 0}, {params[0]: np.pi / 4, params[1]: np.pi / 4},
                       {params[0]: np.pi / 2, params[1]: np.pi}]
        correct_values = [[[0, 0], [1 / (2 * np.sqrt(2)), - 1 / (2 * np.sqrt(2))]],
                          [[1 / 4, - 1 / 4], [1 / 4, - 1 / 4]],
                          [[0, 0], [- 1 / 2, 1 / 2]]]
        for i, value_dict in enumerate(values_dict):
            for j, prob_grad_result in enumerate(prob_grad.assign_parameters(value_dict).eval()):
                np.testing.assert_array_almost_equal(prob_grad_result,
                                                     correct_values[i][j], decimal=1)

    @data('lin_comb_full', 'overlap_block_diag', 'overlap_diag')
    def test_qfi(self, method):
        """Test if the quantum fisher information calculation is correct

        QFI = [[1, 0], [0, 1]] - [[0, 0], [0, cos^2(a)]]
        """

        a = Parameter('a')
        b = Parameter('b')
        params = [a, b]

        q = QuantumRegister(1)
        qc = QuantumCircuit(q)
        qc.h(q)
        qc.rz(params[0], q[0])
        qc.rx(params[1], q[0])

        op = CircuitStateFn(primitive=qc, coeff=1.)
        qfi = QFI(qfi_method=method).convert(operator=op, params=params)
        values_dict = [{params[0]: np.pi / 4, params[1]: 0.1}, {params[0]: np.pi, params[1]: 0.1},
                       {params[0]: np.pi / 2, params[1]: 0.1}]
        correct_values = [[[1, 0], [0, 0.5]], [[1, 0], [0, 0]], [[1, 0], [0, 1]]]
        for i, value_dict in enumerate(values_dict):
            np.testing.assert_array_almost_equal(qfi.assign_parameters(value_dict).eval(),
                                                 correct_values[i], decimal=1)

    @idata(product(['lin_comb', 'param_shift', 'fin_diff'],
                   [None, 'lasso', 'perturb_diag', 'perturb_diag_elements']))
    @unpack
    def test_natural_gradient(self, method, regularization):
        """Test the natural gradient"""
        ham = 0.5 * X - 1 * Z
        a = Parameter('a')
        b = Parameter('b')
        params = [a, b]

        q = QuantumRegister(1)
        qc = QuantumCircuit(q)
        qc.h(q)
        qc.rz(params[0], q[0])
        qc.rx(params[1], q[0])

        op = ~StateFn(ham) @ CircuitStateFn(primitive=qc, coeff=1.)
        nat_grad = NaturalGradient(grad_method=method,
                                   regularization=regularization).convert(operator=op,
                                                                          params=params)
        values_dict = [{params[0]: np.pi / 4, params[1]: np.pi / 2}]
        correct_values = [[-2.36003979, 2.06503481]] if regularization == 'ridge' else [[-4.2, 0]]
        for i, value_dict in enumerate(values_dict):
            np.testing.assert_array_almost_equal(nat_grad.assign_parameters(value_dict).eval(),
                                                 correct_values[i],
                                                 decimal=0)

    @unittest.skipIf(not _HAS_JAX, 'Skipping test due to missing jax module.')
    @idata(product(['lin_comb', 'param_shift', 'fin_diff'], [True, False]))
    @unpack
    def test_jax_chain_rule(self, method: str, autograd: bool):
        """Test the chain rule functionality using Jax

        d<H>/d<X> = 2<X>
        d<H>/d<Z> = - sin(<Z>)
        <Z> = Tr(|psi><psi|Z) = sin(a)sin(b)
        <X> = Tr(|psi><psi|X) = cos(a)
        d<H>/da = d<H>/d<X> d<X>/da + d<H>/d<Z> d<Z>/da = - 2 cos(a)sin(a)
                    - sin(sin(a)sin(b)) * cos(a)sin(b)
        d<H>/db = d<H>/d<X> d<X>/db + d<H>/d<Z> d<Z>/db = - sin(sin(a)sin(b)) * sin(a)cos(b)
        """

        a = Parameter('a')
        b = Parameter('b')
        params = [a, b]

        q = QuantumRegister(1)
        qc = QuantumCircuit(q)
        qc.h(q)
        qc.rz(params[0], q[0])
        qc.rx(params[1], q[0])

        def combo_fn(x):
            return jnp.power(x[0], 2) + jnp.cos(x[1])

        def grad_combo_fn(x):
            return np.array([2 * x[0], -np.sin(x[1])])

        op = ListOp([~StateFn(X) @ CircuitStateFn(primitive=qc, coeff=1.),
                     ~StateFn(Z) @ CircuitStateFn(primitive=qc, coeff=1.)], combo_fn=combo_fn,
                    grad_combo_fn=None if autograd else grad_combo_fn)

        state_grad = Gradient(grad_method=method).convert(operator=op, params=params)
        values_dict = [{a: np.pi / 4, b: np.pi}, {params[0]: np.pi / 4, params[1]: np.pi / 4},
                       {params[0]: np.pi / 2, params[1]: np.pi / 4}]
        correct_values = [[-1., 0.], [-1.2397, -0.2397], [0, -0.45936]]
        for i, value_dict in enumerate(values_dict):
            np.testing.assert_array_almost_equal(state_grad.assign_parameters(value_dict).eval(),
                                                 correct_values[i],
                                                 decimal=1)

    @data('lin_comb', 'param_shift', 'fin_diff')
    def test_operator_coefficient_gradient(self, method):
        """Test the operator coefficient gradient

        Tr( | psi > < psi | Z) = sin(a)sin(b)
        Tr( | psi > < psi | X) = cos(a)
        """
        a = Parameter('a')
        b = Parameter('b')
        q = QuantumRegister(1)
        qc = QuantumCircuit(q)
        qc.h(q)
        qc.rz(a, q[0])
        qc.rx(b, q[0])

        coeff_0 = Parameter('c_0')
        coeff_1 = Parameter('c_1')
        ham = coeff_0 * X + coeff_1 * Z
        op = ~StateFn(ham) @ CircuitStateFn(primitive=qc, coeff=1.0)
        gradient_coeffs = [coeff_0, coeff_1]
        coeff_grad = Gradient(grad_method=method).convert(op, gradient_coeffs)
        values_dict = [{coeff_0: 0.5, coeff_1: -1, a: np.pi / 4, b: np.pi},
                       {coeff_0: 0.5, coeff_1: -1, a: np.pi / 4, b: np.pi / 4}]
        correct_values = [[1 / np.sqrt(2), 0], [1 / np.sqrt(2), 1 / 2]]
        for i, value_dict in enumerate(values_dict):
            np.testing.assert_array_almost_equal(coeff_grad.assign_parameters(value_dict).eval(),
                                                 correct_values[i],
                                                 decimal=1)

    @data('lin_comb', 'param_shift', 'fin_diff')
    def test_operator_coefficient_hessian(self, method):
        """Test the operator coefficient hessian

        <Z> = Tr( | psi > < psi | Z) = sin(a)sin(b)
        <X> = Tr( | psi > < psi | X) = cos(a)
        d<H>/dc_0 = 2 * c_0 * <X> + c_1 * <Z>
        d<H>/dc_1 = c_0 * <Z>
        d^2<H>/dc_0^2 = 2 * <X>
        d^2<H>/dc_0dc_1 = <Z>
        d^2<H>/dc_1dc_0 = <Z>
        d^2<H>/dc_1^2 = 0
        """
        a = Parameter('a')
        b = Parameter('b')
        q = QuantumRegister(1)
        qc = QuantumCircuit(q)
        qc.h(q)
        qc.rz(a, q[0])
        qc.rx(b, q[0])

        coeff_0 = Parameter('c_0')
        coeff_1 = Parameter('c_1')
        ham = coeff_0 * coeff_0 * X + coeff_1 * coeff_0 * Z
        op = ~StateFn(ham) @ CircuitStateFn(primitive=qc, coeff=1.)
        gradient_coeffs = [(coeff_0, coeff_0), (coeff_0, coeff_1), (coeff_1, coeff_1)]
        coeff_grad = Hessian(hess_method=method).convert(op, gradient_coeffs)
        values_dict = [{coeff_0: 0.5, coeff_1: -1, a: np.pi / 4, b: np.pi},
                       {coeff_0: 0.5, coeff_1: -1, a: np.pi / 4, b: np.pi / 4}]

        correct_values = [[2 / np.sqrt(2), 0, 0], [2 / np.sqrt(2), 1 / 2, 0]]

        for i, value_dict in enumerate(values_dict):
            np.testing.assert_array_almost_equal(coeff_grad.assign_parameters(value_dict).eval(),
                                                 correct_values[i],
                                                 decimal=1)

    @data('lin_comb', 'param_shift', 'fin_diff')
    def test_circuit_sampler(self, method):
        """Test the gradient with circuit sampler

        Tr(|psi><psi|Z) = sin(a)sin(b)
        Tr(|psi><psi|X) = cos(a)
        d<H>/da = - 0.5 sin(a) - 1 cos(a)sin(b)
        d<H>/db = - 1 sin(a)cos(b)
        """

        ham = 0.5 * X - 1 * Z
        a = Parameter('a')
        b = Parameter('b')
        params = [a, b]

        q = QuantumRegister(1)
        qc = QuantumCircuit(q)
        qc.h(q)
        qc.rz(params[0], q[0])
        qc.rx(params[1], q[0])
        op = ~StateFn(ham) @ CircuitStateFn(primitive=qc, coeff=1.)

        shots = 8000
        if method == 'fin_diff':
            np.random.seed = 8
            state_grad = Gradient(grad_method=method, epsilon=shots ** (-1 / 6.)).convert(
                operator=op,
                params=params)
        else:
            state_grad = Gradient(grad_method=method).convert(operator=op, params=params)
        values_dict = [{a: np.pi / 4, b: np.pi}, {params[0]: np.pi / 4, params[1]: np.pi / 4},
                       {params[0]: np.pi / 2, params[1]: np.pi / 4}]
        correct_values = [[-0.5 / np.sqrt(2), 1 / np.sqrt(2)], [-0.5 / np.sqrt(2) - 0.5, -1 / 2.],
                          [-0.5, -1 / np.sqrt(2)]]

        backend = BasicAer.get_backend('qasm_simulator')
        q_instance = QuantumInstance(backend=backend, shots=shots)

        for i, value_dict in enumerate(values_dict):
            sampler = CircuitSampler(backend=q_instance).convert(state_grad,
                                                                 params={k: [v] for k, v in
                                                                         value_dict.items()})
            np.testing.assert_array_almost_equal(sampler.eval()[0], correct_values[i], decimal=1)

    @data('lin_comb', 'param_shift', 'fin_diff')
    def test_circuit_sampler2(self, method):
        """Test the probability gradient with the circuit sampler

        dp0/da = cos(a)sin(b) / 2
        dp1/da = - cos(a)sin(b) / 2
        dp0/db = sin(a)cos(b) / 2
        dp1/db = - sin(a)cos(b) / 2
        """

        a = Parameter('a')
        b = Parameter('b')
        params = [a, b]

        q = QuantumRegister(1)
        qc = QuantumCircuit(q)
        qc.h(q)
        qc.rz(params[0], q[0])
        qc.rx(params[1], q[0])

        op = CircuitStateFn(primitive=qc, coeff=1.)

        shots = 8000
        if method == 'fin_diff':
            np.random.seed = 8
            prob_grad = Gradient(grad_method=method, epsilon=shots ** (-1 / 6.)).convert(
                operator=op,
                params=params)
        else:
            prob_grad = Gradient(grad_method=method).convert(operator=op, params=params)
        values_dict = [{a: [np.pi / 4], b: [0]}, {params[0]: [np.pi / 4], params[1]: [np.pi / 4]},
                       {params[0]: [np.pi / 2], params[1]: [np.pi]}]
        correct_values = [[[0, 0], [1 / (2 * np.sqrt(2)), - 1 / (2 * np.sqrt(2))]],
                          [[1 / 4, -1 / 4], [1 / 4, - 1 / 4]],
                          [[0, 0], [- 1 / 2, 1 / 2]]]

        backend = BasicAer.get_backend('qasm_simulator')
        q_instance = QuantumInstance(backend=backend, shots=shots)

        for i, value_dict in enumerate(values_dict):
            sampler = CircuitSampler(backend=q_instance).convert(prob_grad,
                                                                 params=value_dict)
            result = sampler.eval()
            np.testing.assert_array_almost_equal(result[0], correct_values[i], decimal=1)

    @idata(product(['statevector_simulator', 'qasm_simulator'],
                   ['lin_comb', 'param_shift', 'fin_diff']))
    @unpack
    def test_vqe(self, backend, method):
        """Test VQE with gradients"""
        qi_sv = QuantumInstance(Aer.get_backend(backend),
                                seed_simulator=2,
                                seed_transpiler=2)
        # Define the Hamiltonian
        h2_hamiltonian = -1.05 * (I ^ I) + 0.39 * (I ^ Z) - 0.39 * (Z ^ I) - 0.01 * (Z ^ Z) + 0.18 \
            * (X ^ X)
        h2_energy = -1.85727503

        # Define the Ansatz
        wavefunction = QuantumCircuit(2)
        params = ParameterVector('theta', length=8)
        itr = iter(params)
        wavefunction.ry(next(itr), 0)
        wavefunction.ry(next(itr), 1)
        wavefunction.rz(next(itr), 0)
        wavefunction.rz(next(itr), 1)
        wavefunction.cx(0, 1)
        wavefunction.ry(next(itr), 0)
        wavefunction.ry(next(itr), 1)
        wavefunction.rz(next(itr), 0)
        wavefunction.rz(next(itr), 1)

        # Conjugate Gradient algorithm
        optimizer = CG(maxiter=10)

        grad = Gradient(grad_method=method)

        # Gradient callable
        vqe = VQE(h2_hamiltonian, wavefunction, optimizer=optimizer, gradient=grad)

        result = vqe.run(qi_sv)
        np.testing.assert_almost_equal(result['optimal_value'], h2_energy, decimal=1)


@ddt
class TestParameterGradients(QiskitAquaTestCase):
    """Test taking the gradient of parameter expressions."""

    def test_grad(self):
        """Test taking the gradient of parameter expressions."""
        x, y = Parameter('x'), Parameter('y')
        with self.subTest('linear'):
            expr = 2 * x + y

            grad = Gradient.parameter_expression_grad(expr, x)
            self.assertEqual(grad, 2)

            grad = Gradient.parameter_expression_grad(expr, y)
            self.assertEqual(grad, 1)

        with self.subTest('polynomial'):
            expr = x * x * x - x * y + y * y

            grad = Gradient.parameter_expression_grad(expr, x)
            self.assertEqual(grad, 3 * x * x - y)

            grad = Gradient.parameter_expression_grad(expr, y)
            self.assertEqual(grad, -1 * x + 2 * y)

    def test_converted_to_float_if_bound(self):
        """Test the gradient is a float when no free symbols are left."""
        x = Parameter('x')
        expr = 2 * x + 1
        grad = Gradient.parameter_expression_grad(expr, x)
        self.assertIsInstance(grad, float)


if __name__ == '__main__':
    unittest.main()
