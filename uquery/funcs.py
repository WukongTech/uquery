from __future__ import annotations

from urllib.parse import quote_plus

from tqdm import tqdm
import pandas as pd
from pandas.io.sql import pandasSQL_builder
import sqlalchemy
from sqlalchemy.engine.reflection import Inspector
from uquery.configuration import config
from uquery.backends.doris.stream_loader import stream_load_df
from uquery.engine import create_engine, create_flight_sql_connection, is_flight_sql
from uquery.dialect import add_oracle_dblink_param, has_oracle_dblink


def has_table(table_name, con):
    pandas_sql = pandasSQL_builder(con)
    return pandas_sql.has_table(table_name)


def inspect(table_name, db_loc=None):
    if db_loc is None:
        db_loc = config.default_db_loc

    engine, writable = create_engine(db_loc)

    # if not has_oracle_dblink(db_loc):
    insp: Inspector = sqlalchemy.inspect(engine)
    return insp.get_columns(table_name)

    # with engine.connect() as connection:
    #     # cursor = connection.cursor()
    #     sql = add_oracle_dblink_param(f"select * from {table_name} where 1=0", db_loc)
    #     cursor = connection.execute(sql).cursor
    #     return cursor.description


def read_flight_sql(sql: str, db_loc):
    conn = create_flight_sql_connection(db_loc)
    cursor = conn.cursor()
    cursor.execute(sql)
    data = cursor.fetchallarrow().to_pandas()
    cursor.close()
    conn.close()
    return data


def read_sql(sql: str | sqlalchemy.text, *, endpoint: str | None = None, table_name=None, parse_dates=None,
             sql_params=None, **kwargs):
    """
    从数据库中使用sql读取数据
    :param sql:
    :param db_loc:
    :param table_name: 用于校验表是否存在
    :param parse_dates:
    :param sql_params: 使用函数参数进行sql参数绑定，防止sql注入。仅当sql参数为str类型时有效
    :param dblink: 数据表使用了oracle的dblink
    :param kwargs:

    :return:
    """

    db_loc = endpoint
    # if db_loc is None:
    #     db_loc = config.default_db_loc

    if is_flight_sql(db_loc):
        return read_flight_sql(sql, db_loc)


    engine, writable = create_engine(db_loc)

    if engine.name == 'oracle':
        assert isinstance(sql, str)  # oracle 暂时仅支持字符串
        sql = add_oracle_dblink_param(sql, db_loc)

    if isinstance(sql, str):
        op = sql[:6].upper()
    else:
        op = sql.text[:6].upper()
    assert op == 'SELECT'

    if isinstance(sql, str) and sql_params is not None:
        sql = sqlalchemy.text(sql).bindparams(**sql_params)

    with engine.connect() as conn:
        if table_name is not None:
            assert has_table(table_name, conn)
        data = pd.read_sql(sql, con=conn, parse_dates=parse_dates, **kwargs)
    return data


def to_sql(data: pd.DataFrame, table_name: str, db_loc: str, if_exists='fail', index=True, primary_key=None, **kwargs):
    engine, writable = create_engine(db_loc)
    if not writable:
        raise Exception(f'db_loc `{db_loc}` is not writable')
    with engine.connect() as conn:
        data.to_sql(name=table_name, con=conn, if_exists=if_exists, index=index, **kwargs)
        if primary_key is not None:
            if isinstance(primary_key, list):
                primary_key = ','.join(primary_key)
            conn.execute(f'ALTER TABLE {table_name} ADD PRIMARY KEY ({primary_key} )')


def stream_to_sql(data: pd.DataFrame, table_name: str, endpoint: str,
                  buffer_size=2**28,
                  # random_label=True,
                  sep=',',
                  tmp_dir='/dev/shm'
                  ):
    db_config = config.endpoint_config(endpoint)

    assert db_config['db_type'] == 'doris'
    assert db_config['writable']

    host, port = db_config['host'], db_config['port']
    user, password = db_config['user'], db_config['password']
    password = quote_plus(password)
    database = db_config['database']

    stream_load_df(
        df=data,
        host=host,
        username=user,
        password=password,
        table_name=table_name,
        db_name=database,
        label=table_name,
        buffer_size=buffer_size,
        # random_label=random_label,
        sep=sep,
        tmp_dir=tmp_dir
    )



def sync_data(select_stmt, src_db_loc, dst_db_loc, table_name, *,
              schema=None, if_exists='fail', chunk_size=100000,
              progress_bar=True):
    assert if_exists in ('replace', 'append', 'fail')

    if isinstance(select_stmt, str):
        op = select_stmt[:6].upper()
    else:
        op = select_stmt.text[:6].upper()
    assert op == 'SELECT'

    # src_engine, _ = create_engine(src_db_loc)
    # dst_engine, writable = create_engine(dst_db_loc)
    # assert writable
    # with src_engine.connect() as src_conn:
    #     result_proxy = src_conn.execute(select_stmt)
    #     result_proxy.f

    data = read_sql(select_stmt, db_loc=src_db_loc, chunksize=chunk_size)

    if_exists_tag = if_exists
    for entry in tqdm(data, disable=not progress_bar):
        to_sql(entry, table_name=table_name, db_loc=dst_db_loc,
               index=False, if_exists=if_exists_tag, schema=schema, method='multi')
        if_exists_tag = 'append'
