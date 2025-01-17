
import os

import pandas as pd
import pytest
import sqlalchemy as sa


from sqlalchemy_doris import HASH

import uquery.engine





@pytest.fixture(scope='session')
def db_info():
    # print(config.config)

    return {
        'writable': True,
        'db_type': 'doris',
        'user': os.environ['DORIS_USER'],
        'password': os.environ['DORIS_PASSWORD'],
        'host': os.environ['DORIS_HOST'],
        'port': os.environ['DORIS_PORT'],
        'database': os.environ['DORIS_DATABASE'],
        'driver': 'pymysql'
    }


@pytest.fixture(scope='session')
def trade_calendar_df():
    df = pd.DataFrame({
        'trade_dt': [
            '20231122', '20231121', '20231120',
            '20231117', '20231116', '20231115', '20231114', '20231113',
            '20231110', '20231109', '20231108', '20231107', '20231106',
            '20231103', '20231102', '20231101', '20231031', '20231030',
            '20231027', '20231026', '20231025', '20231024',
        ]
    })
    return df


@pytest.fixture(scope='session')
def default_data_db(db_info, trade_calendar_df):
    info = db_info

    assert info['db_type'] == 'doris'

    metadata_obj = sa.MetaData()
    test_data_table = sa.Table(
        'test_data',
        metadata_obj,
        sa.Column('trade_dt', sa.DATE, nullable=False),
        sa.Column('windcode', sa.String(10), nullable=False),
        sa.Column('value', sa.DOUBLE, nullable=True),
        doris_unique_key=('trade_dt', 'windcode'),
        doris_distributed_by=HASH('trade_dt'),
        doris_properties={'replication_allocation': 'tag.location.default: 1'}
    )


    service_engine = uquery.engine.create_doris_engine(db_info)
    metadata_obj.create_all(service_engine)

    data_df1 = trade_calendar_df.copy()
    data_df1['windcode'] = '000001.TE'
    data_df1['value'] = pd.Series(range(len(data_df1['windcode'])))

    data_df2 = trade_calendar_df.copy()
    data_df2['windcode'] = '000002.TE'
    data_df2['value'] = pd.Series(reversed(range(len(data_df2['windcode']))))

    data = pd.concat([data_df1, data_df2])
    data.to_sql(name='test_data', con=service_engine, if_exists='append', index=False)

    yield

    metadata_obj.drop_all(service_engine, [ test_data_table])


@pytest.fixture(scope='session')
def stream_load_data_db(db_info, trade_calendar_df):
    info = db_info

    assert info['db_type'] == 'doris'
    metadata_obj = sa.MetaData()

    test_data_table = sa.Table(
        'test_data_stream',
        metadata_obj,
        sa.Column('trade_dt', sa.DATE, nullable=False),
        sa.Column('windcode', sa.String(10), nullable=False),
        sa.Column('value', sa.DOUBLE, nullable=True),
        doris_unique_key=('trade_dt', 'windcode'),
        doris_distributed_by=HASH('trade_dt'),
        doris_properties={'replication_allocation': 'tag.location.default: 1'}
    )


    service_engine = uquery.engine.create_doris_engine(db_info)
    metadata_obj.create_all(service_engine)


    yield

    metadata_obj.drop_all(service_engine, [ test_data_table])