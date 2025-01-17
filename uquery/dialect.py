import re
from functools import partial
import sqlparse
from uquery.configuration import config


# def add_dblink(matched, link_name):
#     matched_part = matched.group()
#     if matched.groupdict()['table_name1'] is not None:
#         table_name = matched.groupdict()['table_name1']
#     elif matched.groupdict()['table_name2'] is not None:
#         table_name = matched.groupdict()['table_name2']
#     else:
#         raise ValueError("Table not found")
#
#     if table_name.find('@') != -1:
#         raise ValueError(f'Existed dblink in {table_name}')
#
#     table_with_link = table_name + '@' + link_name
#     return matched_part.replace(table_name, table_with_link)


def get_db_link(db_loc):
    db_config = config.endpoint_config(db_loc)
    try:
        db_link = db_config['db_link']
    except KeyError:
        db_link = None
    return db_link


# def add_oracle_dblink_param(sql, db_loc):
#     db_link = get_db_link(db_loc)
#     if db_link is None:
#         return sql
#
#     pattern = re.compile(r"\s+from\s+(?P<table_name1>.*?)(\s+where\s+|\s+order\s+|\s+group\s+)|\s+from\s+(?P<table_name2>.+)", re.I)
#
#     func = partial(add_dblink, link_name=db_link)
#     return pattern.sub(func, sql)


def transform_token_value(token, transform_func):
    value = transform_func(token.value)
    token.value = value
    token.normalized = value.upper() if token.is_keyword else token.value

    token = token.tokens[0]
    value = transform_func(token.value)
    token.value = value
    token.normalized = value.upper() if token.is_keyword else token.value


def add_oracle_dblink_param(sql, db_loc):
    db_link = get_db_link(db_loc)
    if db_link is None:
        return sql

    parsed = sqlparse.parse(sql)[0]
    for token in parsed.tokens:
        if isinstance(token, sqlparse.sql.Identifier):
            # print('is Identifier', token)
            if '@' in token.value:
                raise ValueError('DB link existed in sql', token.value)
            transform_token_value(token, lambda x: f"{x}@{db_link}")
    return str(parsed)


def has_oracle_dblink(db_loc):
    db_config = config.endpoint_config(db_loc)
    if db_config['db_type'] == 'oracle':
        if get_db_link(db_loc) is not None:
            return True
    return False
