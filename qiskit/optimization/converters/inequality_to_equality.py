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
"""The inequality to equality converter."""

import copy
import math
from typing import List, Tuple, Dict, Optional
import logging

from ..problems.quadratic_program import QuadraticProgram
from ..problems.quadratic_objective import ObjSense
from ..problems.constraint import ConstraintSense
from ..problems.variable import VarType
from ..exceptions import QiskitOptimizationError

logger = logging.getLogger(__name__)


class InequalityToEquality:
    """Convert inequality constraints into equality constraints by introducing slack variables.

    Examples:
        >>> problem = QuadraticProgram()
        >>> # define a problem
        >>> conv = InequalityToEquality()
        >>> problem2 = conv.encode(problem)
    """

    _delimiter = '@'  # users are supposed not to use this character in variable names

    def __init__(self) -> None:
        """Initialize the inequality to equality variable converter."""

        self._src = None
        self._dst = None
        self._conv: Dict[str, List[Tuple[str, int]]] = {}
        # e.g., self._conv = {'c1': [c1@slack_var]}

    def encode(
            self, op: QuadraticProgram, name: Optional[str] = None, mode: str = 'auto'
    ) -> QuadraticProgram:
        """Convert a problem with inequality constraints into one with only equality constraints.

        Args:
            op: The problem to be solved, that may contain inequality constraints.
            name: The name of the converted problem.
            mode: To chose the type of slack variables. There are 3 options for mode.
                  - 'integer': All slack variables will be integer variables.
                  - 'continuous': All slack variables will be continuous variables
                  - 'auto': Try to use integer variables but if it's not possible,
                    use continuous variables

        Returns:
            The converted problem, that contain only equality constraints.

        Raises:
            QiskitOptimizationError: If a variable type is not supported.
            QiskitOptimizationError: If an unsupported mode is selected.
            QiskitOptimizationError: If an unsupported sense is specified.
        """
        self._src = copy.deepcopy(op)
        self._dst = QuadraticProgram()
        if name:
            self._dst.name = name
        else:
            self._dst.name = self._src.name

        # Copy variables
        for x in self._src.variables:
            if x.vartype == VarType.BINARY:
                self._dst.binary_var(name=x.name)
            elif x.vartype == VarType.INTEGER:
                self._dst.integer_var(
                    name=x.name, lowerbound=x.lowerbound, upperbound=x.upperbound
                )
            elif x.vartype == VarType.CONTINUOUS:
                self._dst.continuous_var(
                    name=x.name, lowerbound=x.lowerbound, upperbound=x.upperbound
                )
            else:
                raise QiskitOptimizationError("Unsupported variable type {}".format(x.vartype))

        # Copy the objective function
        constant = self._src.objective.constant
        linear = self._src.objective.linear.to_dict(use_name=True)
        quadratic = self._src.objective.quadratic.to_dict(use_name=True)
        if self._src.objective.sense == ObjSense.MINIMIZE:
            self._dst.minimize(constant, linear, quadratic)
        else:
            self._dst.maximize(constant, linear, quadratic)

        # For linear constraints
        for constraint in self._src.linear_constraints:
            linear = constraint.linear.to_dict(use_name=True)
            if constraint.sense == ConstraintSense.EQ:
                self._dst.linear_constraint(
                    linear, constraint.sense, constraint.rhs, constraint.name
                )
            elif constraint.sense == ConstraintSense.LE or constraint.sense == ConstraintSense.GE:
                if mode == 'integer':
                    self._add_integer_slack_var_linear_constraint(
                        linear, constraint.sense, constraint.rhs, constraint.name
                    )
                elif mode == 'continuous':
                    self._add_continuous_slack_var_linear_constraint(
                        linear, constraint.sense, constraint.rhs, constraint.name
                    )
                elif mode == 'auto':
                    self._add_auto_slack_var_linear_constraint(
                        linear, constraint.sense, constraint.rhs, constraint.name
                    )
                else:
                    raise QiskitOptimizationError('Unsupported mode is selected: {}'.format(mode))
            else:
                raise QiskitOptimizationError(
                    'Type of sense in {} is not supported'.format(constraint.name)
                )

        # For quadratic constraints
        for constraint in self._src.quadratic_constraints:
            linear = constraint.linear.to_dict(use_name=True)
            quadratic = constraint.quadratic.to_dict(use_name=True)
            if constraint.sense == ConstraintSense.EQ:
                self._dst.quadratic_constraint(
                    linear, quadratic, constraint.sense, constraint.rhs, constraint.name
                )
            elif constraint.sense == ConstraintSense.LE or constraint.sense == ConstraintSense.GE:
                if mode == 'integer':
                    self._add_integer_slack_var_quadratic_constraint(
                        linear,
                        quadratic,
                        constraint.sense,
                        constraint.rhs,
                        constraint.name,
                    )
                elif mode == 'continuous':
                    self._add_continuous_slack_var_quadratic_constraint(
                        linear,
                        quadratic,
                        constraint.sense,
                        constraint.rhs,
                        constraint.name,
                    )
                elif mode == 'auto':
                    self._add_auto_slack_var_quadratic_constraint(
                        linear,
                        quadratic,
                        constraint.sense,
                        constraint.rhs,
                        constraint.name,
                    )
                else:
                    raise QiskitOptimizationError('Unsupported mode is selected: {}'.format(mode))
            else:
                raise QiskitOptimizationError(
                    'Type of sense in {} is not supported'.format(constraint.name)
                )

        return self._dst

    def _add_integer_slack_var_linear_constraint(self, linear, sense, rhs, name):
        # If a coefficient that is not integer exist, raise error
        if any(isinstance(coef, float) and not coef.is_integer() for coef in linear.values()):
            raise QiskitOptimizationError('Can not use a slack variable for ' + name)

        # If rhs is float number, round up/down to the nearest integer.
        new_rhs = rhs
        if sense == ConstraintSense.LE:
            new_rhs = math.floor(rhs)
        if sense == ConstraintSense.GE:
            new_rhs = math.ceil(rhs)

        # Add a new integer variable.
        slack_name = name + self._delimiter + 'int_slack'
        self._conv[name] = slack_name

        lhs_lb, lhs_ub = self._calc_linear_bounds(linear)

        if sense == ConstraintSense.LE:
            sign = 1
            self._dst.integer_var(name=slack_name, lowerbound=0, upperbound=new_rhs - lhs_lb)
        elif sense == ConstraintSense.GE:
            sign = -1
            self._dst.integer_var(name=slack_name, lowerbound=0, upperbound=lhs_ub - new_rhs)
        else:
            raise QiskitOptimizationError('The type of Sense in {} is not supported'.format(name))

        # Add a new equality constraint.
        new_linear = copy.deepcopy(linear)
        new_linear[slack_name] = sign
        self._dst.linear_constraint(new_linear, "==", new_rhs, name)

    def _add_continuous_slack_var_linear_constraint(self, linear, sense, rhs, name):
        slack_name = name + self._delimiter + 'continuous_slack'
        self._conv[name] = slack_name

        lhs_lb, lhs_ub = self._calc_linear_bounds(linear)

        if sense == ConstraintSense.LE:
            sign = 1
            self._dst.continuous_var(name=slack_name, lowerbound=0, upperbound=rhs - lhs_lb)
        elif sense == ConstraintSense.GE:
            sign = -1
            self._dst.continuous_var(name=slack_name, lowerbound=0, upperbound=lhs_ub - rhs)
        else:
            raise QiskitOptimizationError('The type of Sense in {} is not supported'.format(name))

        # Add a new equality constraint.
        new_linear = copy.deepcopy(linear)
        new_linear[slack_name] = sign
        self._dst.linear_constraint(new_linear, "==", rhs, name)

    def _add_auto_slack_var_linear_constraint(self, linear, sense, rhs, name):
        # If a coefficient that is not integer exist, use a continuous slack variable
        if any(isinstance(coef, float) and not coef.is_integer() for coef in linear.values()):
            self._add_continuous_slack_var_linear_constraint(linear, sense, rhs, name)
        # Else use an integer slack variable
        else:
            self._add_integer_slack_var_linear_constraint(linear, sense, rhs, name)

    def _add_integer_slack_var_quadratic_constraint(self, linear, quadratic, sense, rhs, name):
        # If a coefficient that is not integer exist, raise an error
        if any(
                isinstance(coef, float) and not coef.is_integer() for coef in quadratic.values()
        ) or any(isinstance(coef, float) and not coef.is_integer() for coef in linear.values()):
            raise QiskitOptimizationError('Can not use a slack variable for ' + name)

        # If rhs is float number, round up/down to the nearest integer.
        new_rhs = rhs
        if sense == ConstraintSense.LE:
            new_rhs = math.floor(rhs)
        if sense == ConstraintSense.GE:
            new_rhs = math.ceil(rhs)

        # Add a new integer variable.
        slack_name = name + self._delimiter + 'int_slack'
        self._conv[name] = slack_name

        lhs_lb, lhs_ub = self._calc_quadratic_bounds(linear, quadratic)

        if sense == ConstraintSense.LE:
            sign = 1
            self._dst.integer_var(name=slack_name, lowerbound=0, upperbound=new_rhs - lhs_lb)
        elif sense == ConstraintSense.GE:
            sign = -1
            self._dst.integer_var(name=slack_name, lowerbound=0, upperbound=lhs_ub - new_rhs)
        else:
            raise QiskitOptimizationError('The type of Sense in {} is not supported'.format(name))

        # Add a new equality constraint.
        new_linear = copy.deepcopy(linear)
        new_linear[slack_name] = sign
        self._dst.quadratic_constraint(new_linear, quadratic, "==", new_rhs, name)

    def _add_continuous_slack_var_quadratic_constraint(self, linear, quadratic, sense, rhs, name):
        # If a coefficient that is not integer exist, raise error
        if any(
                isinstance(coef, float) and not coef.is_integer() for coef in quadratic.values()
        ) or any(isinstance(coef, float) and not coef.is_integer() for coef in linear.values()):
            raise QiskitOptimizationError('Can not use a slack variable for ' + name)

        # Add a new continuous variable.
        slack_name = name + self._delimiter + 'continuous_slack'
        self._conv[name] = slack_name

        lhs_lb, lhs_ub = self._calc_quadratic_bounds(linear, quadratic)

        if sense == ConstraintSense.LE:
            sign = 1
            self._dst.continuous_var(name=slack_name, lowerbound=0, upperbound=rhs - lhs_lb)
        elif sense == ConstraintSense.GE:
            sign = -1
            self._dst.continuous_var(name=slack_name, lowerbound=0, upperbound=lhs_ub - rhs)
        else:
            raise QiskitOptimizationError('The type of Sense in {} is not supported'.format(name))

        # Add a new equality constraint.
        new_linear = copy.deepcopy(linear)
        new_linear[slack_name] = sign
        self._dst.quadratic_constraint(new_linear, quadratic, "==", rhs, name)

    def _add_auto_slack_var_quadratic_constraint(self, linear, quadratic, sense, rhs, name):
        # If a coefficient that is not integer exist, use a continuous slack variable
        if any(
                isinstance(coef, float) and not coef.is_integer() for coef in quadratic.values()
        ) or any(isinstance(coef, float) and not coef.is_integer() for coef in linear.values()):
            self._add_continuous_slack_var_quadratic_constraint(linear, quadratic, sense, rhs, name)
        # Else use an integer slack variable
        else:
            self._add_integer_slack_var_quadratic_constraint(linear, quadratic, sense, rhs, name)

    def _calc_linear_bounds(self, linear):
        lhs_lb, lhs_ub = 0, 0
        for var_name, v in linear.items():
            x = self._src.get_variable(var_name)
            lhs_lb += min(x.lowerbound * v, x.upperbound * v)
            lhs_ub += max(x.lowerbound * v, x.upperbound * v)
        return lhs_lb, lhs_ub

    def _calc_quadratic_bounds(self, linear, quadratic):
        lhs_lb, lhs_ub = 0, 0
        # Calcurate the lowerbound and the upperbound of the linear part
        linear_lb, linear_ub = self._calc_linear_bounds(linear)
        lhs_lb += linear_lb
        lhs_ub += linear_ub

        # Calcurate the lowerbound and the upperbound of the quadratic part
        for (name_i, name_j), v in quadratic.items():
            x = self._src.get_variable(name_i)
            y = self._src.get_variable(name_j)

            lhs_lb += min(
                x.lowerbound * y.lowerbound * v,
                x.lowerbound * y.upperbound * v,
                x.upperbound * y.lowerbound * v,
                x.upperbound * y.upperbound * v,
            )
            lhs_ub += max(
                x.lowerbound * y.lowerbound * v,
                x.lowerbound * y.upperbound * v,
                x.upperbound * y.lowerbound * v,
                x.upperbound * y.upperbound * v,
            )
        return lhs_lb, lhs_ub

    def decode(self, result: 'OptimizationResult') -> 'OptimizationResult':
        """Convert a result of a converted problem into that of the original problem.

        Args:
            result: The result of the converted problem.

        Returns:
            The result of the original problem.
        """
        from ..algorithms.optimization_algorithm import OptimizationResult

        new_result = OptimizationResult()
        # convert the optimization result into that of the original problem
        names = [x.name for x in self._dst.variables]
        vals = result.x
        new_vals = self._decode_var(names, vals)
        new_result.x = new_vals
        new_result.fval = result.fval
        new_result.status = result.status
        new_result.results = result.results
        return new_result

    def _decode_var(self, names, vals) -> List[int]:
        # decode slack variables
        sol = {name: vals[i] for i, name in enumerate(names)}

        new_vals = []
        for x in self._src.variables:
            new_vals.append(sol[x.name])
        return new_vals