=======
Turtles
=======

Turtles is a tool to manage LOCKSS plugin sets and LOCKSS plugin registries.

-----------
Quick Start
-----------

::

   # Get Turtles from Git
   git clone .../turtles
   cd turtles
   # Use requirements.txt to install Turtles' Python dependencies
   # If in venv:
   python3 -m venv .venv
   . .venv/bin/activate
   pip3 install -r requirements.txt
   # Put the file turtles on the PATH and run from anywhere: turtles ...
   # Or run from this directory: ./turtles ...
   turtles --help
   turtles usage

-------------
Prerequisites
-------------

To use Turtles, you will need:

*  Python 3.6 or greater.

Turtles' Python dependencies are defined in its ``requirements.txt`` files.

Other prerequisites depend on the `Plugin Set Builders`_ and `Plugin Registry Layouts`_ that may be involved in your activities; see the notes about **system prerequisites** for each.

-----------
Plugin Sets
-----------

A plugin set is a project containing the source code of LOCKSS plugins.

Declaring a Plugin Set
======================

A plugin set is defined in a YAML file typically named ``turtles.yaml`` and found at the root of the project::

   ---
   kind: PluginSet
   id: ...
   name: ...
   builder:
     type: ...
     options: ...
   main: ...
   test: ...

The contents are described below.

``kind``
   Must be set to ``PluginSet``.

``id``
   A short identifier for the plugin set, for example ``my-plugin-set``.

``name``
   A display name for the plugin set, for example ``My Plugin Set``.

``builder``
   A mapping defining the plugin set's builder together with options.

   ``type``
      A plugin set builder type. See `Plugin Set Builders`_ below.

   ``options``
      A mapping of type-specific options for the plugin set builder, if applicable. See `Plugin Set Builders`_ below.

``main``
   The path (relative to the root of the project) under which the source code of the plugins can be found. May have a default value for a given builder type.

``test``
   The path (relative to the root of the project) under which the source code of the plugins' unit tests can be found. May have a default value for a given builder type.

Plugin Set Builders
===================

The following plugin set builder types are supported:

``ant``
   The plugin set builder type ``ant`` designates a project using the legacy Ant layout of the LOCKSS Program's ``lockss-daemon`` project.

   This builder expects an Ant build file named ``build.xml`` at the root of the project, and the scripts ``jarplugin`` and ``signplugin`` at ``test/scripts/jarplugin`` and ``test/scripts/signplugin`` respectively. (These could all become configurable if there are plugin projects out there generally using this builder logic but not matching these assumptions.)

   In this builder, the ``main`` and ``test`` properties of the ``PluginSet`` object default to ``plugins/src`` and ``plugins/test/src`` respectively.

   Currently, this builder does not look for optional configuration information in the ``options`` mapping.

   **System prerequisites.** This builder requires:

   *  Java Development Kit 8 (JDK)

   *  Apache Ant

``mvn``
   **Under development.** *This builder type is not yet available.*

   The plugin set builder type ``mvn`` designates a project using a Maven layout and inheriting from ``org.lockss:lockss-plugins-parent-pom``. In this builder, the ``main`` and ``test`` properties of the ``PluginSet`` object default to the Maven standard ``src/main/java`` and ``src/test/java`` respectively.

   **System prerequisites.** This builder requires:

   *  Java Development Kit 8 (JDK)

   *  Apache Maven

For other types of building strategies out there, more types of builders could be supported, and/or the tool could be extended to allow for custom builder types to be registered.

-----------------
Plugin Registries
-----------------

A plugin registry is a structure containing LOCKSS plugins packaged as signed JAR files.

Currently the only predefined structures are directory structures local to the file system, but in the future this could also be Git trees or other structures.

Plugin Registry Layers
======================

A plugin registry consists of one or more layers. Some plugin registries may have only one layer, in which case the LOCKSS boxes in a network using the plugin registry will get what is released to it. Some plugin registries may have two or more layers, with the additional layers used for plugin development or content processing quality assurance.

Plugin layers are sequential in nature; a new version of a plugin is released to the lowest layer first, then to the next layer (after some process), and so on until the highest layer.

Although the identifiers (see ``id`` below) and display names (see ``name`` below) of plugin registry layers are arbitrary, the highest layer is commonly referred to as the *production* layer, and when there are exactly two layers, the lower layer is commonly referred to as the *testing* layer. Turtles reflects this common idiom with built-in ``--production`` and ``--testing`` options.

It is possible for multiple plugin registries to have a layer path in common. An example would be a team working on several plugin registries for different purposes, having distinct production layer paths for different audiences but sharing a single testing layer path, if they are the only audience for it.

Declaring a Plugin Registry
===========================

A plugin registry is defined in a YAML file::

   ---
   kind: PluginRegistry
   id: ...
   name: ...
   layout:
     type: ...
     options: ...
   layers:
     - id: ...
       name: ...
       path: ...
     - ...
   plugin-identifiers:
     - ...
     - ...
   suppressed-plugin-identifiers:
     - ...
     - ...

The contents are described below.

