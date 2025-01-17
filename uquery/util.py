import threading
import re
KIBANA_SPECIAL = '+ - & | ! ( ) { } [ ] ^ " ~ * ? : \\'.split(' ')




class SingletonType(type):
    _instance_lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        if not hasattr(cls, "_instance"):
            with SingletonType._instance_lock:
                if not hasattr(cls, "_instance"):
                    cls._instance = super(SingletonType, cls).__call__(*args, **kwargs)
        return cls._instance


def get_sql_table_name(sql: str):
    pattern = re.compile(r"\s+from\s+.*?(\s+where\s+|\s+order\s+|\s+group\s+)|\s+from\s+.+", re.I)
    pattern = re.compile(r"\s+from\s+.*?(\s+where\s+|\s+order\s+|\s+group\s+)|\s+from\s+.+", re.I)
    m = pattern.search(sql)
    return m
