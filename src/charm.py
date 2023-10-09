#!/usr/bin/env python3
# Copyright 2023 Ubuntu
# See LICENSE file for licensing details.
#
# Learn more at: https://juju.is/docs/sdk

"""Charm the service.

Refer to the following tutorial that will help you
develop a new k8s charm using the Operator Framework:

https://juju.is/docs/sdk/create-a-minimal-kubernetes-charm
"""

import logging
import time

import ops
import lightkube
import lightkube.models.apps_v1
import lightkube.resources.apps_v1
import lightkube.resources.core_v1

# Log messages can be retrieved using juju debug-log
logger = logging.getLogger(__name__)

class StatefulSet:
    def __init__(self, app_name: str):
        self._app_name = app_name
        self._client = lightkube.Client()

    @property
    def partition(self) -> int:
        stateful_set = self._client.get(
            res=lightkube.resources.apps_v1.StatefulSet, name=self._app_name
        )
        return stateful_set.spec.updateStrategy.rollingUpdate.partition

    @partition.setter
    def partition(self, value: int) -> None:
        self._client.patch(
            res=lightkube.resources.apps_v1.StatefulSet,
            name=self._app_name,
            obj={"spec": {"updateStrategy": {"rollingUpdate": {"partition": value}}}},
        )


class BarCharm(ops.CharmBase):
    """Charm the service."""

    def __init__(self, *args):
        super().__init__(*args)
        self.stateful_set = StatefulSet(self.app.name)
        self.framework.observe(self.on["peer"].relation_changed, self._on_peer_changed)
        self.framework.observe(self.on.stop, self._on_stop)
        self.framework.observe(self.on.start, self._on_start)

    def _on_peer_changed(self, event: ops.RelationChangedEvent):
        if self.unit.is_leader():
            for unit in sorted((self.unit, *event.relation.units), key=lambda unit: int(unit.name.split("/")[-1]), reverse=True):
                if event.relation.data[unit].get("status") != "healthy":
                    break
            partition = int(unit.name.split("/")[-1])
            if partition > 0:
                self.app.status = ops.MaintenanceStatus(f"upgrading unit {self.stateful_set.partition}")
            else:
                self.app.status = ops.ActiveStatus()
            self.stateful_set.partition = partition

    def _on_stop(self, _):
        self.stateful_set.partition = int(self.unit.name.split("/")[-1])
        if relation := self.model.get_relation("peer"):
            relation.data[self.unit]["status"] = "restarting"

    def _on_start(self, _):
        if relation := self.model.get_relation("peer"):
            if relation.data[self.unit].get("status") == "restarting":
                time.sleep(30)
                relation.data[self.unit]["status"] = "healthy"




if __name__ == "__main__":  # pragma: nocover
    ops.main(BarCharm)  # type: ignore
