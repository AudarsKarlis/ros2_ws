import os

from typing import Union

from rosbags.rosbag2 import Reader
from rosbags.typesys import Stores, get_types_from_msg, get_typestore
from rosbags.typesys.store import Typestore


def register_types_from_bag(bag_path: Union[str, os.PathLike]) -> Typestore:
    typestore = get_typestore(Stores.EMPTY)
    with Reader(bag_path) as reader:
        typs = {}
        # register every message type for deserialization. rosbags only supports standard ros messages
        for conn in reader.connections:
            try:
                typs.update(get_types_from_msg(conn.msgdef, conn.msgtype))
                typestore.register(typs)
            except Exception as e:
                print(e)
                print(conn.msgdef, conn.msgtype)
                for k in get_types_from_msg(conn.msgdef, conn.msgtype).keys():
                    typs.pop(k)
                pass
    return typestore