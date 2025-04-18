from __future__ import annotations

import operator
from typing import Any, Callable, Optional

import sqlalchemy as sql

from pixeltable import type_system as ts

from .data_row import DataRow
from .expr import Expr
from .globals import LogicalOperator
from .row_builder import RowBuilder
from .sql_element_cache import SqlElementCache


class CompoundPredicate(Expr):
    def __init__(self, operator: LogicalOperator, operands: list[Expr]):
        super().__init__(ts.BoolType())
        self.operator = operator
        # operands are stored in self.components
        if self.operator == LogicalOperator.NOT:
            assert len(operands) == 1
            self.components = operands
        else:
            assert len(operands) > 1
            self.operands: list[Expr] = []
            for operand in operands:
                self._merge_operand(operand)

        self.id = self._create_id()

    def __repr__(self) -> str:
        if self.operator == LogicalOperator.NOT:
            return f'~({self.components[0]})'
        return f' {self.operator} '.join([f'({e})' for e in self.components])

    @classmethod
    def make_conjunction(cls, operands: list[Expr]) -> Optional[Expr]:
        if len(operands) == 0:
            return None
        if len(operands) == 1:
            return operands[0]
        return CompoundPredicate(LogicalOperator.AND, operands)

    def _merge_operand(self, operand: Expr) -> None:
        """
        Merge this operand, if possible, otherwise simply record it.
        """
        if isinstance(operand, CompoundPredicate) and operand.operator == self.operator:
            # this can be merged
            for child_op in operand.components:
                self._merge_operand(child_op)
        else:
            self.components.append(operand)

    def _equals(self, other: CompoundPredicate) -> bool:
        return self.operator == other.operator

    def _id_attrs(self) -> list[tuple[str, Any]]:
        return [*super()._id_attrs(), ('operator', self.operator.value)]

    def split_conjuncts(self, condition: Callable[[Expr], bool]) -> tuple[list[Expr], Optional[Expr]]:
        if self.operator in (LogicalOperator.OR, LogicalOperator.NOT):
            return super().split_conjuncts(condition)
        matches = [op for op in self.components if condition(op)]
        non_matches = [op for op in self.components if not condition(op)]
        return (matches, self.make_conjunction(non_matches))

    def sql_expr(self, sql_elements: SqlElementCache) -> Optional[sql.ColumnElement]:
        sql_exprs = [sql_elements.get(op) for op in self.components]
        if any(e is None for e in sql_exprs):
            return None
        if self.operator == LogicalOperator.NOT:
            assert len(sql_exprs) == 1
            return sql.not_(sql_exprs[0])
        assert len(sql_exprs) > 1
        operator = sql.and_ if self.operator == LogicalOperator.AND else sql.or_
        combined = operator(*sql_exprs)
        return combined

    def eval(self, data_row: DataRow, row_builder: RowBuilder) -> None:
        if self.operator == LogicalOperator.NOT:
            data_row[self.slot_idx] = not data_row[self.components[0].slot_idx]
        else:
            val = self.operator == LogicalOperator.AND
            op_function = operator.and_ if self.operator == LogicalOperator.AND else operator.or_
            for op in self.components:
                val = op_function(val, data_row[op.slot_idx])
            data_row[self.slot_idx] = val

    def _as_dict(self) -> dict:
        return {'operator': self.operator.value, **super()._as_dict()}

    @classmethod
    def _from_dict(cls, d: dict, components: list[Expr]) -> CompoundPredicate:
        assert 'operator' in d
        return cls(LogicalOperator(d['operator']), components)
