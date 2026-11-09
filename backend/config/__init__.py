"""MySQL driver shim.

Django's MySQL backend imports ``MySQLdb``. Two packages satisfy that import:

* ``mysqlclient`` - the C extension Django recommends (fastest; on Windows it
  needs a prebuilt wheel or MSVC build tools).
* ``PyMySQL``     - pure Python, installs anywhere, marginally slower.

Whichever is installed wins; nothing else in the project needs to change.
If neither is installed this is a no-op and Django only complains when
DB_ENGINE=mysql.
"""
try:  # pragma: no cover - environment dependent
    import pymysql

    pymysql.install_as_MySQLdb()
except ImportError:  # pragma: no cover
    pass
