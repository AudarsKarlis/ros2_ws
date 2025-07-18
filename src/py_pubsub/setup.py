from setuptools import find_packages, setup

package_name = 'py_pubsub'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='vboxuser',
    maintainer_email='vboxuser@todo.todo',
    description='Examples of minimal publisher/subscriber using rclpy',
    license='Apache License 2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
                'talker = py_pubsub.publisher_member_function:main',
                'listener = py_pubsub.subscriber_member_function:main',
                'listener_float = py_pubsub.subscriber_member_function_FLOAT:main',
                'talker_float = py_pubsub.publisher_member_function_FLOAT:main',
                'talker_uint8 = py_pubsub.publisher_member_function_UINT8:main',
                'listener_uint8 = py_pubsub.subscriber_member_function_UINT8:main',
                'talker_float_array = py_pubsub.publisher_member_function_FLOAT32_array:main',
                'listener_float_array = py_pubsub.subscriber_member_function_FLOAT32_array:main',
        ],
    },
)
