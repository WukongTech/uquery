from __future__ import annotations

import calendar
import functools
import math
import operator
from functools import partial
from typing import Any

import sqlglot as sg

import ibis.common.exceptions as com
import ibis.expr.datatypes as dt
import ibis.expr.operations as ops
from ibis import util
from ibis.backends.base.sqlglot import NULL, STAR, AggGen, C, F, interval, make_cast


@functools.singledispatch
def translate_val(op, **_):
    """Translate a value expression into sqlglot."""
    raise com.OperationNotDefinedError(f"No translation rule for {type(op)}")


@translate_val.register(ops.Lag)
def _column(op, *, table, name, **_):
    return sg.column(name, table=table.alias_or_name)