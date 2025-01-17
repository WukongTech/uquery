import ibis
from uquery.backends.doris.doris_backend import ibis_doris


import pytest

@pytest.fixture()
def doris_connection(db_info):

    info = db_info

    assert info['db_type'] == 'doris'
    connection = ibis_doris.connect(
        user=info['user'],
        password=info['password'],
        host=info['host'],
        port=info['port'],
        database=info['database'],
        driver='pymysql'
    )

    return connection


def test_lag_over_op(default_data_db, doris_connection):
    table = doris_connection.table('test_data')
    w = ibis.window(group_by=["windcode"], order_by="trade_dt")
    result = table.mutate(
        new_value=table.value.lag().over(w)
    )
    # print(ibis.to_sql(result))
    # print(result.to_pandas())

    result_df = result.to_pandas()

    part = result_df[result_df['windcode'] == '000001.TE']
    values = part['value'].tolist()
    new_values = part['new_value'].tolist()
    assert values[0] == new_values[1]
    assert values[1] == new_values[2]


def test_mean_over_op(default_data_db, doris_connection):
    table = doris_connection.table('test_data')
    w = ibis.window(group_by="windcode", order_by="trade_dt", preceding=3, following=0)
    result = table.mutate(
        new_value=table.value.mean().over(w)
    )
    result_df = result.to_pandas()

    part = result_df[result_df['windcode'] == '000002.TE']
    # print(part)
    values = part['new_value'].tolist()
    assert values[0] == 0
    assert values[1] == 0.5
    assert values[2] == 1
    assert values[3] == 1.5

