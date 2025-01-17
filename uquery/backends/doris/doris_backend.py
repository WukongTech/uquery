"""Initialize Ibis module."""
from __future__ import annotations

# __version__ = "7.0.0"

from ibis import examples, util
from ibis.backends.base import BaseBackend
from ibis.common.exceptions import IbisError
from ibis.config import options
from ibis.expr import api
from ibis.expr import types as ir
from ibis.expr.api import *  # noqa: F403
from ibis.expr.operations import udf
import ibis.expr.operations as ops

import pandas as pd

import warnings
from typing import TYPE_CHECKING, Literal

import sqlalchemy as sa
from sqlalchemy.dialects import mysql
from sqlalchemy_doris import dialect
from sqlalchemy_doris import datatype

import ibis.expr.schema as sch
from ibis import util
from ibis.backends.base import CanCreateDatabase
from ibis.backends.base.sql.alchemy import BaseAlchemyBackend

# from ibis.backends.mysql.datatypes import MySQLDateTime, MySQLType

from uquery.backends.doris.datatype import MySQLDateTime, MySQLType
from uquery.backends.doris.compiler_sa import DorisCompiler


if TYPE_CHECKING:
    from collections.abc import Iterable

    import ibis.expr.datatypes as dt


__all__ = [  # noqa: PLE0604
    "api",
    "examples",
    "ir",
    "udf",
    "util",
    "DorisBackend",
    "IbisError",
    "options",
    *api.__all__,
]

_KNOWN_BACKENDS = ["heavyai"]


def __dir__() -> list[str]:
    """Adds tab completion for ibis backends to the top-level module."""

    out = set(__all__)
    out.update(ep.name for ep in util.backend_entry_points())
    return sorted(out)