``kind``
   Must be set to ``PluginRegistry``.

``id``
   A short identifier for the plugin registry, for example ``my-plugin-registry``.

``name``
   A display name for the plugin registry, for example ``My Plugin Registry``.

``layout``
   A mapping defining the plugin registry's layout together with options.

   ``type``
      A plugin registry layout type. See `Plugin Registry Layouts`_ below.

   ``options``
      A mapping of type-specific options for the plugin registry layout, if applicable. See `Plugin Registry Layouts`_ below.

``layers``
   An ordered list of the plugin registry's layers. Each list element consists of the following three-element mapping:

      ``id``
         A short identifier for the plugin registry layer, for example ``production`` or ``testing``.

      ``name``
         A display name for the plugin regisry layer, for example ``My Plugin Registry Testing Layer`` or ``My Plugin Registry (Testing)``.

      ``path``
         A directory path where the root of the plugin registry layer can be found.

``plugin-identifiers``
   A list of plugin identifiers contained in the plugin registry.

``suppressed-plugin-identifiers``
   A list of plugin identifiers excluded by the plugin registry. Turtles does not currently do anything with this information but it could be used to record plugins that have been abandoned or retracted over the lifetime of the plugin registry.

Plugin Registry Layouts
=======================

The following plugin registry layout types are supported:

``directory``
   Each layer consists of a directory on the file system where signed plugin JARs are stored, which is then typically served by a Web server. The directory for each layer is designated by the layer's ``path`` property.

   Currently, this layout does not look for optional configuration information in the ``options`` mapping.

``rcs``
   A specialization of the ``directory`` type, that also keeps successive versions of a given JAR locally in RCS. The directory for each layer is designated by the layer's ``path`` property as in the ``directory`` type, and additionally this layout expects an ``RCS`` directory to exist in the layer directory.

   Currently, this layout does not look for optional configuration information in the ``options`` mapping.

   **System prerequisites.** This builder requires:

   *  RCS

Other layout types could be defined to support other uses cases out there, and/or the tool could be extended to allow for custom layout types to be registered.

-----------
Configuring
-----------

When Turtles looks for a configuration file, it looks in the following directories in sequence until it finds the matching file:

*  ``${HOME}/.config/turtles``

*  ``/etc/turtles``

Configuration files are YAML files containing a mapping with ``kind`` set to ``Settings`` along with whatever data is required by the given configuration file.

``settings.yaml``
=================

Overview of this file::

   ---
   kind: Settings
   plugin-signing-alias: ...
   plugin-signing-keystore: ...

If you are using Turtles to build or release plugins (``turtles build-plugin`` or ``turtles release-plugin`` commands), you will need to specify the following keys:

``plugin-signing-alias``
   The alias of your plugin signing key.

``plugin-signing-keystore``
   The path of your plugin signing keystore.

``plugin-sets.yaml``
====================

This configuration file is needed by Turtles when building or releasing plugins (``turtles build-plugin`` or ``turtles release-plugin`` commands)::

   ---
   kind: Settings
   plugin-sets:
     - ...
     - ...

Each entry in the ``plugin-sets`` list is the path to a YAML file containing one or more ``PluginSet`` definitions.

``plugin-registries.yaml``
==========================

This configuration file is needed by Turtles when deploying or releasing plugins (``turtles deploy-plugin`` or ``turtles release-plugin`` commands), and when outputting reports on plugin registries (``turtles analyze-registry`` command)::

   ---
   kind: Settings
   plugin-registries:
     - ...
     - ...

Each entry in the ``plugin-registries`` list is the path to a YAML file containing one or more ``PluginRegistry`` definitions.

-----
Using
-----

Help message (``turtles --help``)::

   usage: turtles [-h] [--debug-cli] [--non-interactive] [--output-format FMT]
                  COMMAND ...

   options:
     -h, --help            show this help message and exit
     --debug-cli           print the result of parsing command line arguments
     --non-interactive, -n
                           disallow interactive prompts (default: allow)
     --output-format FMT   set tabular output format to FMT (default: simple;
                           choices: fancy_grid, fancy_outline, github, grid,
                           html, jira, latex, latex_booktabs, latex_longtable,
                           latex_raw, mediawiki, moinmoin, orgtbl, pipe, plain,
                           presto, pretty, psql, rst, simple, textile, tsv,
                           unsafehtml, youtrack)

   commands:
     Add --help to see the command's own help message

     COMMAND               DESCRIPTION
       analyze-registry (ar)
                           analyze plugin registries
       build-plugin (bp)   build (package and sign) plugins
       copyright           show copyright and exit
       deploy-plugin (dp)  deploy plugins
       license             show license and exit
       release-plugin (rp)
                           release (build and deploy) plugins
       usage               show detailed usage and exit
       version             show version and exit

``turtles analyze-registry``
============================

Synonym: ``turtles ar``

