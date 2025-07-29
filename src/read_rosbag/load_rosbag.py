from __future__ import annotations
import sys
import os
import argparse
import yaml
import numpy
import time
from PIL import Image
from scipy.io import savemat
from tqdm import tqdm

from typing import Union, Iterable

from rosbags.rosbag2 import Reader

from .register_msgs_from_bag import register_types_from_bag
from .loading_anim import loading_anim_circle

sys.setrecursionlimit(16385)  ## Prevent Python from stopping on recurse through message structures

def read_msgs(msg, types=[]):
    if type(msg) not in [numpy.ndarray, numpy.float64, numpy.float32, numpy.int64, numpy.int32, numpy.bool8, int, float, str, bool]: # list
        mat_dict = {}
        for attr in [attrs for attrs in dir(msg)
                  if (not attrs.startswith("__"))
                  and (not callable(getattr(msg, attrs)))
                 ]:
            typ = type(getattr(msg, attr))
            if typ not in types:
                types.append(typ)
            if typ in [list]:
                mat_dict[f"{attr}"] = []
                for elem in getattr(msg, attr):
                    mat_dict[f"{attr}"].append(read_msgs(elem, types=types))
            else:
                mat_dict[f"{attr}"] = read_msgs(getattr(msg, attr), types=types)
    else:
        mat_dict = msg
    return mat_dict


def read_rosbag(rosbag_folder_path: Union[str, os.PathLike], relative_timestamp: bool = True, topics2keep=[]) -> dict:
    rosbag_folder = rosbag_folder_path
    input_file_name = rosbag_folder_path.replace('\\','/').split('/')[-1]
    if input_file_name.endswith("/") or input_file_name.endswith("\\"):
        input_file_name = input_file_name[:-1]

    try:
        with open(rosbag_folder +'/metadata.yaml', 'r') as fil:
            meta_data = yaml.safe_load(fil)['rosbag2_bagfile_information']
    except Exception:
        relative_timestamp=False

    
    # register every message type for deserialization. rosbags only supports standard ros messages
    typestore = register_types_from_bag(rosbag_folder)

    # create reader instance and open for reading
    with Reader(rosbag_folder) as reader:
        types = []
        excluded_topics = []
        mat = {}
        print(f"Processing {input_file_name}")
        print(f"\t  t_start: {meta_data['starting_time']['nanoseconds_since_epoch']}")
        print(f"\t Duration: {meta_data['duration']['nanoseconds']/1e9}")
        print(f"\t# Message: {meta_data['message_count']}")

        # get sum of all used msgs
        if len(topics2keep) == 0:
            msg_cnt = meta_data['message_count']
        else:
            msg_cnt = sum([x.msgcount for x in reader.connections if x.topic in topics2keep])
        # interate over the mesaages in the bag file
        #for conn in reader.connections:
        #    print(f"{conn.topic}: {conn.msgtype}")
        with tqdm(total=msg_cnt, desc=input_file_name) as bar:
            connections = [x for x in reader.connections if x.topic in topics2keep]
            for connection, timestamp, rawdata in reader.messages(connections=connections):
                bar.update(1)
                if relative_timestamp:
                    ts = timestamp-meta_data['starting_time']['nanoseconds_since_epoch']
                else:
                    ts = timestamp
                # try:
                    # if ts < meta_data['duration']['nanoseconds'] - 70e9 :
                    #     continue
                if len(topics2keep) > 0:
                    if connection.topic not in topics2keep:
                        if connection.topic not in excluded_topics:
                            excluded_topics.append(connection.topic)
                        continue
                if connection.topic.__contains__("camera_info"):
                    continue
                if connection.topic == "/color/image_raw":
                    data = typestore.deserialize_cdr(rawdata, connection.msgtype)
                    # print(data.width, data.height, data.encoding, len(data.data))
                    img = numpy.array(data.data,dtype=numpy.uint8).reshape((data.height, data.width, 3))
                    img = Image.fromarray(img)
                    img.save(f"./images/{ts/1e9:.4f}.png")
                # if connection.topic.__contains__("infra1/image_rect_raw"):
                #     continue
                # if connection.topic.__contains__("image_rect_raw"):
                    # continue
                # if connection.topic.__contains__("extrinsics"):
                    # continue
                # if connection.topic.__contains__("depth"):
                    # continue
                msg = typestore.deserialize_cdr(rawdata, connection.msgtype)
                msg_topic_name = "_".join(connection.topic.split("/")[1:])
                msg_dict = read_msgs(msg, types)
                if msg_topic_name in mat.keys():
                    mat[msg_topic_name].append([ts/1e9, msg_dict])
                else:
                    mat[msg_topic_name] = [[ts/1e9, msg_dict]]
    for topic in mat.keys():
        mat[topic] = numpy.array(mat[topic])

    # for t in excluded_topics:
    #     print(t)
    return mat


def combine_rosbags(paths: Iterable, relative_timestamp:bool = True, topics2keep:Iterable=[]) -> dict:
    out = {}
    for path in paths:
        data = read_rosbag(path, relative_timestamp=relative_timestamp, topics2keep=topics2keep)
        for topic in data.keys():
            if topic not in out.keys():
                out[topic] = data[topic]
    return out



if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="Rosbag2ToMat",
                                 description="Rosbag2ToMat exports every topic to a Matlab .mat file")
    parser.add_argument('-i', '--input', type=str, required=True, help="path to rosbag2 folder")
    parser.add_argument('-o', '--output', type=str, help="output path for .mat file. defaults to input-path")
    parser.add_argument('-r','--relative_timestamp', action="store_true", default=False)
    parser.add_argument('-s','--start_time', type=float, default=0.0, help="start time if --relative_timestamp relative to the record start. otherwise timestamp since epoch in s")
    parser.add_argument('--repl', action='store_true', default=False, help="Flag to replace existing output file")
    args = parser.parse_args()

    rosbag_folder = args.input
    input_file_name = args.input.replace('\\','/').split('/')[-1]
    if args.output:
        if os.path.isdir(args.output):
            save_path = os.path.join(args.output, input_file_name +  '_struct.mat')
        else:
            if args.output.endswith('.mat'):
                save_path = args.output
            else:
                save_path = args.output + '.mat'
    else:
        save_path = rosbag_folder+'_struct.mat'
    mat = read_rosbag(rosbag_folder, args.relative_timestamp) # structured as {"topic_name": [[t0, message_as_dict],[t1, message_as_dict],...], "other_topic": [[...]]}
    
    ## uncomment below if you want to save as .mat file
    # try:
    #     print(save_path)
    #     s = time.time()
    #     loading_anim_circle(savemat, save_path, mat)
    #     sc = time.time()
    #     print(f"time needed to save: {sc-s}")
    # except Exception as e:
    #     sys.stderr.write(f"ERROR: {type(e)}: {e} \n")

    sys.exit(0)