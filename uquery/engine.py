from functools import lru_cache

import ibis
import sqlalchemy
import cx_Oracle  # user guide: https://cx-oracle.readthedocs.io/en/latest/user_guide/installation.html
import os

import adbc_driver_manager
import adbc_driver_flightsql.dbapi as flight_sql

# import oracledb
from urllib.parse import quote_plus

from uquery.configuration import config


os.environ['NLS_LANG'] = 'SIMPLIFIED CHINESE_CHINA.UTF8'


def create_oracle_engine(db_config):
    host, port, service_name = db_config['host'], db_config['port'], db_config['service_name']
    user, password = db_config['user'], db_config['password']
    password = quote_plus(password)

    connect_str = f"oracle+cx_oracle://{user}:{password}@{host}:{port}/?service_name={service_name}&encoding=UTF-8&nencoding=UTF-8"

    # oracledb.init_oracle_client()
    # engine = sqlalchemy.create_engine(connect_str)

    try:
        engine = sqlalchemy.create_engine(connect_str)
    except Exception as e:
        cx_Oracle.init_oracle_client(lib_dir=config.oracle_client_path)
        engine = sqlalchemy.create_engine(connect_str)
    return engine


def create_postgresql_engine(db_config):
    host, port = db_config['host'], db_config['port']
    user, password = db_config['user'], db_config['password']
    password = quote_plus(password)
    database = db_config['database']
    engine = sqlalchemy.create_engine(
        f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database}"
    )
    schema = db_config['schema']
    schema_engine = engine.execution_options(schema_translate_map={None: schema})
    return schema_engine


def create_doris_engine(db_config):
    try:
        driver = db_config['driver']
    except KeyError:
        driver = 'pymysql'

    host, port = db_config['host'], db_config['port']
    user, password = db_config['user'], db_config['password']
    password = quote_plus(password)
    database = db_config['database']
    engine = sqlalchemy.create_engine(
        f"doris+{driver}://{user}:{password}@{host}:{port}/{database}"
    )
    return engine



@lru_cache(maxsize=1)
def create_sqlite_engine(tag):
    # 仅用于测试环境
    e = sqlalchemy.create_engine('sqlite://')
    return e



def is_flight_sql(db_loc):
    return config.endpoint_config(db_loc)['db_type'] == 'flight_sql'


def create_flight_sql_connection(db_loc):
    info = config.endpoint_config(db_loc)
    conn = flight_sql.connect(uri=f"grpc://{info['host']}:{info['port']}", db_kwargs={
        adbc_driver_manager.DatabaseOptions.USERNAME.value: info["user"],
        adbc_driver_manager.DatabaseOptions.PASSWORD.value: info["password"],
    })

    return conn


def create_engine(db_loc):
    db_config = config.endpoint_config(db_loc)
    try:
        writable = db_config['writable']
    except KeyError:
        writable = False
    if db_config['db_type'] == 'oracle':
        return create_oracle_engine(db_config), writable
    elif db_config['db_type'] == 'postgresql':
        return create_postgresql_engine(db_config), writable
    elif db_config['db_type'] == 'doris':
        return create_doris_engine(db_config), writable
    elif db_config['db_type'] == 'sqlite':
        return create_sqlite_engine(db_loc), writable
    else:
        assert False


def create_ibis_connection(db_loc):
    db_config = config.endpoint_config(db_loc)
    try:
        writable = db_config['writable']
    except KeyError:
        writable = False

    host, port = db_config['host'], db_config['port']
    user, password = db_config['user'], db_config['password']
    password = quote_plus(password)
    database = db_config['database']

    if db_config['db_type'] == 'postgresql':
        con = ibis.postgres.connect(
            user=user,
            password=password,
            host=host,
            port=port,
            database=database,
            schema=db_config['schema']
        )
        return con, writable
    elif db_config['db_type'] == 'doris':
        try:
            driver = db_config['driver']
        except KeyError:
            driver = 'pymysql'
        from uquery.backends.doris.doris_backend import ibis_doris
        con = ibis_doris.connect(
            user=user,
            password=password,
            host=host,
            port=port,
            database=database,
            driver=driver
        )
        return con, writable