Help message (``turtles analyze-registry --help``)::

   usage: turtles analyze-registry [-h] [--plugin-registries FILE]
                                   [--plugin-sets FILE] [--settings FILE]

   Analyze plugin registries

   options:
     -h, --help            show this help message and exit
     --plugin-registries FILE
                           load plugin registries from FILE (default:
                           $HOME/.config/turtles/plugin-registries.yaml or
                           /etc/turtles/plugin-registries.yaml)
     --plugin-sets FILE    load plugin sets from FILE (default:
                           $HOME/.config/turtles/plugin-sets.yaml or
                           /etc/turtles/plugin-sets.yaml)
     --settings FILE       load settings from FILE (default:
                           $HOME/.config/turtles/settings.yaml or
                           /etc/turtles/settings.yaml)

``turtles build-plugin``
========================

Synonym: ``turtles bp``

Help message (``turtles build-plugin --help``)::

   usage: turtles build-plugin [-h] [--identifier PLUGID] [--identifiers FILE]
                               [--password PASS] [--plugin-sets FILE]
                               [--settings FILE]
                               [PLUGID ...]

   Build (package and sign) plugins

   positional arguments:
     PLUGID                plugin identifier to build

   options:
     -h, --help            show this help message and exit
     --identifier PLUGID, -i PLUGID
                           add PLUGID to the list of plugin identifiers to build
     --identifiers FILE, -I FILE
                           add the plugin identifiers in FILE to the list of
                           plugin identifiers to build
     --password PASS       set the plugin signing password
     --plugin-sets FILE    load plugin sets from FILE (default:
                           $HOME/.config/turtles/plugin-sets.yaml or
                           /etc/turtles/plugin-sets.yaml)
     --settings FILE       load settings from FILE (default:
                           $HOME/.config/turtles/settings.yaml or
                           /etc/turtles/settings.yaml)

``turtles deploy-plugin``
=========================

Synonym: ``turtles dp``

Help message (``turtles deploy-plugin --help``)::

   usage: turtles deploy-plugin [-h] [--jar PLUGJAR] [--jars FILE]
                                [--layer LAYER] [--layers FILE]
                                [--plugin-registries FILE] [--production]
                                [--testing]
                                [PLUGJAR ...]

   Deploy plugins

   positional arguments:
     PLUGJAR               plugin JAR to deploy

   options:
     -h, --help            show this help message and exit
     --jar PLUGJAR, -j PLUGJAR
                           add PLUGJAR to the list of plugin JARs to deploy
     --jars FILE, -J FILE  add the plugin JARs in FILE to the list of plugin JARs
                           to deploy
     --layer LAYER, -l LAYER
                           add LAYER to the list of plugin registry layers to
                           process
     --layers FILE, -L FILE
                           add the layers in FILE to the list of plugin registry
                           layers to process
     --plugin-registries FILE
                           load plugin registries from FILE (default:
                           $HOME/.config/turtles/plugin-registries.yaml or
                           /etc/turtles/plugin-registries.yaml)
     --production, -p      synonym for --layer=production (i.e. add 'production'
                           to the list of plugin registry layers to process)
     --testing, -t         synonym for --layer=testing (i.e. add 'testing' to the
                           list of plugin registry layers to process)

``turtles release-plugin``
==========================

Synonym: ``turtles rp``

Help message (``turtles release-plugin --help``)::

   usage: turtles release-plugin [-h] [--identifier PLUGID] [--identifiers FILE]
                                 [--layer LAYER] [--layers FILE]
                                 [--password PASS] [--plugin-registries FILE]
                                 [--plugin-sets FILE] [--production]
                                 [--settings FILE] [--testing]
                                 [PLUGID ...]

   Release (build and deploy) plugins

   positional arguments:
     PLUGID                plugin identifier to build

   options:
     -h, --help            show this help message and exit
     --identifier PLUGID, -i PLUGID
                           add PLUGID to the list of plugin identifiers to build
     --identifiers FILE, -I FILE
                           add the plugin identifiers in FILE to the list of
                           plugin identifiers to build
     --layer LAYER, -l LAYER
                           add LAYER to the list of plugin registry layers to
                           process
     --layers FILE, -L FILE
                           add the layers in FILE to the list of plugin registry
                           layers to process
     --password PASS       set the plugin signing password
     --plugin-registries FILE
                           load plugin registries from FILE (default:
                           $HOME/.config/turtles/plugin-registries.yaml or
                           /etc/turtles/plugin-registries.yaml)
     --plugin-sets FILE    load plugin sets from FILE (default:
                           $HOME/.config/turtles/plugin-sets.yaml or
                           /etc/turtles/plugin-sets.yaml)
     --production, -p      synonym for --layer=production (i.e. add 'production'
                           to the list of plugin registry layers to process)
     --settings FILE       load settings from FILE (default:
                           $HOME/.config/turtles/settings.yaml or
                           /etc/turtles/settings.yaml)
     --testing, -t         synonym for --layer=testing (i.e. add 'testing' to the
                           list of plugin registry layers to process)

Tabular Output Format
=====================

Turtles' tabular output is performed by the `tabulate <https://pypi.org/project/tabulate/>`_ library through the ``--output-format`` option. See https://github.com/astanin/python-tabulate#table-format for a visual reference of the various output formats available.
