import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

from pythondata_software_compiler_rt import version_str

setuptools.setup(
    name="pythondata-software-compiler_rt",
    version=version_str,
    author="LiteX Authors",
    author_email="litex@googlegroups.com",
    description="""\
Python module containing data files for LLVM Compiler RT Module software.""",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/litex-hub/pythondata-software-compiler_rt",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.5',
    zip_safe=False,
    packages=setuptools.find_packages(),
    package_data={
    	'software_compiler_rt': ['software_compiler_rt/data/**'],
    },
    include_package_data=True,
    project_urls={
        "Bug Tracker": "https://github.com/litex-hub/pythondata-software-compiler_rt/issues",
        "Source Code": "https://github.com/litex-hub/pythondata-software-compiler_rt",
    },
)
