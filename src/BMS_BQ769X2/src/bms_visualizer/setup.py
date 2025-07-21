from setuptools import find_packages, setup

package_name = 'bms_visualizer'

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
    maintainer='kernt',
    maintainer_email='tobiasbenjamin.kern@carissma.eu',
    description='TODO: Package description',
    license='TODO: License declaration',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'bms_visualizer_node = bms_visualizer.bms_visualizer_node:main'
        ],
    },
)
