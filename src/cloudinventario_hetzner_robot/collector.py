import logging, re, sys, asyncio, time
from pprint import pprint
from hetzner.robot import Robot


from cloudinventario.helpers import CloudCollector



def setup(name, config, defaults, options):
  return CloudCollectorHetznerRobot(name, config, defaults, options)

class CloudCollectorHetznerRobot(CloudCollector):

  def __init__(self, name, config, defaults, options):
    super().__init__(name, config, defaults, options)


  def _login(self):
    self.robot = Robot(self.config["user"], self.config["password"])
    return True

  def _fetch(self, collect):
     res = []
     servers = self.robot.servers
     for server in servers:
       res.append(self._process_server(server))
       time.sleep(1/4)
     return res
  
  def _process_server(self, server):
     networks = []
     id = 0
     for iface in server.subnets:
        id = id + 1
        networks.append({
          "id": id,
          "ip": iface.net_ip,
          "mask": iface.mask,
          "gateway": iface.gateway,
          "failover": iface.failover,
        })

     server_data = {
        "id": server.number,
        "name": server.name,
        "primary_ip": server.ip,
        "status": server.status,
        "networks": networks,
        "cluster": server.datacenter,
        "product": server.product,
    }


     return self.new_record('server', server_data, server)
    
  def _logout(self):
    self.robot = None


