import os

from typing import Union

from rosbags.rosbag2 import Reader
from rosbags.typesys import Stores, get_types_from_msg, get_typestore
from rosbags.typesys.store import Typestore


def register_types_from_bag(bag_path: Union[str, os.PathLike]) -> Typestore:
    from rosbags.typesys.types import get_types_from_package
    typestore = get_typestore(Stores.ROS2)
    typestore.register(get_types_from_package('sensor_msgs'))
    with Reader(bag_path) as reader:
        typs = {}
        # register every message type for deserialization
        for conn in reader.connections:
            try:
                new_types = get_types_from_msg(conn.msgdef, conn.msgtype)
                typs.update(new_types)
                typestore.register(new_types)
            except Exception as e:
                print(f"[WARN] Skipping type '{conn.msgtype}' due to parse error:\n{e}\n")
                continue
    return typestore