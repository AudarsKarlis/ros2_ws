import rclpy
from rclpy.serialization import deserialize_message
from rosbag2_py import SequentialReader, StorageOptions, ConverterOptions
from sensor_msgs.msg import BatteryState

def read_bag(file_path):
    storage_options = StorageOptions(uri=file_path, storage_id='sqlite3')
    converter_options = ConverterOptions('', '')

    reader = SequentialReader()
    reader.open(storage_options, converter_options)

    topics_types = reader.get_all_topics_and_types()
    type_map = {topic.name: topic.type for topic in topics_types}

    while reader.has_next():
        (topic, data, t) = reader.read_next()
        msg_type = type_map[topic]

        if msg_type == 'sensor_msgs/msg/BatteryState':
            msg = deserialize_message(data, BatteryState)
            print(f"Time: {t}, Voltage: {msg.voltage}, Current: {msg.current}")

if __name__ == '__main__':
    rclpy.init()
    read_bag('/home/vboxuser/ros2_ws/src/rosbag2_2025_07_21-14_34_13')
    rclpy.shutdown()