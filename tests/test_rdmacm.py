from pyverbs.pyverbs_error import PyverbsError
from tests.rdmacm_utils import sync_traffic
from tests.base import RDMATestCase
import multiprocessing as mp
import pyverbs.device as d
import subprocess
import unittest
import json


class CMTestCase(RDMATestCase):
    def setUp(self):
        if self.dev_name is not None:
            net_name = self.get_net_name(self.dev_name)
            try:
                self.ip_addr = self.get_ip_address(net_name)
            except KeyError:
                raise unittest.SkipTest('Device {} doesn\'t have net interface'
                                        .format(self.dev_name))
        else:
            dev_list = d.get_device_list()
            for dev in dev_list:
                net_name = self.get_net_name(dev.name.decode())
                try:
                    self.ip_addr = self.get_ip_address(net_name)
                except IndexError:
                    continue
                else:
                    self.dev_name = dev.name.decode()
                    break
            if self.dev_name is None:
                raise unittest.SkipTest('No devices with net interface')
        super().setUp()

    @staticmethod
    def get_net_name(dev):
        out = subprocess.check_output(['ls', '/sys/class/infiniband/{}/device/net/'
                                      .format(dev)])
        return out.decode().split('\n')[0]

    @staticmethod
    def get_ip_address(ifname):
        out = subprocess.check_output(['ip', '-j', 'addr', 'show', ifname])
        loaded_json = json.loads(out.decode())
        interface = loaded_json[0]['addr_info'][0]['local']
        if 'fe80::' in interface:
            interface = interface + '%' + ifname
        return interface

    def test_rdmacm_sync_traffic(self):
        ctx = mp.get_context('fork')
        syncer = ctx.Barrier(2, timeout=5)
        notifier = ctx.Queue()
        passive = ctx.Process(target=sync_traffic, args=[self.ip_addr, syncer,
                                                         notifier, True])
        active = ctx.Process(target=sync_traffic, args=[self.ip_addr, syncer,
                                                       notifier, False])
        passive.start()
        active.start()
        while notifier.empty():
            pass

        for _ in range(2):
            res = notifier.get()
            if res is not None:
                passive.terminate()
                active.terminate()
                raise PyverbsError(res)

        passive.join()
        active.join()
