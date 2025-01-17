import atexit
import pathlib

import pandas as pd
import requests
from requests.auth import HTTPBasicAuth
import base64
import random
import json





def stream_load_df(
        df: pd.DataFrame,
        host,
        username,
        password,
        table_name,
        db_name,
        label,
        buffer_size=2**28,
        random_label=True,
        sep=',',
        tmp_dir='/dev/shm'
):
    columns = ','.join(df.columns)
    session = StreamLoadSession(
        host=host,
        username=username,
        password=password,
        buffer_size=buffer_size,
        table_name=table_name,
        db_name=db_name,
        columns=columns,
        random_label=random_label,
        label=label,
        column_separator=sep
    )


    tmp_path = pathlib.Path(tmp_dir) / f'doris_stream_loader_{session.label}'
    file = tmp_path / 'df.csv'
    try:
        tmp_path.mkdir()
        df.to_csv(file, index=False)
        session.stream_load_data(tmp_path / 'df.csv')
        session.clean_up()  # 强制刷新缓冲区
    finally:
        file.unlink()
        tmp_path.rmdir()



class StreamLoadSession:
    def __init__(self, *, host, db_name, table_name, username, password,
                 port=8030, buffer_size=65536, columns=None, label='stream_load', random_label=False, column_separator=','):
        self.db_name = db_name
        self.table_name = table_name
        self.username = username
        self.password = password

        self.url = f'http://{host}:{port}/api/{self.db_name}/{self.table_name}/_stream_load'

        print('load url:', self.url)
        self.auth = HTTPBasicAuth(self.username, self.password)
        self.session = requests.sessions.Session()
        self.session.should_strip_auth = lambda old_url, new_url: False  # Don't strip auth
        self.label = label
        if random_label:
            self.label = self.label + f"_{random.randint(0, 100000):05}"
        self.headers = {
            'Content-Type': 'text/plain; charset=UTF-8',
            # 'label': 'test_stream_load_20401',
            'format': 'csv',
            # "column_separator":  column_separator,
            'Expect': '100-continue',
            # 'Authorization': 'Basic ' + base64.b64encode((username + ':' + password).encode('utf-8')).decode('ascii')
        }
        if column_separator != '\t':
            self.headers['column_separator'] = column_separator
        if columns is not None:
            self.headers['columns'] = columns

        self.part_counter = 0

        self.buffer = []
        self.data_len = 0
        self.buffer_size = buffer_size

        atexit.register(self.clean_up)

    def send_data(self):
        print('sent data:', self.label, f"{float(self.data_len) / 1024.0 /1024.0}MB")
        # print(self.buffer)
        headers = {**self.headers}
        headers['label'] = self.label + '_part' + str(self.part_counter)
        self.part_counter += 1
        data = ''.join(self.buffer)
        resp = self.session.request(
                'PUT', url=self.url,
                data=data, # open('/path/to/your/data.csv', 'rb'),
                headers=headers, auth=self.auth
            )


        # print(resp.status_code, resp.reason)
        resp_pack = json.loads(resp.text)
        if resp_pack["Status"] != 'Success':
            print(resp_pack)
        # print(resp.text)

    def put_data(self, data_line):
        if self.data_len == 0:
            # 缓冲区大小至少要大于一行数据
            assert self.buffer_size > len(data_line)

        total_len = self.data_len + len(data_line)
        if total_len >= self.buffer_size: # 缓冲区已满
            self.send_data()
            # 清空缓冲区并放入新数据
            s = data_line + '\n'

            self.buffer = [s]
            self.data_len = len(s)
        else:
            s = data_line + '\n'
            self.buffer.append(s)
            self.data_len += len(s) + 1

    def stream_load_data(self, file_path, skip_header=True):
        with open(file_path, 'r') as f:
            if skip_header:
                s = f.readline()  # skip header
            while True:
                s = f.readline()
                if s == '':
                    break
                self.put_data(s[:-1])


    def clean_up(self):
        if self.data_len > 0:
            self.send_data()
            self.data_len = 0
