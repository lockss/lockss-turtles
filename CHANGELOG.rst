=============
Release Notes
=============

-----
0.7.0
-----

Released: NOT YET RELEASED

-----
0.6.0
-----

Released: 2025-10-23

*  **Changes**

   *  The configuration directory for Turtles in ``$XDG_CONFIG_HOME`` (by default ``$HOME/.config`` which is typically ``/home/$USER/.config``), ``/usr/local/share``, and ``/etc`` is now called ``lockss-turtles`` instead of ``lockss.turtles``.

   *  Some long options have been renamed (the corresponding short options remain unchanged):

      .. list-table::
         :header-rows: 1

         *  *  Short option
            *  Long option, version 0.5.0
            *  Long option, version 0.6.0
         *  *  ``-i``
            *  ``--identifier``
            *  ``--plugin-identifier``
         *  *  ``-I``
            *  ``--identifiers``
            *  ``--plugin-identifiers``
         *  *  ``-j``
            *  ``--jar``
            *  ``--plugin-jar``
         *  *  ``-J``
            *  ``--jars``
            *  ``--plugin-jars``
         *  *  ``-l``
            *  ``--layer``
            *  ``--plugin-registry-layer``
         *  *  ``-L``
            *  ``--layers``
            *  ``--plugin-registry-layers``
         *  *  n/a
            *  ``--password``
            *  ``--plugin-signing-password``

   *  Some short options have been renamed (the corresponding long options remain unchanged):

      .. list-table::
         :header-rows: 1

         *  *  Long option
            *  Short option, version 0.5.0
            *  Short option, version 0.6.0
         *  *  ``--plugin-registry-catalog``
            *  ``-r``
            *  ``-R``
         *  *  ``--plugin-set-catalog``
            *  ``-s``
            *  ``-S``

   *  Bare arguments are no longer allowed and treated as plugin identifiers or plugin JARs; all plugin identifiers must be specified via ``--plugin-identifier/-i`` or ``--plugin-identifiers/-I`` options and all plugin JARS via ``--plugin-jar/-j`` or ``--plugin-jars/-J`` options.

   *  The ``usage`` command has been removed.

*  **Features**

   *  New options have been added:

      .. list-table::
         :header-rows: 1

         *  *  Long option
            *  Short option
         *  *  ``--plugin-registry``
            *  ``-r``
         *  *  ``--plugin-set``
            *  ``-s``

   *  Options that read YAML files no longer expect each file to contain a single YAML configuration object, which must be of the kind they target; they now read all YAML configuration objects in each file, loading all the ones with the right kind and ignoring all the others with the other kinds. This applies to existing options ``--plugin-registry-catalog``/``-R`` and ``--plugin-set-catalog``/``-S``, and new options ``--plugin-registry``/``-r`` and ``--plugin-set``/``-s``.

   *  In YAML files, values that are paths can now all be either relative with respect to the enclosing file or absolute.

   *  Now using Pydantic for configuration objects instead of maintaining JSON Schema instances.

   *  Now using type hinting throughout.

   *  Now using *lockss-pybasic* and *pydantic-argparse* internally.

   *  `Turtles documentation <https://docs.lockss.org/en/latest/software/turtles>`_ is now on the `LOCKSS Documentation Portal <https://docs.lockss.org/>`_.

-----
0.5.0
-----

Released: 2024-09-04

*  **Features**

   *  ``AntPluginSet``: also include plugin auxiliary packages (``plugin_aux_packages``).

-----
0.4.0
-----

Released: 2023-05-17

*  **Features**

   *  ``directory`` plugin registry layout now has the same file naming convention option as ``rcs``.

   *  New ``directory``/``rcs`` file naming convention ``underscore``: replace ``.`` in the plugin identifier by ``_`` and add ``.jar``.

   *  CLI improvements.

*  **Changes**

   *  The ``--output-format`` option is now only available in the context of commands where it makes sense.

-----
0.3.1
-----

Released: 2023-03-07

*  **Bug Fixes**

   *  Fixed use of the ``importlib.resources`` library.

-----
0.3.0
-----

Released: 2023-03-07

*  **Features**

   *  Completely refactored to be in the package ``lockss.turtles``.

   *  Using Poetry to make uploadable to and installable from PyPI as `lockss-turtles <https://pypi.org/project/lockss-turtles>`_. Removed the requirements file.

   *  Validate the various YAML objects (like a ``PluginSet``) against a `JSON Schema <https://json-schema.org/>`_.

*  **Changes**

   *  Temporarily disabled the ``analyze-registry`` command.

   *  ``$XDG_CONFIG_HOME/turtles`` (by default ``$HOME/.config/turtles``) is now ``$XDG_CONFIG_HOME/lockss.turtles`` (by default ``$HOME/.config/lockss.turtles``) or ``/etc/lockss.turtles`` (formerly ``turtles``).

   *  ``settings.yaml`` is now ``plugin-signing.yaml`` and its ``kind`` is now ``PluginSigning``. The corresponding command line option ``--settings`` is now ``--plugin-signing``.

   *  ``plugin-sets.yaml``, its kind ``PluginSets``, its key ``plugin-sets``, and the command line option ``--plugin-sets`` are now ``plugin-set-catalog.yaml``, ``PluginSetCatalog``, ``plugin-set-files`` and ``--plugin-set-catalog``, respectively. The builder ``options`` key is deprecated.

   *  ``plugin-registries.yaml``, its kind ``PluginRegistries``, its key ``plugin-registries``, and the command line option ``--plugin-registries`` are now ``plugin-registry-catalog.yaml``, ``PluginRegistryCatalog``, ``plugin-registry-files`` and ``--plugin-registry-catalog``, respectively. The ``file-naming-convention`` key is now directly under ``layout`` and the value ``full`` is now ``identifier``. The layout ``options`` key is deprecated.

-----
0.2.0
-----

Released: 2022-10-26

*  **Features**

   *  ``MavenPluginSet``, for Maven projects inheriting from ``org.lockss:lockss-plugins-parent-pom``.

   *  ``RcsPluginRegistry``: file naming convention layout option.

   *  Tabular output now includes the plugin version.

*  **Bug Fixes**

   *  ``AntPluginSet``: run ``ant load-plugins`` before building plugins.

-----
0.1.1
-----

Released: 2022-10-23

*  **Bug Fixes**

   *  ``RcsPluginRegistry``: Better handle incompletely managed RCS areas.

   *  ``DirectoryPluginRegistry``: Better file handling with ``cp``.

-----
0.1.0
-----

Released: 2022-10-10

*  **Features**

   *  Initial release.

   *  ``AntPluginSet``, based on the classic ``lockss-daemon`` Ant builder.

   *  ``DirectoryPluginRegistry``, for a simple layout.

   *  ``RcsPluginRegistry``, based on the classic RCS layout.

   *  Tabular output by `tabulate <https://pypi.org/project/tabulate/>`_.
