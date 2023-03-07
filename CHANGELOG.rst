=============
Release Notes
=============

-----
0.4.0
-----

Released: unreleased

-----
0.3.1
-----

Released: 2023-03-07

.. rubric:: Bug Fixes

*  Fixed use of the ``importlib.resources`` library.

-----
0.3.0
-----

Released: 2023-03-07

.. rubric:: Features

*  Completely refactored to be in the package ``lockss.turtles``.

*  Using Poetry to make uploadable to and installable from PyPI as `lockss-turtles <https://pypi.org/project/lockss-turtles>`_. Removed the requirements file.

*  Validate the various YAML objects (like a ``PluginSet``) against a `JSON Schema <https://json-schema.org/>`_.

.. rubric:: Changes

*  Temporarily disabled the ``analyze-registry`` command.

*  ``$XDG_CONFIG_HOME/turtles`` (by default ``$HOME/.config/turtles``) is now ``$XDG_CONFIG_HOME/lockss.turtles`` (by default ``$HOME/.config/lockss.turtles``) or ``/etc/lockss.turtles`` (formerly ``turtles``).

*  ``settings.yaml`` is now ``plugin-signing.yaml`` and its ``kind`` is now ``PluginSigning``. The corresponding command line option ``--settings`` is now ``--plugin-signing``.

*  ``plugin-sets.yaml``, its kind ``PluginSets``, its key ``plugin-sets``, and the command line option ``--plugin-sets`` are now ``plugin-set-catalog.yaml``, ``PluginSetCatalog``, ``plugin-set-files`` and ``--plugin-set-catalog``, respectively. The builder ``options`` key is deprecated.

*  ``plugin-registries.yaml``, its kind ``PluginRegistries``, its key ``plugin-registries``, and the command line option ``--plugin-registries`` are now ``plugin-registry-catalog.yaml``, ``PluginRegistryCatalog``, ``plugin-registry-files`` and ``--plugin-registry-catalog``, respectively. The ``file-naming-convention`` key is now directly under ``layout`` and the value ``full`` is now ``identifier``. The layout ``options`` key is deprecated.

-----
0.2.0
-----

Released: 2022-10-26

.. rubric:: Features

*  ``MavenPluginSet``, for Maven projects inheriting from ``org.lockss:lockss-plugins-parent-pom``.

*  ``AntPluginSet``: file naming convention layout option.

*  Tabular output now includes the plugin version.

.. rubric:: Bug Fixes

*  ``AntPluginSet``: run ``ant load-plugins`` before building plugins.

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
