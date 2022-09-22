from typing import Iterable, Dict
from odd_collector_sdk.domain.adapter import AbstractAdapter
from odd_collector_aws.domain.plugin import DmsPlugin
from itertools import chain
from oddrn_generator.generators import DmsGenerator
from odd_collector_aws.adapters.dms.mappers.endpoints import engines_map
from odd_models.models import DataEntityList, DataEntity
from odd_collector_aws.domain.paginator_config import PaginatorConfig
from odd_collector_aws.domain.fetch_paginator import fetch_paginator
from .client import DMSClient
from .mappers.tasks import map_dms_task

MAX_RESULTS_FOR_PAGE = 100


class Adapter(AbstractAdapter):
    def __init__(self, config: DmsPlugin) -> None:
        self._dms_client = DMSClient(config)
        self._oddrn_generator = DmsGenerator(
            cloud_settings={"region": config.aws_region, "account": self._dms_client.account_id}
        )

    def get_data_source_oddrn(self) -> str:
        return self._oddrn_generator.get_data_source_oddrn()

    def get_data_entity_list(self) -> DataEntityList:
        endpoints_entities_dict = self._get_endpoints_entities_arn_dict()
        tasks_entities = list(chain(
            self._get_tasks(endpoints_entities_dict),
        ))
        endpoints_entities_values = list(endpoints_entities_dict.values())

        return DataEntityList(
            data_source_oddrn=self.get_data_source_oddrn(),
            items=[*tasks_entities, *endpoints_entities_values],
        )

    def _get_tasks(self, endpoints_entities_arn_dict: Dict[str, DataEntity]) -> Iterable[DataEntity]:
        return fetch_paginator(
            PaginatorConfig(
                op_name="describe_replication_tasks",
                parameters={},
                page_size=MAX_RESULTS_FOR_PAGE,
                list_fetch_key='ReplicationTasks',
                mapper=map_dms_task,
                mapper_args={"oddrn_generator": self._oddrn_generator,
                             "endpoints_arn_dict": endpoints_entities_arn_dict,
                             },
            ),
            self._dms_client.dms
        )

    def _get_endpoints_nodes(self):
        paginator = fetch_paginator(
            PaginatorConfig(
                op_name="describe_endpoints",
                parameters={},
                page_size=MAX_RESULTS_FOR_PAGE,
                list_fetch_key='Endpoints',
            ),
            self._dms_client.dms
        )
        return paginator

    def _get_endpoints_entities_arn_dict(self) -> Dict[str, DataEntity]:
        entities: Dict[str, DataEntity] = {}
        for endpoint_node in self._get_endpoints_nodes():
            endpoint_arn = endpoint_node.get('EndpointArn')
            engine_name = endpoint_node.get('EngineName')
            engine = engines_map.get(engine_name)
            endpoint_entity = engine(endpoint_node,
                                     self._oddrn_generator.server_obj).map_database()
            entities.update({endpoint_arn: endpoint_entity})
        return entities
