# spyder-teimport
Tellurium Import plugin for Spyder 4.1.0+

Copyright (c) 2020 Kiri Choi

## Introduction
spyder-teimport is a plugin for [Spyder IDE](https://github.com/spyder-ide/spyder) version 4 and over. 

The plugin adds set of functions to directly import either a COMBINE archive or SED-ML files and translates the contents into executable Python scripts. 
For both COMBINE archive and SED-ML files, users can import it as full Python script utilizing tesedml module in [Tellurium](http://tellurium.analogmachine.org/), 
or use [PhrasedML](https://sourceforge.net/projects/phrasedml/) notation instead for more readable output.
When importing a COMBINE archive, the plugin will look for manifest file and read all SED-ML files inside the archive, generating multiple separate Python scripts translated from each and every SED-ML files.

## Installation
To install, obtain the source, go to the folder where source is located and run:

`pip install .`

## Dependencies
spyder-teimport requires Spyder IDE, PhrasedML, Tellurium, and all of its dependencies. Tellurium is not available on PyPI yet and the dependency requirement is not enforced, so manual installation for Tellurium is required.
