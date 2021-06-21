"""Classes used by CloudInventario."""
import requests
import datetime
import json
import logging
import importlib
from pprint import pprint

import cloudinventario.platform as platform

class CloudEncoder(json.JSONEncoder):
  def default(self, z):
    if isinstance(z, datetime.datetime):
      return (str(z))
    else:
      return super().default(z)

class CloudCollector:
  """Cloud collector."""

  def __init__(self, name, config, defaults, options):
    self.name = name
    self.config = config
    self.defaults = defaults
    self.options = options
    self.allow_self_signed = options.get('allow_self_signed', config.get('allow_self_signed', False))
    if self.allow_self_signed:
      requests.packages.urllib3.disable_warnings()
    self.verify_ssl = self.options.get('verify_ssl_certs', config.get('verify_ssl_certs', True))
    self.resource_manager = None
    self.res_collectors = self.load_res_collectors(self.config.get("collect"), options["tasks"]) or []  # TODO: check whether "options" implemented as intended

  def __pre_request(self):
    pass

  def __post_request(self):
    pass

  def login(self):
    self.__pre_request()
    try:
      session = self._login()
      self.resource_login(session)
    except:
      logging.error("Failed to login the following collector: {}".format(self.name))
      raise
    finally:
      self.__post_request()

  def resource_login(self, session):
    for resource, res_collector in self.res_collectors.items():
      try:
        logging.info("Passing session to: {}".format(resource))
        res_collector.login(session)
      except Exception:
        logging.error("Failed to pass session to the following resource: {}".format(resource))
        raise

  def fetch(self, collect = None):
    self.__pre_request()
    try:
      data = []
      data.extend(self.resource_fetch())
      data.extend(self._fetch(collect))
      return data
    except:
      raise
    finally:
      self.__post_request()

  def resource_fetch(self):
    data = []
    try:
      for res in self.resource_manager.dep_classif["dep_only"]:
        self.res_collectors[res].fetch()
      for res in self.resource_manager.dep_classif["dep_not_only"]:
        data.extend(self.res_collectors[res].fetch())
      for res in self.resource_manager.dep_classif["not_dep"]:
        data.extend(self.res_collectors[res].fetch())
      return data
    except Exception:
      logging.error("Failed to fetch the following resource collector: {}".format(res))
      raise

  def logout(self):
    self.__pre_request()
    try:
      res = self._logout()
      return res
    except:
      raise
    finally:
      self.__post_request()

  def get_resource_data(self, resource):
    try:
      return self.rd[resource]
    except Exception:
      logging.error("Failed to get data of the following resource: {}".format(resource))
      raise

  def delete_resource_data(self, resource):
    try:
      self.rd[resource] = ""
    except Exception:
      logging.error("Failed to delete data of the following resource: {}".format(resource))
      raise

  def set_resource_data(self, resource, new_data):
    try:
      self.rd[resource] = new_data
    except Exception:
      logging.error("Failed to set data of the following resource: {}".format(resource))
      raise

  def load_res_collectors(self, res_list, tasks):
    try:
      res_collectors = self._load_res_collectors(res_list, tasks)
      return res_collectors
    except:
      raise

  def new_record(self, rectype, attrs, details):

    attr_keys = ["created",
                 "name", "project", "location", "description", "id",
                 "cpus", "memory", "disks", "storage", "primary_ip",
                 "os", "os_family",
                 "is_on",
                 "owner"]
    attrs = {**self.defaults, **attrs}

    attr_json_keys = [ "networks", "storages", "tags"]
    rec = {
      "type": rectype,
      "source": self.name,
      "attributes": None
    }

    for key in attr_keys:
      if not attrs.get(key):
        rec[key] = None
      else:
        rec[key] = attrs[key]
        del(attrs[key])

#    for key in attr_tag_keys:
#      data = attrs.get(key, [])
#      rec[key] = ",".join(map(lambda k: "{}={}".format(k, data[k]), data.keys()))

    for key in attr_json_keys:
      if not attrs.get(key):
        rec[key] = '[]'
      else:
        rec[key] = json.dumps(attrs[key], default=str) # added default=str -> problem with AttachTime,CreateTime
        del(attrs[key])

    for key in ["cluster", "status"]: # fields that possibly contain data structures
      value = attrs.get(key)
      if not value:
        rec[key] = None
      else:
        if type(value) in [dict, list]:
          rec[key] = json.dumps(value, default=str)
        else:
          rec[key] = value

    if "os_family" not in attrs.keys() and rec.get("os"):
      rec["os_family"] = platform.get_os_family(rec.get("os"), rec.get("description"))

    if rec.get("os"):
      rec["os"] = platform.get_os(rec.get("os"), rec.get("description"))

    if len(attrs) > 0:
      rec["attributes"] = json.dumps(attrs, default=str)
    rec["details"] = json.dumps(details, cls=CloudEncoder, default=str)
    return rec

class CloudInvetarioResourceManager:

  def __init__(self, res_list, COLLECTOR_PKG, collector):
    self.res_list = res_list
    self.COLLECTOR_PKG = COLLECTOR_PKG
    self.collector = collector
    self.dep_classif = {  # dependency_classification
      "dep_only": set(),
      "dep_not_only": set(),
      "not_dep": set()
    }


  def get_resource_objs(self, res_dep_list = None):
    obj_list = {}

    # sorting based on whether a resource needs priority in fetching or not
    for resource in set(res_dep_list):
      if resource in self.res_list:
        self.dep_classif["dep_not_only"].add(resource)
      else:
        self.dep_classif["dep_only"].add(resource)
    self.dep_classif["not_dep"] = set(self.res_list) - set(res_dep_list)

    res_list = []
    res_list.extend(self.dep_classif["dep_only"] or [])
    res_list.extend(self.dep_classif["dep_not_only"] or [])
    res_list.extend(self.dep_classif["not_dep"] or [])

    for res in res_list:
      try:
        mod_name = self.COLLECTOR_PKG + ".res_collectors." + res
        logging.info("Importing module: {}".format(mod_name))
        res_mod = importlib.import_module(mod_name)
      except Exception as e:
        logging.error("Failed to load the following module:{}, reason: {}".format(mod_name, e))
        continue
      obj_list[res] = res_mod.get_resource_obj(self.collector)

    return obj_list

class CloudInvetarioResource():

  def __init__(self, res_type, collector):
    self.res_type = res_type
    self.collector = collector
    self.session = None
    self.client = None
    self.data = None

  def login(self, session):
    try:
      self._login(session)
    except Exception:
      raise

  def fetch(self):
    try:
      logging.info("Fetching the following type of resource: {}".format(self.res_type))
      self.data = self._fetch()
      return self.data
    except Exception:
      logging.error("Failed to fetch the data of the following type of cloud resource: {}". format(self.res_type))
      raise

  def process_resource(self, resource_data):
    try:
      logging.info("Processing the following type of resource: {}".format(self.res_type))
      data = self._process_resource(resource_data)
      return data
    except Exception:
      logging.error("Failed to process the following type of resource: {}".format(self.res_type))
      raise

  def get_client(self):
    try:
      client = self._get_client()
      return client
    except Exception:
      logging.error("Failed to get the client of the following type of resource: {}".format(self.res_type))
      raise

  def get_data(self):
    try:
      if self.data is None:
        self.data = self.fetch()
      return self.data
    except Exception:
      logging.error("Failed to get the data of the following of resource: {}".format(self.res_type))

