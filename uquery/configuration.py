import pathlib
import toml
import platform
import copy
import pydash
from uquery.util import SingletonType

DEFAULT_CONFIG = {
    "uquery": {
        "endpoint": {}
    }
}


if platform.system() == "Windows":
    DEFAULT_CONFIG_FILE = str(pathlib.Path().home().joinpath('.uquery.toml'))
    USER_CONFIG_FILE = str(pathlib.Path().home().joinpath('.uquery.toml'))
elif platform.system() == "Linux":
    DEFAULT_CONFIG_FILE = "/etc/uquery/uquery.toml"
    USER_CONFIG_FILE = str(pathlib.Path().home().joinpath('.uquery.toml'))
else:
    raise Exception("Unsupported system:", platform.system())


class Configuration(metaclass=SingletonType):
    def __init__(self):
        self._config = copy.deepcopy(DEFAULT_CONFIG)
        self._config_loaded = True
        self._use_system_config = False
        self._use_user_config = False
        try:
            self._config = pydash.objects.merge(self._config, toml.load(DEFAULT_CONFIG_FILE))
            self._use_system_config = True
        except FileNotFoundError:
            pass
        try:
            self._config = pydash.objects.merge(self._config, toml.load(USER_CONFIG_FILE))
            self._use_user_config = True
        except FileNotFoundError:
            pass

        try:
            self._config = pydash.objects.merge(self._config, toml.load('.uquery.toml'))
            self._use_local_config = True
        except FileNotFoundError:
            pass

        # self._default_db_loc = None
        # self._default_dblink = None

    @property
    def use_system_config(self):
        return self._use_system_config

    @property
    def use_user_config(self):
        return self._use_user_config

    @property
    def config_loaded(self):
        return self._config_loaded

    def load_config(self, config_path):
        self._config_path = config_path
        self._config = toml.load(self._config_path)
        self._config_loaded = True

    @property
    def config(self):
        return self._config

    @property
    def oracle_client_path(self):
        return self._config['oracle_client']

    @property
    def endpoint(self):
        return self._config['endpoint']

    @property
    def uquery(self):
        return self._config['uquery']


    def endpoint_config(self, name):
        return self.uquery['endpoint'][name]

    # @property
    # def tushare_token(self):
    #     return self._config['tushare']['token']

    # @property
    # def default_db_loc(self):
    #     """
    #     read_sql 默认使用的db_loc
    #     :param db_loc:
    #     :return:
    #     """
    #     if self._default_db_loc is None:
    #         return self._config['uquery']['db_loc']
    #     return self._default_db_loc

    # @default_db_loc.setter
    # def default_db_loc(self, db_loc):
    #     self._default_db_loc = db_loc

    def update_config(self, config_):
        if isinstance(config_, str):
            config_ = toml.load(config_)
        self._config = pydash.objects.merge(self._config, config_)


config = Configuration()
