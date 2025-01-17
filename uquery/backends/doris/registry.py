from __future__ import annotations

import contextlib
import functools
import operator
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.elements import RANGE_CURRENT, RANGE_UNBOUNDED
from sqlalchemy.sql.functions import FunctionElement, GenericFunction

import ibis.common.exceptions as com
import ibis.expr.analysis as an
import ibis.expr.datatypes as dt
import ibis.expr.operations as ops
import ibis.expr.types as ir

import sqlalchemy as sa
# from sqlalchemy.ext.compiler import compiles
# from sqlalchemy.sql.functions import GenericFunction
#
import ibis
import ibis.common.exceptions as com
import ibis.expr.operations as ops
from ibis.backends.mysql.registry import operation_registry



def _translate_window_boundary(boundary):
    if boundary is None:
        return None

    if isinstance(boundary.value, ops.Literal):
        if boundary.preceding:
            return -boundary.value.value
        else:
            return boundary.value.value

    raise com.TranslationError("Window boundaries must be literal values")


def _translate_window_boundary_7_2_0(boundary):
    if boundary is None:
        return None

    if isinstance(boundary, ops.Literal):
        return boundary.value

    raise com.TranslationError("Window boundaries must be literal values")

def _window_function(t, window):
    func = window.func.__window_op__

    reduction = t.translate(func)

    # Some analytic functions need to have the expression of interest in
    # the ORDER BY part of the window clause
    if isinstance(func, t._require_order_by) and not window.frame.order_by:
        order_by = t.translate(func.args[0])
    else:
        order_by = [t.translate(arg) for arg in window.frame.order_by]

    partition_by = [t.translate(arg) for arg in window.frame.group_by]

    if isinstance(window.frame, ops.RowsWindowFrame):
        if window.frame.max_lookback is not None:
            raise NotImplementedError(
                "Rows with max lookback is not implemented for SQLAlchemy-based "
                "backends."
            )
        how = "rows"
    elif isinstance(window.frame, ops.RangeWindowFrame):
        how = "range_"
    else:
        raise NotImplementedError(type(window.frame))

    if t._forbids_frame_clause and isinstance(func, t._forbids_frame_clause):
        # some functions on some backends don't support frame clauses
        additional_params = {}
    elif window.frame.start is None and window.frame.end is None:
        additional_params = {}
    else:
        start = _translate_window_boundary(window.frame.start)
        end = _translate_window_boundary(window.frame.end)
        additional_params = {how: (start, end)}

    result = sa.over(
        reduction, partition_by=partition_by, order_by=order_by, **additional_params
    )

    if isinstance(func, (ops.RowNumber, ops.DenseRank, ops.MinRank, ops.NTile)):
        return result - 1
    else:
        return result



def _lag(t, op):
    # print(expr)
    # raise NotImplementedError()
    # if op.default is not None:
    #     raise NotImplementedError()

    sa_arg = t.translate(op.arg)
    sa_offset = t.translate(op.offset) if op.offset is not None else 1
    sa_default = t.translate(op.default) if op.default is not None else 0
    return sa.func.lag(sa_arg, sa_offset, sa_default)


def _window_function_0_7_2_0(t, window):
    func = window.func.__window_op__

    reduction = t.translate(func)

    # Some analytic functions need to have the expression of interest in
    # the ORDER BY part of the window clause
    if isinstance(func, t._require_order_by) and not window.frame.order_by:
        order_by = t.translate(func.args[0])
    else:
        order_by = [t.translate(arg) for arg in window.frame.order_by]

    partition_by = [t.translate(arg) for arg in window.frame.group_by]

    if isinstance(window.frame, ops.RowsWindowFrame):
        if window.frame.max_lookback is not None:
            raise NotImplementedError(
                "Rows with max lookback is not implemented for SQLAlchemy-based "
                "backends."
            )
        how = "rows"
    elif isinstance(window.frame, ops.RangeWindowFrame):
        how = "range_"
    else:
        raise NotImplementedError(type(window.frame))

    additional_params = {}

    # some functions on some backends don't support frame clauses
    if not t._forbids_frame_clause or not isinstance(func, t._forbids_frame_clause):
        if (start := window.frame.start) is not None:
            start = t.translate(start.value)
            # start = _translate_window_boundary_7_2_0(start.value)

        if (end := window.frame.end) is not None:
            end = t.translate(end.value)
            # end = _translate_window_boundary_7_2_0(end.value)

        # Lag 不支持 between
        if start is not None or end is not None:
            additional_params[how] = (start, end)

    result = sa.over(
        reduction, partition_by=partition_by, order_by=order_by, **additional_params
    )

    if isinstance(func, (ops.RowNumber, ops.DenseRank, ops.MinRank, ops.NTile)):
        result -= 1

    return result


def _reinterpret_range_bound(bound):
    if bound is None:
        return RANGE_UNBOUNDED

    try:
        lower = int(bound)
    except ValueError as err:
        sa.util.raise_(
            sa.exc.ArgumentError(
                "Integer, None or expression expected for range value"
            ),
            replace_context=err,
        )
    except TypeError:
        return RANGE_CURRENT if bound.value == 0 else bound
        # return bound
    else:
        return RANGE_CURRENT if lower == 0 else lower


def _interpret_range(self, range_):
    if not isinstance(range_, tuple) or len(range_) != 2:
        raise sa.exc.ArgumentError("2-tuple expected for range/rows")

    lower = _reinterpret_range_bound(range_[0])
    upper = _reinterpret_range_bound(range_[1])
    return lower, upper



if ibis.__version__ == '7.1.0':
    operation_registry.update({
        ops.Lag: _lag,
        ops.Window: _window_function
    })
elif ibis.__version__ == '7.2.0':

    # monkeypatch to allow expressions in range and rows bounds
    sa.sql.elements.Over._interpret_range = _interpret_range

    operation_registry.update({
        ops.Lag: _lag,
        ops.WindowFunction: _window_function_0_7_2_0
    })
