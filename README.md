# UQuery

uQuery is a tool designed for data analysis that simplifies reading data from multiple sources.


## Usage

1. write a config file `.uquery.toml` and place it in your home directory or project working directory
```toml
[uquery.endpoint.my_data_src]
db_type = 'doris'
host = '<your db host>'
port = '<your db port>'
user = '<your db username>'
password = '<your db password>'
```

We currently support the following database types:
* oracle
* postgres
* doris


2. read data

```python
import pandas as pd
import uquery

data: pd.DataFrame = uquery.read_sql('select * from table', endpoint='my_data_src')
print(data)
```


## Installation

```bash
pip install uquery
```