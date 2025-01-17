import pandas as pd
import pytest

import uquery
from uquery.backends.doris.doris_backend import ibis_doris
from uquery.configuration import Configuration, config



@pytest.fixture()
def doris_connection(db_info):

    info = db_info
    # print(info)
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


@pytest.fixture
def mock_config(db_info, monkeypatch):
    def mock_db():
        return {
            'endpoint': {'test_loc': db_info}
        }

    monkeypatch.setattr(Configuration, 'uquery', mock_db())


def test_stream_load(db_info, stream_load_data_db, mock_config):

    data = pd.DataFrame({
        'trade_dt': ['20241101', '20241102', '20241103'],
        'windcode': ['TE.000001', 'TE.000001', 'TE.000001'],
        'value': [1, 2, 3]
    })

    uquery.stream_to_sql(data, 'test_data_stream', endpoint='test_loc')

    data2 = uquery.read_sql("select * from test_data_stream order by trade_dt", endpoint='test_loc')
    data2['trade_dt'] =data2['trade_dt'].map(lambda x: x.strftime('%Y%m%d'))

    assert (data == data2).sum().sum() == 9