class DorisBackend(BaseAlchemyBackend, CanCreateDatabase):
    name = "doris"
    compiler = DorisCompiler
    supports_create_or_replace = False

    def do_connect(
        self,
        host: str = "localhost",
        user: str | None = None,
        password: str | None = None,
        port: int = 3306,
        database: str | None = None,
        url: str | None = None,
        driver: Literal["pymysql"] = "pymysql",
        charset: str= "utf8mb4",
        **kwargs,
    ) -> None:
        """Create an Ibis client using the passed connection parameters.

        Parameters
        ----------
        host
            Hostname
        user
            Username
        password
            Password
        port
            Port
        database
            Database to connect to
        url
            Complete SQLAlchemy connection string. If passed, the other
            connection arguments are ignored.
        driver
            Python MySQL database driver
        kwargs
            Additional keyword arguments passed to `connect_args` in
            `sqlalchemy.create_engine`. Use these to pass dialect specific
            arguments.

        Examples
        --------
        >>> import os
        >>> import getpass
        >>> host = os.environ.get("IBIS_TEST_MYSQL_HOST", "localhost")
        >>> user = os.environ.get("IBIS_TEST_MYSQL_USER", getpass.getuser())
        >>> password = os.environ.get("IBIS_TEST_MYSQL_PASSWORD")
        >>> database = os.environ.get("IBIS_TEST_MYSQL_DATABASE", "ibis_testing")
        >>> con = connect(database=database, host=host, user=user, password=password)
        >>> con.list_tables()  # doctest: +ELLIPSIS
        [...]
        >>> t = con.table("functional_alltypes")
        >>> t
        MySQLTable[table]
          name: functional_alltypes
          schema:
            id : int32
            bool_col : int8
            tinyint_col : int8
            smallint_col : int16
            int_col : int32
            bigint_col : int64
            float_col : float32
            double_col : float64
            date_string_col : string
            string_col : string
            timestamp_col : timestamp
            year : int32
            month : int32
        """
        # if driver != "pymysql":
        #     raise NotImplementedError("pymysql is currently the only supported driver")
        alchemy_url = self._build_alchemy_url(
            url=url,
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            driver=f"doris+{driver}"
        )

        kwargs['charset'] = charset

        # alchemy_url = f"doris://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"

        engine = sa.create_engine(
            alchemy_url, poolclass=sa.pool.StaticPool, connect_args=kwargs
        )

        @sa.event.listens_for(engine, "connect")
        def connect(dbapi_connection, connection_record):
            with dbapi_connection.cursor() as cur:
                pass
                # try:
                #     cur.execute("SET @@session.time_zone = 'UTC'")
                # except sa.exc.OperationalError:
                #     warnings.warn("Unable to set session timezone to UTC.")
        super().do_connect(engine)

    def connect(self, *args, **kwargs):
        """Connect to the database.

        Parameters
        ----------
        *args
            Mandatory connection parameters, see the docstring of `do_connect`
            for details.
        **kwargs
            Extra connection parameters, see the docstring of `do_connect` for
            details.

        Notes
        -----
        This creates a new backend instance with saved `args` and `kwargs`,
        then calls `reconnect` and finally returns the newly created and
        connected backend instance.

        Returns
        -------
        BaseBackend
            An instance of the backend
        """
        # print('call connect')
        new_backend = self.__class__(*args, **kwargs)
        new_backend.reconnect()
        return new_backend

    @property
    def current_database(self) -> str:
        return self._scalar_query(sa.select(sa.func.database()))

    @staticmethod
    def _new_sa_metadata():
        meta = sa.MetaData()

        @sa.event.listens_for(meta, "column_reflect")
        def column_reflect(inspector, table, column_info):
            if isinstance(column_info["type"], mysql.DATETIME):
                column_info["type"] = MySQLDateTime()
            if isinstance(column_info["type"], datatype.DOUBLE):
                column_info["type"] = mysql.DOUBLE(asdecimal=False) # 暂时使用mysql版本代替
            if isinstance(column_info["type"], mysql.FLOAT):
                column_info["type"] = mysql.FLOAT(asdecimal=False)

        # @sa.event.listens_for(meta, "column_reflect")
        # def column_reflect(inspector, table, column_info):
        #     if isinstance(column_info["type"], datatype.sqltypes.DATETIME):
        #         column_info["type"] = MySQLDateTime()
        #     if isinstance(column_info["type"], mysql.DOUBLE):
        #         column_info["type"] = mysql.DOUBLE(asdecimal=False)
        #     if isinstance(column_info["type"], mysql.FLOAT):
        #         column_info["type"] = mysql.FLOAT(asdecimal=False)

        return meta

    def list_databases(self, like: str | None = None) -> list[str]:
        # In MySQL, "database" and "schema" are synonymous
        databases = self.inspector.get_schema_names()
        return self._filter_with_like(databases, like)

    def _metadata(self, table: str) -> Iterable[tuple[str, dt.DataType]]:
        with self.begin() as con:
            result = con.exec_driver_sql(f"DESCRIBE {table}").mappings().all()

        for field in result:
            name = field["Field"]
            type_string = field["Type"]
            is_nullable = field["Null"] == "YES"
            yield name, MySQLType.from_string(type_string, nullable=is_nullable)

    def _get_schema_using_query(self, query: str):
        table = f"__ibis_mysql_metadata_{util.guid()}"

        with self.begin() as con:
            con.exec_driver_sql(f"CREATE TEMPORARY TABLE {table} AS {query}")
            result = con.exec_driver_sql(f"DESCRIBE {table}").mappings().all()
            con.exec_driver_sql(f"DROP TABLE {table}")

        fields = {}
        for field in result:
            name = field["Field"]
            type_string = field["Type"]
            is_nullable = field["Null"] == "YES"
            fields[name] = MySQLType.from_string(type_string, nullable=is_nullable)

        return sch.Schema(fields)

    def _get_temp_view_definition(
        self, name: str, definition: sa.sql.compiler.Compiled
    ) -> str:
        yield f"CREATE OR REPLACE VIEW {name} AS {definition}"

    def create_database(self, name: str, force: bool = False) -> None:
        name = self._quote(name)
        if_exists = "IF NOT EXISTS " * force
        with self.begin() as con:
            con.exec_driver_sql(f"CREATE DATABASE {if_exists}{name}")

    def drop_database(self, name: str, force: bool = False) -> None:
        name = self._quote(name)
        if_exists = "IF EXISTS " * force
        with self.begin() as con:
            con.exec_driver_sql(f"DROP DATABASE {if_exists}{name}")

    def insert_dataframe(
        self, table_name: str, df: pd.DataFrame, schema=None, overwrite: bool = False
    ) -> None:
        namespace = ops.Namespace(schema=schema)

        t = self._get_sqla_table(table_name, namespace=namespace)
        with self.con.begin() as con:
            if overwrite:
                con.execute(t.delete())
            con.execute(t.insert(), df.to_dict(orient="records"))


    def insert(
        self,
        table_name: str,
        obj: pd.DataFrame | ir.Table | list | dict,
        database: str | None = None,
        overwrite: bool = False,
    ) -> None:
        """Insert data into a table.

        Parameters
        ----------
        table_name
            The name of the table to which data needs will be inserted
        obj
            The source data or expression to insert
        database
            Name of the attached database that the table is located in.
        overwrite
            If `True` then replace existing contents of table

        Raises
        ------
        NotImplementedError
            If inserting data from a different database
        ValueError
            If the type of `obj` isn't supported
        """

        import pandas as pd

        if database == self.current_database:
            # avoid fully qualified name
            database = None

        # if database is not None:
        #     raise NotImplementedError(
        #         "Inserting data to a table from a different database is not "
        #         "yet implemented"
        #     )



        # If we've been passed a `memtable`, pull out the underlying dataframe
        if isinstance(obj, ir.Table) and isinstance(
            in_mem_table := obj.op(), ops.InMemoryTable
        ):
            obj = in_mem_table.data.to_frame()

        if isinstance(obj, pd.DataFrame):
            self.insert_dataframe(table_name, obj, schema=database, overwrite=overwrite)
        elif isinstance(obj, ir.Table):
            schema_str = database  # We set scheme equivalent to database in doris
            to_table_expr = self.table(table_name, database=database, schema=schema_str)
            to_table_schema = to_table_expr.schema()

            if overwrite:
                self.drop_table(table_name, database=database)
                self.create_table(table_name, schema=to_table_schema, database=database)

            to_table = self._get_sqla_table(
                table_name, namespace=ops.Namespace(database=database, schema=schema_str)
            )

            from_table_expr = obj

            if from_table_expr is not None:
                compiled = from_table_expr.compile()
                columns = [
                    self.con.dialect.normalize_name(c) for c in from_table_expr.columns
                ]
                with self.begin() as bind:
                    bind.execute(to_table.insert().from_select(columns, compiled))
        elif isinstance(obj, (list, dict)):
            to_table = self._get_sqla_table(
                table_name, namespace=ops.Namespace(database=database)
            )

            with self.begin() as bind:
                if overwrite:
                    bind.execute(to_table.delete())
                bind.execute(to_table.insert().values(obj))

        else:
            raise ValueError(
                "No operation is being performed. Either the obj parameter "
                "is not a pandas DataFrame or is not a ibis Table."
                f"The given obj is of type {type(obj).__name__} ."
            )


    # def _to_sqlglot(
    #     self, expr: ir.Expr, limit: str | None = None, params=None, **_: Any
    # ):
    #     """Compile an Ibis expression to a sqlglot object."""
    #     table_expr = expr.as_table()
    #
    #     if limit == "default":
    #         limit = ibis.options.sql.default_limit
    #     if limit is not None:
    #         table_expr = table_expr.limit(limit)
    #
    #     if params is None:
    #         params = {}
    #
    #     sql = translate(table_expr.op(), params=params)
    #     assert not isinstance(sql, sg.exp.Subquery)
    #
    #     if isinstance(sql, sg.exp.Table):
    #         sql = sg.select(STAR).from_(sql)
    #
    #     assert not isinstance(sql, sg.exp.Subquery)
    #     return sql
    #
    # def compile(
    #     self, expr: ir.Expr, limit: str | None = None, params=None, **kwargs: Any
    # ):
    #     """Compile an Ibis expression to a ClickHouse SQL string."""
    #     return self._to_sqlglot(expr, limit=limit, params=params, **kwargs).sql(
    #         dialect=self.name, pretty=True
    #     )
    #
    # def _to_sql(self, expr: ir.Expr, **kwargs) -> str:
    #     return self.compile(expr, **kwargs)


