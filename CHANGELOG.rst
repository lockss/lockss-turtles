=============
Release Notes
=============

-----
0.2.0
-----

Released: FIXME

.. rubric:: Features

*  ``MavenPluginSet``, for Maven projects inheriting from ``org.lockss:lockss-plugins-parent-pom``.

*  ``AntPluginSet``: file naming convention layout option.

*  Tabular output now includes the plugin version.

.. rubric:: Bug Fixes

*  ``AntPluginSet``: run ``ant load-plugins`` before building plugins.

.. rubric:: Changes

*  Default tabular output format is now ``tsv``.

-----
0.1.1
-----

Released: 2022-10-23

.. rubric:: Bug Fixes

*  ``RcsPluginRegistry``: Better handle incompletely managed RCS areas.

*  ``DirectoryPluginRegistry``: Better file handling with ``cp``.

-----
0.1.0
-----

Released: 2022-10-10

Initial release.

.. rubric:: Features

*  ``AntPluginSet``, based on the classic ``lockss-daemon`` Ant builder.

*  ``DirectoryPluginRegistry``, for a simple layout.

*  ``RcsPluginRegistry``, based on the classic RCS layout.

*  Tabular output by `tabulate <https://pypi.org/project/tabulate/>`_.
