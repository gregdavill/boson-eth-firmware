# pythondata-software-picolibc

Non-Python  files needed for the software picolibc packaged
into a Python module so they can be used with Python libraries and tools.

This is useful for usage with tools like
[LiteX](https://github.com/enjoy-digital/litex.git).

The data files can be found under the Python module `pythondata_software_picolibc`. The
`pythondata_software_picolibc.data_location` value can be used to find the files on the file
system.

Example of getting the data file directly;
```python
import pythondata_software_picolibc

my_data_file = "abc.txt"

with open(os.path.join(pythondata_software_picolibc.data_location, my_data_file)) as f:
    print(f.read())
```

Example of getting the data file using `litex.data.find` API;
```python
from pythondata_software_picolibc import data_file

my_data_file = "abc.txt"

with open(data_file(my_data_file)) as f:
    print(f.read())
```


The data files come from https://github.com/picolibc/picolibc
and are imported using `git subtrees` to the directory
[pythondata_software_picolibc/data](pythondata_software_picolibc/data).



## Installing from git repository

## Manually

You can install the package manually, however this is **not** recommended.

```
git clone https://github.com/litex-hub/pythondata-software-picolibc.git
cd pythondata-software-picolibc
sudo python setup.py install
```

## Using [pip](https://pip.pypa.io/) with git repository

You can use [pip](https://pip.pypa.io/) to install the data package directly
from github using;

```
pip install --user git+https://github.com/litex-hub/pythondata-software-picolibc.git
```

If you want to install for the whole system rather than just the current user,
you need to remove the `--user` argument and run as sudo like so;

```
sudo pip install git+https://github.com/litex-hub/pythondata-software-picolibc.git
```

You can install a specific revision of the repository using;
```
pip install --user git+https://github.com/litex-hub/pythondata-software-picolibc.git@<tag>
pip install --user git+https://github.com/litex-hub/pythondata-software-picolibc.git@<branch>
pip install --user git+https://github.com/litex-hub/pythondata-software-picolibc.git@<hash>
```

### With `requirements.txt` file

Add to your Python `requirements.txt` file using;
```
-e git+https://github.com/litex-hub/pythondata-software-picolibc.git
```

To use a specific revision of the repository, use the following;
```
-e https://github.com/litex-hub/pythondata-software-picolibc.git@<hash>
```

## Installing from [PyPi](https://pypi.org/project/pythondata-software-picolibc/)

## Using [pip](https://pip.pypa.io/)

```
pip install --user pythondata-software-picolibc
```
