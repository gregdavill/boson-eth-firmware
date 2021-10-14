import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

from pythondata_software_picolibc import version_str

setuptools.setup(
    name="pythondata-software-picolibc",
    version=version_str,
    author="LiteX Authors",
    author_email="litex@googlegroups.com",
    description="""\
Python module containing data files for picolibc - a C library designed for embedded 32- and 64- bit systems. software.""",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/litex-hub/pythondata-software-picolibc",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.5',
    zip_safe=False,
    packages=setuptools.find_packages(),
    package_data={
    	'software_picolibc': ['software_picolibc/data/**'],
    },
    include_package_data=True,
    project_urls={
        "Bug Tracker": "https://github.com/litex-hub/pythondata-software-picolibc/issues",
        "Source Code": "https://github.com/litex-hub/pythondata-software-picolibc",
    },
)