def doris(name='doris'):
    """Load backends in a lazy way with `ibis.<backend-name>`.

    This also registers the backend options.

    Examples
    --------
    >>> import ibis
    >>> con = ibis.sqlite.connect(...)

    When accessing the `sqlite` attribute of the `ibis` module, this function
    is called, and a backend with the `sqlite` name is tried to load from
    the `ibis.backends` entrypoints. If successful, the `ibis.sqlite`
    attribute is "cached", so this function is only called the first time.
    """
    # entry_points = {ep for ep in util.backend_entry_points() if ep.name == name}
    #
    # if not entry_points:
    #     msg = f"module 'ibis' has no attribute '{name}'. "
    #     if name in _KNOWN_BACKENDS:
    #         msg += f"""If you are trying to access the '{name}' backend,
    #                 try installing it first with `pip install 'ibis-framework[{name}]'`"""
    #     raise AttributeError(msg)
    #
    # if len(entry_points) > 1:
    #     raise RuntimeError(
    #         f"{len(entry_points)} packages found for backend '{name}': "
    #         f"{entry_points}\n"
    #         "There should be only one, please uninstall the unused packages "
    #         "and just leave the one that needs to be used."
    #     )

    import types

    import ibis

    # (entry_point,) = entry_points
    # try:
    #     module = entry_point.load()
    # except ImportError as exc:
    #     raise ImportError(
    #         f"Failed to import the {name} backend due to missing dependencies.\n\n"
    #         f"You can pip or conda install the {name} backend as follows:\n\n"
    #         f'  python -m pip install -U "ibis-framework[{name}]"  # pip install\n'
    #         f"  conda install -c conda-forge ibis-{name}           # or conda install"
    #     ) from exc
    backend = DorisBackend()
    # The first time a backend is loaded, we register its options, and we set
    # it as an attribute of `ibis`, so `__getattr__` is not called again for it
    backend.register_options()

    # We don't want to expose all the methods on an unconnected backend to the user.
    # In lieu of a full redesign, we create a proxy module and add only the methods
    # that are valid to call without a connect call. These are:
    #
    # - connect
    # - compile
    # - has_operation
    # - add_operation
    # - _from_url
    # - _to_sql
    # - _sqlglot_dialect (if defined)
    #
    # We also copy over the docstring from `do_connect` to the proxy `connect`
    # method, since that's where all the backend-specific kwargs are currently
    # documented. This is all admittedly gross, but it works and doesn't
    # require a backend redesign yet.

    def connect(*args, **kwargs):
        return backend.connect(*args, **kwargs)

    connect.__doc__ = backend.do_connect.__doc__
    connect.__wrapped__ = backend.do_connect
    connect.__module__ = f"ibis.{name}"

    proxy = types.ModuleType(f"ibis.{name}")
    setattr(ibis, name, proxy)
    proxy.connect = connect
    proxy.compile = backend.compile
    proxy.has_operation = backend.has_operation
    proxy.add_operation = backend.add_operation
    proxy.name = name
    proxy._from_url = backend._from_url
    proxy._to_sql = backend._to_sql
    if (dialect := getattr(backend, "_sqlglot_dialect", None)) is not None:
        proxy._sqlglot_dialect = dialect
    # Add any additional methods that should be exposed at the top level
    for name in getattr(backend, "_top_level_methods", ()):
        setattr(proxy, name, getattr(backend, name))

    proxy.insert = backend.insert

    return proxy


ibis_doris = doris()
