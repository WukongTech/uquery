from __future__ import annotations

import sqlalchemy as sa
import ibis.expr.operations as ops
from ibis.backends.base.sql.alchemy import AlchemyCompiler, AlchemyExprTranslator
from ibis.backends.mysql.datatypes import MySQLType
# from ibis.backends.mysql.registry import operation_registry
from ibis.expr.rewrites import rewrite_sample
from uquery.backends.doris.registry import operation_registry
from sqlalchemy_doris.dialect import MySQLDialect_mysqldb


class DorisExprTranslator(AlchemyExprTranslator):
    _registry = operation_registry.copy()
    _rewrites = AlchemyExprTranslator._rewrites.copy()
    _integer_to_timestamp = sa.func.from_unixtime
    native_json_type = False
    _dialect_name = "doris"
    type_mapper = MySQLType


rewrites = DorisExprTranslator.rewrites


# @rewrites(ops.Lag)
# def _lag(expr):
#     print(expr)
#     raise NotImplementedError()
    # if op.default is not None:
    #     raise NotImplementedError()
    #
    # sa_arg = t.translate(op.arg)
    # sa_offset = t.translate(op.offset) if op.offset is not None else 1
    # return sa.func.lag(sa_arg, sa_offset)


class DorisCompiler(AlchemyCompiler):
    translator_class = DorisExprTranslator
    support_values_syntax_in_select = False
    null_limit = None
    rewrites = AlchemyCompiler.rewrites | rewrite_sample

